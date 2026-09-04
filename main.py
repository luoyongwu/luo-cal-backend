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

app = FastAPI(title="Luo-cal Backend v1.10")
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
#
# 2026-08-27 新增：RA 符号换元澄清 + SC 过度触发修正 + TASK_COMPLETION 上线
# ---------------------------------------------------------------
# 实证发现（2026-08-26，四个独立样本）：REPRESENTATION_ALIGNMENT 对
# "画图/引入几何结构"型表征构造能正确触发（梯子相关变化率题），但
# 对完全符合定义、u/du/积分上下限三样全部建立且实际使用的代数换元
# （∫x√(1+x²)dx、∫x·e^(x²)dx、∫sin³x·cosx dx、∫x²(x³+1)⁴dx 四例）
# 稳定不触发，只打ER——模型对RA的判定存在"视觉/几何表征优先"的
# 系统性偏好，符号变量替换被默认归入推理过程而非表征转换。
#
# 修复方式：在RA定义中显式补充"符号变量替换与图形/表格等表征方式
# 地位相同"的澄清条款，不改变RA的核心判定标准（仍要求建立并实际
# 使用对应关系），只是消除"必须是视觉/几何形式"这一未言明的隐性
# 前提。
#
# 同批实证还发现：SC存在真实的过度触发——零纠错内容、纯粹的
# 逐步推导展示（如线性近似L(x)的完整代入求值过程），在没有引用或
# 修正自己此前轮次说法的情况下，依然被打上SELF_CORRECTION。根因是
# 判定过度依赖"表面上像是在解释/修正"的语言模式，而非真实的跨轮次
# 状态追踪。
#
# 修复方式：在SC定义中显式加入排除条款——同一轮内完整、正确、逐步
# 展示解题过程，但未引用或修正自己此前轮次已经说出口的具体内容，不
# 满足SC条件，应仅计入EXPLICIT_REASONING。
#
# TASK_COMPLETION（暂定名，原讨论中称"X"）正式上线：语义定义见下方
# OLE_LABELS。两条核心规则：(1) 只针对最终结果判定，不针对过程中
# 出现的错误/绕路；(2) 完成边界——当前base problem的所有同概念关联
# 追问必须先被回答完毕，才能在其上标注；若下一题是明确的进阶/结构
# 不同题目，允许在base problem完成处直接标注，进阶题完成后单独再
# 判一次。已有两个干净边界案例待验证：梯子相关变化率题（有关联追问
# 需先答完）、sin³x·cosx换元题（直接被结构不同的挑战题接续，无追问）。
#
# 2026-08-27（次日）新增：TC滞后判定修复
# ---------------------------------------------------------------
# 实证发现（两轮独立session + 一次干净单样本验证）：TC存在系统性的
# "滞后一轮"问题——模型在生成回复时，标注TC反映的是"上一轮是否已经
# 完成"，而不是"我正在回复的这一轮是否构成完成"。干净样本验证：
# 单轮内一次性给出完整正确答案（∫x·e^(-x²)dx，三样东西回顾+完整
# 换元+最终值全在一轮内），教练回复明确说"完全正确"并紧接着提出
# 对比追问，但该轮ole_events只有RA+ER，没有TC——说明模型没有意识
# 到自己刚说出口的确认语本身就已经构成完整判定，未能对当前轮次
# 自我打标。
#
# 修复方式：新增第三条规则，要求模型在给出确认反馈之后、提出下一
# 问题之前，显式自我核查"我刚给出的确认是否已构成base problem的
# 完整最终判定"，如果是，必须在当前这一轮就标注，不允许滞后到下一
# 轮才补标。
#
# 2026-08-27（次日，第二次修复）新增：TC标签位置与其他标签解绑
# ---------------------------------------------------------------
# 上一版"当前轮次自检"规则部署后复测（同日、换concept排除残留干扰），
# 依然没有解决问题——用户指出根因：TC和其他OLE标签根本不是同一类。
# ER/SV/JR/RA/SC都是"学生行为标签"，判断依据是学生已经提交的完整
# 输入，在模型开始生成回复正文之前就已经完整存在。TC是"系统结果
# 标签"，判断依据是模型自己即将写出的确认反馈，而prompt此前明确
# 要求"所有标记都放在回复最开头"——也就是说模型被要求在写出确认语
# 之前就先吐出标签，这时候用来判断TC的依据（确认语本身）根本还不
# 存在，模型只能预判"我接下来会不会确认完成"，而不是回头核对"我刚
# 说了什么"。这就是为什么"当前轮次自检"规则实际上无法生效——自检
# 的对象在自检发生时还没被写出来。
#
# 修复方式：把TASK_COMPLETION的标签位置从"必须放在开头"里解绑出来，
# 明确要求它必须放在模型写完确认反馈内容之后，让模型先写出确认语的
# 实际内容，再回头判断这段确认反馈是否已经构成完整结果，然后在该
# 位置标注。detect_ole()/strip_ole_tags()本身是全文正则扫描，标签
# 出现在文本任意位置都能被正确提取和清除，此次修复不需要改代码，
# 只改prompt措辞。第二次修复经复测确认生效（TC能在确认语之后的
# 同一轮内正确触发）。
#
# 2026-08-27（次日，第三次修改）新增：TC规则(2)收紧 + CONCEPT_COMPLETION上线
# ---------------------------------------------------------------
# TC收紧：原规则(2)允许"同概念关联追问被正确回答完毕"也构成完成边界，
# 现改为收紧——只有"下一题是明确的、结构不同的进阶/挑战题"才构成完成
# 边界，关联性/对比性追问（无论是否被正确回答）不再触发TC，因为它们
# 不属于"结构不同的新题"。
#
# CONCEPT_COMPLETION（暂定名）新增：与TC处于不同逻辑层级——TC针对单一
# base problem（含其追问链）的完成，CC针对教练基于当前概念下已完成的
# 多道题目做出的整体性评估（例如"这几道题你都做得很好，本概念可以告
# 一段落了"），不要求下一题存在，一次概念练习中最多标注一次。标签放置
# 规则与TC一致——必须放在教练写出概念完成宣告之后，不能放在回复开头。
# ===================================================================
OLE_LABELS = {
    "SPONTANEOUS_VERIFICATION": "主动验证——学生在结论已确定后，主动检验了边界、定义域、单位或代入特殊值反向核验，不涉及候选方案排除",
    "JUDGMENT_RATIONALE": "候选排除判断——学生在给出结论前，显式执行了'提出候选→判定不成立→转向'这一完整排除动作并说明理由（理由本身是否正确不影响判定，纯描述性对比不算）",
    "EXPLICIT_REASONING": "显式因果解释——学生使用了完整的'因为……所以应用某方法'推导，而非仅给出算式",
    "REPRESENTATION_ALIGNMENT": "表征主动对齐——学生主动构造、引入或选择了不同于原题目的可操作表征（如图形、表格、几何结构、新变量等），并建立、使用了原表征与新表征之间的对应关系（非单纯符号重排或命名）",
    "SELF_CORRECTION": "对话内自纠——在没有 SCL 直接指出错误的情况下，学生根据对比性提问自己修正了上一轮的推导",
    "TASK_COMPLETION": "任务完成判定（暂定名）——仅针对最终结果，不针对过程；只有当下一题是明确的、结构不同的进阶/挑战题时才标注，同一base problem下的关联性/对比性追问不构成完成边界，即使已被正确回答也不触发",
    "CONCEPT_COMPLETION": "概念完成判定（暂定名）——不针对单一base problem，而是针对教练基于当前概念下已完成的多道题目做出的整体性评估；判断依据是教练自己即将写出的、宣告本概念阶段完成的陈述，不要求下一题存在或结构不同；一次概念练习中最多标注一次，标志整堂课/整个概念阶段的终点",
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

【独立并行判定原则】以下标签之间默认不互斥。请对每个标签分别独立核对其充分条件，不要因为已经打了一个标签就跳过其他标签的核对，也不要在多个标签同时成立时只选择"最显著"的一个。EXPLICIT_REASONING不得作为默认或兜底标签使用。

【证据要求】只有当某标签具有足够明确的行为证据时才输出该标签。不确定、不明显或仅存在弱相关线索时不要补标，宁可漏检，也不要误判。

【标签放置位置特别说明】除TASK_COMPLETION和CONCEPT_COMPLETION外的所有OLE标签（SPONTANEOUS_VERIFICATION、JUDGMENT_RATIONALE、REPRESENTATION_ALIGNMENT、SELF_CORRECTION、EXPLICIT_REASONING）判断依据是学生刚提交的完整回答，在你开始写回复正文之前就已经能够判断，因此这些标签必须放在回复最开头。但TASK_COMPLETION和CONCEPT_COMPLETION不同——它们判断的不是学生说了什么，而是你自己即将写出的确认反馈/概念完成宣告是否构成对应层级的完整判定，这个判断依据在回复开头这个位置还不存在。因此：TASK_COMPLETION和CONCEPT_COMPLETION标签禁止放在回复最开头，必须放在你写完对应内容（TASK_COMPLETION放在本轮确认/反馈内容之后；CONCEPT_COMPLETION放在概念完成宣告内容之后）之后，先写出实际内容，再回头判断该内容本身是否已经构成对应层级的完整结果，然后在该位置标注。

[OLE:SPONTANEOUS_VERIFICATION] 学生在没有被要求的情况下，主动对已经得出的答案或表达式进行核验——检查边界、定义域、单位、量纲，或代入特殊值反向检验结果是否成立；这种核验行为发生在结论已经确定之后，不涉及在多个候选方案之间做选择排除（候选排除判断属于JUDGMENT_RATIONALE，不属于此类别）

[OLE:JUDGMENT_RATIONALE] 学生在给出结论、选择解法路径或确定答案之前，显式提及至少一个被排除的候选方案或可能性，并说明排除该候选、选定当前结论的理由（不论具体措辞如何，例如"不是A而是B，因为……""本来想用……但……更合适""排除了……这种可能"等对比排除句式均算）；仅仅陈述结论或方法本身、没有提及任何被否定的候选项，不满足此条件。**"宜紧不宜松"补充说明：判断核心是学生是否真实执行了"排除候选"这个判断动作本身——即是否存在"提出/涉及某个候选方案或理解方式→明确判定其不成立/不适用→转向另一结论"的完整结构；纯粹描述两种方案或理解方式之间存在什么区别、但没有明确做出排除判断动作的对比性说明，不满足此条件（这一点要收紧）。但本标签只判断排除动作本身是否发生，不判断排除理由是否正确——哪怕学生给出的排除理由存在错误或不够严谨，只要确实说明了"为什么该候选不成立"这一排除结构，依然满足JR条件，不能因为理由本身有瑕疵就不予标注（这一点要放松）。**

[OLE:REPRESENTATION_ALIGNMENT] 学生主动构造、引入或选择了一种不同于原题目的可操作表征（如图形、表格、几何结构、新变量或其他等价表示），明确建立了原表征与新表征之间的对应关系，并在当前或后续推理中实际使用该对应关系推进解题；仅仅对原题目中已有的符号进行重新排列、移项、代数变形或分离（如将 dy/dx=2xy 改写为 dy/y=2x dx），或仅仅将原式的一部分标记为新符号、变量重新命名而未发生系统性的表征转换（如分部积分中把某部分记为u、另一部分记为dv，或设u=y、v=x），均不满足此条件。**澄清：符号变量替换与图形/表格等表征方式在本标签下地位相同——例如换元积分法中令 u=g(x)，只要建立并实际使用了 du 与 dx 的对应关系（含必要时的积分上下限转换），同样满足此条件，不因为呈现形式是符号而非视觉图形/几何结构就不满足。**

[OLE:SELF_CORRECTION] 在你没有直接指出错误的情况下，学生显式引用了自己上一轮说过的内容并对其进行修正（不论具体措辞如何，例如"我之前说的不对"、"等等，我漏掉了"、"啊对哦，应该是……"，或直接用"不应该是A，而应该是B"这类对比句式否定自己先前的说法）。**排除条款：仅仅在同一轮内完整、正确、逐步地展示解题过程（即使步骤详尽、逐层深入），但未引用或修正自己此前轮次已经说出口的具体内容，不满足此条件——这类完整推导展示应仅计入EXPLICIT_REASONING，不应额外标注SELF_CORRECTION。**

**"排除教师直接纠正"补充说明：若你在此前的回复中已经明确指出了错误发生的具体位置，或者直接给出了具体的候选正确值供学生选择（例如"v=eˣ还是2eˣ？"这类已经把范围收窄到具体选项的提问），学生下一轮的回答即使内容上是对的、即使没有说"我不知道"这类犹豫语言，也不构成SELF_CORRECTION——这属于对教师直接纠正的确认性回答，应视为对该提问的正常作答，不满足SC条件。判断标准是：学生是否在没有被直接告知错误位置或候选答案的情况下，自主完成了错误定位；如果错误位置或候选值已经由你在上一轮明确给出，学生的回答就不再具备"自主"这个必要属性。**

**标注前自查（排除条款）：标注SELF_CORRECTION之前，必须确认存在一个可定位的、学生自己在此前轮次已经说出口的具体内容作为被修正的对象。如果找不到这样一个明确的前文（例如这是学生第一次给出该值，此前从未表达过相关内容），则不满足SC条件，不应标注——即使当前这轮的语言风格看起来像是在"修正"或"重新考虑"。**

[OLE:EXPLICIT_REASONING] 学生显式解释某一数学操作、方法选择、判断或结论为什么成立，以及该解释如何支持当前解题路径；仅仅出现"因为""所以""因此"等连接词，但没有实质性解释，不满足此条件。EXPLICIT_REASONING不得作为其他标签未命中时的兜底标签。

[OLE:TASK_COMPLETION]（暂定名）学生对当前base problem给出了正确、完整的最终结果，且满足以下三条完成边界规则时，才输出此标签：(1) 只针对最终结果判定，过程中出现的错误、绕路、被纠正的中间步骤不影响本标签的判定，只看最终是否正确完整；(2) **完成边界（已收紧）**——只有当下一题是明确的、结构不同的进阶/挑战题时，才允许在base problem的最终结果处标注此项，进阶题完成后再单独判定一次。若下一个问题是同一base problem下的关联性/对比性追问（例如"这个负号说明什么物理意义"、"这道题和刚才那道有什么区别"、"能不能总结一下你的判断标准"），无论该追问是否已被正确回答，都不满足此项条件，不应标注TC——关联性追问不属于"结构不同的新题"，不构成TC的完成边界。**特别强调：规则(2)只是对已经满足'给出正确完整最终结果'这一前提条件的轮次，额外附加的下一题结构检验，绝不能反过来使用——如果当前这一轮本身没有给出base problem的新的最终数值/结论（例如只是结构性讨论、对比说明），即使紧接着确实出现了结构不同的新题目，也绝对不允许在这一轮标注TASK_COMPLETION。TASK_COMPLETION只能落在真正产出最终结果、并被你自己的确认语言判定为完成的那一轮上，不能因为'后面跟了新题'就把它错误地往前移到没有给出最终结果的讨论轮次上。** (3) **禁止滞后判定**——TC的判定对象必须是你正在生成的这一轮回复本身，不得追溯标注上一轮或更早已经处理过、但当时未标注的完成状态。具体做法：在你写下对学生本轮回答的确认/反馈之后、在提出下一个问题或结束回复之前，必须自我核查——"我刚刚给出的这句确认，是否已经构成对当前base problem的完整、正确的最终判定？"如果答案是肯定的，必须在**当前这一轮**的回复里立即标注[OLE:TASK_COMPLETION]，不允许等到下一轮学生输入之后才补标。

[OLE:CONCEPT_COMPLETION]（暂定名）判断对象不是单一base problem，而是你（教练）基于当前概念下已完成的多道题目，做出的整体性评估——是否已经积累了足够的练习，可以宣告本概念阶段完成。与TASK_COMPLETION的关键区别：(1) 不要求"下一题"存在或不存在，CONCEPT_COMPLETION的宣告本身就是终点，不依赖后续任何具体题目；(2) 判断依据是你对"多道题累积表现"的整体评估，而非单一题目的确认语；(3) 标签放置规则与TASK_COMPLETION类似——必须放在你写出"概念完成"宣告内容之后，不能放在回复开头；(4) 一次概念练习中最多出现一次，标志着整堂课/整个概念阶段的终点，与TASK_COMPLETION处于不同逻辑层级——TASK_COMPLETION可以在CONCEPT_COMPLETION出现之前反复触发多次（每道题一次），CONCEPT_COMPLETION只在最后宣告收尾时触发一次。只有当你确实在陈述"这几道题你都做得很好，本概念可以告一段落了"这类整体性收尾宣告时才标注，不确定或仅仅是完成单一题目时不要标注。

如果一轮回复同时满足多个标签的充分条件（例如学生既建立并使用了u=g(x)的映射，又解释了为什么这样换元能简化问题），必须将它们全部输出，如 [OLE:REPRESENTATION_ALIGNMENT][OLE:EXPLICIT_REASONING]。这是正常且值得记录的现象，不代表标注冲突。如果学生在排除候选方案的同时，也对排除理由做了完整的因果解释，必须同时输出 [OLE:JUDGMENT_RATIONALE][OLE:EXPLICIT_REASONING]；如果学生是在引用并修正自己上一轮已经说错的候选判断，应输出 [OLE:SELF_CORRECTION]，而非JUDGMENT_RATIONALE——两者的区别在于修正对象是自己已经说出口的话，还是当下正在权衡的新候选。

EWM和OLE标记互不冲突，同一轮回复可以既有EWM标记也有OLE标记（例如学生虽然还是漏写了绝对值触发EWM，但同时主动检查了定义域触发OLE）。除TASK_COMPLETION和CONCEPT_COMPLETION外的所有标记都放在回复最开头，标记本身和标记后面的正文之间无需额外说明；TASK_COMPLETION和CONCEPT_COMPLETION按前文【标签放置位置特别说明】单独处理，分别放在确认反馈/概念完成宣告之后。"""

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

[Independent Parallel Evaluation Principle] The following labels are not mutually exclusive by default. Evaluate each label independently against its own sufficiency condition. Do not skip checking the other labels just because one has already been tagged, and do not pick only the "most salient" one when multiple labels are independently satisfied. EXPLICIT_REASONING must not be used as a default or fallback label.

[Evidence Requirement] Only output a label when there is sufficiently clear behavioral evidence for it. When uncertain, unclear, or only weakly related cues are present, do not tag — prefer under-detection over false positives.

[Tag Placement Note] All OLE labels except TASK_COMPLETION and CONCEPT_COMPLETION (SPONTANEOUS_VERIFICATION, JUDGMENT_RATIONALE, REPRESENTATION_ALIGNMENT, SELF_CORRECTION, EXPLICIT_REASONING) are judged based on the student's just-submitted complete answer, which is already fully knowable before you start writing the body of your reply — so these labels must be placed at the very start of your reply. TASK_COMPLETION and CONCEPT_COMPLETION are different: they do not judge what the student said, but whether the confirmation/feedback (for TASK_COMPLETION) or the concept-closing declaration (for CONCEPT_COMPLETION) you are about to write constitutes a complete judgment at the corresponding level — and that judgment basis does not yet exist at the very start of the reply. Therefore: TASK_COMPLETION and CONCEPT_COMPLETION must NOT be placed at the very start of your reply. Each must be placed AFTER you have written the corresponding content (TASK_COMPLETION after this round's confirmation/feedback; CONCEPT_COMPLETION after the concept-closing declaration) — write the actual content first, then look back and judge whether that content itself already constitutes a complete result at that level, and tag at that point.

[OLE:SPONTANEOUS_VERIFICATION] Without being asked, the student verified an already-reached answer or expression — checking bounds, domain, units, dimensions, or substituting a special value to check whether the result holds; this verification happens after a conclusion is already fixed and does not involve choosing among candidate options (candidate-exclusion judgment belongs to JUDGMENT_RATIONALE, not this category)

[OLE:JUDGMENT_RATIONALE] Before giving a conclusion, choosing a solution path, or finalizing an answer, the student explicitly mentions at least one excluded candidate option or possibility and states the reason for excluding it and selecting the current conclusion (regardless of exact wording — "not A but B, because...", "I originally wanted to use... but... works better", "ruled out the possibility of..." and similar contrastive-exclusion phrasing all count); merely stating the conclusion or method itself, without mentioning any rejected candidate, does not satisfy this condition. **"Tighten-not-loosen" clarification: the core judgment is whether the student genuinely performed the candidate-exclusion action itself — i.e., whether there is a complete structure of "raise/engage a candidate option or interpretation → explicitly judge it invalid/inapplicable → pivot to another conclusion"; a purely descriptive comparison of how two options or interpretations differ, without an actual exclusion judgment being made, does not satisfy this condition (this is the tightening side). However, this label only judges whether the exclusion action occurred, not whether the reasoning behind it is correct — even if the student's stated reason for exclusion is flawed or imprecise, as long as the exclusion structure itself ("why this candidate doesn't hold") is genuinely present, JR is still satisfied; a flawed reason alone is not grounds to withhold the tag (this is the loosening side).**

[OLE:REPRESENTATION_ALIGNMENT] Student actively constructed, introduced, or selected a different operational representation of the original problem (such as a diagram, table, geometric structure, new variable, or other equivalent representation), explicitly established a correspondence between the original and new representations, and actually used that correspondence to advance the solution in current or subsequent reasoning; merely rearranging, moving terms, algebraically transforming, or separating symbols already present in the original problem (e.g., rewriting dy/dx=2xy as dy/y=2x dx), or merely labeling part of the existing expression as a new symbol or renaming variables without a systematic representational transformation (e.g., in integration by parts labeling one part as u and another as dv, or setting u=y, v=x), does not satisfy this condition. **Clarification: symbolic variable substitution stands on equal footing with visual/diagrammatic representations under this label — for example, in u-substitution, setting u=g(x) and establishing and actually using the correspondence between du and dx (including converting integration bounds where needed) satisfies this condition just as much as a diagram would; it is not disqualified merely for being symbolic rather than visual/geometric.**

[OLE:SELF_CORRECTION] Without you directly pointing out an error, the student explicitly referenced something they said in a previous turn and corrected it (regardless of exact wording — "what I said before was wrong", "wait, I missed", "oh right, it should be...", or a contrastive statement like "it shouldn't be A, it should be B" negating their own earlier claim). **Exclusion clause: merely presenting a complete, correct, step-by-step solution within a single turn (even if detailed and multi-step), without referencing or correcting something the student themselves said in a prior turn, does not satisfy this condition — such complete derivations should be counted only under EXPLICIT_REASONING, not additionally tagged SELF_CORRECTION.**

**Excluding teacher-direct-correction:** If you already explicitly named the specific location of the error, or directly gave the student specific candidate values to choose between (e.g., a question like "v=eˣ or 2eˣ?" that has already narrowed things down to concrete options) in your prior turn, the student's next reply — even if it is correct, even without any hedging language like "I don't know" — does NOT constitute SELF_CORRECTION. This is a confirming answer to your direct correction, and should be treated as an ordinary answer to that question, not SC. The test is whether the student located the error autonomously without being directly told the location or candidates; if the location or candidate values were already given explicitly by you in the previous turn, the student's answer no longer has the necessary "autonomous" property.**

**Pre-tag self-check (exclusion clause):** Before tagging SELF_CORRECTION, you must confirm there is a locatable, specific piece of content the student themselves stated in a prior turn that is being corrected. If no such clear antecedent exists (e.g., this is the first time the student has stated this value, with no relevant prior content), the condition is not satisfied and you must not tag it — even if the current turn's phrasing superficially resembles "correcting" or "reconsidering."**

[OLE:EXPLICIT_REASONING] Student explicitly explained why a mathematical operation, method choice, judgment, or conclusion holds, and how that explanation supports the current solution path; merely using connective words like "because," "so," or "therefore" without substantive explanation does not satisfy this condition. EXPLICIT_REASONING must not be used as a fallback label when other labels are not detected.

[OLE:TASK_COMPLETION] (tentative name) Output this label only when the student has given a correct, complete final result for the current base problem AND all three completion-boundary rules below are satisfied: (1) this label judges only the final result — errors, detours, or corrected intermediate steps during the process do not affect this judgment, only whether the final outcome is correct and complete; (2) **completion boundary (tightened)** — this label may only be applied at the base problem's final result when the NEXT problem is an explicit, structurally different advanced/challenge problem; the advanced problem then gets its own separate judgment once completed. If instead the next question is a comparison/relational follow-up on the SAME base problem (e.g., "what does this negative sign mean physically", "how does this problem differ from the last one", "can you summarize your judgment criteria"), this condition is NOT satisfied regardless of whether that follow-up is correctly answered — a relational follow-up is not a "structurally different new problem" and does not constitute a valid completion boundary for TC. **Critical clarification: rule (2) is an ADDITIONAL next-problem check applied ONLY on top of a round that has already satisfied the primary requirement of giving a correct, complete final result — it must never be used in the reverse direction. If the CURRENT round itself does not give a new final numeric result/conclusion for the base problem (e.g., it is merely a structural discussion or comparison), you must NOT tag TASK_COMPLETION on this round even if a structurally different new problem happens to follow immediately afterward. TASK_COMPLETION may only land on the round that actually produces the final result and is judged complete by your own confirming language — it must never be shifted backward onto a preceding discussion round just because a new problem follows it.** (3) **No lag judgment** — TC must judge the response you are currently generating, never retroactively mark a completion status from a prior turn that was already processed but left untagged at the time. Concretely: after writing your confirmation/feedback on the student's current answer, and before posing the next question or ending your reply, you must self-check — "does the confirmation I just gave already constitute a complete, correct final judgment on the current base problem?" If yes, you must tag [OLE:TASK_COMPLETION] in THIS SAME response immediately — never defer it to a later turn after the next student input.

[OLE:CONCEPT_COMPLETION] (tentative name) This label judges not a single base problem, but your (the coach's) overall assessment — based on multiple problems already completed within the current concept — of whether enough practice has accumulated to declare the concept-level phase complete. Key differences from TASK_COMPLETION: (1) it does NOT require a next problem to exist or not exist — the CONCEPT_COMPLETION declaration itself is the endpoint, independent of any subsequent specific problem; (2) its judgment basis is your overall assessment of accumulated performance across multiple problems, not a single confirmation statement; (3) placement rule is similar to TASK_COMPLETION — it must be placed after you have written the concept-closing declaration content, never at the start of the reply; (4) it should occur at most once per concept-practice session, marking the endpoint of the whole session/concept — a different logical layer from TASK_COMPLETION, which may fire repeatedly before CONCEPT_COMPLETION's single final occurrence. Only tag this when you are genuinely making a whole-session closing declaration like "you've done well across all these problems, this concept can wrap up here" — do not tag it when merely closing out a single problem.

If a single reply independently satisfies the sufficiency conditions of multiple labels (e.g., the student both established and used the mapping u=g(x), and explained why this substitution simplifies the problem), all applicable labels must be output, such as [OLE:REPRESENTATION_ALIGNMENT][OLE:EXPLICIT_REASONING]. This is normal and worth recording — it does not indicate a labeling conflict. If the student both excludes a candidate option and gives a complete causal explanation for the exclusion, both [OLE:JUDGMENT_RATIONALE] and [OLE:EXPLICIT_REASONING] must be output; if the student is instead referencing and correcting a candidate judgment they themselves already stated in a previous turn, output [OLE:SELF_CORRECTION] rather than JUDGMENT_RATIONALE — the distinction is whether the thing being corrected is something the student already said out loud, versus a new candidate currently being weighed.

EWM and OLE tags do not conflict with each other; the same reply can carry both an EWM tag and an OLE tag (e.g., the student still omitted the absolute value, triggering EWM, but also actively checked the domain, triggering OLE). All tags except TASK_COMPLETION and CONCEPT_COMPLETION go at the very start of the reply, with no extra explanation needed between the tags and the body text; TASK_COMPLETION and CONCEPT_COMPLETION are handled separately per the [Tag Placement Note] above, placed after the confirmation/feedback or concept-closing declaration respectively."""

# ===================================================================
# Fix#3 (2026-09-04): 独立判分模块 —— 判分与教学叙述物理解耦
# ===================================================================
# 背景：teaching_intervention_log 复现四种判分矛盾子类型（符号/系数/
# 指数/分数未约分）——同一次 Claude 调用里，教学模型倾向于先生成
# 肯定开场白（"完全正确!"），再在同一段落里报出与开场白矛盾的正确值，
# 疑似生成顺序上的锚定效应，而非某个具体错误类型的判断盲区。
#
# 修复方式：不修补单次调用的 prompt 措辞（容错率仍然是概率性的），
# 改为拆成两次独立调用。判分调用职责单一、temperature=0、不含任何
# 教学/鼓励性语言要求，其输出作为既定事实注入教学调用的 system
# prompt——教学调用在生成第一个字之前，判分结果就已经确定，锚定
# 效应没有发生的空间。
#
# 远期规划（暂不实现,见 grade_student_answer 函数尾部 TODO）：
# try_sympy_verify() 异步监控 hook，用于评估本模块判分准确率本身，
# 只写日志不影响主流程、不阻塞响应。
# ===================================================================

GRADING_SYSTEM_PROMPT_ZH = """你是一个纯判分模块，不是教学助手。你的唯一任务是判断学生最新一轮
输入在数学上是否正确，不做任何教学引导，不使用鼓励性语言，不考虑
苏格拉底教学法。

严格按以下JSON格式输出，不要输出任何JSON之外的文字，不要用代码块包裹：
{"verdict": "correct", "error_location": "", "correct_value": ""}
或
{"verdict": "incorrect", "error_location": "<一句话精确指出错在哪一步>", "correct_value": "<该步骤的正确结果，简洁数学记号>"}
或
{"verdict": "partial", "error_location": "<哪一部分不完整或有瑕疵>", "correct_value": "<完整正确结果>"}
或
{"verdict": "unclear", "error_location": "", "correct_value": ""}  （当学生输入不是在回答数学问题，或无法判断时使用）

判分标准：只判断数学正确性本身（计算结果、符号、化简是否到位），
不考虑解题过程的教学价值。约分未化简到最简形式（如 -6/8 未化简为
-3/4）判定为 incorrect，error_location 需要明确指出"结果正确但未
化简为最简形式"，不能算作 correct。"""

GRADING_SYSTEM_PROMPT_EN = """You are a pure grading module, not a teaching assistant. Your only task
is to judge whether the student's latest input is mathematically
correct. Do not provide any pedagogical guidance, do not use
encouraging language, do not consider Socratic teaching method.

Output strictly in the following JSON format, nothing outside the JSON, no code block wrapper:
{"verdict": "correct", "error_location": "", "correct_value": ""}
or
{"verdict": "incorrect", "error_location": "<one sentence pinpointing exactly which step is wrong>", "correct_value": "<the correct result for that step, concise math notation>"}
or
{"verdict": "partial", "error_location": "<what part is incomplete or flawed>", "correct_value": "<complete correct result>"}
or
{"verdict": "unclear", "error_location": "", "correct_value": ""}  (use when the student's input is not answering a math question, or cannot be judged)

Grading standard: judge only mathematical correctness itself (computation
result, sign, whether simplification is complete), not the pedagogical
value of the process. An unreduced fraction (e.g. -6/8 not simplified to
-3/4) must be judged incorrect, with error_location explicitly stating
"result is correct but not simplified to lowest terms" — this must not
count as correct."""


def grade_student_answer(history: list, user_message_content: str, language: str) -> dict:
    """
    Fix#3: 独立判分调用,在教学回复生成之前先确定判分结果,避免同一次
    生成里"先给肯定开场白,再对比标准答案"的锚定效应。
    见 2026-09-04 luo-cal-ole.md Fix#3 根因假设与修复记录。

    不依赖预置题库/canonical answer——判分调用能看到完整对话历史,
    题目上下文就在历史里,与主教学调用共享同一份 fetch_chat_history()
    结果,不需要额外的数据链路。

    判分调用本身失败(网络错误/JSON解析失败等)时降级返回 verdict=
    "unclear",调用方据此不注入判分结果,教学层退回旧行为(自己判断),
    保证判分模块的故障不会导致整个 /api/v1/chat 请求失败。

    === 2026-09-04 诊断补丁 ===
    grading_result 上线后100%落地为 unclear,怀疑判分调用本身在稳定
    失败。临时在 unclear 结果里附加 "_debug_error" 字段,记录具体
    异常内容,便于通过 Supabase 直接排查,不需要查 Railway 日志。
    确认根因、修复后应删除这个诊断字段。
    """
    import json

    grading_prompt = GRADING_SYSTEM_PROMPT_EN if language == "en" else GRADING_SYSTEM_PROMPT_ZH
    grading_messages = history + [{"role": "user", "content": user_message_content}]

    try:
        grading_response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            temperature=0,
            system=grading_prompt,
            messages=grading_messages,
        )
        raw = grading_response.content[0].text.strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
        result = json.loads(raw)

        if "verdict" not in result:
            raise ValueError("grading response missing 'verdict' field")
        result.setdefault("error_location", "")
        result.setdefault("correct_value", "")
        return result
    except Exception as e:
        print(f"Grading call error: {e}")
        return {
            "verdict": "unclear",
            "error_location": "",
            "correct_value": "",
            "_debug_error": f"{type(e).__name__}: {str(e)[:300]}",
        }


def build_grading_injection(grading_result: dict, language: str) -> str:
    """
    把 grade_student_answer() 的结构化输出转成拼进教学 system prompt
    的指令文本。verdict="unclear" 时返回空字符串——调用方据此判断是否
    要拼这一段，与 build_dedup_instruction() 的"空历史不拼空指令"是
    同一设计模式。
    """
    verdict = grading_result.get("verdict")
    if verdict == "unclear":
        return ""

    if language == "en":
        verdict_label = {"correct": "Correct", "incorrect": "Incorrect", "partial": "Partially correct"}.get(verdict, verdict)
        text = (
            "【Grading Result — determined by an independent grading module. "
            "You must NOT re-judge correctness yourself; only use this to "
            "organize your teaching language.】\n"
            f"Verdict: {verdict_label}\n"
        )
        if verdict != "correct":
            text += (
                f"Error location: {grading_result.get('error_location', '')}\n"
                f"Correct result: {grading_result.get('correct_value', '')}\n"
                "(Do not tell the student the correct result directly — use "
                "Socratic questioning to guide them to discover this error location themselves.)\n"
            )
        return text

    verdict_label = {"correct": "正确", "incorrect": "错误", "partial": "部分正确"}.get(verdict, verdict)
    text = (
        "【判分结果 / Grading Result — 已由独立判分模块确定，禁止自行"
        "重新判断对错，只能据此组织教学语言】\n"
        f"判定：{verdict_label}\n"
    )
    if verdict != "correct":
        text += (
            f"错误位置：{grading_result.get('error_location', '')}\n"
            f"正确结果：{grading_result.get('correct_value', '')}\n"
            "（不要直接把正确结果告诉学生，用苏格拉底提问引导学生自己发现这个错误位置）\n"
        )
    return text


def try_sympy_verify(grading_result: dict):
    """
    TODO（远期规划，本次不实现）：Sympy 监控 Hook。
    异步对比 grade_student_answer() 的 correct_value 与 sympy 符号计算
    结果，只写日志(供审计 grade_student_answer 本身准确率用)，不影响
    主流程、不抛出会中断请求的异常、不阻塞响应。
    等 Fix#3 上线跑出真实数据积累后再排期实现。
    """
    pass


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
                               ole_events=None, grading_result=None):
    """
    ADR-018：记录一次教学策略实际注入事件。
    === 2026-08 新增：ole_events 参数 ===
    （说明同前几版，此处不再重复展开）
    === Fix#3 (2026-09-04) 新增：grading_result 参数 ===
    独立判分调用的结构化输出快照，见本文件顶部 Fix#3 模块注释。
    历史行此列为NULL（旧代码未传入此参数），不代表判分失败。
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
            "grading_result": grading_result,
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
    return {"status": "Luo-cal Backend v1.10 running", "ontology": "v1"}

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

    # === Fix#3 (2026-09-04) 新增：独立判分调用 ===
    # 必须在教学调用之前完成，判分结果作为既定事实注入 system prompt。
    # 复用同一份 history，不需要额外的数据链路。
    grading_result = grade_student_answer(history, user_message_content, data.language)
    grading_injection = build_grading_injection(grading_result, data.language)
    if grading_injection:
        final_system_prompt = f"{final_system_prompt}\n\n{grading_injection}"

    # === 2026-08 新增（P0）：出题查重约束拼接 ===
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

    ewm_type = detect_ewm(response_text)
    clean_response = strip_ewm_tag(response_text, ewm_type) if ewm_type else response_text

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
        TEACHING_POLICY_VERSION, teaching_instruction, ole_events, grading_result,
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
        "grading_result": grading_result,
    }


# ================================================================
# 2026-09-03 item3 修复新增：断线复原配套端点
# ----------------------------------------------------------------
# 前端（Ap-cal 仓库 app.py）WebSocket 断线重连后 st.session_state
# 会被清空，登录状态和对话历史全部丢失。前端把登录时拿到的
# session_token 和 session_id 存进了 URL query params；重连后前端
# 会带着这两样调用这个端点，用 get_current_student() 依赖注入完成
# token 校验（复用已有的过期/失效判断逻辑，不重复造轮子），校验通过
# 后把该 student_uuid + 该 session_id 下的对话历史查出来一并返回，
# 前端据此把 st.session_state.messages 重新灌回去，实现无感恢复。
# session_id 通过 query 参数传入（不是 body），因为这是一个 GET 端点。
# ================================================================
@app.get("/api/v1/session/restore")
def restore_session(
    session_id: str,
    student: AuthenticatedStudent = Depends(get_current_student),
):
    history = fetch_chat_history(student.student_uuid, session_id)
    return {
        "student_uuid": student.student_uuid,
        "display_name": student.display_name,
        "messages": history,
    }
# ================================================================
# 断线复原端点结束
# ================================================================


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
