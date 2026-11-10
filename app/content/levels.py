"""关卡与 SOP 目标库。

关卡把客服培训拆成 8 个递进情景；每个目标都带有关键词（规则引擎检出）
与提示语（学员点“提示”时返回）。权重之和为 100。
"""

from __future__ import annotations

from .personas import PERSONAS

LEVELS: list[dict] = [
    {
        "id": "bronze-1",
        "order": 1,
        "tier": "青铜",
        "tier_color": "#B08D57",
        "name": "第一声问候",
        "subtitle": "登录验证码风波",
        "persona_id": "newbie",
        "difficulty": "入门",
        "xp": 120,
        "pass_score": 80,
        "suggested_turns": 4,
        "scene": (
            "《星海纪元》新服开放第二天。新手玩家小鹿在登录页连续三次获取验证码失败，"
            "她担心是自己的手机问题，向在线客服发起会话。"
        ),
        "brief": (
            "这是新人客服的第一关：玩家没有怒气，但很迷茫。"
            "目标是把她从“我是不是弄错了”带到“我知道下一步该做什么”。"
            "记住：一次只让玩家做一个动作。"
        ),
        "coach_focus": "耐心引导 · 分步排查 · 确认闭环",
        "knowledge_ids": ["login", "redline"],
        "objectives": [
            {
                "key": "greet",
                "label": "礼貌开场",
                "weight": 15,
                "keywords": ["您好", "你好", "在的", "很高兴为您服务", "欢迎", "客服小助手"],
                "hint": "先用一句自然的问候接住玩家，别一上来就丢排查步骤。",
            },
            {
                "key": "empathy",
                "label": "共情安抚",
                "weight": 20,
                "keywords": ["理解", "着急", "别担心", "不用担心", "我来帮您", "别着急", "放心", "辛苦"],
                "hint": "告诉她“验证码收不到确实很让人着急，我来帮您”，先稳住情绪。",
            },
            {
                "key": "diagnose",
                "label": "分步排查",
                "weight": 25,
                "keywords": [
                    "验证码", "短信", "手机号", "手机号码", "网络", "飞行模式",
                    "重新发送", "垃圾短信", "拦截", "权限", "信号", "运营商", "邮箱",
                ],
                "hint": "带她逐项排查：垃圾短信箱 → 安全软件拦截 → 等 60 秒重发 → 换网络。一次只问一项。",
            },
            {
                "key": "solution",
                "label": "给出方案",
                "weight": 25,
                "keywords": [
                    "重新发送", "再次尝试", "稍后再试", "更换手机号", "人工验证",
                    "绑定邮箱", "联系运营商", "切换网络", "关闭拦截", "帮您转",
                ],
                "hint": "清楚地说出下一步怎么操作；如果短信仍然不行，告诉她还可以改人工验证或绑定邮箱。",
            },
            {
                "key": "confirm",
                "label": "确认闭环",
                "weight": 15,
                "keywords": [
                    "试一下", "麻烦您", "请您", "如果还", "随时", "再联系",
                    "稍后", "告诉我", "反馈", "不行再来",
                ],
                "hint": "结尾确认她理解了，并留一个明确的回访口子：“还不行随时回来找我”。",
            },
        ],
    },
    {
        "id": "bronze-2",
        "order": 2,
        "tier": "青铜",
        "tier_color": "#B08D57",
        "name": "消失的钻石",
        "subtitle": "充值未到账",
        "persona_id": "buyer",
        "difficulty": "入门",
        "xp": 150,
        "pass_score": 80,
        "suggested_turns": 4,
        "scene": (
            "小氪玩家布丁首次购买 98 元月卡，支付成功已过去 20 分钟，"
            "游戏内钻石仍未到账，她担心钱打了水漂，向客服求助。"
        ),
        "brief": (
            "充值问题最怕两件事：让玩家重复提供信息，以及给出没有依据的承诺。"
            "这一关练的是“核实 → 解释 → 时效 → 安抚”的完整链条。"
        ),
        "coach_focus": "信息核实 · 时效管理 · 承诺边界",
        "knowledge_ids": ["recharge", "redline"],
        "objectives": [
            {
                "key": "greet",
                "label": "礼貌开场",
                "weight": 10,
                "keywords": ["您好", "你好", "很高兴", "客服", "在的", "收到"],
                "hint": "先回应她的着急，不要让她感觉消息掉进了机器人队列。",
            },
            {
                "key": "verify",
                "label": "核对订单",
                "weight": 25,
                "keywords": [
                    "订单号", "订单", "支付截图", "截图", "角色名", "区服",
                    "充值时间", "支付方式", "账号", "核实", "查询",
                ],
                "hint": "一次性说清需要哪些信息：订单号、支付截图、角色名与区服，别分三次要。",
            },
            {
                "key": "explain",
                "label": "解释原因",
                "weight": 25,
                "keywords": [
                    "到账", "延迟", "补单", "核实", "订单状态", "服务器",
                    "支付渠道", "同步", "未到账", "异常", "回调",
                ],
                "hint": "用玩家听得懂的话解释：支付通道同步有延迟，你这边会帮她核验。",
            },
            {
                "key": "eta",
                "label": "给出时效",
                "weight": 20,
                "keywords": ["分钟", "小时", "工作日", "24", "48", "预计", "时效", "尽快", "稍后", "1 个工作日"],
                "hint": "给出明确预期：正常几分钟到账，超过 2 小时会走补单，1 个工作日内有结果。",
            },
            {
                "key": "reassure",
                "label": "安抚与跟进",
                "weight": 20,
                "keywords": [
                    "放心", "会到账", "通知您", "补发", "跟进", "结果",
                    "回访", "给您答复", "不用担心", "帮您记",
                ],
                "hint": "明确告诉她：钱不会丢，结果出来后你会主动通知她。",
            },
        ],
    },
    {
        "id": "silver-1",
        "order": 3,
        "tier": "白银",
        "tier_color": "#9FB3C8",
        "name": "掉星风暴",
        "subtitle": "情绪安抚与排位申诉",
        "persona_id": "angry",
        "difficulty": "进阶",
        "xp": 200,
        "pass_score": 80,
        "suggested_turns": 5,
        "scene": (
            "巅峰赛进行中，服务器短时波动导致玩家峡谷火焰掉线，系统判定失败并扣除两颗星。"
            "他正在气头上，连续发来质问。"
        ),
        "brief": (
            "面对愤怒玩家，先处理情绪，再处理问题。"
            "不要急着解释技术原因——他要先确认“你们认不认这个体验损失”。"
        ),
        "coach_focus": "情绪降温 · 实质方案 · 升级路径",
        "knowledge_ids": ["rank", "redline"],
        "objectives": [
            {
                "key": "empathy",
                "label": "承认体验影响",
                "weight": 20,
                "keywords": ["理解", "确实", "抱歉", "给您添麻烦", "换我", "心情", "影响体验", "失望", "难怪"],
                "hint": "先正面承认：掉两颗星确实很难受，这个体验影响我们不回避。",
            },
            {
                "key": "calm",
                "label": "情绪降温",
                "weight": 15,
                "keywords": ["冷静", "先别", "别急", "消消气", "我帮您", "一起", "先", "听我"],
                "hint": "用“我先帮您把情况查清楚”取代“您冷静一下”，把火气转成动作。",
            },
            {
                "key": "verify",
                "label": "核实对局",
                "weight": 20,
                "keywords": ["角色名", "区服", "对局", "时间", "账号", "截图", "战报", "核实", "确认", "对局 ID"],
                "hint": "要角色名、区服和对局时间/战报截图，说清“只查这一次，不用重复提交”。",
            },
            {
                "key": "solution",
                "label": "给出实质方案",
                "weight": 30,
                "keywords": [
                    "申诉", "补偿", "恢复", "反馈", "技术", "工单", "核查",
                    "处理", "申请", "记录", "排位", "礼包",
                ],
                "hint": "给他申诉路径 + 补偿申请，明确哪些你能做、哪些需要审核。",
            },
            {
                "key": "followup",
                "label": "承诺跟进",
                "weight": 15,
                "keywords": ["结果", "通知", "24", "工作日", "回访", "答复", "跟进", "后续", "邮件"],
                "hint": "给出反馈节点，例如“7 个工作日内邮件通知申诉结果”，别只说“已反馈”。",
            },
        ],
    },
    {
        "id": "silver-2",
        "order": 4,
        "tier": "白银",
        "tier_color": "#9FB3C8",
        "name": "6480 元的账单",
        "subtitle": "未成年人退款",
        "persona_id": "guardian",
        "difficulty": "困难",
        "xp": 240,
        "pass_score": 80,
        "suggested_turns": 5,
        "scene": (
            "晨晨妈妈发现 10 岁的孩子用她的手机在《星海纪元》累计充值 6480 元，"
            "她要求按未成年人保护相关规定申请退款。"
        ),
        "brief": (
            "这是合规红线关。家长要的不是安慰，是明确的流程、材料和时效。"
            "任何“肯定能退”的承诺都会给公司带来风险。"
        ),
        "coach_focus": "合规边界 · 材料清单 · 审核时效",
        "knowledge_ids": ["minor_refund", "redline"],
        "objectives": [
            {
                "key": "empathy",
                "label": "理解家长处境",
                "weight": 15,
                "keywords": ["理解", "担心", "着急", "孩子", "家长", "抱歉", "给您添麻烦", "不容易", "换位"],
                "hint": "先站在家长角度承认这件事让人着急，再进入流程，不要一上来读条款。",
            },
            {
                "key": "verify",
                "label": "核实充值信息",
                "weight": 20,
                "keywords": [
                    "未成年", "实名", "身份证", "消费记录", "订单", "充值",
                    "金额", "账号", "材料", "关系证明", "户口本", "出生证明",
                ],
                "hint": "一次性列出材料清单：监护人身份证明、监护关系证明、订单记录、账号实名信息。",
            },
            {
                "key": "policy",
                "label": "说明退款流程",
                "weight": 25,
                "keywords": [
                    "未成年人", "退款", "申请", "审核", "流程", "渠道", "工单",
                    "按规定", "保护", "风控", "原路",
                ],
                "hint": "说明完整链路：登记未成年人退款工单 → 材料审核 → 风控复核 → 原路退款。",
            },
            {
                "key": "boundary",
                "label": "守住承诺边界",
                "weight": 25,
                "keywords": [
                    "无法直接", "需核实", "审核通过", "不能", "无法", "根据",
                    "以审核", "不承诺", "视审核", "需提供", "按规定", "以结果为准",
                ],
                "hint": "明确表述“能否退款及比例以审核结果为准”，不要承诺无条件全额退款。",
            },
            {
                "key": "followup",
                "label": "给出时效与跟进",
                "weight": 15,
                "keywords": ["工作日", "时效", "通知", "结果", "回访", "跟进", "短信", "电话", "7", "15"],
                "hint": "给出 7–15 个工作日的审核时效，并说明结果会通过电话或短信通知。",
            },
        ],
    },
    {
        "id": "gold-1",
        "order": 5,
        "tier": "黄金",
        "tier_color": "#F3C969",
        "name": "保底疑云",
        "subtitle": "概率与规则解释",
        "persona_id": "lawyer",
        "difficulty": "困难",
        "xp": 300,
        "pass_score": 80,
        "suggested_turns": 5,
        "scene": (
            "硬核玩家概率论信徒在限定池连续 380 抽未获得限定角色，"
            "他带着官网概率截图来到客服，要求解释保底机制。"
        ),
        "brief": (
            "这类玩家不要“安抚”，要“依据”。任何自编概率、含糊话术都会被抓住。"
            "不懂规则时，正确动作是核查与升级，而不是硬答。"
        ),
        "coach_focus": "规则准确 · 数据核查 · 专业升级",
        "knowledge_ids": ["gacha", "redline"],
        "objectives": [
            {
                "key": "verify",
                "label": "核实抽卡记录",
                "weight": 15,
                "keywords": ["抽卡记录", "记录", "角色", "账号", "时间", "截图", "核对", "查询", "角色 ID"],
                "hint": "先要角色 ID、抽卡记录截图和时间区间，表明你是认真核查而不是复读公告。",
            },
            {
                "key": "policy",
                "label": "引用官方规则",
                "weight": 30,
                "keywords": ["概率", "保底", "公示", "规则", "综合", "抽取", "次数", "机制", "官方", "官网"],
                "hint": "所有解释以官网公示为准：综合概率包含保底贡献，不能与单抽概率直接比较。",
            },
            {
                "key": "explain",
                "label": "解释保底机制",
                "weight": 25,
                "keywords": [
                    "综合概率", "保底", "第", "抽", "机制", "统计", "样本",
                    "公示", "说明", "计算", "累计", "次数",
                ],
                "hint": "用可核查的语言解释保底累计规则；不确定的数字不要编。",
            },
            {
                "key": "escalate",
                "label": "提交技术核查",
                "weight": 15,
                "keywords": ["核查", "技术", "工单", "提交", "反馈", "专项", "记录", "复查", "升级"],
                "hint": "380 抽属于异常样本，明确提交技术核查工单，并说明会书面反馈结论。",
            },
            {
                "key": "followup",
                "label": "书面反馈承诺",
                "weight": 15,
                "keywords": ["结果", "答复", "通知", "工作日", "跟进", "回访", "书面", "邮件"],
                "hint": "告诉他核查结果会以书面/邮件形式反馈，给出时间范围。",
            },
        ],
    },
    {
        "id": "gold-2",
        "order": 6,
        "tier": "黄金",
        "tier_color": "#F3C969",
        "name": "无限维护",
        "subtitle": "服务器雪崩",
        "persona_id": "veteran",
        "difficulty": "进阶",
        "xp": 340,
        "pass_score": 80,
        "suggested_turns": 5,
        "scene": (
            "《星海纪元》3.0 大版本更新，原定 6 小时维护已三次延期，"
            "开服时间仍未确定。900 天老玩家熬夜冠军在客服窗口表达失望。"
        ),
        "brief": (
            "服务器故障时，客服最容易犯的错是“替官方乱给时间”。"
            "这一关练的是信息口径、补偿说明和情绪承接，而不是甩锅。"
        ),
        "coach_focus": "口径统一 · 补偿说明 · 老玩家维系",
        "knowledge_ids": ["outage", "redline"],
        "objectives": [
            {
                "key": "inform",
                "label": "同步维护信息",
                "weight": 20,
                "keywords": ["维护", "延迟", "公告", "停机", "更新", "服务器", "开服", "时间", "公告为准", "延期"],
                "hint": "先同步已知信息：维护延期与下一次公告节点，明确“以官方公告为准”。",
            },
            {
                "key": "empathy",
                "label": "承接失望情绪",
                "weight": 15,
                "keywords": ["理解", "抱歉", "等待", "辛苦", "失望", "心情", "老玩家", "感谢支持", "感谢您"],
                "hint": "承认等了很久，感谢他 900 天的陪伴，别用“请耐心等待”打发。",
            },
            {
                "key": "compensation",
                "label": "说明补偿方案",
                "weight": 25,
                "keywords": ["补偿", "发放", "邮件", "钻石", "道具", "礼包", "领取", "全服", "体力"],
                "hint": "按停机时长分档说明补偿内容，并说明通过全服邮件发放。",
            },
            {
                "key": "eta",
                "label": "给出时间节点",
                "weight": 20,
                "keywords": ["点", "预计", "稍后", "尽快", "具体", "公告", "通知", "下一次", "小时"],
                "hint": "不要给假开服时间；给“下一次公告时间点”与已知进度，这比含糊更可信。",
            },
            {
                "key": "boundary",
                "label": "口径边界",
                "weight": 20,
                "keywords": ["以公告为准", "不传谣", "官方", "不承诺", "无法", "需", "根据", "确认后", "未经确认"],
                "hint": "明确不承诺未确认的开服时间，避免玩家截图后二次舆情。",
            },
        ],
    },
    {
        "id": "platinum-1",
        "order": 7,
        "tier": "铂金",
        "tier_color": "#7FE7D5",
        "name": "榜一的最后通牒",
        "subtitle": "高价值用户维稳",
        "persona_id": "whale",
        "difficulty": "困难",
        "xp": 420,
        "pass_score": 80,
        "suggested_turns": 6,
        "scene": (
            "新版本调整了限定皮肤特效，全服榜一、公会会长夜皇认为官方忽视高价值玩家，"
            "公会 200 人正在等他表态。"
        ),
        "brief": (
            "高价值用户要的不是“礼貌”，而是“被看见”。"
            "既不能跪，也不能硬；用专属跟进 + 可申请的权益方案留住他。"
        ),
        "coach_focus": "价值认可 · 权益申请 · 专属跟进",
        "knowledge_ids": ["vip", "redline"],
        "objectives": [
            {
                "key": "acknowledge",
                "label": "认可长期价值",
                "weight": 15,
                "keywords": ["感谢", "支持", "重视", "专属", "长期", "消费", "抱歉", "理解", "感谢您"],
                "hint": "具体提到他的长期支持与榜一身份，别只说“感谢您对游戏的支持”。",
            },
            {
                "key": "verify",
                "label": "核实账号与影响",
                "weight": 15,
                "keywords": ["账号", "角色", "消费记录", "订单", "区服", "核实", "确认", "皮肤", "特效"],
                "hint": "确认账号、区服与具体皮肤条目，表明你确实在查他的问题。",
            },
            {
                "key": "investigate",
                "label": "反馈与评估",
                "weight": 20,
                "keywords": ["核查", "反馈", "策划", "记录", "评估", "技术", "专项", "提交", "版本", "调整"],
                "hint": "承诺将问题反馈给策划/技术评估，并给出内部反馈节点。",
            },
            {
                "key": "offer",
                "label": "申请权益方案",
                "weight": 25,
                "keywords": ["补偿", "方案", "申请", "专属", "礼包", "福利", "权益", "回退", "恢复", "临时"],
                "hint": "给出“可申请的权益方案”，明确需要审批，不承诺具体回退数值。",
            },
            {
                "key": "retain",
                "label": "专属跟进",
                "weight": 25,
                "keywords": [
                    "跟进", "专属", "顾问", "回访", "一对一", "后续", "继续",
                    "反馈您", "对接", "24", "工作日",
                ],
                "hint": "安排专属对接人与回访节奏，让他能在公会里有一个可以交代的答复。",
            },
        ],
    },
    {
        "id": "king-1",
        "order": 8,
        "tier": "王者",
        "tier_color": "#FF7AC3",
        "name": "直播间风暴",
        "subtitle": "主播舆情危机",
        "persona_id": "streamer",
        "difficulty": "地狱",
        "xp": 520,
        "pass_score": 80,
        "suggested_turns": 6,
        "scene": (
            "人气主播键盘侠客在直播中声称发现“暗改削弱”，已剪辑对比视频，"
            "直播间在线 2 万人。他要求官方立刻给说法。"
        ),
        "brief": (
            "舆情关的核心不是说服主播，而是稳住节奏、核实事实、交给官方口径。"
            "任何一句情绪化的话都可能被剪进视频。"
        ),
        "coach_focus": "冷静控场 · 事实核实 · 官方口径",
        "knowledge_ids": ["pr", "redline"],
        "objectives": [
            {
                "key": "calm",
                "label": "冷静控场",
                "weight": 15,
                "keywords": ["冷静", "理解", "重视", "感谢关注", "先", "别急", "认真对待", "不回避", "不会回避"],
                "hint": "先表明态度：这件事我们认真对待、不会回避；不要要求他“先冷静”。",
            },
            {
                "key": "verify",
                "label": "核实素材",
                "weight": 15,
                "keywords": ["直播", "视频", "账号", "情况", "截图", "内容", "核实", "确认", "时间", "素材"],
                "hint": "请他提供视频素材、账号与争议时间点，表明你在核实事实而不是封口。",
            },
            {
                "key": "official",
                "label": "官方回应口径",
                "weight": 25,
                "keywords": ["官方", "公告", "回应", "渠道", "核实", "声明", "正式", "说明", "公开"],
                "hint": "明确回应会通过官方账号/公告发布，客服个人不擅自给结论。",
            },
            {
                "key": "escalate",
                "label": "升级专项对接",
                "weight": 25,
                "keywords": ["升级", "专项", "负责人", "公关", "团队", "上报", "跟进", "记录", "对接", "品牌"],
                "hint": "登记舆情工单并升级至公关/品牌负责人，给出内部首次反馈节点。",
            },
            {
                "key": "boundary",
                "label": "守住公开边界",
                "weight": 20,
                "keywords": ["不承诺", "以官方为准", "不公开", "无法", "需核实", "根据", "暂不", "调查", "以公告", "正式"],
                "hint": "不承诺处理结果，不在公开渠道对线，一切以调查与官方公告为准。",
            },
        ],
    },
]


LEVELS_BY_ID = {lv["id"]: lv for lv in LEVELS}

for _lv in LEVELS:
    assert sum(o["weight"] for o in _lv["objectives"]) == 100, _lv["id"]
    assert _lv["persona_id"] in PERSONAS, _lv["id"]


def level_public(level: dict) -> dict:
    """去掉关键词与提示，避免前端提前“看到答案”。"""
    return {
        "id": level["id"],
        "order": level["order"],
        "tier": level["tier"],
        "tier_color": level["tier_color"],
        "name": level["name"],
        "subtitle": level["subtitle"],
        "persona_id": level["persona_id"],
        "difficulty": level["difficulty"],
        "xp": level["xp"],
        "pass_score": level["pass_score"],
        "suggested_turns": level["suggested_turns"],
        "scene": level["scene"],
        "brief": level["brief"],
        "coach_focus": level["coach_focus"],
        "objectives": [{"key": o["key"], "label": o["label"], "weight": o["weight"]} for o in level["objectives"]],
        "knowledge_ids": level["knowledge_ids"],
    }


def first_level_id() -> str:
    return LEVELS[0]["id"]


def next_level_of(level_id: str) -> dict | None:
    for i, lv in enumerate(LEVELS):
        if lv["id"] == level_id and i + 1 < len(LEVELS):
            return LEVELS[i + 1]
    return None
