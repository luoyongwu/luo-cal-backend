import os
import re
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

app = FastAPI(title="Luo-cal Backend v1.5")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
dan_service = DANMemoryService(client=supabase)

# ===== 身份系统 v0.2 接入 =====
from auth import init_auth, router as auth_router, get_current_student, AuthenticatedStudent
init_auth(supabase)
app.include_router(auth_router)
# ===== 身份系统接入结束 =====

from inference_pipeline import BayesianAggregator, load_aggregator_config
bayesian_aggregator = BayesianAggregator(load_aggregator_config())

from concept_constraints import get_concept_constraint

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

# ===================================================================
# Teaching Effect Theory v0.2 — OLE（Observable Pedagogical Event）
# ===================================================================
# 2026-08 新增：V1 最小可验证单元。见 theory/Teaching_Effect_Theory_
# 骨架大纲_v0.2.md 第 2.3 节、第 5 节。现场验证记录见
# theory/OLE_V1_现场验证记录.md。
#
# 2026-08 更新：SELF_CORRECTION / EXPLICIT_REASONING 判别优先级规则
# ---------------------------------------------------------------
# 现场验证（2026-08-07，5.4概念）发现：当学生的回复同时符合
# "完整因果推导"（EXPLICIT_REASONING）和"引用并修正自己上一轮说法"
# （SELF_CORRECTION）两种模式时，模型倾向于只打 EXPLICIT_REASONING，
# SELF_CORRECTION 被系统性压制。这不是检测机制的 bug（两个都是正向
# 信号，误标不影响学生体验），而是"标签竞争"问题——需要一条判别
# 优先级规则，不是重新定义标签本身。
#
# 修复采用语义原则版（不用关键词列表版）：判断标准是"学生是否显式
# 引用了自己上一轮说过的内容并对其进行修正"，不依赖具体措辞（"我
# 之前说的不对"/"等等我漏掉了"/"啊对哦"都算），这样比关键词匹配
# 更泛化、更不容易漏判。
#
# 2026-08-21 新增：SPONTANEOUS_VERIFICATION / JUDGMENT_RATIONALE 拆分
# ---------------------------------------------------------------
# 实证发现（三变量对照实验）：SV的真实触发条件并非"真正的验证行为"，
# 而是"候选排除判断陈述"（学生说"不是A而是B"这类否定式判断句）。
# A组（无判断陈述）→0/6触发SV；B组（含候选排除判断）→SV+ER共现；
# C组（纯因果陈述，无排除结构）→仅ER，无SV。说明原SV标签名不副实，
# 测到的其实是判断句式，不是验证行为本身。
#
# 修复方式：收窄SV定义到真正的验证行为（结论已确定后的核验），新增
# JUDGMENT_RATIONALE（JR）标签单独承接候选排除判断陈述。同样采用
# 语义原则版定义，并在SV定义中显式加入排除条款，防止模型继续把
# "排除候选"误判成"验证"。同步补充JR与SC的区分说明（修正对象是
# 已经说出口的话，还是当下正在权衡的新候选），避免重蹈SC曾被ER
# 压制的覆辙。
# ===================================================================
OLE_LABELS = {
    "SPONTANEOUS_VERIFICATION": "主动验证——学生在结论已确定后，主动检验了边界、定义域、单位或代入特殊值反向核验，不涉及候选方案排除",
    "JUDGMENT_RATIONALE": "候选排除判断——学生在给出结论前，显式提及至少一个被排除的候选方案或可能性，并说明排除理由",
    "EXPLICIT_REASONING": "显式因果解释——学生使用了完整的'因为……所以应用某方法'推导，而非仅给出算式",
    "REPRESENTATION_ALIGNMENT": "表征主动对齐——学生主动构造、引入或选择了不同于原题目的可操作表征（如图形、表格、几何结构、新变量等），并建立、使用了原表征与新表征之间的对应关系（非单纯符号重排或命名）",
    "SELF_CORRECTION": "对话内自纠——在没有 SCL 直接指出错误的情况下，学生根据对比性提问自己修正了上一轮的推导",
}

def detect_ole(text):
    """
    从模型回复里提取所有 [OLE:XXX] 标签（可能同时出现多个）。
    复用 detect_ewm() 的反斜杠清洗逻辑（2026-07-30 那次修复的同款
    防御性处理）。返回值是列表（可能为空）。
    """
    matches = re.findall(r"\[OLE:([A-Z_\\]+)\]", text)
    return [m.replace("\\", "") for m in matches]


def strip_ole_tags(text: str) -> str:
    """
    去除模型回复里全部 [OLE:xxx] 标签，返回学生应该看到的干净文本。
    标签后允许任意空白（含换行），不假设精确跟一个空格。
    """
    return re.sub(r"\[OLE:[A-Z_\\]+\]\s*", "", text)


# ===================================================================
# 2026-08 新增：出题查重（B1 重复出题问题修复，P0）
# ===================================================================
# 背景：Session 3 报告记录过 B1 概念下 ∫x²eˣ dx 在同一 session 内被
# 完整出了两次——一次是正常测试题，一次是系统主动出的"综合挑战题"。
# 根因不是模型看不到历史（fetch_chat_history() 早已把完整对话历史
# 拼进 messages 数组发给模型），而是模型在生成新题目时没有被明确
# 要求主动核对历史、避免结构重复——历史"在场"不等于模型会主动去
# 反复扫描它做查重判断。
#
# 修复方式：不新增数据链路、不建题库，只是把"已经在上下文里的历史"
# 提炼成一份更醒目的清单，通过 system prompt 显式提醒模型注意。
# 抓取范围限定为 assistant 历史消息里出现过的积分表达式（\int...dx
# 或 Unicode ∫...dx 两种写法都兼容，覆盖 LaTeX 源码和纯符号两种
# 可能的书写习惯），最多保留最近 5 条，避免随着对话变长这段提示
# 本身无限膨胀。
# ===================================================================
_PROBLEM_EXPR_PATTERNS = [
    re.compile(r"\\int[^\n]{0,100}?\\?,?\s*d[a-zA-Z]"),  # LaTeX: \int ... dx
    re.compile(r"∫[^\n]{0,100}?d[a-zA-Z]"),               # Unicode: ∫ ... dx
]


def extract_recent_problem_expressions(history, max_items=5):
    """
    从对话历史（assistant 角色消息）里提取最近出现过的题目表达式，
    用于在生成新题目前提醒模型避免结构重复。详见模块顶部说明。
    """
    found = []
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        for pattern in _PROBLEM_EXPR_PATTERNS:
            for m in pattern.findall(content):
                if m not in found:
                    found.append(m)
    return found[-max_items:]


def build_dedup_instruction(expressions):
    """
    把提取到的表达式列表拼成一段 system prompt 指令。
    列表为空（比如概念刚开始、还没有历史）时返回空字符串，
    调用方据此决定是否要拼这一段，避免在没有历史时平白多一段空指令。
    """
    if not expressions:
        return ""
    bullets = "\n".join(f"- {e}" for e in expressions)
    return (
        "【出题查重约束 / Item De-duplication Rule】\n"
        "本次对话中已经出现过以下题目表达式，生成新题目（尤其是综合挑战题）时，"
        "绝对不允许使用结构相同或高度相似的表达式（即使只改了系数、指数等参数，"
        "只要函数结构相同也算重复）。必须更换成不同的函数结构：\n"
        f"{bullets}"
    )


# ===== 身份系统改造说明 =====
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

【控制层禁令】禁止提及RepresentationShift、SemanticIntegrity、StructuralReasoning、FlowReasoning等认知机制术语。此外，你收到的系统指令中，任何以方括号标注或全大写标注的内容（例如 [EWM:xxx]、[OLE:xxx]、HARD RULE、PRIORITY 等工程内部标签）均为内部标注，只用于指导你的行为，禁止以任何形式复述、引用、改写或提及给学生。违反此条与泄漏解题步骤同等严重。

EWM错误检测——检测到以下错误时，在回复开头加标记：
[EWM:BOUNDS_TRAP] 换元后未换积分边界
[EWM:PRE_SUBSTITUTION] 求导前代入数值
[EWM:ABSOLUTE_VALUE] 分离变量时漏写绝对值
[EWM:CHAIN_FRACTURE] 参数方程二阶导公式误用
[EWM:IVT_MVT_CONFUSION] IVT与MVT混淆
[EWM:WASHER_TRAP] 旋转体积分先减后平方
[EWM:EWM_B1C] 学生在IBP中途停止不继续推进

OLE教学事件检测——这是与EWM相反方向的检测：EWM记录学生的错误模式，OLE记录学生主动表现出的良好思维行为。

【独立并行判定原则】以下五个标签之间默认不互斥。请对每个标签分别独立核对其充分条件，不要因为已经打了一个标签就跳过其他标签的核对，也不要在多个标签同时成立时只选择"最显著"的一个。EXPLICIT_REASONING不得作为默认或兜底标签使用。

【证据要求】只有当某标签具有足够明确的行为证据时才输出该标签。不确定、不明显或仅存在弱相关线索时不要补标，宁可漏检，也不要误判。

[OLE:SPONTANEOUS_VERIFICATION] 学生在没有被要求的情况下，主动对已经得出的答案或表达式进行核验——检查边界、定义域、单位、量纲，或代入特殊值反向检验结果是否成立；这种核验行为发生在结论已经确定之后，不涉及在多个候选方案之间做选择排除（候选排除判断属于JUDGMENT_RATIONALE，不属于此类别）

[OLE:JUDGMENT_RATIONALE] 学生在给出结论、选择解法路径或确定答案之前，显式提及至少一个被排除的候选方案或可能性，并说明排除该候选、选定当前结论的理由（不论具体措辞如何，例如"不是A而是B，因为……""本来想用……但……更合适""排除了……这种可能"等对比排除句式均算）；仅仅陈述结论或方法本身、没有提及任何被否定的候选项，不满足此条件

[OLE:REPRESENTATION_ALIGNMENT] 学生主动构造、引入或选择了一种不同于原题目的可操作表征（如图形、表格、几何结构、新变量或其他等价表示），明确建立了原表征与新表征之间的对应关系，并在当前或后续推理中实际使用该对应关系推进解题；仅仅对原题目中已有的符号进行重新排列、移项、代数变形或分离（如将 dy/dx=2xy 改写为 dy/y=2x dx），或仅仅将原式的一部分标记为新符号、变量重新命名而未发生系统性的表征转换（如分部积分中把某部分记为u、另一部分记为dv，或设u=y、v=x），均不满足此条件

[OLE:SELF_CORRECTION] 在你没有直接指出错误的情况下，学生显式引用了自己上一轮说过的内容并对其进行修正（不论具体措辞如何，例如"我之前说的不对"、"等等，我漏掉了"、"啊对哦，应该是……"，或直接用"不应该是A，而应该是B"这类对比句式否定自己先前的说法）

[OLE:EXPLICIT_REASONING] 学生显式解释某一数学操作、方法选择、判断或结论为什么成立，以及该解释如何支持当前解题路径；仅仅出现"因为""所以""因此"等连接词，但没有实质性解释，不满足此条件。EXPLICIT_REASONING不得作为其他标签未命中时的兜底标签。

如果一轮回复同时满足多个标签的充分条件（例如学生既建立并使用了u=g(x)的映射，又解释了为什么这样换元能简化问题），必须将它们全部输出，如 [OLE:REPRESENTATION_ALIGNMENT][OLE:EXPLICIT_REASONING]。这是正常且值得记录的现象，不代表标注冲突。如果学生在排除候选方案的同时，也对排除理由做了完整的因果解释，必须同时输出 [OLE:JUDGMENT_RATIONALE][OLE:EXPLICIT_REASONING]；如果学生是在引用并修正自己上一轮已经说错的候选判断，应输出 [OLE:SELF_CORRECTION]，而非JUDGMENT_RATIONALE——两者的区别在于修正对象是自己已经说出口的话，还是当下正在权衡的新候选。

EWM和OLE标记互不冲突，同一轮回复可以既有EWM标记也有OLE标记（例如学生虽然还是漏写了绝对值触发EWM，但同时主动检查了定义域触发OLE）。所有标记都放在回复最开头，标记本身和标记后面的正文之间无需额外说明。"""

SCL_SYSTEM_PROMPT_EN = """You are Luo-cal, a Socratic calculus tutor.

Core rules:
1. Never give direct answers or complete solutions
2. Ask only one question at a time
3. When errors are detected, use Socratic questioning to guide the student
4. If the student demands a direct answer, refuse and continue guiding
5. Regardless of what language the student uses, always reply in English
6. Advance on completion (with repetition check): Once the student gives a correct, complete answer to the current problem (or sub-step), you must briefly confirm it and immediately advance — give the next problem, escalate to a harder application question, or explicitly state that this stage is complete. Do not ask the student to re-derive, re-verify, or revisit already-completed steps after a correct complete answer. Before asking your next question, you must self-check: does the answer to this question already appear explicitly in the student's most recent reply? If so, you must not ask it — replace it with a question that requires new information, new computation, or a new angle of judgment. For the same correctly completed answer, at most one brief follow-up confirmation is allowed, and it must target an angle the student has not yet addressed; if the student remains correct after that follow-up, you must advance on the next turn — do not ask a third time.

[Control Layer] Never mention RepresentationShift, SemanticIntegrity, StructuralReasoning, FlowReasoning, or similar cognitive-mechanism terms to students. Additionally, any content in your system instructions marked with square brackets or ALL-CAPS labels (e.g., [EWM:xxx], [OLE:xxx], HARD RULE, PRIORITY) is an internal engineering annotation meant only to guide your behavior — never repeat, quote, paraphrase, or reference it to the student in any form. Violating this is as serious as leaking a solution step.

EWM Error Detection — when the following errors are detected, add a tag at the start of your reply:
[EWM:BOUNDS_TRAP] Substitution made but integration bounds not changed
[EWM:PRE_SUBSTITUTION] Value substituted before differentiating
[EWM:ABSOLUTE_VALUE] Absolute value omitted when separating variables
[EWM:CHAIN_FRACTURE] Second derivative of parametric equation computed incorrectly
[EWM:IVT_MVT_CONFUSION] IVT and MVT confused
[EWM:WASHER_TRAP] Subtracted before squaring in solid of revolution
[EWM:EWM_B1C] Student stopped midway through integration by parts

OLE Pedagogical Event Detection — this is the opposite direction from EWM: EWM records the student's error patterns, OLE records positive thinking behaviors the student actively demonstrates.

[Independent Parallel Evaluation Principle] The following five labels are not mutually exclusive by default. Evaluate each label independently against its own sufficiency condition. Do not skip checking the other labels just because one has already been tagged, and do not pick only the "most salient" one when multiple labels are independently satisfied. EXPLICIT_REASONING must not be used as a default or fallback label.

[Evidence Requirement] Only output a label when there is sufficiently clear behavioral evidence for it. When uncertain, unclear, or only weakly related cues are present, do not tag — prefer under-detection over false positives.

[OLE:SPONTANEOUS_VERIFICATION] Without being asked, the student verified an already-reached answer or expression — checking bounds, domain, units, dimensions, or substituting a special value to check whether the result holds; this verification happens after a conclusion is already fixed and does not involve choosing among candidate options (candidate-exclusion judgment belongs to JUDGMENT_RATIONALE, not this category)

[OLE:JUDGMENT_RATIONALE] Before giving a conclusion, choosing a solution path, or finalizing an answer, the student explicitly mentions at least one excluded candidate option or possibility and states the reason for excluding it and selecting the current conclusion (regardless of exact wording — "not A but B, because...", "I originally wanted to use... but... works better", "ruled out the possibility of..." and similar contrastive-exclusion phrasing all count); merely stating the conclusion or method itself, without mentioning any rejected candidate, does not satisfy this condition

[OLE:REPRESENTATION_ALIGNMENT] Student actively constructed, introduced, or selected a different operational representation of the original problem (such as a diagram, table, geometric structure, new variable, or other equivalent representation), explicitly established a correspondence between the original and new representations, and actually used that correspondence to advance the solution in current or subsequent reasoning; merely rearranging, moving terms, algebraically transforming, or separating symbols already present in the original problem (e.g., rewriting dy/dx=2xy as dy/y=2x dx), or merely labeling part of the existing expression as a new symbol or renaming variables without a systematic representational transformation (e.g., in integration by parts labeling one part as u and another as dv, or setting u=y, v=x), does not satisfy this condition

[OLE:SELF_CORRECTION] Without you directly pointing out an error, the student explicitly referenced something they said in a previous turn and corrected it (regardless of exact wording — "what I said before was wrong", "wait, I missed", "oh right, it should be...", or a contrastive statement like "it shouldn't be A, it should be B" negating their own earlier claim)

[OLE:EXPLICIT_REASONING] Student explicitly explained why a mathematical operation, method choice, judgment, or conclusion holds, and how that explanation supports the current solution path; merely using connective words like "because," "so," or "therefore" without substantive explanation does not satisfy this condition. EXPLICIT_REASONING must not be used as a fallback label when other labels are not detected.

If a single reply independently satisfies the sufficiency conditions of multiple labels (e.g., the student both established and used the mapping u=g(x), and explained why this substitution simplifies the problem), all applicable labels must be output, such as [OLE:REPRESENTATION_ALIGNMENT][OLE:EXPLICIT_REASONING]. This is normal and worth recording — it does not indicate a labeling conflict. If the student both excludes a candidate option and gives a complete causal explanation for the exclusion, both [OLE:JUDGMENT_RATIONALE] and [OLE:EXPLICIT_REASONING] must be output; if the student is instead referencing and correcting a candidate judgment they themselves already stated in a previous turn, output [OLE:SELF_CORRECTION] rather than JUDGMENT_RATIONALE — the distinction is whether the thing being corrected is something the student already said out loud, versus a new candidate currently being weighed.

EWM and OLE tags do not conflict with each other; the same reply can carry both an EWM tag and an OLE tag (e.g., the student still omitted the absolute value, triggering EWM, but also actively checked the domain, triggering OLE). All tags go at the very start of the reply, with no extra explanation needed between the tags and the body text."""

def detect_ewm(text):
    """
    从模型回复里提取 [EWM:XXX] 标签。
    === 2026-07-30 修复：清洗 markdown 转义反斜杠 ===
    （说明同前几版，此处不再重复展开，见历史注释）
    """
    if "[EWM:" in text:
        s = text.index("[EWM:") + 5
        e = text.index("]", s)
        raw = text[s:e]
        return raw.replace("\\", "")
    return None


def strip_ewm_tag(text: str, ewm_type: str) -> str:
    """
    去除模型回复里的 [EWM:xxx] 标签，返回学生应该看到的干净文本。
    2026-08 修复：正则替代精确空格匹配，标签后允许任意空白（含换行）。
    """
    pattern = re.compile(r"\[EWM:" + re.escape(ewm_type) + r"\]\s*")
    return pattern.sub("", text, count=1)


# ---------------------------------------------------------------------------
# 对话历史读写（2026-08-02 修复，说明同前几版，此处不再重复展开）
# ---------------------------------------------------------------------------
CHAT_HISTORY_LIMIT = 20

def fetch_chat_history(student_id: str, session_id: str, limit: int = CHAT_HISTORY_LIMIT):
    try:
        resp = supabase.table("chat_messages") \
            .select("role, content, timestamp") \
            .eq("student_id", student_id) \
            .eq("session_id", session_id) \
            .order("timestamp", desc=True) \
            .limit(limit) \
            .execute()
        rows = list(reversed(resp.data))
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    except Exception as e:
        print(f"Chat history read error: {e}")
        return []


def save_chat_message(student_id: str, session_id: str, role: str, content: str):
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
                               policy_version, injected_strategy_text,
                               ole_events=None):
    """
    ADR-018：记录一次教学策略实际注入事件。
    === 2026-08 新增：ole_events 参数 ===
    （说明同前几版，此处不再重复展开）
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
            "ole_events": ole_events or [],
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
    """（说明同前几版，此处不再重复展开）"""
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
    return {"status": "Luo-cal Backend v1.5 running", "ontology": "v1"}

@app.post("/api/v1/chat")
def socratic_chat(
    data: StudentInput,
    background_tasks: BackgroundTasks,
    student: AuthenticatedStudent = Depends(get_current_student),
):
    prompt = SCL_SYSTEM_PROMPT_EN if data.language == "en" else SCL_SYSTEM_PROMPT_ZH

    concept_constraint = get_concept_constraint(data.concept_id) or "Guide step by step."
    final_system_prompt = (
        f"{prompt}\n\n"
        f"【当前概念专项教学约束 / Concept-Specific Teaching Constraint】\n"
        f"{concept_constraint}"
    )

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

    history = fetch_chat_history(student.student_uuid, data.session_id)

    # === 2026-08 新增（P0）：出题查重约束拼接 ===
    # 从历史里提取已出现过的题目表达式，拼进 system prompt 末尾提醒模型
    # 避免结构重复。历史为空（概念刚开始）时 build_dedup_instruction()
    # 返回空字符串，不会平白多出一段没有内容的指令。
    recent_problems = extract_recent_problem_expressions(history)
    dedup_instruction = build_dedup_instruction(recent_problems)
    if dedup_instruction:
        final_system_prompt = f"{final_system_prompt}\n\n{dedup_instruction}"

    messages = history + [{"role": "user", "content": user_message_content}]

    message = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=final_system_prompt,
        messages=messages,
    )
    response_text = message.content[0].text

    # === EWM 检测与清洗（说明同前几版）===
    ewm_type = detect_ewm(response_text)
    clean_response = strip_ewm_tag(response_text, ewm_type) if ewm_type else response_text

    # === OLE 检测与清洗（说明同前几版）===
    ole_events = detect_ole(clean_response)
    clean_response = strip_ole_tags(clean_response)

    background_tasks.add_task(
        save_chat_message, student.student_uuid, data.session_id, "user", user_message_content
    )
    background_tasks.add_task(
        save_chat_message, student.student_uuid, data.session_id, "assistant", clean_response
    )

    background_tasks.add_task(
        log_teaching_intervention, student.student_uuid, "ap_calculus", data.session_id,
        data.concept_id, teaching_locked_mechanism, teaching_locked_worlds, teaching_stage,
        TEACHING_POLICY_VERSION, teaching_instruction, ole_events,
    )

    if ewm_type:
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
        "ole_detected": ole_events,
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
    """（说明同前几版，此处不再重复展开）"""
    student_id = student.student_uuid

    result = supabase.table("cognitive_signals") \
        .select("*").eq("student_id", student_id) \
        .order("timestamp", desc=True).limit(50).execute()
    signals = [s for s in result.data if not (s.get("signal") or "").startswith("REFLECTION")]
    total = len(signals)

    concept_counts = {}
    for s in signals:
        concept = s.get("concept") or "unknown"
        concept_counts[concept] = concept_counts.get(concept, 0) + 1

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


@app.get("/api/v1/pipeline-stress-test")
def stress_test_pipeline():
    from inference_pipeline import run_pipeline
    from pcsa_interfaces import Evidence

    test_id = "TEST_PIPELINE_STRESS"
    subject = "ap_calculus"
    dan_service.ensure_student_initialized(test_id, subject)

    results = []
    try:
        now = datetime.now()
        for round_i in range(1, 13):
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
