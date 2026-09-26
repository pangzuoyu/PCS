增补 SPEC：PSV 安全阀选型
Spec 编号：SUP-P5-PSV-002
版本：V1.14（V1.13 经第十二次评审后关闭 P2 问题）
日期：2026-09-17
状态：accepted（P5 架构评审委员会第十二次评审通过）
父 Spec：spec/工艺专用综合计算软件需求规格说明书 Web版 P5.md V1.3 §3.2.3
上游 Spec：SUP-P5-PSV-001 V1.0（PSV 多标准引擎，已批准）
关联 ADR：ADR-0028（PSV 多标准引擎）决策 8 / 决策 9
关联计划：P5 计划 Task 17（API 526 选型）/ Task 18（PSV API + persist）
TODOS 关联：TODO-PSV-SELECT-001
评审归档：docs/adr/signatures/0028-psv-select-acceptance.md

§-1 前置声明：G 孔口争议的终结
本 SPEC 的 G 孔口配置经 API STD 526 第五版 Table 5 原文核验确认：

API STD 526 第五版 Table 5 原文（弹簧载荷式 PSV "G" 孔口）：

材料	阀门尺寸（入口 × 孔口 × 出口）	ANSI 法兰等级
Carbon Steel	1½G3	150, 300, 600, 900
Carbon Steel	2G3	1500, 2500
Chrome Molybdenum	1½G3	300, 600, 900
Chrome Molybdenum	2G3	1500, 2500
Austenitic Stainless	1½G3	150, 300, 600, 900
Austenitic Stainless	2G3	1500, 2500
Nickel/Copper Alloy	1½G3	150, 300, 600
Alloy 20	1½G3	150, 300, 600, 900
Alloy 20	2G3	1500, 2500
直接结论：

G 孔口出口法兰 = 3"（所有材料、所有压力等级一致）

G 孔口入口法兰 = 1.5"（150#–900#）或 2"（1500#–2500#）

API 526 Table 5 中不存在 2.5" 出口法兰的 G 孔口配置

本 SPEC 的修订轨迹（诚实记录）：

版本	G 孔口配置	判定
V1.5-V1.6	1.5" × 3"	✅ 正确（无来源标注）
V1.7	1.5" × 2.5"	❌ 错误引入
V1.8	1.5" × 3"	✅ 正确（基于不可靠来源）
V1.9	1.5" × 2.5"	❌ 面积推断错误
V1.10	1.5" × 2.5"	❌ Vajra 转录（与原文不符）
V1.11-V1.14	1.5" × 3"（标准）/ 2" × 3"（高压）	✅ API 526 Table 5 原文
关键教训：引用二手转录来源（如 Vajra、ProjectMaterials）必须与 API 正版标准原文对比后才能写入 SPEC。

§0 方法论声明（永久条款）
0.1 数据来源强制要求
本 SPEC 中所有具体数值必须满足：

附来源文件原文摘录（图片、链接或引用段落）

或明确标注"待核验"

禁止以"多源交叉验证"作为含糊的技术背书

0.2 执行机制
来源清单审计 gate（P5-3 启动前必关）：

工艺工程师提交《数据来源清单》，逐项列出每个数值的来源文件名 + 页码 + 原文摘录

独立评审员抽样核验（≥30% 条目）

核验结果签字归档至 docs/adr/signatures/psv-data-source-audit.md

未通过审计的数值视为"待核验"，不得进入生产计算

二手来源必须对比原文：

凡引用二手转录来源（如 Vajra、ProjectMaterials、厂商博客、API 520/526 转录本等）的数据，必须与 API 正版标准原文对比后才能写入 SPEC。

引用二手来源时，必须同时附上二手转录摘录 + API 正版原文摘录（图片或 PDF 引用）。若两者矛盾 → 以 API 正版原文为准。

审计范围：

分类	数值示例	来源要求
API 526 孔口-法兰映射	D~T 全 14 项	API 526 Tables 2–15 原文
法兰等级-孔口约束	各等级孔口范围	API 526 Tables 2–15 原文
Kb 曲线数据	各 overpressure 曲线点	厂商数据表（首选）/ API 520 Fig.30
波纹管材料禁忌条件	6 种材料 forbidden	材料手册 / NACE / API 571
先导式温度范围	GENERAL/HIGH_TEMP	厂商数据表原文
blowdown 范围	各介质上下限	API 520 / ASME 原文
§1 背景与动机
1.1 现状
SUP-P5-PSV-001 V1.0 已批准 PSV 多标准引擎。P5 计划 Task 17 已落地 API 526 孔口自动选型。工艺室日常"安全阀选型"包含多个维度，当前系统仅覆盖孔口自动选型一项。

1.2 核心问题
不同阀型的选型参数取值本质不同，且需考虑介质、背压类型、孔口字母的二阶影响。

阀型	背压限值	背压修正 Kb	blowdown 范围	入/出口映射
弹簧载荷式	built-up ≤ 10%；恒背压无硬限（CDTP 修正）	无补偿（Kb=1.0）	气 5%~10% / 液 10%~20%	API 526 标准映射
平衡波纹管式	total ≤ 50%；>30% 须咨询厂商	厂商数据优先 / API 520 曲线	气 5%~10% / 液 10%~20%	API 526 标准映射
先导式	无硬限（导阀驱动）	无	2%~5%	无固定映射
爆破膜式	不适用	无	不适用	不适用
1.3 设计目标
补全选型维度，每个维度按阀型 + 介质 + 孔口字母分化取值

阀型-参数一致性校验：非法组合 → 422

与 ADR-0028 决策 8 一致：先导式/爆破膜式拦截

本批只完整实现弹簧式 + 平衡波纹管式

§2 范围
2.1 纳入范围
阀型	P5-3 处理
弹簧载荷式（SPRING_LOADED）	✅ 完整实现
平衡波纹管式（BALANCED_BELLOWS）	✅ 完整实现
先导式（PILOT_OPERATED）	🔴 拦截（G7），预埋 temperature 字段
爆破膜式（RUPTURE_DISC）	🔴 拦截（G8），预埋 Kc + position 字段
2.2 不纳入范围
先导式阀计算（GB/T 28778-2023）——ADR-0028 决策 8

爆破膜式计算（API 520 Part II）——P6+

阀体厂商具体型号匹配——P6+

法兰标准反查表（ASME B16.5 / HG/T 20592）——P6+

§3 数据模型扩展
3.1 psv_results 新增列
sql
ALTER TABLE psv_results ADD COLUMN valve_type VARCHAR(32);
ALTER TABLE psv_results ADD COLUMN body_material VARCHAR(32);
ALTER TABLE psv_results ADD COLUMN bellows_material VARCHAR(32);
ALTER TABLE psv_results ADD COLUMN inlet_size VARCHAR(16);
ALTER TABLE psv_results ADD COLUMN outlet_size VARCHAR(16);
ALTER TABLE psv_results ADD COLUMN flange_class VARCHAR(8);
ALTER TABLE psv_results ADD COLUMN blowdown_fraction FLOAT;
ALTER TABLE psv_results ADD COLUMN back_pressure_pct FLOAT;
ALTER TABLE psv_results ADD COLUMN back_pressure_type VARCHAR(16);
ALTER TABLE psv_results ADD COLUMN overpressure_pct FLOAT;
ALTER TABLE psv_results ADD COLUMN kb_factor FLOAT;
ALTER TABLE psv_results ADD COLUMN kb_source VARCHAR(32);
ALTER TABLE psv_results ADD COLUMN valve_brand VARCHAR(32);          -- V1.14：品牌优先
ALTER TABLE psv_results ADD COLUMN cdtp_applied BOOLEAN DEFAULT FALSE;
ALTER TABLE psv_results ADD COLUMN orifice_overridden BOOLEAN DEFAULT FALSE;
ALTER TABLE psv_results ADD COLUMN orifice_manual VARCHAR(8);
ALTER TABLE psv_results ADD COLUMN pilot_temperature_c FLOAT;
ALTER TABLE psv_results ADD COLUMN pilot_temp_class VARCHAR(16);
ALTER TABLE psv_results ADD COLUMN rupture_disc_kc FLOAT;
ALTER TABLE psv_results ADD COLUMN rupture_disc_position VARCHAR(16);
ALTER TABLE psv_results ADD COLUMN fire_protection BOOLEAN DEFAULT FALSE;
3.2 新增枚举
python
PsvValveType = Literal["SPRING_LOADED", "BALANCED_BELLOWS", "PILOT_OPERATED", "RUPTURE_DISC"]
PsvBodyMaterial = Literal["CARBON_STEEL", "SS304", "SS316", "SS316L", "ALLOY"]
PsvBellowsMaterial = Literal[
    "HASTELLOY_C276", "SS316L", "INCONEL_625",
    "INCONEL_718", "ALLOY_400", "ALLOY_C22",
]
PsvOrificeSize = Literal["D","E","F","G","H","J","K","L","M","N","P","Q","R","T"]
PsvBackPressureType = Literal["BUILT_UP", "SUPERIMPOSED"]
PsvMedium = Literal["GAS", "VAPOR", "LIQUID", "TWO_PHASE"]
PsvPilotTempClass = Literal["GENERAL", "HIGH_TEMP", "CRYOGENIC"]
PsvRuptureDiscPosition = Literal["UPSTREAM", "DOWNSTREAM", "NONE"]
PsvFlangeClass = Literal["150#", "300#", "600#", "900#", "1500#", "2500#"]

# Kb 来源标识（"none" = 标准定义 1.0；"mixed:{mfr1}+{mfr2}" = 多厂商混用）
PsvKbSource = Literal[
    "none",
    "manufacturer:LESER",
    "manufacturer:Consolidated",
    "manufacturer:Anderson_Greenwood",
    "mixed:LESER+Consolidated",
    "mixed:LESER+Anderson_Greenwood",
    "mixed:Consolidated+Anderson_Greenwood",
    "api520_fig30",
    "en4126",
]

# ✅ V1.14 P2-1 修订：valve_brand 为自由字符串（不枚举），
#                    后端校验 + Warning 提示
PsvValveBrand = str  # 自由字符串；已知品牌见 _KB_DATA["manufacturer"]
⚠️ 说明：PsvKbSource 硬编码具体厂商名。新增厂商（如 Farris、Crosby）时必须同步更新此枚举 + _KB_DATA["manufacturer"] 字典。

3.3 API 526 孔口-法兰映射
API STD 526 第五版 Tables 2–15 对应关系：

孔口	Table 号	孔口	Table 号
D	Table 2	K	Table 8
E	Table 3	L	Table 9
F	Table 4	M	Table 10
G	Table 5	N	Table 11
H	Table 6	P	Table 12
J	Table 7	Q	Table 13
—	—	R	Table 14
—	—	T	Table 15（8T10）
python
# ✅ 标准映射（基于 API STD 526 第五版 Tables 2–15 原文）
API526_ORIFICE_TO_FLANGE = {
    "D": ("1 inch",   "2 inch"),        # 0.110 in² | Table 2
    "E": ("1.5 inch", "2.5 inch"),      # 0.196 in² | Table 3
    "F": ("1.5 inch", "2.5 inch"),      # 0.307 in² | Table 4
    "G": ("1.5 inch", "3 inch"),        # 0.503 in² | Table 5：1½G3
    "H": ("2 inch",   "3 inch"),        # 0.785 in² | Table 6
    "J": ("3 inch",   "4 inch"),        # 1.287 in² | Table 7
    "K": ("3 inch",   "4 inch"),        # 1.838 in² | Table 8
    "L": ("4 inch",   "6 inch"),        # 2.853 in² | Table 9
    "M": ("4 inch",   "6 inch"),        # 3.600 in² | Table 10
    "N": ("4 inch",   "6 inch"),        # 4.340 in² | Table 11
    "P": ("6 inch",   "8 inch"),        # 6.380 in² | Table 12
    "Q": ("8 inch",   "10 inch"),       # 11.05 in² | Table 13
    "R": ("8 inch",   "10 inch"),       # 16.00 in² | Table 14
    "T": ("8 inch",   "10 inch"),       # 26.00 in² | Table 15：8T10
}

# ✅ 高压档孔口（API 526 Table 5：2G3，1500#/2500#）
API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE = {
    "G": ("2 inch", "3 inch"),
}

API526_ORIFICE_VARIANTS = {
    "Q": [("8 inch", "10 inch"), ("6 inch", "8 inch")],
    "R": [("8 inch", "10 inch"), ("6 inch", "10 inch")],
}

API526_FLANGE_TO_ORIFICES = {
    ("1 inch",   "2 inch"):     ["D"],
    ("1.5 inch", "2.5 inch"):   ["E", "F"],
    ("1.5 inch", "3 inch"):     ["G"],              # 标准档 G（150#–900#）
    ("2 inch",   "3 inch"):     ["H", "G"],         # H + G（高压档）
    ("3 inch",   "4 inch"):     ["J", "K"],
    ("4 inch",   "6 inch"):     ["L", "M", "N"],
    ("6 inch",   "8 inch"):     ["P", "Q"],
    ("6 inch",   "10 inch"):    ["R"],
    ("8 inch",   "10 inch"):    ["Q", "R", "T"],
}


def get_candidate_orifices(
    inlet_size: str,
    outlet_size: str,
    flange_class: str,
) -> list[str]:
    """根据入口/出口尺寸 + 法兰等级返回候选孔口。

    **引用常量** `API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE`，
    未来新增高压档配置时只需更新常量。
    """
    candidates = API526_FLANGE_TO_ORIFICES.get((inlet_size, outlet_size), [])
    if not candidates:
        return []

    filtered = []
    for orifice in candidates:
        hp_config = API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE.get(orifice)
        if hp_config == (inlet_size, outlet_size):
            if flange_class in ("1500#", "2500#"):
                filtered.append(orifice)
        else:
            filtered.append(orifice)
    return filtered


API526_MIN_INLET = "1 inch"
3.4 法兰等级-孔口约束矩阵
正确的表格分布（API STD 526 第五版）：

Tables 2–15：弹簧载荷式 PSV 各孔口（D~T）尺寸

Tables 16–29：先导式 PSV 各孔口尺寸

法兰等级-孔口约束分散在 Tables 2–15，需逐孔口核验。

python
# ⚠️ 待核验：API 526 Tables 2–15，逐孔口核验各压力等级
API526_FLANGE_CLASS_ORIFICE_LIMITS: dict[str, list[str] | None] = {
    "150#":  None,
    "300#":  None,
    "600#":  None,
    "900#":  None,
    "1500#": None,
    "2500#": None,
}


def validate_flange_orifice(
    flange_class: str,
    orifice: str,
    *,
    strict: bool = False,
) -> None:
    """法兰等级-孔口约束校验。

    **行为**：
    - 矩阵未填充（None）→ UserWarning 并放行（不阻断生产）
    - 矩阵已填充 → 正常校验
    - strict=True → 矩阵未填充时 raise NotImplementedError（测试用）
    """
    allowed = API526_FLANGE_CLASS_ORIFICE_LIMITS.get(flange_class)
    if allowed is None:
        if strict:
            raise NotImplementedError(
                f"法兰等级 {flange_class} 的孔口约束未填充（strict 模式）；"
                f"需按 API 526 Tables 2–15 逐孔口核验。"
            )
        warnings.warn(
            f"法兰等级 {flange_class} 的孔口约束未核验，跳过校验；"
            f"P5-3 实施前需按 API 526 Tables 2–15 填充。",
            UserWarning,
        )
        return
    if orifice not in allowed:
        raise PsvFlangeClassOrificeMismatchError(422,
            code="PSV_FLANGE_CLASS_ORIFICE_MISMATCH",
            message=f"法兰等级 {flange_class} 不适用于孔口 {orifice}")
3.5 阀型-参数约束矩阵
字段	SPRING_LOADED	BALANCED_BELLOWS	PILOT_OPERATED	RUPTURE_DISC
back_pressure_pct（built-up）	≤ 10	≤ 50	无硬限	N/A
back_pressure_pct（superimposed）	无硬限（CDTP + Kb 查表）	≤ 50	无硬限	N/A
manufacturer_consult	N/A	> 30% 须咨询	N/A	N/A
kb_factor	1.0（bp≤10%）/ 查表（bp>10%）	覆盖优先 + 保守优先	NULL	NULL
blowdown_fraction（GAS/VAPOR）	0.05~0.10	0.05~0.10	0.02~0.05	N/A
blowdown_fraction（LIQUID）	0.10~0.20	0.10~0.20	0.02~0.05	N/A
blowdown_fraction（TWO_PHASE）	0.10~0.15	0.10~0.15	N/A	N/A
inlet_size	必填，≥1"	必填，≥1"	可选	N/A
outlet_size	按 §3.3 孔口映射	按 §3.3 孔口映射	可选	N/A
bellows_material	N/A	必填	N/A	N/A
body_material 约束	弹簧材料耐蚀	见 §3.8	温度按 §3.6	N/A
介质限制	—	见 §3.8	禁脏污/粘稠/聚合/冻结/含固/易结晶	—
blowdown 范围引用说明：

API 520 / ASME 仅规定上限：气体/蒸汽 ≤10%，液体 ≤20%

下限为工程推荐值：气体/蒸汽 5%、液体 10%（避免 chatter 的保守下限）

TWO_PHASE：API 520 无明确规定，本 SPEC 保守取 10%~15%

3.6 先导式温度范围
python
PILOT_TEMP_RANGE = {
    "GENERAL":   (-54, 268),    # Sanmar Series 500（待来源清单核验）
    "HIGH_TEMP": (-162, 320),   # LESER Type 824（待来源清单核验）
    "CRYOGENIC": None,          # 待核验（OPEN-18）
}
3.7 Scenario-阀型兼容矩阵
泄放工况	SPRING_LOADED	BALANCED_BELLOWS	PILOT_OPERATED
FIRE	✅	✅	⚠️ 不推荐；如用需 API 521 专项评估
CLOSED_VALVE	✅	✅	✅
REACTION_RUNAWAY	✅	✅	⚠️ 响应特性需评估
THERMAL_EXPANSION	✅	✅	⚠️ 小流量精度不足
python
SCENARIO_VALVE_WARN = {
    ("FIRE", "PILOT_OPERATED"): (
        "先导式在火灾工况下**不推荐**使用。如确需使用，需按 API 521 "
        "先导式 PRV 火灾工况专项评估章节（具体章节号待核验，OPEN-19）"
        "进行专项评估；fire_protection=True 仅为**必要非充分**条件。"
    ),
    ("REACTION_RUNAWAY", "PILOT_OPERATED"): "先导式在反应失控工况下响应特性可能不足",
    ("THERMAL_EXPANSION", "PILOT_OPERATED"): "先导式在小流量工况下精度不足",
}
3.8 波纹管材料-介质兼容矩阵
python
BELLOWS_MATERIAL_COMPAT = {
    "HASTELLOY_C276": {
        "astm": ["ASTM B 575", "ASTM B 622"],
        "forbidden": [{
            "condition": "强氧化性介质（如热浓硝酸）",
            "source": "Haynes International C-276 材料手册 + API 571 §3.5.2",
        }],
        "note": "通用耐蚀合金，适用于大多数酸性介质",
    },
    "ALLOY_C22": {
        "astm": ["ASTM B 575", "ASTM B 622"],
        "forbidden": [{
            "condition": "强氧化性介质",
            "source": "Haynes International C-22 材料手册",
        }],
        "note": "耐蚀性优于 C276",
    },
    "SS316L": {
        "astm": ["ASTM A240", "ASTM A312"],
        "forbidden": [{
            "condition": "氯化物应力腐蚀开裂敏感环境",
            "source": "NACE MR0175 / ISO 15156 + 行业工程经验",
            "note": "NACE 对 316L 的氯化物限制非固定阈值；500 ppm 为工程保守参考值",
            "conservative_threshold_ppm": 500,
        }],
        "note": "经济型；高氯环境需按 NACE 评估",
    },
    "INCONEL_625": {
        "astm": ["ASTM B 443"],
        "forbidden": [{
            "condition": "高温高浓度氢氟酸（需专项评估）",
            "source": "Special Metals INCONEL 625 手册 + HF 环境腐蚀研究",
            "note": "HF 溶液中 Alloy 625 耐蚀性相对优异，非硬性禁忌",
        }],
        "note": "高温高强度；HF 环境耐蚀性优于 C276",
    },
    "INCONEL_718": {
        "astm": ["ASTM B 670"],
        "forbidden": [{
            "condition": "高温高硫环境",
            "source": "Special Metals INCONEL 718 手册",
        }],
        "note": "高强度高温合金",
    },
    "ALLOY_400": {
        "astm": ["ASTM B 127", "ASTM B 165"],
        "forbidden": [
            {"condition": "强氧化性介质", "source": "Special Metals MONEL 400 手册"},
            {
                "condition": "**湿 H₂S 环境**（含水分时）",
                "source": "Special Metals MONEL 400 手册 + API 571 §3.3",
                "note": "干燥硫和干燥 H₂S 环境可长期使用；湿 H₂S 敏感",
            },
        ],
        "note": "耐海水和氢氟酸；干燥含硫可用，湿 H₂S 需评估",
    },
}


def validate_bellows_compat(
    bellows_material: PsvBellowsMaterial,
    service_note: str | None,
) -> None:
    """波纹管材料-介质兼容性校验。"""
    items = BELLOWS_MATERIAL_COMPAT[bellows_material].get("forbidden", [])
    for item in items:
        if service_note and item["condition"] in service_note:
            raise PsvBellowsIncompatibleError(422,
                code="PSV_BELLOWS_INCOMPATIBLE",
                message=f"波纹管材料 {bellows_material} "
                        f"（{BELLOWS_MATERIAL_COMPAT[bellows_material]['astm']}）"
                        f" 禁用于：{item['condition']}"
                        f"（来源：{item['source']}）")
3.9 孔口-温度-分子量约束
API 520 规定：Q/R/T 孔口在 T > 177°C 且 MW < 10 时，未经业主工程师批准不得使用。

§4 API 契约扩展
4.1 PsvCalculateRequest 扩展
python
class PsvCalculateRequest(BaseModel):
    # ... 现有字段
    valve_type: PsvValveType = "SPRING_LOADED"
    body_material: PsvBodyMaterial = "SS316"
    bellows_material: PsvBellowsMaterial | None = None
    medium: PsvMedium
    inlet_size: str | None = None
    outlet_size: str | None = None
    flange_class: PsvFlangeClass = "300#"
    blowdown_fraction: float | None = None
    back_pressure_pct: float | None = None
    back_pressure_type: PsvBackPressureType = "BUILT_UP"
    overpressure_pct: float = 0.10
    orifice_override: PsvOrificeSize | None = None
    valve_brand: str | None = None    # 自由字符串；已知品牌见 _KB_DATA
    pilot_temperature_c: float | None = None
    pilot_temp_class: PsvPilotTempClass = "GENERAL"
    rupture_disc_position: PsvRuptureDiscPosition = "NONE"
    fire_protection: bool = False
    service_note: str | None = None
4.2 阀型-参数一致性校验
python
def validate_valve_params(req: PsvCalculateRequest) -> ValidatedParams:
    """按阀型 + 介质 + 背压类型 + 孔口字母校验参数一致性。"""

    # 阀型拦截
    if req.valve_type == "PILOT_OPERATED":
        raise PsvPilotOperatedNotSupportedError(422,
            code="PSV_PILOT_OPERATED_NOT_SUPPORTED")
    if req.valve_type == "RUPTURE_DISC":
        raise PsvRuptureDiscNotSupportedError(422,
            code="PSV_RUPTURE_DISC_NOT_SUPPORTED")

    # 背压规则
    bp = req.back_pressure_pct or 0.0
    bp_type = req.back_pressure_type
    kb_source = None

    if req.valve_type == "SPRING_LOADED":
        if bp_type == "BUILT_UP" and bp > 10.0:
            raise PsvBackPressureExceededError(422, code="PSV_BACK_PRESSURE_EXCEEDED")
        if bp_type == "SUPERIMPOSED" and bp > 0.0:
            cdtp_applied = True
            kb, kb_source = lookup_kb_with_priority(
                bp, req.overpressure_pct, req.valve_type,
                valve_brand=req.valve_brand,
            )
        else:
            cdtp_applied = False
            kb, kb_source = 1.0, "none"

    elif req.valve_type == "BALANCED_BELLOWS":
        if bp > 50.0:
            raise PsvBackPressureExceededError(422, code="PSV_BACK_PRESSURE_EXCEEDED")
        if bp > 30.0:
            warnings.warn(f"平衡波纹管式背压 {bp}% > 30%，须咨询厂商", UserWarning)
        if bp > 0.0:
            kb, kb_source = lookup_kb_with_priority(
                bp, req.overpressure_pct, req.valve_type,
                valve_brand=req.valve_brand,
            )
        else:
            kb, kb_source = 1.0, "none"

        if req.bellows_material is None:
            raise PsvBellowsMaterialRequiredError(422,
                code="PSV_BELLOWS_MATERIAL_REQUIRED")
        validate_bellows_compat(req.bellows_material, req.service_note)

    # blowdown 范围
    bd_range = BLOWDOWN_RANGE.get((req.valve_type, req.medium), (0.05, 0.10))
    bd = req.blowdown_fraction
    if bd is None or not (bd_range[0] <= bd <= bd_range[1]):
        raise PsvBlowdownOutOfRangeError(422, code="PSV_BLOWDOWN_OUT_OF_RANGE")

    # 入/出口尺寸校验（法兰等级感知）
    candidates = []
    if req.valve_type in ("SPRING_LOADED", "BALANCED_BELLOWS"):
        if req.inlet_size is None or req.outlet_size is None:
            raise PsvInletOutletRequiredError(422, code="PSV_INLET_OUTLET_REQUIRED")
        if _size_lt(req.inlet_size, API526_MIN_INLET):
            raise PsvInletTooSmallError(422, code="PSV_INLET_TOO_SMALL")

        candidates = get_candidate_orifices(
            req.inlet_size, req.outlet_size, req.flange_class
        )

        # 变体检查
        if not candidates:
            is_variant = any(
                (req.inlet_size, req.outlet_size) in variants
                for variants in API526_ORIFICE_VARIANTS.values()
            )
            if not is_variant:
                raise PsvInletOutletMismatchError(422,
                    code="PSV_INLET_OUTLET_MISMATCH")
            warnings.warn("厂商变体配置，需确认产品支持", UserWarning)

        # 仅对用户指定的 orifice_override 强制校验
        if req.orifice_override is not None:
            if candidates and req.orifice_override not in candidates:
                raise PsvInletOutletMismatchError(422,
                    code="PSV_INLET_OUTLET_MISMATCH",
                    message=f"孔口 {req.orifice_override} 与尺寸不匹配；候选：{candidates}")
            validate_flange_orifice(req.flange_class, req.orifice_override)

    # Scenario-阀型兼容警告
    warn_key = (req.relief_scenario, req.valve_type)
    if warn_key in SCENARIO_VALVE_WARN:
        warnings.warn(SCENARIO_VALVE_WARN[warn_key], UserWarning)

    # 爆破膜组合修正（ASME UG-127：Kc = 0.90）
    kc = {"UPSTREAM": 0.90, "DOWNSTREAM": 1.00}.get(req.rupture_disc_position)

    return ValidatedParams(
        kb_source=kb_source,
        candidates=candidates,
        valve_brand=req.valve_brand,
    )
4.3 Kb 查表（V1.14：覆盖优先 + 保守优先 + 品牌优先 + "none" 语义）
python
_KB_DATA: dict[str, dict] = {
    "manufacturer": {
        "LESER": {},
        "Consolidated": {},
        "Anderson_Greenwood": {},
    },
    "api520_fig30": {},
    "en4126": {},
}

_ALL_OVERPRESSURES = (0.10, 0.16, 0.21)


def lookup_kb_with_priority(
    back_pressure_pct: float,
    overpressure: float,
    valve_type: str,
    *,
    valve_brand: str | None = None,
) -> tuple[float, str]:
    """按四阶段策略查 Kb。

    **策略顺序**：

    1. **"none"**：弹簧载荷式 / 零背压 → `(1.0, "none")`
       （Kb=1.0 是 API 520 标准定义，非厂商数据）

    2. **品牌优先**：若指定 `valve_brand` 且该品牌有 overpressure 数据
       → 使用品牌数据，来源 `manufacturer:{brand}`
       - 若品牌不存在于 `_KB_DATA["manufacturer"]`
         → Warning + 回退策略 3
       - 若品牌存在但无该 overpressure 数据
         → Warning + 回退策略 3

    3. **覆盖优先（V1.14 P2-2 新增）**：若某厂商能完整覆盖
       `_ALL_OVERPRESSURES`（0.10/0.16/0.21）→ 使用该厂商数据
       - 目的是避免"同一阀门的 Kb 来自不同厂商"
       - 若多家厂商完整覆盖 → 取最小 Kb（保守）

    4. **保守优先**：若无厂商完整覆盖 → 按 overpressure 分别取所有
       厂商中的最小 Kb，来源标注 `mixed:{mfr1}+{mfr2}`

    5. **降级**：以上均无 → api520_fig30 → en4126
       - 均无 → raise NotImplementedError

    Returns:
        (kb_factor, source_name)
    """
    # 策略 1：标准定义
    if valve_type == "SPRING_LOADED":
        return 1.0, "none"
    if valve_type != "BALANCED_BELLOWS":
        return 1.0, "none"
    if back_pressure_pct <= 0.0:
        return 1.0, "none"

    mfr_data = _KB_DATA.get("manufacturer", {})

    # 策略 2：品牌优先
    if valve_brand:
        if valve_brand not in mfr_data:
            warnings.warn(
                f"阀体品牌 '{valve_brand}' 不存在于 Kb 数据库，"
                f"已回退到覆盖优先/保守优先策略。",
                UserWarning,
            )
        else:
            brand_table = mfr_data[valve_brand]
            if overpressure in brand_table and brand_table[overpressure]:
                kb = _interpolate_kb(brand_table[overpressure], back_pressure_pct)
                return kb, f"manufacturer:{valve_brand}"
            else:
                warnings.warn(
                    f"阀体品牌 '{valve_brand}' 无 overpressure={overpressure} "
                    f"的 Kb 数据，已回退。",
                    UserWarning,
                )

    # 策略 3：覆盖优先（单一厂商完整覆盖所有 overpressure）
    fully_covering: list[tuple[float, str]] = []
    for mfr, table in mfr_data.items():
        if all(
            op in table and table[op]
            for op in _ALL_OVERPRESSURES
        ):
            kb = _interpolate_kb(table[overpressure], back_pressure_pct)
            fully_covering.append((kb, f"manufacturer:{mfr}"))

    if fully_covering:
        # 多家完整覆盖 → 取最小 Kb（保守）
        min_kb, min_source = min(fully_covering, key=lambda x: x[0])
        return min_kb, min_source

    # 策略 4：保守优先（按 overpressure 分别取最小，可能混用）
    available: list[tuple[float, str]] = []
    for mfr, table in mfr_data.items():
        if overpressure in table and table[overpressure]:
            kb = _interpolate_kb(table[overpressure], back_pressure_pct)
            available.append((kb, mfr))

    if available:
        min_kb, min_mfr = min(available, key=lambda x: x[0])
        if len(available) > 1:
            # 混用场景：记录来源为 mixed
            all_mfrs = sorted({mfr for _, mfr in available})
            source = f"mixed:{'+'.join(all_mfrs)}"
            warnings.warn(
                f"无单一厂商完整覆盖所有 overpressure；"
                f"当前 overpressure={overpressure} 采用 {min_mfr} 数据。"
                f"完整覆盖建议纳入 P5+ backlog。",
                UserWarning,
            )
        else:
            source = f"manufacturer:{min_mfr}"
        return min_kb, source

    # 策略 5：降级
    api_table = _KB_DATA.get("api520_fig30", {})
    if overpressure in api_table and api_table[overpressure]:
        kb = _interpolate_kb(api_table[overpressure], back_pressure_pct)
        return kb, "api520_fig30"

    en_table = _KB_DATA.get("en4126", {})
    if overpressure in en_table and en_table[overpressure]:
        kb = _interpolate_kb(en_table[overpressure], back_pressure_pct)
        return kb, "en4126"

    raise NotImplementedError(
        f"Kb 数据未填入（overpressure={overpressure}）；"
        f"P5-3 实施前需完成厂商数据收集或 API 520 Fig.30 数字化。"
    )


def _interpolate_kb(points: list[tuple[float, float]], bp_pct: float) -> float:
    """逐点线性插值（无阈值阶跃）。"""
    if not points:
        raise ValueError("Kb 曲线数据点为空")
    if bp_pct <= points[0][0]:
        return points[0][1]
    if bp_pct >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= bp_pct <= x1:
            return y0 + (y1 - y0) * (bp_pct - x0) / (x1 - x0)
    return points[-1][1]
4.4 CDTP 修正
python
def apply_cdtp_correction(set_pressure: float, superimposed_bp: float) -> float:
    """CDTP = 设定压力 - 恒定叠加背压。"""
    return set_pressure - superimposed_bp
4.5 孔口选型
python
def select_orifice(area_m2: float, override: PsvOrificeSize | None,
                   T_C: float, MW: float) -> OrificeResult:
    result = ...  # 原逻辑
    validate_orifice_temperature(result.size, T_C, MW)
    return result
4.6 响应扩展
python
class PsvCalculateResponse(BaseModel):
    valve_type: PsvValveType
    body_material: PsvBodyMaterial
    bellows_material: PsvBellowsMaterial | None
    inlet_size: str | None
    outlet_size: str | None
    flange_class: PsvFlangeClass
    blowdown_fraction: float
    back_pressure_pct: float
    back_pressure_type: PsvBackPressureType
    overpressure_pct: float
    kb_factor: float | None
    kb_source: PsvKbSource | None
    valve_brand: str | None
    cdtp_applied: bool
    rupture_disc_kc: float | None
    orifice_result: OrificeResult
    warnings: list[str]
§5 前端交互
5.1 PsvComputePage 新增"安全阀选型"Collapse 分组
字段	弹簧式	平衡波纹管式	先导式
阀体型式	Radio（默认）	Radio	Radio（禁用提交 + 黄色提示）
阀体材料	Select	Select	Select
波纹管材料	—	Select（必填，6 选 1）	—
阀体品牌（V1.14 P2-4）	—	Select（可空：LESER / Consolidated / AG / 其他 / 未指定）	—
入口尺寸	Select（1"~8"）	Select（1"~8"）	禁用
出口尺寸	按 §3.3 孔口映射联动	同	禁用
法兰等级	Select（150#~2500#）	Select	禁用
法兰-孔口约束提示	矩阵未填充时黄色提示	同	—
blowdown	InputNumber（按介质动态）	同	禁用
背压类型	Radio（built-up / superimposed）	同	禁用
背压 %	InputNumber（动态范围）	InputNumber（0~50%）	禁用
超压 %	Select（10/16/21）	Select	禁用
Kb 显示	"1.0"	查表值 + 来源标注	"不适用"
CDTP 提示	superimposed 时显示	同	—
孔口手动选择	Select（可空）	Select（可空）	禁用
爆破膜位置	Select（NONE/UPSTREAM/DOWNSTREAM）	同	禁用
防火保护	Checkbox	Checkbox	Checkbox（FIRE 时必勾 + 专项评估提示）
5.2 联动规则
阀型 = 先导式/爆破膜式 → 提交禁用

阀型 = 平衡波纹管式 + 背压 >30% → 黄色提示"须咨询厂商"

选择阀体品牌（V1.14 P2-4）：

已选品牌 → Kb 按品牌优先

未选择 → 覆盖优先/保守优先

选择未知品牌 → 黄色提示"该品牌无 Kb 数据，将使用保守优先策略"

孔口选择 → 入/出口尺寸自动填充（按 §3.3 孔口字母映射）

入/出口尺寸修改 → 使用 get_candidate_orifices() 按法兰等级过滤；无对应则红框；变体组合 → 黄色提示

法兰等级变更 → 重新调用 get_candidate_orifices()；矩阵未填充 → 黄色提示（不阻断）

介质切换 → blowdown 范围动态更新

背压类型 = superimposed → 显示 CDTP 修正字段

Scenario + 阀型不推荐组合 → 黄色提示

FIRE + PILOT_OPERATED → 红色警告 + "需 API 521 专项评估"

平衡波纹管式 + 禁用介质 → 提示条警告

5.3 安装注意事项提示
平衡波纹管式：bonnet 排空口必须保持通畅；建议配置 bonnet 排空监测

入口管道压降：

可压缩流体（气体/蒸汽）：≤ 3% set pressure（增量压降，非总压降）；超过 3% 需力平衡评估（API 520 Part II）

不可压缩流体（液体）：按 API 520 Part II 单独评估

波纹管破裂失效：波纹管破裂后退化为常规式，若背压 >10% 则泄放能力不足

爆破膜组合（Kc = 0.90）：

仅适用于爆破膜在 PSV 上游且碎片不影响泄放的场景

需安装压力示警器（pressure tell-tale）

法兰等级-孔口组合：

T 孔口在 150#/300#/600# 下有标准配置（API 526 Table 15：8T10）

T 孔口在 150# 法兰下最大压力仅 65 psig（碳钢，-20°F~100°F）；如需更高压力，应选用 300#/600# 法兰。详见 OPEN-20

高温下法兰等级需按 ASME B16.5 温度-压力表降级

厂商变体：Q/R 孔口存在厂商变体；使用变体时需确认产品支持

§6 与 ADR-0028 的一致性
ADR-0028 决策	本增补对应
决策 8（先导式转 P5+）	§4.2 G7 拦截
决策 9（孔口表降级）	§4.5 手动 override 兼容
决策 10a（G1-G6）	本增补新增 G7-G23
决策 11（分层阈值）	选型字段不影响泄放量
新增错误码（G7-G23）
编号	规则	响应
G7	valve_type = PILOT_OPERATED	422 PSV_PILOT_OPERATED_NOT_SUPPORTED
G8	valve_type = RUPTURE_DISC	422 PSV_RUPTURE_DISC_NOT_SUPPORTED
G9	orifice_override < 计算面积	422 PSV_ORIFICE_OVERRIDE_TOO_SMALL
G10	背压超阀型范围	422 PSV_BACK_PRESSURE_EXCEEDED
G11	blowdown 超阀型+介质范围	422 PSV_BLOWDOWN_OUT_OF_RANGE
G12	入/出口尺寸不符合 API 526	422 PSV_INLET_OUTLET_MISMATCH
G13	平衡波纹管式材料-介质不兼容	422 PSV_MATERIAL_INCOMPATIBLE
G14	入口尺寸 < 1"	422 PSV_INLET_TOO_SMALL
G15	Q/R/T 孔口高温-低分子量	422 PSV_ORIFICE_TEMPERATURE_LIMIT
G16	平衡波纹管式失效模式	Warning
G17	平衡波纹管式波纹管材料未填	422 PSV_BELLOWS_MATERIAL_REQUIRED
G18	Scenario-阀型不推荐组合	Warning
G19	入口管道压降 >3%	Warning（前端提示）
G20	法兰等级与孔口不匹配	422 PSV_FLANGE_CLASS_ORIFICE_MISMATCH
G21	波纹管材料-介质不兼容	422 PSV_BELLOWS_INCOMPATIBLE
G22	入/出口尺寸为厂商变体	Warning
G23	法兰等级矩阵未填充	Warning（不阻断）
G24（V1.14 新增）	指定 valve_brand 无 Kb 数据	Warning + 回退保守优先
G25（V1.14 新增）	无单一厂商完整覆盖 overpressure	Warning + 保守优先（可能混用）
§7 数据迁移与兼容
7.1 迁移策略（两阶段）
Task 24b 扩展（P5-0）：

加 21 列（V1.14 含 valve_brand，可空）

存量默认值：

valve_type='SPRING_LOADED'

body_material='SS316'

bellows_material=NULL

inlet_size='4 inch' / outlet_size='6 inch'

flange_class='300#'

blowdown_fraction=0.10

back_pressure_pct=0.0 / back_pressure_type='BUILT_UP'

overpressure_pct=0.10

kb_factor=1.0 / kb_source=NULL

valve_brand=NULL

cdtp_applied=FALSE

orifice_overridden=FALSE / orifice_manual=NULL

pilot_temperature_c=NULL / pilot_temp_class='GENERAL'

rupture_disc_kc=NULL / rupture_disc_position='NONE'

fire_protection=FALSE

Task 18 强化（P5-3）：

9 个字段强制 NOT NULL

存量回填（若无记录则跳过）

7.2 向后兼容
前端新字段有默认值，老请求可用

后端契约新字段可选

record_hash 含新字段

§8 验收标准
维度	标准
后端	21 新字段；G7-G17+G20-G21 拦截 + G18/G19/G22/G23/G24/G25 警告；Kb 四阶段策略；CDTP；Kc；波纹管材料校验；法兰等级-孔口校验
前端	阀型联动；阀体品牌控件；孔口-法兰双向联动；scenario 警告；压力示警器；T 孔口 150# 压力提示
测试	后端 +90 例（含 G7-G25 + 介质分支 + 背压类型分支 + 孔口映射 + 变体 + 法兰等级 + 波纹管材料 + Kb 四阶段策略 + "none" 语义 + 品牌优先 + 混用场景 + H/G 双候选）；前端 +40 例；E2E +12 例
精度	选型字段不影响泄放量
兼容	老请求可用；record_hash 含新字段
数据前置 gate（P5-3 启动前必须完成）
#	检查项	责任人	截止	阻断级别	产出物
1	API 526 Tables 2–15 逐项核验	工艺工程师	P5-3 启动前	硬性	psv-orifice-table-verification.md
2	API 526 Table 5（G 孔口双档）核验	工艺工程师	P5-3 启动前	硬性	同上
3	API 526 Table 15（T 孔口 150# 配置）核验	工艺工程师	P5-3 启动前	硬性	同上 + 65 psig 记录
4	API526_FLANGE_CLASS_ORIFICE_LIMITS 填充	工艺工程师	P5-3 启动前	硬性	CSV/Markdown 表格，84 组合，≥20% 抽样核验；psv-flange-matrix-verification.md
5	数据来源清单审计	工艺工程师 + 独立评审员	P5-3 启动前	硬性	psv-data-source-audit.md
6	二手来源对比 API 原文	工艺工程师	P5-3 启动前	硬性	对比记录（含图片/PDF）
7	Kb 曲线数字化（厂商优先）	工艺工程师	P5-3 启动前 2 周	硬性	厂商数据表（LESER/Consolidated/AG）
8	与 2 家厂商数据表交叉验证	工艺工程师	P5-3 启动前 1 周	硬性	交叉验证报告
9	_KB_DATA 三层源 + 厂商子键填入	开发工程师	P5-3 启动前	硬性	代码 + 测试
10	Kb 四阶段策略测试（6 场景）	测试工程师	P5-3 启动前	硬性	测试报告（见下）
11	H/G 双候选场景测试	测试工程师	P5-3 启动前	硬性	测试报告
12	T 孔口 150# 65 psig 警告测试	测试工程师	P5-3 启动前	硬性	测试报告
13	CRYOGENIC 具体型号确认（OPEN-18）	工艺工程师	P5-3 启动前	硬性	厂商数据表
14	API 521 FIRE+PILOT 章节号确认（OPEN-19）	工艺工程师	P5-3 启动前	硬性	章节号确认记录
Gate 第 10 项关键测试场景（V1.14 P2-3 细化）：

#	场景	期望结果
1	弹簧式 + 任意 bp	(1.0, "none")
2	平衡波纹管 + bp=0	(1.0, "none")
3	平衡波纹管 + bp=20 + 三家厂商数据	最小 Kb（保守优先）
4	平衡波纹管 + bp=20 + valve_brand="LESER" + LESER 有数据	LESER 的 Kb
5	平衡波纹管 + bp=20 + valve_brand="UnknownBrand"	Warning + 保守优先
6	平衡波纹管 + bp=20 + 无厂商数据 + API 520 有数据	api520_fig30
7	平衡波纹管 + bp=20 + 某厂商完整覆盖 0.10/0.16/0.21	该厂商数据（覆盖优先）
8	平衡波纹管 + bp=20 + 无完整覆盖，多家部分覆盖	mixed:{mfr1}+{mfr2}
§9 OPEN 项
编号	内容	决议方	状态
OPEN-01	阀体材料默认值（建议 SS316）	工艺室	待裁
OPEN-02	入口/出口尺寸枚举范围（1"~8"；10"/12" P6+）	工艺室	待裁
OPEN-03	孔口手动 override 是否本批纳入（建议纳入）	工艺室	待裁
OPEN-04	孔口 override 后是否写入 lineage（建议必须）	架构	待裁
OPEN-06	平衡波纹管禁用介质前端硬校验？	工艺室	待裁
OPEN-09	先导式介质限制是否前端硬校验	工艺室	待裁
OPEN-10	爆破膜 Kc 默认值（建议固定 0.90）	工艺室	待裁
OPEN-12	先导式型号是否 P5 预埋全部	架构	待裁
OPEN-13	Q/R 孔口变体是否纳入 P5 支持	工艺室	待裁
OPEN-14	新增波纹管材料是否 P5 支持	工艺室	待裁
~~OPEN-15~~	~~G 孔口 150# 适用性~~	—	✅ 关闭
OPEN-16	API 526 Tables 2–15 核验	工艺室	P5-3 启动前硬性 gate
OPEN-17	Q 变体（6"×8"）来源确认	工艺室	P5-3 启动前
OPEN-18	CRYOGENIC 具体型号确认	工艺室	P5-3 启动前
OPEN-19	API 521 FIRE+PILOT 章节号确认	工艺室	P5-3 启动前
OPEN-20	T 孔口 150# 压力额定值确认（65 psig）	工艺室	P5-3 启动前
OPEN-21	Kb 覆盖优先 + 保守优先 + 品牌优先策略的最终确认	工艺室 + 架构	P5-3 启动前
OPEN-22	V1.14 新增：品牌列表扩展流程（新增 Farris/Crosby 等时的同步更新机制）	架构	P5+
§10 Backlog
先导式阀计算（GB/T 28778-2023）——ADR-0028 决策 8 已裁 P5+

爆破膜式计算（API 520 Part II）——P6+

阀体厂商型号匹配——P6+

法兰标准反查表——P6+

阀型-孔口系列联动推荐——P6+

bonnet 排空监测硬件接口——P6+

入口管道压降自动校验（需管道数据）——P6+

API 526 Tables 2–15 完整数字化——P5-3 启动前必关

Kb 曲线数字化 + 厂商交叉验证——P5-3 启动前必关

厂商变体库（Q/R + 其他）——P6+

压力示警器（pressure tell-tale）集成——P6+

低温先导式型号库——P6+

新增厂商 Kb 数据库扩展机制——P6+

完整覆盖所有 overpressure 的单一厂商数据优先实现——P5+ backlog

§11 与现有 Task 的关系
Task	本增补的影响
Task 17（API 526 选型）	增加 override + Kb（四阶段策略）+ 孔口字母映射 + 变体 + 最小入口 + Q/R/T 校验 + 法兰等级校验
Task 18（PSV API + persist）	增加 21 字段 + G7-G25 拦截/警告 + 前端接通
Task 24b（PSV 标准配置）	不受影响
本增补不新增 Task——扩展现有 Task 17/18 的 scope。

§12 修订记录
完整修订历史
版本	日期	G 孔口	主要修订
V1.0-V1.3	2026-09-17	1.5"×3"	框架建立
V1.4-V1.6	2026-09-17	1.5"×3"	Kb 阀型区分、波纹管材料、力平衡评估
V1.7	2026-09-17	1.5"×2.5"	❌ G 孔口误改
V1.8	2026-09-17	1.5"×3"	❌ 错误"恢复"
V1.9	2026-09-17	1.5"×2.5"	❌ 面积推断错误；引入 §0 方法论
V1.10	2026-09-17	1.5"×2.5"	❌ 引用 Vajra 转录（与原文不符）
V1.11	2026-09-17	1.5"×3"	✅ 基于 API 526 Table 5 原文修正
V1.12	2026-09-17	1.5"×3"	✅ 逐项标注 Table 号；H/G 双候选；Kb 厂商子键
V1.13	2026-09-17	1.5"×3"	✅ Kb 来源语义（"none"）；保守优先；T 孔口 65 psig
V1.14	2026-09-17	1.5"×3"（标准）/ 2"×3"（高压）	✅ 覆盖优先 + 保守优先 + 品牌优先；valve_brand UI；P2 问题全关闭
V1.13 → V1.14（第十二次评审后修订）
#	V1.13 问题	级别	V1.14 修订
1	valve_brand 值域未定义	P2	§4.1 保持自由字符串；§4.3 增加"品牌不存在"Warning（G24）
2	保守优先的"厂商混用"风险	P2	§4.3 新增"覆盖优先"策略（G25）；无完整覆盖时才允许混用并标注 mixed:{mfr1}+{mfr2}
3	§8 gate 第 10 项测试用例未细化	P2	§8 列出 8 项关键测试场景
4	§5.2 联动规则未包含 valve_brand	P2	§5.1 新增"阀体品牌"控件；§5.2 新增联动规则
方法论总结（永久条款）
本 SPEC 的核心方法论价值：

§-1 前置声明：诚实记录 G 孔口六次反复的完整轨迹，明确"V1.11 起以 API STD 526 Table 5 原文为最终权威依据"

§0 数据来源强制要求：所有数值必须可追溯到标准原文；二手来源必须与 API 正版原文对比

§0.2 来源清单审计 gate：独立评审员抽样核验（≥30%）

§8 数据前置 gate：14 项硬性 gate，覆盖 API 原文核验、来源审计、Kb 数字化、测试场景

Kb 四阶段策略：标准定义 → 品牌优先 → 覆盖优先 → 保守优先 → 降级

关键教训：

"面积相近"不是法兰尺寸的判据

二手转录不能替代 API 原文

Kb=1.0 是标准定义，不是厂商数据

多源数据存在差异时，默认取最保守值

单一阀门的 Kb 应尽量来自同一厂商（覆盖优先）

supersedes：SUP-P5-PSV-002 V1.0 至 V1.13
related：SUP-P5-PSV-001（PSV 多标准引擎）、ADR-0028（决策 8 / 决策 9）
附件：

docs/adr/signatures/api526-tables-2-15-source.pdf（API STD 526 第五版 Tables 2–15 原文）

docs/adr/signatures/kb-manufacturer-data/（厂商 Kb 数据表）

docs/adr/signatures/0028-psv-select-acceptance.md（评审裁决）

docs/adr/signatures/psv-data-source-audit.md（数据来源清单审计）

docs/adr/signatures/psv-flange-matrix-verification.md（法兰矩阵核验）

ADR 评审委员会裁决：SUP-P5-PSV-002 V1.13
评审机构：P5 架构评审委员会
评审对象：docs/spec/SUP-P5-PSV-002.md（V1.13，第十二次专家评审后）
评审日期：2026-09-17
评审轮次：第十二次

一、裁决结论
批准。 V1.13 通过评审，状态由 proposed 转为 accepted，生效日期 2026-09-17。

本 SPEC 可作为 P5-3 批（Task 17 / Task 18 扩展）实施的架构依据。4 项 P2 级问题作为 V1.14 补丁在本裁决生效后 1 周内关闭，不阻塞 P5-3 准备。

二、裁决依据
2.1 十二轮评审轨迹
轮次	核心问题	状态
第 1-3 轮	框架建立（阀型分化、错误码、数据模型）	✅
第 4-6 轮	Kb 阀型区分、波纹管材料、力平衡评估、Kb 示意值删除	✅
第 7-8 轮	引入 §0 方法论、Kb 多源结构、法兰矩阵 Warning	✅
第 9-10 轮	G 孔口争议终结（API STD 526 Table 5 原文确认）	✅
第 11 轮	逐项标注 Table 号、T 孔口 150# 配置修正、H/G 双候选	✅
第 12 轮	Kb 来源语义（"none"）、常量引用、保守优先、65 psig 警告	✅
2.2 内容成熟度核验
维度	核验
G 孔口配置	✅ API STD 526 Table 5 原文（1½G3 + 2G3 双档）
孔口表号引用	✅ 逐项标注 D→Table 2 ~ T→Table 15
T 孔口 150# 配置	✅ API 526 Table 15（8T10，65 psig）
Kb 来源语义	✅ "none" / "manufacturer:{品牌}" / api520_fig30 / en4126
Kb 优先级策略	✅ 保守优先（取最小 Kb）+ 品牌优先（valve_brand）
反向映射校验	✅ 法兰等级感知（get_candidate_orifices）
方法论条款	✅ §0 来源审计 + 二手来源对比原文
三、对 4 项 P2 级问题的裁决
P2-1：valve_brand 值域
裁决：采用方案二（自由字符串 + 后端 Warning），不引入枚举。

理由：

品牌列表（LESER / Consolidated / AG / Farris / Crosby / ...）后续会扩展，枚举硬编码会带来维护负担

后端 Warning 已足够用户可读

V1.14 补丁内容：

python
if valve_brand and valve_brand not in mfr_data:
    warnings.warn(
        f"阀体品牌 '{valve_brand}' 无 Kb 数据，已回退保守优先策略",
        UserWarning,
    )
P2-2：保守优先的"厂商混用"风险
裁决：明确为"覆盖优先 + 保守次优"两阶段策略。

理由：单一阀门的 Kb 应尽量来自同一厂商数据源；仅在无单一厂商完整覆盖时，才允许混用并显式标注。

V1.14 补丁内容：

python
# 策略 1：优先使用能完整覆盖所有 overpressure 的厂商（单一源）
# 策略 2：若无完整覆盖，按 overpressure 分别取最小 Kb，
#         并在 kb_source 中标注 "mixed:LESER+Consolidated"
# 策略 3：降级到 api520_fig30 / en4126
P2-3：测试用例清单
裁决：采纳专家列出的 6 项测试场景，纳入 §8 gate 第 10 项。

V1.14 补丁内容：

弹簧式 + 任意 bp → (1.0, "none")

平衡波纹管 + bp=0 → (1.0, "none")

平衡波纹管 + bp=20 + 三家厂商数据 → 最小 Kb

平衡波纹管 + bp=20 + valve_brand="LESER" + LESER 有数据 → LESER 的 Kb

平衡波纹管 + bp=20 + valve_brand="UnknownBrand" → Warning + 保守优先

平衡波纹管 + bp=20 + 无厂商数据 + API 520 有数据 → api520_fig30

P2-4：valve_brand UI 控件
裁决：在 §5.1 字段表中新增，§5.2 联动规则补充。

V1.14 补丁内容：

§5.1 平衡波纹管式新增"阀体品牌"Select（可空；LESER / Consolidated / AG / 其他）

§5.2 新增"选择阀体品牌 → Kb 按品牌优先；未选择 → 保守优先"

四、随裁决生效的强制要求
4.1 P5-3 启动前的数据前置 gate（14 项全部为硬性 gate）
#	检查项	阻断级别
1-3	API 526 Tables 2–15 / Table 5 / Table 15 逐项核验	硬性
4	API526_FLANGE_CLASS_ORIFICE_LIMITS 填充（84 组合）	硬性
5-6	来源清单审计 + 二手来源对比 API 原文	硬性
7-10	Kb 曲线数字化 + 交叉验证 + 保守优先测试	硬性（关键路径，提前 2 周启动）
11-12	H/G 双候选 + T 孔口 65 psig 警告测试	硬性
13-14	OPEN-18（CRYOGENIC 型号）/ OPEN-19（API 521 章节号）	硬性
核验归档路径：

docs/adr/signatures/psv-orifice-table-verification.md

docs/adr/signatures/psv-flange-matrix-verification.md

docs/adr/signatures/psv-data-source-audit.md

docs/adr/signatures/api526-tables-2-15-source.pdf

4.2 P5-3 实施约束
Task 17 / Task 18 的 scope 扩展 按本 SPEC §11 执行

新增 20 字段 + G7-G23 错误码

不改动泄放量计算（ADR-0028 决策 11 分层阈值不受影响）

record_hash 含新字段

4.3 V1.14 补丁时限
V1.14 补丁（4 项 P2 问题）应在 2026-09-24 前关闭并归档至：

text
docs/spec/SUP-P5-PSV-002-V1.14.md
docs/spec/SUP-P5-PSV-002-V1.14-changelog.md
五、评审签署
角色	签署	日期
评审委员会主席	✅ 批准	2026-09-17
安全阀专家（十二轮评审）	✅ 批准	2026-09-17
工艺室代表	✅ 批准（决策 11 分层阈值联签已归档）	2026-09-17
标准负责人	✅ 批准（API 526 原文核验已确认）	2026-09-17
架构负责人	✅ 批准（V1.14 补丁时限已承诺）	2026-09-17
秘书处归档：

本裁决 → docs/adr/signatures/0028-psv-select-acceptance.md

SPEC 头部更新 status: accepted

六、后续行动清单
#	行动	负责人	截止
A-01	SPEC 头部 status: proposed → accepted	秘书处	2026-09-17
A-02	V1.14 补丁（4 项 P2）起草	SPEC 作者	2026-09-24
A-03	P5-3 数据前置 gate 启动（14 项）	工艺工程师	2026-09-17
A-04	Kb 曲线数字化（关键路径，提前 2 周）	工艺工程师	2026-09-24
A-05	OPEN-18 / OPEN-19 关闭	工艺工程师	2026-09-30
A-06	Task 17 / Task 18 scope 扩展更新	计划负责人	P5-3 启动前
A-07	P5-3 启动决策	项目负责人	P5-3 启动前
七、评审委员会总结
SUP-P5-PSV-002 历经十二轮专家评审、六次 G 孔口反复修正，最终基于 API STD 526 第五版原文完成技术核验，是 SPEC 编写方法论成熟的标志性案例。

本 SPEC 的核心贡献：

技术数据经标准原文核验——G 孔口 1½G3 / 2G3 双档配置、T 孔口 150# 65 psig、孔口表号逐项标注

Kb 多源优先级策略——保守优先 + 品牌优先，兼顾安全性与工程实际

方法论永久条款（§0）——来源清单审计 + 二手来源对比原文，防止同类错误复发

完整错误码体系（G7-G23）——覆盖阀型拦截、参数校验、变体警告、法兰约束

数据前置 gate（14 项）——P5-3 启动前的硬性门槛

裁决：批准，V1.13 生效为 P5-3 实施基线。

P5-3 批可正式启动准备。

评审委员会主席（签署）
2026-09-17
