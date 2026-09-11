"""
Luo-cal 身份系统 v0.2 — auth.py
================================================================
职责边界（对应 ADR-010）：
    本模块只负责"这些证据属于哪个学生"，不参与任何认知推断
    （Mechanism / World / Bayesian Inference 等一律与本模块无关）。

包含内容：
    1. POST /auth/login          —— login_code 换取 session_token
    2. get_current_student()     —— FastAPI 依赖注入，供其它路由使用，
                                     解析 session_token -> student_uuid，
                                     这是整个系统里唯一"知道 token"的地方。

安全原则（必须遵守，不可绕过）：
    - 任何业务端点都不接受客户端传入的 student_id / student_uuid 参数。
    - student_uuid 永远只能通过 get_current_student() 依赖注入获得。

================================================================
2026-09-11 新增：httpx 连接池死连接重试
----------------------------------------------------------------
根因（详见 memory /areas/luo-cal-backend-incident.md）：main.py 里
全局单例的 supabase 客户端在整个进程生命周期内只创建一次，其底层
httpx 连接池长时间空闲后，Supabase 服务端会主动关闭该连接，但客户端
连接池并不知情。下一次有请求复用这条"看起来还活着、实际已经死了"的
连接时，会抛出 httpx.RemoteProtocolError（ConnectionTerminated），
且这个异常此前完全没有被捕获，直接导致 /auth/login 崩溃返回裸 500，
连 auth_audit_log 都来不及写入。

修复：新增 _execute_with_retry() 包装所有 .execute() 调用，遇到这个
特定异常时自动重试一次——重试时连接池会因为上一次失败已经把死连接
剔除，重新建立新连接，几乎总能成功。不改变任何业务逻辑，只加一层
网络层容错。
================================================================
"""

import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from supabase import Client


# ================================================================
# 配置加载
# ================================================================
def _load_auth_config() -> dict:
    """从 config.yaml 读取 auth 配置段。找不到文件时使用兜底默认值，
    确保本地开发/测试环境下即使没有 config.yaml 也不会直接崩溃。"""
    default_config = {
        "session_expiry_hours": {
            "internal_test": 168,
            "student": 24,
            "teacher": 72,
            "enterprise": 12,
        },
        "last_seen_throttle_minutes": 5,
    }

    config_path = os.environ.get("CONFIG_YAML_PATH", "config.yaml")
    if not os.path.exists(config_path):
        return default_config

    with open(config_path, "r", encoding="utf-8") as f:
        full_config = yaml.safe_load(f)

    return full_config.get("auth", default_config)


AUTH_CONFIG = _load_auth_config()


# ================================================================
# Supabase 客户端
# ================================================================
# 本模块不自己创建 Supabase 连接，而是复用 main.py 里已经建好的那个连接
# （main.py 里叫 `supabase`，环境变量名是 SUPABASE_KEY，不需要在这里重复关心）。
# main.py 启动时调用一次 init_auth(supabase) 完成注入即可。
_supabase_client: Optional[Client] = None


def init_auth(supabase_client: Client):
    """在 main.py 里，创建好 supabase 连接之后，调用一次这个函数完成注入。
    用法：
        from auth import init_auth, router as auth_router
        init_auth(supabase)          # supabase 是 main.py 里已经创建好的客户端
        app.include_router(auth_router)
    """
    global _supabase_client
    _supabase_client = supabase_client


def get_supabase() -> Client:
    if _supabase_client is None:
        raise RuntimeError(
            "auth 模块尚未初始化：请在 main.py 里先调用 init_auth(supabase) 再挂载路由。"
        )
    return _supabase_client


def _execute_with_retry(query_builder, max_retries: int = 1):
    """包装 supabase-py 的 .execute() 调用，遇到 httpx.RemoteProtocolError
    （连接池复用了已被服务端关闭的死连接）时自动重试一次。见本文件顶部
    2026-09-11 修复说明。max_retries=1 即最多重试1次（总共最多尝试2次），
    第二次仍失败则把异常原样抛出，交给 FastAPI 正常返回500（不掩盖真正
    的、非网络类的错误，比如表名写错、字段类型不对等）。"""
    attempt = 0
    while True:
        try:
            return query_builder.execute()
        except httpx.RemoteProtocolError:
            if attempt >= max_retries:
                raise
            attempt += 1


# ================================================================
# 数据模型
# ================================================================
class LoginRequest(BaseModel):
    login_code: str


class LoginResponse(BaseModel):
    session_token: str
    display_name: Optional[str]
    expires_at: str


class AuthenticatedStudent(BaseModel):
    """Auth Context —— 所有业务代码应该只依赖这个对象里的 student_uuid，
    不应该自己再去解析 token 或接受前端传来的 student_id。"""
    student_uuid: str
    display_name: Optional[str]
    tier: str


# ================================================================
# 工具函数
# ================================================================
def _generate_session_token() -> str:
    """生成一个足够随机、不可预测的会话token"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(48))


def _log_audit(supabase: Client, student_uuid: Optional[str], login_code_attempted: str,
                event_type: str, reason: Optional[str] = None):
    """写入最小审计日志。审计写入失败不应该阻断主流程（比如登录本身成功了，
    不能因为日志表写入失败就让用户登录不了），所以这里吞掉异常但不静默——打印出来。
    2026-09-11：内部也改用 _execute_with_retry()，死连接导致的失败会先
    自动重试一次，只有非网络类的真实错误才会走到下面的 except 打印分支。"""
    try:
        _execute_with_retry(
            supabase.table("auth_audit_log").insert({
                "student_uuid": student_uuid,
                "login_code_attempted": login_code_attempted,
                "event_type": event_type,
                "reason": reason,
            })
        )
    except Exception as e:
        print(f"[auth_audit_log 写入失败，不影响主流程] {e}")


# ================================================================
# 路由：登录
# ================================================================
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    supabase = get_supabase()
    login_code = payload.login_code.strip()

    if not login_code:
        _log_audit(supabase, None, login_code, "LOGIN_FAILED", reason="empty_code")
        raise HTTPException(status_code=400, detail="授权码不能为空")

    result = _execute_with_retry(
        supabase.table("students")
        .select("student_uuid, display_name, tier, is_active")
        .eq("login_code", login_code)
    )

    if not result.data:
        _log_audit(supabase, None, login_code, "LOGIN_FAILED", reason="invalid_code")
        raise HTTPException(status_code=401, detail="授权码无效")

    student = result.data[0]

    if not student["is_active"]:
        _log_audit(supabase, student["student_uuid"], login_code, "LOGIN_FAILED", reason="inactive_account")
        raise HTTPException(status_code=403, detail="该授权码已被禁用")

    # 生成新 session，单设备策略：无条件覆盖旧 token
    tier = student.get("tier") or "internal_test"
    expiry_hours = AUTH_CONFIG["session_expiry_hours"].get(tier, 24)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expiry_hours)
    new_token = _generate_session_token()

    _execute_with_retry(
        supabase.table("students").update({
            "active_session_token": new_token,
            "session_started_at": now.isoformat(),
            "session_expires_at": expires_at.isoformat(),
            "last_seen_at": now.isoformat(),
        }).eq("student_uuid", student["student_uuid"])
    )

    _log_audit(supabase, student["student_uuid"], login_code, "LOGIN_SUCCESS")

    return LoginResponse(
        session_token=new_token,
        display_name=student.get("display_name"),
        expires_at=expires_at.isoformat(),
    )


# ================================================================
# 依赖注入：Auth Context
# ================================================================
def get_current_student(authorization: str = Header(...)) -> AuthenticatedStudent:
    """
    所有需要身份的业务端点，应该这样使用：

        @app.post("/some-endpoint")
        def some_endpoint(student: AuthenticatedStudent = Depends(get_current_student)):
            student_uuid = student.student_uuid   # 唯一可信来源
            ...

    前端调用约定：请求头需带 Authorization: Bearer <session_token>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少有效的 Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="token 为空")

    supabase = get_supabase()

    result = _execute_with_retry(
        supabase.table("students")
        .select("student_uuid, display_name, tier, active_session_token, session_expires_at, last_seen_at, is_active")
        .eq("active_session_token", token)
    )

    if not result.data:
        # token 不匹配任何学生：要么从没登录过，要么已经被其他设备的新登录覆盖掉了
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效，可能您的账号已在其他设备登录，请重新登录",
        )

    student = result.data[0]

    if not student["is_active"]:
        raise HTTPException(status_code=403, detail="该账号已被禁用")

    expires_at = datetime.fromisoformat(student["session_expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")

    # last_seen_at 节流更新：只有超过阈值才真正写库，避免高并发下的数据库热点
    _maybe_update_last_seen(supabase, student)

    return AuthenticatedStudent(
        student_uuid=student["student_uuid"],
        display_name=student.get("display_name"),
        tier=student.get("tier") or "internal_test",
    )


def _maybe_update_last_seen(supabase: Client, student: dict):
    throttle_minutes = AUTH_CONFIG.get("last_seen_throttle_minutes", 5)
    now = datetime.now(timezone.utc)

    last_seen_raw = student.get("last_seen_at")
    should_update = True

    if last_seen_raw:
        last_seen = datetime.fromisoformat(last_seen_raw)
        if (now - last_seen) < timedelta(minutes=throttle_minutes):
            should_update = False

    if should_update:
        _execute_with_retry(
            supabase.table("students").update({
                "last_seen_at": now.isoformat()
            }).eq("student_uuid", student["student_uuid"])
        )
