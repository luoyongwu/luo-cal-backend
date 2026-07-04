"""
dan_memory_service.py (v2 — 改用 supabase-py，替代 v1 的 psycopg2 直连)
Luo-cal v3.0 PCSA (Persistent Cognitive State Architecture) — Phase 1 Persistence Service

变更说明（v1 → v2）：
- v1 使用 psycopg2 直连（DSN + 数据库密码），与 main.py 现有代码风格不一致，
  且要求获取 Supabase 数据库密码——这条路径在 Migration 阶段已经证明脆弱
  （Session Pooler 鉴权、Fail2ban 封禁等问题反复出现）。
- v2 改用 supabase-py 客户端，与 main.py 现有的 write_signal() / get_dan_snapshot()
  完全一致的访问方式，复用已经在生产环境验证过的 SUPABASE_KEY 环境变量，
  不再需要数据库密码，不再需要 psycopg2。

架构边界（不变，仍然重要）：
- 本模块只做读写（CRUD），不做证据聚合、不做 Stage 演化判断。
- 真正的证据聚合算法由 Phase 2 的 Evidence Aggregation Engine 实现；
  该引擎算出 stage / evidence_count / weight_vector 后，调用本模块的 write_state()
  写回数据库。本模块绝不包含任何聚合逻辑（四层解耦原则）。
- cognitive_signals（Event Log）的写入路径不受影响，仍由既有 write_signal()
  负责，本模块完全不接触 cognitive_signals 的写入。

⚠️ 待确认的前提（会影响本模块能否正常工作，需要去 Supabase 后台核实）：
dan_state 表已启用 RLS（Phase 1 Migration 时选择了 "Run and enable RLS"）。
如果 SUPABASE_KEY 环境变量存的是 anon/public key，RLS 会拦截所有读写请求，
返回空结果而不报错——这会是和 cognitive_signals 那次一样的"静默失败"模式。
如果 SUPABASE_KEY 存的是 service_role/secret key，会绕过 RLS，一切正常。
请去 Supabase → Project Settings → API Keys 核实 SUPABASE_KEY 实际用的是哪一个。

已知限制：write_state() 的 state_revision_count 递增采用"先读后写"，
不是原子操作，高并发场景下存在竞态风险。Phase 1 阶段（低并发）可接受，
若未来需要真正的高并发写入，应改用 Postgres RPC 函数做原子递增。
"""

import os
from typing import Optional
from datetime import datetime, timezone
from supabase import create_client, Client

VALID_WORLDS = ("RWM", "FWM", "AWM")
VALID_STAGES = ("fragile", "emerging", "stable")


class DANMemoryService:
    """
    读写 dan_state（Persistent Cognitive State 的 Materialized View）。
    使用 supabase-py 客户端，与 main.py 现有代码风格一致。
    不做聚合计算——那是 Phase 2 Evidence Aggregation Engine 的职责。
    """

    def __init__(self, client: Optional[Client] = None):
        """
        client: 已初始化的 supabase Client。若不传，从环境变量
                SUPABASE_URL / SUPABASE_KEY 自行创建（与 main.py 完全一致）。
        """
        if client is not None:
            self.client = client
        else:
            url = os.environ.get("SUPABASE_URL", "https://cckahbvgzffyfucrluym.supabase.co")
            key = os.environ["SUPABASE_KEY"]
            self.client = create_client(url, key)

    def get_state(self, student_id: str, subject_id: str = "ap_calculus") -> dict:
        """
        读取某学生在某学科下，三个认知世界的当前持久状态。

        返回结构：
        {
            "RWM": {"stage": "fragile", "evidence_count": 0, "weight_vector": {},
                    "aggregator_version": None, "state_revision_count": 0,
                    "last_updated": None},
            "FWM": {...},
            "AWM": {...},
        }
        若某世界尚无记录（理论上 Migration 已回填，不应发生），对应键值为 None。
        """
        result = {world: None for world in VALID_WORLDS}
        resp = self.client.table("dan_state") \
            .select("cognitive_world, stage, evidence_count, weight_vector, "
                    "aggregator_version, state_revision_count, last_updated") \
            .eq("student_id", student_id) \
            .eq("subject_id", subject_id) \
            .execute()
        for row in resp.data:
            world = row["cognitive_world"]
            result[world] = {
                "stage": row["stage"],
                "evidence_count": row["evidence_count"],
                "weight_vector": row["weight_vector"],
                "aggregator_version": row["aggregator_version"],
                "state_revision_count": row["state_revision_count"],
                "last_updated": row["last_updated"],
            }
        return result

    def write_state(
        self,
        student_id: str,
        cognitive_world: str,
        stage: str,
        evidence_count: int,
        weight_vector: dict,
        aggregator_version: str,
        subject_id: str = "ap_calculus",
    ) -> None:
        """
        写回某学生、某认知世界的最新状态。

        调用方（Phase 2 的 Evidence Aggregation Engine）负责算出这些值；
        本方法只负责持久化，并自动递增 state_revision_count、更新 last_updated。
        state_revision_count 是红线约束的工程落地：Phase 4 的 Constitution Audit
        会检查是否存在长期 revision_count=0 的"粘滞"状态。
        """
        if cognitive_world not in VALID_WORLDS:
            raise ValueError(f"非法 cognitive_world: {cognitive_world}，必须是 {VALID_WORLDS} 之一")
        if stage not in VALID_STAGES:
            raise ValueError(f"非法 stage: {stage}，必须是 {VALID_STAGES} 之一")

        current = self.client.table("dan_state") \
            .select("state_revision_count") \
            .eq("student_id", student_id) \
            .eq("subject_id", subject_id) \
            .eq("cognitive_world", cognitive_world) \
            .execute()

        if not current.data:
            raise RuntimeError(
                f"未找到对应行：student_id={student_id}, subject_id={subject_id}, "
                f"cognitive_world={cognitive_world}。"
                f"该行应在 Migration 阶段已回填；若学生是 Migration 之后才注册的新用户，"
                f"请先调用 ensure_student_initialized()。"
            )

        new_revision = current.data[0]["state_revision_count"] + 1
        now = datetime.now(timezone.utc).isoformat()

        self.client.table("dan_state").update({
            "stage": stage,
            "evidence_count": evidence_count,
            "weight_vector": weight_vector,
            "aggregator_version": aggregator_version,
            "state_revision_count": new_revision,
            "last_updated": now,
        }).eq("student_id", student_id) \
          .eq("subject_id", subject_id) \
          .eq("cognitive_world", cognitive_world) \
          .execute()

    def ensure_student_initialized(self, student_id: str, subject_id: str = "ap_calculus") -> None:
        """
        为新学生（Migration 之后才首次出现、尚未被回填过的学生）初始化
        三条默认状态行。幂等：依赖 (student_id, subject_id, cognitive_world)
        唯一约束的 upsert，已存在则不受影响。

        这是 Migration 脚本里 BACKFILL_SQL 逻辑的运行时版本，用于处理系统
        持续运行后不断加入的新学生，而不必每次都重跑整份 Migration。
        """
        rows = [
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "cognitive_world": world,
                "stage": "fragile",
                "evidence_count": 0,
                "state_revision_count": 0,
            }
            for world in VALID_WORLDS
        ]
        self.client.table("dan_state").upsert(
            rows, on_conflict="student_id,subject_id,cognitive_world"
        ).execute()


# ---------------------------------------------------------------------------
# FastAPI 集成示例（供参考，不是完整 main.py，不会自动生效）
#
# from dan_memory_service import DANMemoryService
# dan_service = DANMemoryService()  # 复用 main.py 已有的 SUPABASE_URL/SUPABASE_KEY
#
# 建议新增一个端点，不覆盖现有的 /api/v1/dan/{student_id}（那个是旧的、
# 基于最近50条信号临时计算的版本，等 Phase 2 Evidence Aggregation Engine
# 完成后再考虑是否用这个持久化版本替换它）：
#
# @app.get("/api/v1/dan-state/{student_id}")
# def get_dan_state(student_id: str):
#     return dan_service.get_state(student_id)
#
# write_state() 的真正调用方是 Phase 2 的 Evidence Aggregation Engine，
# 尚未实现，Phase 1 此时只需要 get_state 的读取端点可用即可。
# ---------------------------------------------------------------------------
