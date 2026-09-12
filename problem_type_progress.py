"""
problem_type_progress.py
Bug 2a：per-concept 换题类型循环（problem-type variety）核心模块。

设计依据（已在 2026-09-10/11 讨论中定案）：
- 只覆盖前端已知的 3 个"新题"触发点（进入概念、点击刷新、切换概念成功），
  由调用方在这三处传 new_problem_requested=True。
- 本模块只负责"选哪个类型 + 落库"，不涉及 Claude 调用本身。
- concept_problem_progress 表保持真正 append-only：assigned_type 和
  actual_type 在同一次 INSERT 中一起写入（调用方需先选型 → 调用 Claude
  → 解析 Claude 自报的 actual_type 标签 → 再落库），不做 UPDATE。
- 试点仅 3 个概念（5.4 / B1 / 1.X）；其余概念 get_type_enum() 返回 None，
  调用方应据此判断"该概念暂不受 Bug 2a 控制，走原有随机出题逻辑"。
"""

import random
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

from supabase import Client


# ---------------------------------------------------------------------------
# 试点概念的类型枚举（2026-09-11 定案，命名为描述性短语，不用 type1/typeA 编号）
# ---------------------------------------------------------------------------
TYPE_ENUMS = {
    "5.4": [
        "指数型复合",
        "幂次型复合",
        "根式或分式型复合",
        "隐蔽或非显式代换",
        "定积分换元",
        "三角代换",
    ],
    "B1": [
        "多项式×指数或三角",
        "多项式×对数或反三角",
        "单独反三角或对数函数",
        "循环型",
        "换元+分部组合",
    ],
    "1.X": [
        "直接代入",
        "因式分解消去",
        "有理化",
        "三角极限",
        "无穷远处比较",
        "左右极限或分段函数",
    ],
}

# Claude 在题目生成回复中自报类型所用的标签格式，需与 prompt 里要求的格式一致。
# 例如：Claude 回复末尾附 [PROBLEM_TYPE: 三角代换]，展示给学生前需 strip 掉。
_TYPE_TAG_RE = re.compile(r"\[PROBLEM_TYPE:\s*(.+?)\]")


def get_type_enum(concept_id: str) -> Optional[list]:
    """返回该 concept 的类型枚举；非试点概念返回 None。"""
    return TYPE_ENUMS.get(concept_id)


def select_next_type(
    supabase: Client, student_id: str, concept_id: str
) -> Tuple[Optional[str], Optional[int]]:
    """
    决定该学生在该 concept 下一题该出哪个类型。

    规则：
    - 本轮（round）内无放回随机；
    - 本轮所有类型都出过后，进入下一轮，重新洗牌；
    - 若新一轮第一个类型恰好等于上一轮最后一个出的类型，与随机位置的另一个
      类型互换，避免跨轮边界连续同类型。
    - 学生该 concept 首次出题：round_number=1，随机起始类型。
    - 非试点概念：返回 (None, None)，调用方应回退到原有逻辑。

    只读 + 计算，不写库。
    """
    types = get_type_enum(concept_id)
    if not types:
        return None, None

    resp = (
        supabase.table("concept_problem_progress")
        .select("assigned_type, round_number, served_at")
        .eq("student_id", student_id)
        .eq("concept_id", concept_id)
        .order("served_at", desc=True)
        .execute()
    )
    rows = resp.data or []

    if not rows:
        return random.choice(types), 1

    latest_round = rows[0]["round_number"]
    served_this_round = {
        r["assigned_type"] for r in rows if r["round_number"] == latest_round
    }
    remaining = [t for t in types if t not in served_this_round]

    if remaining:
        return random.choice(remaining), latest_round

    # 本轮已出满，进入下一轮
    next_round = latest_round + 1
    last_served_type = rows[0]["assigned_type"]
    candidates = types.copy()
    random.shuffle(candidates)
    if candidates[0] == last_served_type and len(candidates) > 1:
        swap_idx = random.randint(1, len(candidates) - 1)
        candidates[0], candidates[swap_idx] = candidates[swap_idx], candidates[0]
    return candidates[0], next_round


def build_type_instruction(assigned_type: str) -> str:
    """
    生成注入给 Claude 的出题类型指令片段（供 main.py 拼进 system prompt 或
    user turn）。同时要求 Claude 在回复末尾用 [PROBLEM_TYPE: ...] 自报实际
    出的类型，便于后续核对（不保证一致，仅作审计用）。
    """
    return (
        f"本题请出【{assigned_type}】这一类型的换元/分部/极限问题"
        f"（以第一步的解题决策方式为准，不要只是数字不同的同类题）。"
        f"生成完题目后，在你的回复末尾单独一行附上标签 "
        f"[PROBLEM_TYPE: {assigned_type}]（若实际出的类型与要求不同，"
        f"标签内容按你实际出的类型填写，不要瞒报）。"
    )


def parse_and_strip_actual_type(response_text: str) -> Tuple[str, Optional[str]]:
    """
    从 Claude 的原始回复中解析 [PROBLEM_TYPE: ...] 标签，返回
    (去掉标签后的干净文本, 解析出的 actual_type 或 None)。
    与现有 EWM/OLE 标签的 strip 方式保持同一模式：正则匹配 + 从展示文本中删除。
    """
    match = _TYPE_TAG_RE.search(response_text)
    if not match:
        return response_text, None
    actual_type = match.group(1).strip()
    clean_text = _TYPE_TAG_RE.sub("", response_text).strip()
    return clean_text, actual_type


def log_served_problem(
    supabase: Client,
    student_id: str,
    subject_id: str,
    concept_id: str,
    assigned_type: str,
    actual_type: Optional[str],
    round_number: int,
    source: str = "controlled",
) -> None:
    """
    落库一条 append-only 记录。必须在 Claude 回复生成、actual_type 解析完成
    之后调用（assigned_type 与 actual_type 一次性一起写入，不做后续 UPDATE）。
    """
    row = {
        "student_id": student_id,
        "subject_id": subject_id,
        "concept_id": concept_id,
        "assigned_type": assigned_type,
        "actual_type": actual_type,
        "round_number": round_number,
        "source": source,
        "served_at": datetime.now(timezone.utc).isoformat(),
    }
    supabase.table("concept_problem_progress").insert(row).execute()
