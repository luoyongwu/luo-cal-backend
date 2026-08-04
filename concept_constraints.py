"""
concept_constraints.py
Luo-cal Backend — 逐概念（Concept-Specific）教学策略约束

=== 2026-08-02 迁移记录 ===
本文件的内容原本活在 Streamlit 前端仓库（luoyongwu/Ap-cal）的 app.py
里，是一份 CONCEPT_CONSTRAINTS 字典，为每个 AP Calculus 概念定制了
Socratic 教学策略（HARD RULE），原本在前端 get_ai_response() 里拼进
发给 LLM 的 system prompt。

发现的问题（2026-08-02）：前端 RailwayAdapter.chat(self, system, ...)
函数签名接收了 system 参数，但函数体从未把它放进发给后端 /api/v1/chat
的 payload 里——也就是说，只要学生走的是"🚀 Railway Backend"这条真实
生产链路（需要授权码、真正调用 Claude、真正写入 dan_state 的那一支），
这整套精心设计的逐概念教学策略从未真正生效过，包括 4.3 概念那条重要
的 PRE-OVERRIDE 硬性规则。后端此前也没有任何地方能接收/使用这类信息，
即使前端把 system 传过去也不会被消费。

决策（2026-08-02，Yongwu 拍板）：采纳"方案1"——把 CONCEPT_CONSTRAINTS
彻底搬进后端，作为 SCL 策略引擎的硬性组成部分，而不是让前端透传自己
构造的 system prompt 给后端（那样会让前端拥有"篡改导师控制策略"的
特权，且未来若有更多客户端接入后端，会导致教学策略在多处重复维护、
彼此不同步）。前端（Ap-cal 仓库）已同步删除这份字典，RailwayAdapter
现在只传递干净的 concept_id/user_input/session_id/language，不再构造
或发送 system 参数——这是"单一真值源"迁移的完整闭环。

内容本身逐字迁移自前端原有字典，未做任何改写，保持策略定义的连续性。
main.py::socratic_chat() 按 concept_id 查表，把对应约束拼进
SCL_SYSTEM_PROMPT_ZH/EN 之后再发给 Claude。

=== 2026-08 修复记录：内部标注前缀泄漏（Session 3 真实对话测试发现）===
问题：字典值里写死的 "HARD RULE:" 及其变体（"HARD RULE BC:"、
"HARD RULE FWM:"、"HARD RULE BC RWM:"、"HARD RULE [LAYER: ...]:"）
本来是写给维护者看的元层标注，用来提示"这条约束是硬性规则、必须
严格执行"，从未打算发给学生看。但 Session 3 真实对话测试（7.2 概念，
三次复现）发现模型会把这个前缀原样复述进学生可见的回复文本里，且这
类"元层面"泄漏不会被 Leakage Score 自评机制捕捉到——它评估的是
"是否泄漏解题步骤"，不是"是否泄漏系统内部工程标注词"，是自评机制
本身的盲区。

修复策略：字典本身的原始内容【不做改写】——"HARD RULE:"这个前缀对
维护者依然有用（一眼看出哪些是硬性规则、哪些是普通引导建议），删掉
会降低这份文件本身的可读性和可维护性。真正的修复点在于"这份内容被
拼进发给模型的 system prompt 之前"这唯一必经的关口，也就是本文件
新增的 get_concept_constraint() 函数——它在返回约束文本之前，先用
确定性的正则清洗掉所有已确认会泄漏的 "HARD RULE" 家族前缀。

【重要】main.py::socratic_chat() 必须改为调用 get_concept_constraint()
取值，不能再直接读 CONCEPT_CONSTRAINTS[concept_id]——直接读字典会把
清洗前的原始文本（含"HARD RULE:"字样）带进最终发给模型的 prompt，
这次修复就形同虚设。

这一层清洗只精确处理已确认会泄漏的 "HARD RULE" 家族前缀，是确定性
修复（不依赖模型是否"听话"，正则清洗后物理上就不存在这个字符串了）。
字典里还有一些同样是"标签风格"但尚未被观测到泄漏的措辞（比如
"SIGN RULE:"、"STUDENT FOLLOW-UP:"、"Bounds trap:"、"Washer trap:"
这类），本次刻意没有动它们——一是没有真实证据表明它们会泄漏，二是
"trap" 类术语本身更像是可以对学生说的内容描述（"这里有个边界陷阱"
是一句正常的教学提醒，不是明显的内部工程黑话），贸然大范围重写反而
增加破坏 4.3 PRE-OVERRIDE 这类已验证通过的复杂规则的风险。更广义的
"任何方括号标签/全大写标签一律不许复述给学生"的行为层防御规则，
属于 SCL_SYSTEM_PROMPT 的职责——是防御的第二层，两层合起来才是完整
方案（正则做确定性兜底，prompt 规则应对未来任何新增的、还没被正则
覆盖到的标注词）。见 SCL_SYSTEM_PROMPT 里新增的通用禁令。
"""

import re

CONCEPT_CONSTRAINTS = {
    "1.1": "Ensure student builds intuition numerically/graphically before algebra.",
    "1.2": "Guide student to apply limit laws step by step. Do not skip steps.",
    "1.3": "Focus on the three-part definition of continuity at a point.",
    "1.4": "Guide student to identify vertical and horizontal asymptotes separately.",
    "1.X": "Generate a comprehensive problem combining limits, continuity, and asymptotes.",
    "2.1": "HARD RULE: Guide student to derive the derivative using the limit definition. Do not skip the limit process.",
    "2.2": "Ensure student understands differentiability implies continuity but not vice versa.",
    "2.3": "Focus on connecting the sign of f prime to increasing/decreasing behavior of f.",
    "2.4": "Guide student to apply differentiation rules repeatedly for higher-order derivatives.",
    "2.X": "Generate a comprehensive problem combining limit definition of derivative, differentiability, and graphical interpretation.",
    "3.1": "HARD RULE: Decompose f(g(x)) into f(u) and g(x) explicitly before differentiating.",
    "3.2": "HARD RULE: Ensure dy/dx appears explicitly when differentiating y terms.",
    "3.3": "HARD RULE: For products, require student to identify u and v explicitly. For quotients, identify numerator and denominator before applying quotient rule.",
    "3.4": "Verify student correctly applies the inverse function derivative formula.",
    "3.5": "HARD RULE: Require student to write dx/dt and dy/dt separately before computing dy/dx.",
    "3.X": "HARD RULE: Generate ONE problem combining at least TWO Unit 3 skills. Maximum 2 sub-questions. First question: Which method and why? Never choose starting point for student.",
    "4.1": "HARD RULE: Student MUST state ALL EVT conditions before applying. Critical points include where f prime is zero OR undefined. Always compare all candidates including endpoints.",
    "4.2": "HARD RULE: Verify all THREE MVT hypotheses in order. IVT vs MVT: MVT gives f prime(c) equals average rate of change, not f(c)=0. Existence via IVT, uniqueness via monotonicity.",
    "4.3": ("HARD RULE [LAYER: PROBLEM_SOLVING]: Student MUST follow exact sequence: "
            "(1) identify variables, (2) write relationship equation, "
            "(3) differentiate with respect to t, (4) THEN substitute values. "
            "SIGN RULE: Require interpretation of negative derivatives. "
            "HARD RULE 4.3-PRE-OVERRIDE [HIGHEST PRIORITY - CROSS-LAYER]: "
            "This rule overrides SINGLE-PROBLEM RULE and all other rules. "
            "If student input contains substitution of a numerical value into a variable BEFORE differentiating, "
            "BEFORE doing anything else - even before applying SINGLE-PROBLEM RULE - "
            "you MUST immediately ask ONLY this one question: "
            "'你是在求导之前代入的数值，还是在求导之后？/ "
            "Did you substitute the numerical value before differentiating, or after?' "
            "Do NOT list multiple problems. Do NOT ask student to choose. "
            "Do NOT mention variable relationships disappearing. "
            "Do NOT hint at consequences. Do NOT point out other errors. "
            "Wait for answer to THIS question first. Only after student answers "
            "may you proceed to SINGLE-PROBLEM RULE or any other rule. "
            "STUDENT FOLLOW-UP: If student asks what to do, reply ONLY: "
            "'回到代入数值之前的那一步。在你代入具体数值之前，你的方程是什么？'"),
    "4.4": "HARD RULE: Where f prime has extremum, f has INFLECTION POINT not extremum. f prime zero is necessary but NOT sufficient for inflection; verify sign change.",
    "4.5": "HARD RULE: Student MUST write L(x)=f(a)+f prime(a)(x-a) before substituting. Redirect if student computes directly or omits f(a).",
    "4.X": "Generate comprehensive problem combining EVT, MVT, related rates, derivative graph reading, and linearization. Cover at least three sub-topics.",
    "5.1": "HARD RULE: Never accept antiderivative without +C. Geometric anchor: student must describe family of curves before computation.",
    "5.2": "HARD RULE: Approximation must be NAMED first. Require over/under-estimate judgment. Definite integral must be voiced as LIMIT of sums before FTC.",
    "5.3": "HARD RULE: Always tag FTC Part 1 or Part 2. Variable-limit trap: upper limit g(x) requires chain rule factor. Confirm F is antiderivative before Part 2 evaluation.",
    "5.4": "HARD RULE: Declare u and du explicitly first. Bounds trap: new bounds u(a) and u(b) required BEFORE evaluation. No back-substitution after bounds converted.",
    "5.5": "HARD RULE: Physical anchor first. Total distance integrates absolute value of v. Solve v(t)=0 and split before computing.",
    "5.X": "HARD RULE: Combine at least TWO skills including one flagged trap. Max 2 sub-questions. First move: which tool and why? Tag FTC Part 1 or Part 2.",
    "6.1": "HARD RULE: Slicing decision first with geometric justification. Intersections before limits. Name top/bottom or right/left functions.",
    "6.2": "HARD RULE: Method classification first. Washer trap: pi times (R squared minus r squared), never pi times (R minus r) squared. Radii are distances to axis.",
    "6.3": "HARD RULE: Conflation trap: average VALUE versus average RATE OF CHANGE. Equal-area rectangle anchor before any formula. State continuity for MVT for Integrals.",
    "6.X": "HARD RULE: Combine at least TWO whitelist skills with one flagged trap. Max 2 sub-questions. First move: slicing and setup strategy.",
    "7.1": "HARD RULE FWM: Each point carries slope as local flow direction. Identify three slope regions before drawing. Find where dy/dx equals zero and classify equilibria.",
    "7.2": "HARD RULE: Show separated form before any integral sign. Write ln absolute value of y not ln y. Track plus C through exponentiation.",
    "7.3": "HARD RULE BC: World model declaration mandatory before step 1. Each step needs current point, slope, new estimate. Concavity determines over or underestimate.",
    "7.4": "HARD RULE: Initial condition gate before any computation. k-sign blindness check. BC only: equilibrium first, classify stability, sketch S-curve before algebra.",
    "7.X": "HARD RULE: AB whitelist is 7.1, 7.2, 7.4 exponential only. BC whitelist is full 7.1 through 7.4 plus B1. FWM world declaration first.",
    "8.1": "HARD RULE BC RWM: Motion model anchor mandatory before any derivative. Derive dy/dx from chain rule not from memory. Second derivative chain fracture: d2y/dx2 is not (d2y/dt2)/(d2x/dt2).",
    "8.2": "HARD RULE BC RWM: Area element is thin sector not rectangle. Check pole as intersection. Sketch before area setup.",
    "Bridge-R1": "Reflective session only, no new problem. Unify errors from 5.4, 8.1, 8.2.",
    "8.X": "HARD RULE BC: At least one flagged trap. Representation declaration first. Sketch before integral.",
    "B1": "HARD RULE BC: Product rule reversal anchor before u/dv selection. LIATE is heuristic not rule. Single-round tunnel vision trap. Infinite loop trap. Substitution first always.",
}

# ============================================================
# 内部标注前缀清洗层（2026-08 新增，修复 HARD RULE 泄漏问题）
# ============================================================
#
# 匹配以下已确认会出现在 CONCEPT_CONSTRAINTS 字典值里的变体：
#   "HARD RULE: "
#   "HARD RULE BC: "
#   "HARD RULE FWM: "
#   "HARD RULE BC RWM: "
#   "HARD RULE [LAYER: PROBLEM_SOLVING]: "
#   "HARD RULE 4.3-PRE-OVERRIDE [HIGHEST PRIORITY - CROSS-LAYER]: "
#
# 已针对全部 42 条 CONCEPT_CONSTRAINTS 条目（含 4.3 一条内两处出现）
# 做过验证，清洗后不再含 "HARD RULE" 字样，且不改变除该前缀外的
# 任何文本内容。
_HARD_RULE_RE = re.compile(
    r"HARD RULE(?:\s+(?:BC\s+RWM|BC|FWM))?(?:\s+[\w.\-]+)?(?:\s*\[[^\]]+\])?\s*:\s*"
)


def sanitize_constraint(text: str) -> str:
    """
    去除单条约束文本里的 "HARD RULE" 家族内部标注前缀，只保留真正
    要发给模型的教学指令正文。是确定性的字符串清洗，不依赖模型
    是否遵守指令。
    """
    return _HARD_RULE_RE.sub("", text).strip()


def get_concept_constraint(concept_id: str):
    """
    main.py::socratic_chat() 应该调用这个函数取约束文本，而不是
    直接读 CONCEPT_CONSTRAINTS[concept_id]——直接读字典会把清洗前
    的原始文本（含 "HARD RULE:" 字样）带进最终发给模型的 system
    prompt，这次修复就形同虚设。

    找不到对应 concept_id 时返回 None（和原来直接查字典的行为一致，
    调用方原有的 None 判断逻辑不需要改）。
    """
    raw = CONCEPT_CONSTRAINTS.get(concept_id)
    if raw is None:
        return None
    return sanitize_constraint(raw)
