import os
from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
import anthropic
from datetime import datetime
from dan_memory_service import DANMemoryService
from datetime import timedelta

SUPABASE_URL = "https://cckahbvgzffyfucrluym.supabase.co"
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
import sys

# ===== 环境变量启动校验（自动生成，禁止手动删除）=====
REQUIRED_ENV_VARS = {
    "ANTHROPIC_KEY": "调用 Claude API",
    "DEEPSEEK_API_KEY": "调用 DeepSeek 后端",
    "SUPABASE_URL": "连接 Supabase 项目",
    "SUPABASE_KEY": "Supabase 访问密钥",
}

def validate_env_vars():
    missing = {k: v for k, v in REQUIRED_ENV_VARS.items() if not os.environ.get(k)}
    if missing:
        print("=" * 60, file=sys.stderr)
        print("启动失败：以下环境变量在 Railway Variables 中缺失：", file=sys.stderr)
        for k, v in missing.items():
            print(f"   - {k}  ({v})", file=sys.stderr)
        print("请前往 Railway 对应 service 的 Variables 补齐后重新部署。", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        sys.exit(1)
    else:
        print(f"环境变量校验通过（共 {len(REQUIRED_ENV_VARS)} 项）", file=sys.stderr)

validate_env_vars()
# ===== 环境变量启动校验结束 =====
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]

app = FastAPI(title="Luo-cal Backend v1.3")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
dan_service = DANMemoryService(client=supabase)

# ===== 身份系统 v0.2 接入（新增）=====
# 对应 DESIGN_NOTES.md ADR-009 / ADR-010
# 职责边界：auth 模块只负责"这些证据属于哪个学生"，不参与任何认知推断。
from auth import init_auth, router as auth_router, get_current_student, AuthenticatedStudent
init_auth(supabase)
app.include_router(auth_router)
# ===== 身份系统接入结束 =====

# Phase 2：全局贝叶斯聚合器实例（一次构造，避免每次请求重复读取 config.yaml）
# 严格对照 planning/BAYESIAN_AGGREGATOR_SPEC_v0.2.md 实现，见 inference_pipeline.py
from inference_pipeline import BayesianAggregator, load_aggregator_config
bayesian_aggregator = BayesianAggregator(load_aggregator_config())

# 2026-08-02 新增：CONCEPT_CONSTRAINTS 从前端（Ap-cal 仓库）迁移进后端，
# 详见 concept_constraints.py 模块文档字符串了解完整决策记录。
from concept_constraints import CONCEPT_CONSTRAINTS

# 2026-08-02 新增（ADR-018）：Teaching Policy Layer
from teaching_policy import TEACHING_POLICY_INJECTIONS, TEACHING_POLICY_VERSION

ONTOLOGY = {
    "BOUNDS_TRAP":       {"root_cause": "RepresentationShift", "dimension": "RWM", "error_level": "procedural"},
    "PRE_SUBSTITUTION":  {"root_cause": "RepresentationShift", "dimension": "RWM", "error_level": "procedural"},
    "CHAIN_FRACTURE":    {"root_cause": "SemanticIntegrity",  "dimension": "RWM", "error_level": "procedural"},
    "ABSOLUTE_VALUE":    {"root_cause": "SemanticIntegrity",  "dimension": "RWM", "error_level": "procedural"},
    "IVT_MVT_CONFUSION": {"root_cause": "StructuralReasoning", "dimension": "FWM", "error_level": "conceptual"},
    "WASHER_TRAP":       {"root_cause": "StructuralReasoning", "dimension": "FWM", "error_level": "conceptual"},
    "EWM_B1C":           {"root_cause": "FlowReasoning",       "dimension": "FWM", "error_level": "procedural"},
}

ROOT_CAUSE_LABELS = {
    "RepresentationShift": "变量追踪薄弱——你知道怎么换元，但换完之后积分限还停留在原变量上。",
    "SemanticIntegrity":  "执行完整性不足——你知道方法，但在关键符号上反复遗漏。",
    "StructuralReasoning": "结构映射薄弱——你知道各个定理的定义，但在题目和模型之间的对应关系上容易混淆。",
    "FlowReasoning":       "推理流程中断——你在推导过程中途停止，无法自主推进到下一步。",
}

# ===== 身份系统改造说明 =====
# StudentInput / ReflectionInput 不再包含 student_id 字段。
# 学生身份统一由 Depends(get_current_student) 从 session_token 解析得出，
# 前端不再、也不应该自己传学生是谁（安全底线，见 ADR-010）。
class StudentInput(BaseModel):
    concept_id: str
    user_input: str
    session_id: str = "default"
    language: str = "zh"

class ReflectionInput(BaseModel):
    reflection: str
    comment: str = ""
# ===== 身份系统改造说明结束 =====

SCL_SYSTEM_PROMPT_ZH = """你是Luo-cal苏格拉底微积分导师。

核心规则：
1. 绝对禁止直接给出答案或完整解法
2. 每次只问一个问题
3. 检测到错误时，用苏格拉底反问引导学生自己发现
4. 如果学生要求直接给答案，拒绝并继续引导
5. 无论学生用什么语言输入，你必须始终用中文回复
6. 任务完成推进（含信息重复检测）：当学生对当前问题（或当前子步骤）给出正确、完整的回答后，你必须明确确认（一句话即可），并立即推进——出下一道题、进阶到更难的应用题，或明确说明本阶段已完成。禁止在学生已经给出正确完整答案后，还要求其重新推导、重新验证或回溯确认之前已完成的步骤。在提出下一个问题之前，你必须自我核查：这个问题的答案是否已经明确出现在学生刚才的回复文本中？如果是，禁止提出该问题，必须换成一个要求新信息、新计算或新判断角度的问题。对同一个已经正确完成的回答，最多允许一次简短的巩固性追问，且该追问必须针对学生尚未提及的新角度；如果学生在追问后依然正确，下一轮必须推进，不得再追问第三次。

【控制层禁令】禁止提及RepresentationShift、SemanticIntegrity、StructuralReasoning等术语。

EWM错误检测——检测到以下错误时，在回复开头加标记：
[EWM:BOUNDS_TRAP] 换元后未换积分边界
[EWM:PRE_SUBSTITUTION] 求导前代入数值
[EWM:ABSOLUTE_VALUE] 分离变量时漏写绝对值
[EWM:CHAIN_FRACTURE] 参数方程二阶导公式误用
[EWM:IVT_MVT_CONFUSION] IVT与MVT混淆
[EWM:WASHER_TRAP] 旋转体积分先减后平方
[EWM:EWM_B1C] 学生在IBP中途停止不继续推进"""

SCL_SYSTEM_PROMPT_EN = """You are Luo-cal, a Socratic calculus tutor.

Core rules:
1. Never give direct answers or complete solutions
2. Ask only one question at a time
3. When errors are detected, use Socratic questioning to guide the student
4. If the student demands a direct answer, refuse and continue guiding
5. Regardless of what language the student uses, always reply in English
6. Advance on completion (with repetition check): Once the student gives a correct, complete answer to the current problem (or sub-step), you must briefly confirm it and immediately advance — give the next problem, escalate to a harder application question, or explicitly state that this stage is complete. Do not ask the student to re-derive, re-verify, or revisit already-completed steps after a correct complete answer. Before asking your next question, you must self-check: does the answer to this question already appear explicitly in the student's most recent reply? If so, you must not ask it — replace it with a question that requires new information, new computation, or a new angle of judgment. For the same correctly completed answer, at most one brief follow-up confirmation is allowed, and it must target an angle the student has not yet addressed; if the student remains correct after that follow-up, you must advance on the next turn — do not ask a third time.

[Control Layer] Never mention RepresentationShift, SemanticIntegrity, StructuralReasoning or similar terms to students.

EWM Error Detection — when the following errors are detected, add a tag at the start of your reply:
[EWM:BOUNDS_TRAP] Substitution made but integration bounds not changed
[EWM:PRE_SUBSTITUTION] Value substituted before differentiating
[EWM:ABSOLUTE_VALUE] Absolute value omitted when separating variables
[EWM:CHAIN_FRACTURE] Second derivative of parametric equation computed incorrectly
[EWM:IVT_MVT_CONFUSION] IVT and MVT confused
[EWM:WASHER_TRAP] Subtracted before squaring in solid of revolution
[EWM:EWM_B1C] Student stopped midway through integration by parts"""

def detect_ewm(text):
    """
    从模型回复里提取 [EWM:XXX] 标签。

    === 2026-07-30 修复：清洗 markdown 转义反斜杠 ===
    Shadow Run 排查真实生产数据时发现，cognitive_signals 表里存在一条
    signal = 'BOUNDS\\_TRAP'（比正常的 'BOUNDS_TRAP' 多一个字面反斜杠）。
    根因：模型在 markdown 语境下生成回复时，偶尔会习惯性地把下划线转义成
    '\\_'（markdown 里下划线是斜体语法），这个函数此前是原样截取
    [EWM:...] 中间的文字、不做任何清洗，导致带反斜杠的信号原样存入数据库。

    由于 BayesianAggregator.SIGNAL_TO_MECHANISM 字典里的 key 是干净的
    'BOUNDS_TRAP'（不含反斜杠），两者字符串不匹配，这条证据会被
    _aggregate() 的未知信号分支静默跳过（打印 UserWarning，不报错），
    这条学生真实答错的证据从此不参与任何认知判断——属于"某个环节解析不够
    防御性、真实数据静默丢失"的同一类模式（对照 fetch_evidence_history()
    缺失、cognitive_signals 缺字段两次历史事故）。

    影响范围核实：全表排查只有 1 条历史记录受影响（2026-07-30 SQL 核实），
    不是普遍性事故，但修复成本很小，直接修。

    修复方式：合法的 EWM 信号名只由大写字母和下划线组成，永远不应包含
    反斜杠，所以直接去掉所有反斜杠是安全的清洗方式，不会误伤正常信号。
    """
    if "[EWM:" in text:
        s = text.index("[EWM:") + 5
        e = text.index("]", s)
        raw = text[s:e]
        return raw.replace("\\", "")
    return None


# ---------------------------------------------------------------------------
# 2026-08-02 新增：对话历史读写（修复 socratic_chat() 无跨轮记忆的问题）
#
# 背景：socratic_chat() 此前每次调用 Claude API 只发一条孤立消息
# （messages=[{"role":"user","content":...}]），完全不携带对话历史。
# 这导致 SCL_SYSTEM_PROMPT 规则6（"任务完成推进（含信息重复检测）"，
# 要求模型自我核查"这个问题的答案是否已经明确出现在学生刚才的回复
# 文本中"）在架构层面根本无法真正生效——模型每一轮都是从零开始，不
# 知道自己上一轮问过什么、学生上一轮答过什么。见
# THEORY_CHANGELOG.md 对应条目了解完整发现过程。
#
# CHAT_HISTORY_LIMIT 取最近 20 条（约10轮问答）作为上下文窗口，未做
# 基于 token 数的动态截断或摘要——这是已知的、留待后续优化的简化，
# 不影响本次修复的核心目标（让规则6具备跨轮次记忆的架构基础）。
# ---------------------------------------------------------------------------
CHAT_HISTORY_LIMIT = 20

def fetch_chat_history(student_id: str, session_id: str, limit: int = CHAT_HISTORY_LIMIT):
    """
    读取某学生某 session 下最近的对话历史，按时间升序返回，格式与
    Claude API 的 messages 数组元素一致（{"role": ..., "content": ...}），
    可以直接拼接使用。

    失败不应该打断对话——如果这次读取失败，退化为空历史（等同于本次
    修复之前的行为），不向上抛出异常，与 write_signal()/
    update_dan_state_after_signal() 的既有容错模式保持一致。
    """
    try:
        resp = supabase.table("chat_messages") \
            .select("role, content, timestamp") \
            .eq("student_id", student_id) \
            .eq("session_id", session_id) \
            .order("timestamp", desc=True) \
            .limit(limit) \
            .execute()
        rows = list(reversed(resp.data))  # 取到最近N条(倒序)后，转回时间升序
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    except Exception as e:
        print(f"Chat history read error: {e}")
        return []


def save_chat_message(student_id: str, session_id: str, role: str, content: str):
    """持久化一条对话消息。失败仅打印，不打断对话体验（与 write_signal() 一致）。"""
    try:
        supabase.table("chat_messages").insert({
            "student_id": student_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }).execute()
    except Exception as e:
        print(f"Chat history write error: {e}")


def log_teaching_intervention(student_id, subject_id, session_id, concept_id,
                               locked_mechanism, locked_worlds, stage,
                               policy_version, injected_strategy_text):
    """
    ADR-018：记录一次教学策略实际注入事件，供未来关联学生认知状态变化、
    统计"某类认知缺陷学生在给定策略版本下的改善情况"。

    失败不应该打断对话，仅打印，与 write_signal()/save_chat_message()
    的既有容错模式一致。
    """
    try:
        supabase.table("teaching_intervention_log").insert({
            "student_id": student_id,
            "subject_id": subject_id,
            "session_id": session_id,
            "concept_id": concept_id,
            "timestamp": datetime.now().isoformat(),
            "locked_mechanism": locked_mechanism,
            "locked_worlds": locked_worlds,
            "stage": stage,
            "policy_version": policy_version,
            "injected_strategy_text": injected_strategy_text,
        }).execute()
    except Exception as e:
        print(f"Teaching intervention log write error: {e}")


def write_signal(student_id, concept, signal, trigger_context, intercept_result, session_id="default"):
    try:
        onto = ONTOLOGY.get(signal, {})
        supabase.table("cognitive_signals").insert({
            "student_id": student_id,
            "concept": concept,
            "signal": signal,
            "timestamp": datetime.now().isoformat(),
            "dan_profile": {},
            "trigger_context": trigger_context,
            "intercept_result": intercept_result,
            "root_cause": onto.get("root_cause", "Unknown"),
            "error_level": onto.get("error_level", "unknown"),
            "cognitive_dimension": {"dimension": onto.get("dimension", "Unknown")},
        }).execute()
    except Exception as e:
        print(f"Signal write error: {e}")

def update_dan_state_after_signal(student_id: str):
    """
    Phase 2 首次接入真实对话流（此前只在专用测试端点里跑过合成数据）。
    每次检测到新的 EWM 信号后，重新拉取该学生完整的证据历史（cognitive_signals），
    对三个认知世界分别跑一次推断管道（Aggregator -> Damper -> Stage 决策），
    更新 dan_state。

    身份系统接入后，这里的 student_id 参数现在传入的是 student_uuid
    （由 Depends(get_current_student) 解析得出），不再是前端自由传入的字符串。

    失败不应该打断学生的对话体验，所以这里 catch 全部异常只打印，
    不向上抛出。这个模式和 write_signal() 一致；已知局限见
    THEORY_CHANGELOG.md 里 write_signal 相关条目的"后续建议"部分
    （静默 print 不是长期方案，未来应升级为结构化日志）。

    === Route A 更新（2026-07-31，ADR-016 v8/§12）===
    此前对三个 world 分别调用 run_pipeline()，每次都会（在
    use_promotion_policy=True 时）重复计算并各自写入同一份全局 Promotion
    判断，导致 dan_state.FWM.stage="stable" 但真正锁定的 locked_world
    其实是 RWM 这类语义歧义（详见 ADR-016 v8）。现在改为：per-world 循环
    只负责诊断存储（不变），全局 Promotion 判断改为在循环外额外调用一次
    update_global_promotion_state()，写入独立的 dan_global_state 表。

    这里显式复用 inference_pipeline._promotion_policy_enabled() 同一个
    判断函数，而不是自己重新读一遍环境变量——避免两处判断逻辑不同步（例如
    以后这个函数的默认值判断规则变了，这里却忘记同步改，导致 per-world
    诊断走了新路径、全局判断却还留在旧路径判断结果上，产生新的不一致）。
    """
    try:
        from inference_pipeline import (
            run_pipeline, fetch_evidence_history,
            update_global_promotion_state, _promotion_policy_enabled,
        )
        dan_service.ensure_student_initialized(student_id)
        evidence_history = fetch_evidence_history(supabase, student_id)
        current_full_state = dan_service.get_state(student_id)
        for world in ["RWM", "FWM", "AWM"]:
            run_pipeline(student_id, world, evidence_history, current_full_state[world],
                         dan_service, aggregator=bayesian_aggregator)

        if _promotion_policy_enabled():
            update_global_promotion_state(
                student_id, evidence_history, dan_service, aggregator=bayesian_aggregator,
            )
    except Exception as e:
        print(f"dan_state pipeline update error: {e}")


@app.get("/")
def root():
    return {"status": "Luo-cal Backend v1.3 running", "ontology": "v1"}

@app.post("/api/v1/chat")
def socratic_chat(
    data: StudentInput,
    background_tasks: BackgroundTasks,
    student: AuthenticatedStudent = Depends(get_current_student),
):
    prompt = SCL_SYSTEM_PROMPT_EN if data.language == "en" else SCL_SYSTEM_PROMPT_ZH

    # === 2026-08-02 新增：逐概念教学约束拼接（方案1迁移，Yongwu 拍板）===
    # 此前这套 CONCEPT_CONSTRAINTS 活在前端（Ap-cal/app.py），但前端
    # RailwayAdapter.chat() 从未把它发给后端，导致这套精心设计的逐概念
    # 硬性规则（包括 4.3 概念的 PRE-OVERRIDE）在真实 Railway Backend
    # 链路上从未生效过。现在后端自己按 concept_id 查表、动态拼进
    # system prompt，不再依赖前端透传——前端已同步删除这份字典，
    # RailwayAdapter 现在只传递干净的 concept_id/user_input/session_id/
    # language，不再构造或发送 system 参数。这是"单一真值源"迁移，
    # 避免教学策略在前后端两处重复维护、彼此不同步。
    concept_constraint = CONCEPT_CONSTRAINTS.get(data.concept_id, "Guide step by step.")
    final_system_prompt = (
        f"{prompt}\n\n"
        f"【当前概念专项教学约束 / Concept-Specific Teaching Constraint】\n"
        f"{concept_constraint}"
    )

    # === 2026-08-02 新增（ADR-018）：Teaching Policy 层拼接 ===
    # 按学生当前锁定的 locked_mechanism 查表，追加教学策略指令。这层
    # 内容不暴露任何内部术语（延续【控制层禁令】原则），只告诉模型
    # "该怎么做"。未锁定（stage != "stable"）时走 None 对应的兜底策略。
    # 这段内容的地位是"未经验证的初始教学假设"，不是已验证的最优解，
    # 见 teaching_policy.py 模块文档字符串与 ADR-018 §2/§3.1。
    teaching_locked_mechanism = None
    teaching_locked_worlds = None
    teaching_stage = None
    try:
        global_state_for_teaching = dan_service.get_global_state(student.student_uuid)
        if global_state_for_teaching:
            teaching_stage = global_state_for_teaching.get("stage")
            teaching_locked_worlds = global_state_for_teaching.get("locked_worlds")
            if teaching_stage == "stable":
                teaching_locked_mechanism = global_state_for_teaching.get("locked_mechanism")
    except Exception as e:
        print(f"dan_global_state read error (teaching policy): {e}")

    teaching_instruction = TEACHING_POLICY_INJECTIONS.get(
        teaching_locked_mechanism, TEACHING_POLICY_INJECTIONS[None]
    )
    final_system_prompt = (
        f"{final_system_prompt}\n\n"
        f"【当前教学策略指引 / Teaching Policy Guidance】\n"
        f"{teaching_instruction}"
    )

    user_message_content = f"概念{data.concept_id}\n学生输入：{data.user_input}"

    # === 2026-08-02 修复 ===
    # 此前这里直接 messages=[{"role":"user","content":user_message_content}]，
    # 每轮都是孤立的单条消息，模型完全看不到之前说过什么，规则6（任务完成
    # 推进/信息重复检测）在架构层面无法真正生效。现在先读取该
    # (student_id, session_id) 下最近的对话历史，拼进 messages 数组一起
    # 发给 Claude，使模型具备跨轮次的真实记忆。
    history = fetch_chat_history(student.student_uuid, data.session_id)
    messages = history + [{"role": "user", "content": user_message_content}]

    message = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=final_system_prompt,
        messages=messages,
    )
    response_text = message.content[0].text
    ewm_type = detect_ewm(response_text)
    clean_response = response_text.replace(f"[EWM:{ewm_type}] ", "") if ewm_type else response_text

    # 持久化本轮对话（学生输入 + 模型回复，回复存的是 clean_response——即
    # 学生实际看到的文本，不含内部 [EWM:...] 标记——保持模型"自己说过什么"
    # 这份记忆与学生视角完全一致，不掺入内部专用标记）。
    background_tasks.add_task(
        save_chat_message, student.student_uuid, data.session_id, "user", user_message_content
    )
    background_tasks.add_task(
        save_chat_message, student.student_uuid, data.session_id, "assistant", clean_response
    )

    # ADR-018: 记录本次教学策略注入事件
    background_tasks.add_task(
        log_teaching_intervention, student.student_uuid, "ap_calculus", data.session_id,
        data.concept_id, teaching_locked_mechanism, teaching_locked_worlds, teaching_stage,
        TEACHING_POLICY_VERSION, teaching_instruction,
    )

    if ewm_type:
        # Phase 2 性能修复：write_signal + update_dan_state_after_signal 涉及
        # 3 次数据库查询、3 次贝叶斯聚合计算、3 次数据库写入，改为响应返回后
        # 在后台异步执行，避免阻塞用户等待对话回复（此前导致 502 超时）。
        background_tasks.add_task(
            write_signal, student.student_uuid, data.concept_id, ewm_type,
            {"concept_id": data.concept_id, "student_input_snippet": data.user_input[:200]},
            {"intercepted": True, "ewm_type": ewm_type},
            data.session_id,
        )
        background_tasks.add_task(update_dan_state_after_signal, student.student_uuid)
    onto = ONTOLOGY.get(ewm_type, {}) if ewm_type else {}
    return {
        "status": "success",
        "response": clean_response,
        "ewm_detected": ewm_type,
        "intercepted": ewm_type is not None,
        "root_cause": onto.get("root_cause"),
        "dimension": onto.get("dimension"),
    }

@app.get("/api/v1/dan")
def get_dan_snapshot(student: AuthenticatedStudent = Depends(get_current_student)):
    student_id = student.student_uuid
    result = supabase.table("cognitive_signals")\
        .select("*").eq("student_id", student_id)\
        .order("timestamp", desc=True).limit(50).execute()
    signals = [s for s in result.data if not (s.get("signal") or "").startswith("REFLECTION")]
    total = len(signals)
    if total == 0:
        return {"student_id": student_id, "total_signals": 0, "show_dashboard": False,
                "summary": "我还在学习你的思维模式。完成几次练习后会给出认知画像。",
                "ewm_breakdown": {}, "root_cause_breakdown": {}, "concept_breakdown": {}, "recent_signals": []}
    ewm_counts, root_cause_counts, concept_counts = {}, {}, {}
    for s in signals:
        sig = s.get("signal") or "Unknown"
        concept = s.get("concept") or "unknown"
        rc = s.get("root_cause") or "Unknown"
        ewm_counts[sig] = ewm_counts.get(sig, 0) + 1
        concept_counts[concept] = concept_counts.get(concept, 0) + 1
        root_cause_counts[rc] = root_cause_counts.get(rc, 0) + 1
    top_rc = max(root_cause_counts, key=root_cause_counts.get)
    summary = ROOT_CAUSE_LABELS.get(top_rc, "") if total >= 3 else f"你在概念{max(concept_counts, key=concept_counts.get)}上出现了问题，系统正在观察你的思维模式。"
    return {"student_id": student_id, "total_signals": total, "show_dashboard": True,
            "summary": summary, "ewm_breakdown": ewm_counts,
            "root_cause_breakdown": root_cause_counts, "concept_breakdown": concept_counts,
            "recent_signals": signals[:5]}


@app.get("/api/v1/dan-state")
def get_dan_state_for_student(student: AuthenticatedStudent = Depends(get_current_student)):
    """
    Session 2（2026-08-02 新增）：面向学生展示的认知状态端点。

    与既有 /api/v1/dan 的区别：/api/v1/dan 是旧版、基于最近50条信号
    即时计算的调试用端点，本端点是专门为学生设计的展示层，读取
    dan_global_state（ADR-016 Route A + ADR-017 mechanism-level track
    的持久化结果），并严格遵守与 SCL_SYSTEM_PROMPT【控制层禁令】同一条
    原则：不对学生暴露任何 Ontology 内部术语、RWM/FWM/AWM 代号、原始
    贝叶斯数字（confidence/entropy/weight_vector）、stage 中间态本身、
    或 EWM 信号代码——这些都是工程内部坐标，对学生没有意义，暴露出来
    容易引发不必要的焦虑或误解。

    诊断结论只在 stage=="stable" 且有 locked_mechanism 时给出（复用
    main.py 已有的 ROOT_CAUSE_LABELS 翻译表，这份表本来就是"给学生看
    的语言"，不是给工程师看的）；未锁定时统一显示中性的"系统正在观察"
    文案，避免在诊断尚未确定时过早给学生下结论。

    复合锁定（locked_worlds长度>1，如 StructuralReasoning 场景）不需要
    特殊处理——locked_mechanism 本身已经完整对应一句翻译好的人话，不
    需要额外解释背后的 world 组合，这层复杂度停留在工程内部即可（这
    也是 ADR-017 §6 设计讨论时就想清楚的一点）。
    """
    student_id = student.student_uuid

    # 练习进度统计：复用与 /api/v1/dan 相同的 cognitive_signals 口径，
    # 保持两个端点在"总练习次数"这类基础数字上不会自相矛盾。
    result = supabase.table("cognitive_signals") \
        .select("*").eq("student_id", student_id) \
        .order("timestamp", desc=True).limit(50).execute()
    signals = [s for s in result.data if not (s.get("signal") or "").startswith("REFLECTION")]
    total = len(signals)

    concept_counts = {}
    for s in signals:
        concept = s.get("concept") or "unknown"
        concept_counts[concept] = concept_counts.get(concept, 0) + 1
    # EWM 信号代码（如 BOUNDS_TRAP）故意不纳入返回内容——这些是内部
    # 代码，不是学生认识的词汇，暴露出来没有帮助，反而可能困惑。

    # 诊断结论：只在真正锁定时给出翻译后的人话
    diagnosis_ready = False
    diagnosis_summary = "我还在学习你的思维模式。完成几次练习后会给出认知画像。"

    try:
        global_state = dan_service.get_global_state(student_id)
    except Exception as e:
        print(f"dan_global_state read error (dan-state endpoint): {e}")
        global_state = None

    if global_state and global_state.get("stage") == "stable":
        locked_mechanism = global_state.get("locked_mechanism")
        if locked_mechanism:
            label = ROOT_CAUSE_LABELS.get(locked_mechanism)
            if label:
                diagnosis_summary = label
                diagnosis_ready = True

    return {
        "student_id": student_id,
        "total_practice_count": total,
        "concepts_covered": sorted(concept_counts.keys()),
        "concept_practice_counts": concept_counts,
        "diagnosis_ready": diagnosis_ready,
        "diagnosis_summary": diagnosis_summary,
    }


@app.post("/api/v1/reflection")
def save_reflection(
    data: ReflectionInput,
    student: AuthenticatedStudent = Depends(get_current_student),
):
    try:
        supabase.table("cognitive_signals").insert({
            "student_id": student.student_uuid, "concept": "REFLECTION",
            "signal": f"REFLECTION_{data.reflection.upper()}",
            "timestamp": datetime.now().isoformat(), "dan_profile": {},
            "trigger_context": {"comment": data.comment},
            "intercept_result": {"reflection": data.reflection}
        }).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 临时诊断端点：测试 DANMemoryService 对 dan_state 的读写（Phase 1 联调）
# 使用固定测试学生 ID "TEST_DAN_SERVICE"，不触碰真实学生数据。
# 不涉及真实学生身份，不需要 Depends(get_current_student)。
# 验证完成后建议删除此端点（或保留作为健康检查，视需要而定）。
# ---------------------------------------------------------------------------
@app.get("/api/v1/dan-state-test")
def test_dan_memory_service():
    test_id = "TEST_DAN_SERVICE"
    subject = "ap_calculus"
    results = {}
    try:
        dan_service.ensure_student_initialized(test_id, subject)
        results["step1_ensure_initialized"] = "ok"

        results["step2_initial_state"] = dan_service.get_state(test_id, subject)

        dan_service.write_state(
            student_id=test_id,
            cognitive_world="RWM",
            stage="emerging",
            evidence_count=3,
            weight_vector={"RWM": 0.7, "FWM": 0.3},
            aggregator_version="test_v0",
            subject_id=subject,
        )
        results["step3_write"] = "ok"

        results["step4_after_write"] = dan_service.get_state(test_id, subject)
        results["status"] = "success"
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
    return results


# ---------------------------------------------------------------------------
# 临时压力测试端点：Phase 2 管道联调（Evidence -> Aggregator -> Damper -> State）
# 使用固定测试学生 ID "TEST_PIPELINE_STRESS"，用合成证据（不查真实 cognitive_signals，
# 不污染真实数据），连续高频撞击 dan_state，验证：
#   1. state_revision_count 是否正确递增
#   2. 复合联合主键 (student_id, subject_id, cognitive_world) 是否稳定，无冲突
#   3. 三个 World 并行写入是否互相干扰
# DummyAggregator 是占位实现，不是最终交付物，仅用于验证管道本身。
# Streamlit 前端渲染需要人工在前端页面上核实，本端点无法验证。
# 不涉及真实学生身份，不需要 Depends(get_current_student)。
# ---------------------------------------------------------------------------
@app.get("/api/v1/pipeline-stress-test")
def stress_test_pipeline():
    from inference_pipeline import run_pipeline
    from pcsa_interfaces import Evidence
    # 与生产路径保持一致，同样显式传入 BayesianAggregator（而非默认 DummyAggregator）

    test_id = "TEST_PIPELINE_STRESS"
    subject = "ap_calculus"
    dan_service.ensure_student_initialized(test_id, subject)

    results = []
    try:
        now = datetime.now()
        for round_i in range(1, 13):  # 连续 12 轮，模拟证据逐步积累
            for world in ["RWM", "FWM", "AWM"]:
                current = dan_service.get_state(test_id, subject)[world]
                fake_evidence = [
                    Evidence(
                        signal="BOUNDS_TRAP",
                        mechanism="RepresentationShift",
                        concept="5.4",
                        timestamp=now - timedelta(hours=k),
                    )
                    for k in range(round_i)
                ]
                pipeline_result = run_pipeline(test_id, world, fake_evidence, current, dan_service, subject,
                                              aggregator=bayesian_aggregator)
                results.append({"round": round_i, "world": world, **pipeline_result})

        final_state = dan_service.get_state(test_id, subject)
        return {
            "status": "success",
            "rounds_completed": 12,
            "total_writes": len(results),
            "final_state": final_state,
            "last_5_results": results[-5:],
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "completed_writes": len(results)}
