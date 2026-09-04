PCS-DICT-007 增补文件十四
文件标识	PCS-DICT-007-SUP-014
当前版本	V1.14
发布日期	2026-08-29
增补基准	PCS-DICT-007 V3.0 + SUP-012/013
新增参考	PPG张家港涂料设施成本估算JSON（AACE Class 4，蒙特卡洛模拟10000次迭代）
1. 增补说明
1.1 新增素材价值
本素材填补了cost_est_results的最后一个高优先级缺口，且格式已经是结构化JSON，可直接作为字典模板：

维度	已有（平铺字段）	本增补新增
cost_est_results	estimated_cost/currency/cost_index_year 3个平铺字段	✅ 完整成本估算JSON结构（7大模块）
成本分解	❌	✅ A直接成本（10专业×4成本要素）/B间接成本/C税费/D业主成本
风险因子	❌	✅ 45个三角分布因子（min/mode/max）
蒙特卡洛	❌	✅ 10000次迭代统计+P10~P95百分位
应急费建议	❌	✅ 激进/推荐/保守三方案
验证检查	❌	✅ 自检逻辑
2. 成本估算完整JSON结构（cost_estimate_json）
2.1 顶层结构
json
{
  "metadata": {},                 // 元数据
  "cost_summary": {},             // 成本汇总
  "cost_categories": {},          // 成本分类（A/B/C/D）
  "risk_factors": [],             // 风险因子（45个三角分布）
  "monte_carlo_results": {},      // 蒙特卡洛模拟结果
  "contingency_recommendation": {},// 应急费建议
  "validation_checks": {}         // 验证检查
}
2.2 metadata（元数据）
字段名	类型	必填	说明
project	string	✅	项目名称
version	string	✅	估算版本号
currency	string	✅	币种（RMB/USD/EUR）
exchange_rate_usd	float	❌	美元汇率
aace_class	int	✅	AACE等级（1~5，Class 4=±30%）
data_sources	object	✅	数据来源说明
sheets	array	✅	工作簿页签列表
data_sources子结构：

json
{
  "A_direct_cost": "summary.xls",
  "A3_piping_detail": "pipe.xls (1699 rows, 11 areas)",
  "B_C_D": "summary.xls Summary cost",
  "risk_factors": "Worley PMF-312 + engineering practice"
}
2.3 cost_summary（成本汇总）
字段名	类型	必填	说明
A_direct_cost_total	float	✅	直接成本合计
B_indirect_cost_total	float	✅	间接成本合计
C_tax_total	float	✅	税费合计
D_owner_cost_total	float	✅	业主成本合计
grand_total_before_contingency	float	✅	应急费前总计（A+B+C+D）
2.4 cost_categories（成本分类）
2.4.1 A类：直接成本（DIRECT COST）
json
{
  "A": {
    "name": "DIRECT COST",
    "items": [
      {
        "id": "A1",
        "name": "General Plat plan",
        "amount": 7715349.95,
        "elements": {
          "MAIN_MATL": {"ratio": 0.5796, "amount": 4471543.74},
          "LABOR": {"ratio": 0.1040, "amount": 802048.78},
          "CONSU_MATL": {"ratio": 0.2158, "amount": 1665120.54},
          "CONST_EQUIP": {"ratio": 0.1007, "amount": 776636.89}
        },
        "risk_mapping": {
          "MAIN_MATL": ["mat_site", "qty_site", "freight"],
          "LABOR": ["labor_rate", "labor_prod", "dur_site"],
          "CONSU_MATL": ["consu_rate", "qty_site"],
          "CONST_EQUIP": ["equip_rate", "dur_site"]
        }
      }
    ]
  }
}
10个A类专业：

ID	名称	说明
A1	General Plat plan	总图（场地/道路/围墙）
A2	Equipment	设备（容器/泵/压缩机）
A3	Piping	管道（材料/安装）
A4	Architecture	建筑
A5	Structure	结构（混凝土/钢结构）
A6	Electrical	电气
A7	Instrument	仪表（DCS/现场仪表/安装材料）
A8	Fire fighting and plumbing	消防给排水
A9	Telecom	通讯
A10	HVAC	暖通
4个成本要素：

要素	中文	说明
MAIN_MATL	主材	设备/材料费
LABOR	人工	安装人工费
CONSU_MATL	辅材	消耗材料
CONST_EQUIP	施工机械	施工机具费
risk_mapping：将成本要素映射到风险因子ID（用于蒙特卡洛模拟）。

2.4.2 B类：间接成本（INDIRECT COST）
json
{
  "B": {
    "name": "INDIRECT COST",
    "groups": [
      {
        "id": "B-1",
        "group": "epcm",
        "risk_factor": "rate_epcm",
        "items": [
          {"code": "B11", "description": "EPCM", "amount": 21771428}
        ],
        "subtotal": 21771428
      }
    ],
    "total": 43408095.00
  }
}
5个B类组：

组ID	组名	风险因子	内容
B-1	epcm	rate_epcm	EPCM管理费
B-2	eng_design	rate_eng_design	设计费/详细设计
B-3	supervision	rate_supervision	第三方审查/监理/设备检验
B-4	insurance	rate_insurance	保险费
B-5	commission	rate_commission	临设/竣工图/调试支持
2.4.3 C类：税费（OTHERS/TAX）
json
{
  "C": {
    "name": "OTHERS (TAX)",
    "deterministic": true,
    "items": [
      {"code": "C3", "description": "Business tax", "amount": 653742.95},
      {"code": "C4", "description": "Corporate Income Tax", "amount": 43794.81},
      {"code": "C5", "description": "Stamp tax", "amount": 276093.14}
    ],
    "total": 973630.90
  }
}
特点：deterministic=true——税费不参与蒙特卡洛模拟（确定性值）。

2.4.4 D类：业主成本（OWNER'S COST）
json
{
  "D": {
    "name": "OWNER'S COST",
    "groups": [
      {
        "id": "D-1",
        "group": "permits",
        "risk_factor": "rate_owner_permits",
        "items": [
          {"code": "D1", "description": "Land & Company Set-up", "amount": 6380000},
          {"code": "D3", "description": "Project Application Package", "amount": 100000}
        ],
        "subtotal": 7336000
      }
    ],
    "total": 12201500
  }
}
3个D类组：

组ID	组名	风险因子	内容
D-1	permits	rate_owner_permits	土地/报批/许可/安保
D-2	purchase	rate_owner_purchase	业主采购（实验室设备）
D-3	connect	rate_owner_connect	接驳费（水/电/气/污）
2.5 risk_factors（风险因子，45个三角分布）
json
[
  {
    "id": "RF01",
    "name": "qty_site",
    "min": 0.9,
    "mode": 1.0,
    "max": 1.3,
    "description": "土方/场地工程量"
  }
]
字段定义：

字段名	类型	必填	说明
id	string	✅	因子编号（RF01~RF45）
name	string	✅	因子标识（qty_/mat_/labor_/dur_/consu_/contr_/equip_/freight/rate_/indirect_）
min	float	✅	最小值（三角分布下限）
mode	float	✅	最可能值（均为1.0）
max	float	✅	最大值（三角分布上限）
description	string	✅	因子描述
45个风险因子分类：

类别	数量	因子前缀
工程量因子	10个	qty_*（site/equipment/piping/arch/structure/elec/instrument/fire/telecom/hvac）
材料单价因子	10个	mat_*（同上）
人工因子	2个	labor_rate/labor_prod
工期因子	10个	dur_*（同上）
辅助费率因子	5个	consu_rate/contr_distrib/equip_rate/freight
间接费率因子	6个	rate_epcm/rate_eng_design/rate_supervision/rate_insurance/rate_commission
业主费率因子	3个	rate_owner_permits/rate_owner_purchase/rate_owner_connect
间接工期因子	1个	indirect_dur
2.6 monte_carlo_results（蒙特卡洛模拟结果）
json
{
  "iterations": 10000,
  "seed": 42,
  "base_total": 315483821.20,
  "statistics": {
    "mean": 601601234.72,
    "stddev": 29512357.40,
    "cv": 0.049,
    "min": 530278458.93,
    "max": 717878372.49
  },
  "percentiles": {
    "P10": {"total_rmb": 566198294.57, "total_usd": 75352448.04, "deviation_pct": 0.060, "contingency_rmb": 250714473.37, "contingency_pct": 79.46},
    "P50": {"total_rmb": 598248092.21, "total_usd": 79617792.42, "deviation_pct": 0.120, "contingency_rmb": 282764271.01, "contingency_pct": 89.61},
    "P80": {"total_rmb": 626988789.21, "total_usd": 83442745.44, "deviation_pct": 0.173, "contingency_rmb": 311504968.01, "contingency_pct": 98.72},
    "P85": {"total_rmb": 634256789.84, "total_usd": 84410006.63, "deviation_pct": 0.187, "contingency_rmb": 318772968.64, "contingency_pct": 101.02},
    "P90": {"total_rmb": 642834197.37, "total_usd": 85551530.13, "deviation_pct": 0.203, "contingency_rmb": 327350376.17, "contingency_pct": 103.73},
    "P95": {"total_rmb": 655010779.68, "total_usd": 87172049.47, "deviation_pct": 0.226, "contingency_rmb": 339526958.48, "contingency_pct": 107.62}
  }
}
statistics字段定义：

字段名	说明
mean	均值
stddev	标准差
cv	变异系数（stddev/mean）
min	最小值
max	最大值
percentiles子结构：

字段名	说明
total_rmb	百分位对应总成本（本币）
total_usd	百分位对应总成本（美元）
deviation_pct	偏差百分比（相对base_total）
contingency_rmb	应急费金额（total - base）
contingency_pct	应急费百分比
2.7 contingency_recommendation（应急费建议）
json
{
  "base_estimate": 315483821.20,
  "options": [
    {
      "scenario": "激进",
      "confidence": "P80",
      "total_rmb": 626988789.21,
      "total_usd": 83442745.44,
      "contingency_rmb": 311504968.01,
      "contingency_usd": 41456474.59,
      "ratio": 0.9872
    },
    {
      "scenario": "推荐",
      "confidence": "P85",
      "total_rmb": 634256789.84,
      "total_usd": 84410006.63,
      "contingency_rmb": 318772968.64,
      "contingency_usd": 42427800.83,
      "ratio": 1.0102
    },
    {
      "scenario": "保守",
      "confidence": "P90",
      "total_rmb": 642834197.37,
      "total_usd": 85551530.13,
      "contingency_rmb": 327350376.17,
      "contingency_usd": 43565367.63,
      "ratio": 1.0373
    }
  ]
}
三方案定义：

方案	置信度	说明
激进	P80	接受较高的超支风险（20%概率超出）
推荐	P85	平衡方案（15%概率超出）
保守	P90	严格控制超支风险（10%概率超出）
2.8 validation_checks（验证检查）
json
{
  "MC_P85 > MC_P50": true,
  "MC_P90 > MC_P85": true,
  "Risk_Factors_Mode_equals_1_count": 45
}
验证规则：

P85 > P50（单调性检查）

P90 > P85（单调性检查）

所有风险因子mode=1.0（基准校验）

3. 与cost_est_results平铺字段的映射
cost_est_results字段	cost_estimate_json字段
estimated_cost	cost_summary.grand_total_before_contingency
currency	metadata.currency
cost_index_year	从metadata.data_sources推导（或单独存）
equipment_id	关联设备（单台设备估算时使用）
4. 与EQUIP_LIB成本字段的关系
equipment_lib字段	cost_estimate_json
cost	单台设备成本（从A2-Equipment的raw_sheets中提取）
cost_currency	metadata.currency
cost_year	从metadata推导
5. 版本历史
版本	日期	修改内容
V1.0~V1.11	2026-08-29	初始+10次增补
V2.0	2026-08-29	完整整合版
V3.0	2026-08-29	V2.0+SUP-001~011完整合并
V1.12	2026-08-29	增补冷却塔（SUP-012）
V1.13	2026-08-29	增补限流孔板+文丘里洗涤器（SUP-013）
V1.14	2026-08-29	增补成本估算JSON（SUP-014），填补cost_est_results缺口
增补完成。 PCS-DICT-007 SUP-014填补了最后一个高优先级缺口：

结构	内容
cost_estimate_json	7大模块完整成本估算结构（元数据/汇总/四类成本/45风险因子/蒙特卡洛/应急费建议/验证）
4个成本要素	MAIN_MATL/LABOR/CONSU_MATL/CONST_EQUIP
10个A类专业	A1~A10
5个B类组	EPCM/设计/监理/保险/调试
45个风险因子	三角分布min/mode/max
7个百分位	P10/P20/P50/P80/P85/P90/P95
3个应急费方案	激进P80/推荐P85/保守P90
缺口状态最终更新：
