P5 设备计算模块（第二批）开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P5
当前版本	V1.3
发布日期	2026-08-27（V1.2 修订 2026-08-29；V1.3 修订 2026-09-03，incorporate SUP-008 V1.1 + SUP-009 V1.0 + SUP-010 V1.1：relief_results/column_sizing/two_phase_results/mixer_results/heat_results/steam_drum_results 等 6 张结果表扩展 + 39+ 字段扩展 + 双阶段设计 design_stage 字段下沉至 P5）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2 §3.2.5/§3.2.6/§3.2.7、SUP-003 §3.2.28、SUP-007、SUP-008 V1.1、SUP-009 V1.0、SUP-010 V1.1、换热器规格书数据字典、空冷器规格书数据字典、SPEC-P0/P1/P2/P3/P4
第一部分：引言
1.1 目的
本文档定义P5阶段（设备计算模块第二批）的完整需求规格，明确VESSEL容器计算、SEP_EQUIP气固/气液分离设备、PSV安全阀计算和HEAT换热器计算四个模块的详细功能需求、算法规格和验收标准。

1.2 文档范围
包含：

VESSEL：分离器/分液罐/缓冲罐计算、容器流体力学校核

SEP_EQUIP：旋风分离器、丝网除沫器、重力沉降器、颗粒沉降计算

PSV：泄放量计算（火灾/阀门关闭/反应失控）、泄放面积计算、选型

HEAT：HTRI文件解析、换热器规格书数据管理、重量估算

不包含：

CV/RESTRICTION/FLARE_SYS/COOL_TOWER/PSYCHRO/OPEN_CHANNEL（P6阶段）

EQUIP_LIST/UTIL集成（P7阶段）

报表输出（P8阶段）

1.3 定义、缩略语和术语
术语/缩写	定义
Souders-Brown	气液分离器气相允许速度计算方程
NPSH	Net Positive Suction Head
API 520	安全阀选型标准
API 521	泄放和减压系统指南
API 526	安全阀标准孔口尺寸
API 2000	常压储罐呼吸阀标准
HTRI	Heat Transfer Research Inc.换热器计算软件
TEMA	Tubular Exchanger Manufacturers Association
BEM	TEMA换热器型式代码（固定管板）
ACHE	Air Cooled Heat Exchanger，空冷器
Lapple/Swift/Barth	旋风分离器计算方法
York法	丝网除沫器计算方法
Stokes定律	颗粒层流沉降速度
MDMT	Minimum Design Metal Temperature
1.4 参考文献
HT-REQ-2026-002 V2.2 §3.2.5（PSV）、§3.2.6（VESSEL）、§3.2.7（HEAT）、§3.4.5-3.4.7

SUP-003 §3.2.28（SEP_EQUIP）

换热器规格书数据字典（HeatResults表完整JSON结构）

空冷器规格书数据字典（ACHE专用字段和焓值表结构）

API 520/521/526/2000

SPEC-P4（FLASH/PIPE/PUMP已交付）

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述四个模块的定位。第三部分详细定义各模块的算法和验收标准。第四部分为附录。

第二部分：综合描述
2.1 产品前景
P5阶段交付第二批设备计算模块。VESSEL和SEP_EQUIP处理气液/气固分离设备，PSV保障系统安全，HEAT承接换热器选型数据。这些模块共同覆盖了工艺设计中最常见的设备类型计算需求。

2.2 产品功能
模块	核心功能	主要依赖
VESSEL	分离器直径/容积/停留时间	Souders-Brown + fluids.tanks
SEP_EQUIP	旋风/除沫器/沉降器	自研 + fluids.particle_size
PSV	泄放量/面积/选型	API 520/521/526 + FLASH
HEAT	HTRI解析/数据管理/重量估算	自研解析器
2.3 用户类和特征
用户类	特征	P5阶段相关需求
工艺设计人员	执行容器/安全阀/换热器计算	日常使用
工艺负责人	审核计算结果	结果审查
设备工程师	查看换热器规格书数据	HEAT数据使用
2.4 运行环境
同SPEC-P0 §2.4。

2.5 设计和实现上的限制
所有计算模块必须记录公式版本号到DataLineage。

数值计算使用numpy.float64。

PSV泄放量计算需支持多泄放工况叠加。

HEAT需支持管壳式和空冷器两种类型。

容器计算需与EQUIP_LIB复用推荐关联。

记录生命周期（V1.1，SUP-007）：各模块计算结果为计算记录——9 态门禁（批准深度按 record_approval_config，默认 VESSEL 2 级、HEAT 2~3 级、PSV 3~4 级可含客户代录步骤）、record_hash、无 version 字段；引用物流须为 CHECKED；模块 UI 提供"弃用"操作（位号终身锁定）；容器/安全阀/换热器数据表作为交付物由交付物机制发布。

2.6 假设和依赖
依赖P4：FLASH可用（PSV两相流和物性计算）。

依赖P3：SIM物流数据、PMS设计条件。

依赖P2：CONFIG中的Souders-Brown K因子和PSV相关系数。

假设：有HTRI实际输出文件可用于解析器测试。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
界面	规格
VESSEL计算	容器类型选择（分离器/分液罐/缓冲罐/回流罐）、设计参数输入、结果展示、复用推荐
SEP_EQUIP计算	设备类型选择（旋风/丝网/沉降器）、参数输入、效率和压降输出
PSV计算	被保护设备配置、泄放工况选择、泄放量计算、面积计算、选型结果
HEAT数据管理	HTRI文件导入、换热器规格书表格展示、空冷器焓值表查看
3.1.2 软件接口
接口组	端点	说明
VESSEL	POST /api/v1/vessel/calculate	容器计算
GET /api/v1/vessel/{vessel_id}/recommend	复用推荐
SEP_EQUIP	POST /api/v1/sep-equip/calculate	分离设备计算
PSV	POST /api/v1/psv/calculate-relief	泄放量计算
POST /api/v1/psv/calculate-area	泄放面积计算
POST /api/v1/psv/select-orifice	孔口选型
HEAT	POST /api/v1/heat/import-htri	HTRI文件导入
GET /api/v1/heat/{heat_id}	获取换热器数据
POST /api/v1/heat/{heat_id}/weight-estimate	重量估算
3.2 功能需求
3.2.1 VESSEL容器计算
需求编号：P5-VES-001

功能描述：实现分离器/分液罐/缓冲罐/回流罐的尺寸计算。

计算类型：

容器类型	计算内容	方法
分离器/分液罐	气相允许速度、最小直径、液体容积	Souders-Brown
缓冲罐/回流罐	基于停留时间和进出料差	容积计算
容器流体力学校核	排空时间、溢流、液位-容积	fluids.tanks
Souders-Brown方程：
V_max = K × √((ρ_L - ρ_V) / ρ_V)

K因子取值（从CONFIG读取，SI m/s）：

立式分离器：K=0.01~0.05 m/s

卧式分离器：K=0.05~0.11 m/s

带除沫器：K=0.04~0.10 m/s

（注：以上为 SI m/s；原 0.03~0.15 / 0.15~0.35 为英制 ft/s 经典值，1 ft/s = 0.3048 m/s。本节按 P5-1 OPEN-2 裁决修订为 SI 单位。）

最小直径：
D_min = √(4×Q_V / (π×V_max))

液体停留时间：按工艺要求（3~5分钟）核算液体容积。

容器流体力学校核（fluids.tanks）：

排空时间：重力流/泵送条件下容器排空所需时间

溢流校核：溢流口尺寸是否满足最大进料

液位-容积关系：卧式罐/立式罐部分容积计算

放空管能力：呼吸量校核（供PSV的PVRV选型参考）

复用推荐：调用EQUIP_LIB匹配接口，返回相似设备列表。

验收标准：

Souders-Brown计算与手算偏差<1%

卧式罐液位-容积关系与几何计算偏差<1%

排空时间与手算偏差<5%

复用推荐返回合理结果

3.2.2 SEP_EQUIP气固/气液分离设备
需求编号：P5-SEP-001

功能描述：实现旋风分离器、丝网除沫器、重力沉降器等专用分离设备计算。

设备类型：

设备类型	计算内容	方法
旋风分离器	筒体直径、入口尺寸、压降、分离效率	Lapple/Swift/Barth
丝网除沫器	网垫面积、厚度、压降	York法/Souders-Brown
重力沉降器	沉降室尺寸	Stokes定律/Terminal Velocity
叶片式除雾器	叶片间距、面积	经验法
纤维过滤器	面积、压降	经验法
颗粒沉降计算（fluids.particle_size）：

终端沉降速度（Stokes/Intermediate/Newton区域）

颗粒雷诺数判定

粒径分布（从筛分数据生成）

切割粒径

验收标准：

Stokes沉降速度与手算偏差<1%

粒径分布拟合与实验数据偏差<5%

旋风分离器压降与手算偏差<10%

3.2.3 PSV安全阀计算
需求编号：P5-PSV-001

功能描述：实现安全阀的泄放量计算、泄放面积计算和选型。

泄放工况计算（API 520/521）：

工况	计算方法	输入
外部火灾	润湿面积×热输入量	设备尺寸、绝热类型
阀门关闭	流体膨胀	泵性能、流量
反应失控	反应热和泄放动力学	反应数据
热膨胀	液体膨胀	温度变化、体积
泄放面积计算：

介质类型	公式	标准
气体/蒸汽	A = W/(C×Kd×P1×Kb) × √(T×Z/M)	API 520
液体	液体泄放公式	API 520
两相流	附录D两相流方法	API 520 8th Ed.
选型：向上圆整至API 526标准孔口（D/E/F/G/H/J/K/L/M/N/P/Q/R/T）。

呼吸阀计算（API 2000）：

热呼吸量（温度变化引起）

操作呼吸量（进出料引起）

总呼吸量 = 热呼吸 + 操作呼吸

验收标准：

火灾工况泄放量与API 521手算偏差<2%

泄放面积与API 520手算偏差<2%

孔口圆整正确

两相流计算与HYSYS偏差<5%

3.2.4 HEAT换热器计算
需求编号：P5-HEAT-001

功能描述：实现HTRI文件解析、换热器规格书数据管理和重量估算。

HTRI解析：解析热负荷Q、总传热系数U、面积、壳径、管长、管数、折流板间距等。

换热器数据管理（完整HeatResults表）：

总体参数：型式、布置、串并联、面积、TEMA类别

壳程/管程性能：流体、流量、温度、物性、压降

传热性能：换热量、MTD、传热系数

结构参数：设计压力/温度、腐蚀裕量、接口尺寸

管束参数：管数、尺寸、排列、材料

壳体及内部件：折流板、管板、密封

重量信息

空冷器专用字段（ACHE）：

风扇数量/功率、管束面积

空侧参数（入口温度、海拔）

焓值表（多温度点物性数据）

MDMT及说明

重量估算：U型管/固定管板换热器重量估算公式（基于壳径、管长、管数）。

出口物流规则（V1.2，ADR-0022）：HEAT 计算完成后自动创建出口物流（source_type=DEVICE_CALCULATED、sign_status=DRAFT、change_type=HEAT_EXCHANGE），物流号经过换热器后更换，血缘记录 {上游物流}--[换热器]-->{出口物流}。

验收标准：

HTRI文件解析正确

换热器规格书数据完整

空冷器焓值表存储正确

重量估算与手算偏差<10%

3.3 非功能需求
3.3.1 性能需求
指标	要求
VESSEL单次计算	≤2秒
SEP_EQUIP单次计算	≤2秒
PSV单工况计算	≤2秒
PSV多工况叠加	≤5秒
HTRI文件解析（大文件）	≤10秒
重量估算	≤1秒
3.3.2 精度需求
指标	要求
VESSEL计算	与手算偏差<1%
SEP_EQUIP	Stokes沉降<1%，粒径分布<5%
PSV	泄放量<2%，面积<2%，两相流<5%
HEAT重量	与手算偏差<10%
3.4 数据需求
P5阶段使用P0创建的表：

vessel_results（容器计算结果）

sep_equip_results（分离设备结果）

psv_results（安全阀结果）

heat_results（换热器结果，含管壳式和空冷器）

data_lineage（血缘记录）

第四部分：附录
4.1 PSV计算流程图
text
┌─────────────────────────────────────────────────────────┐
│                   PSV计算链                             │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  被保护设备配置  │ ← VESSEL/EQUIP_LIST
              │  (尺寸/绝热)     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  泄放工况选择    │ ← 火灾/阀门关闭/反应失控/热膨胀
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  泄放量计算      │ ← API 520/521
              │  (各工况)        │ ← FLASH辅助两相流
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  最大泄放量确定  │ ← 多工况取最大
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  泄放面积计算    │ ← 气体/液体/两相流公式
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  API 526选型    │ ← 向上圆整至标准孔口
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  安全阀数据表    │ → PSVResults表
              └─────────────────┘
4.2 HEAT换热器数据流
text
┌─────────────────────────────────────────────────────────┐
│                   HEAT数据流                            │
└─────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │HTRI文件  │     │手动录入  │     │EQUIP_LIB │
    │(解析导入)│     │(补充字段)│     │(选型参考)│
    └────┬─────┘     └────┬─────┘     └────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          ▼
                 ┌─────────────────┐
                 │  HeatResults表  │
                 │  (管壳式/空冷器)│
                 └────────┬────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │EQUIP_LIST│    │  UTIL    │    │ REPORT   │
   │(设备汇总)│    │(热负荷)  │    │(规格书)  │
   └──────────┘    └──────────┘    └──────────┘
4.3 待确定问题列表
编号	问题	影响	建议解决方案	状态
P5-OPEN-001	HTRI输出文件的版本兼容范围？	解析器兼容性	收集公司常用HTRI版本输出样本	待确认
P5-OPEN-002	旋风分离器采用哪种方法（Lapple/Swift/Barth）？	SEP_EQUIP精度	默认Lapple，其他作为备选	已确认
P5-OPEN-003	呼吸阀计算API 2000版本？	PSV精度	采用API 2000第7版	待确认
P5-OPEN-004	空冷器焓值表是否必须来自工艺包？	HEAT数据完整性	是，焓值表通常来自Licensor	已确认
P5-OPEN-005	[设备结果表扩展 + 双阶段设计] 详见 SUP-008 V1.1 §2.2-§2.6 + §8.4 + SUP-009 V1.0 + SUP-010 V1.1：① PSV 增 relief_results 表 8 字段（relief_scenario 枚举 FIRE/CLOSED_VALVE/REACTION_LOSS_OF_CONTROL/BLOCKED_OUTLET/COOLING_FAILURE/UPSET 等 + relief_area/relief_mass_flow/relief_volume_flow/set_pressure_choice 等）+ SUP-008 §8.3.3；② COLUMN 增 column_sizing 表 14 字段（含 diameter/height/number_of_trays/tray_spacing 等）；③ MIXER 增 mixer_results 表 7 字段（含 impeller_diameter/rotational_speed/power/mixing_time）；④ HEAT 增 heat_results 表 39 字段（详见 SUP-009 §3.1）+ ache_params JSONB（风机/空气侧/翅片/管嘴/空气侧阻力分布）；⑤ VESSEL/PSV/COLUMN 增 design_stage 字段（BASIC/DETAIL，下沉自 P4-OPEN-009）；⑥ 新增 4 张表：steam_drum_results/two_phase_pipe_sizing_results/blowdown_drum_results/thermosiphon_circulation_results（SUP-010 §3.1）。验收：设备计算输出与 Excel/HTRI 偏差 ≤ 5%。	P5 结果表 + 数据模型迁移	按 SUP-008 §3.2 + SUP-009 §3.2 + SUP-010 §3.2 ALTER/CREATE TABLE；列入 DICT V3.7/V3.9；ADR-0026 起草	待启动
P5-OPEN-006	[HEAT 旧字段清洗] 详见 SUP-009 V1.0 §3.4：原 heat_results 表 9 字段（equipment_no/equipment_name/duty/effective_area/hot_inlet_pressure/hot_outlet_pressure/cold_inlet_pressure/cold_outlet_pressure/u_overall）保留（向后兼容），新增 39 字段同时扩展。建议新建 ADR-0027 记录 heat_results 双轨设计裁决。	HEAT 数据迁移	ALTER TABLE + 旧字段审计 + ADR-0027	待启动

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-007：记录生命周期约束（9 态门禁/record_hash/无 version 字段/弃用/交付物外置；PSV 批准深度可含客户代录）；文件标识改 PCS 前缀 | 联合项目组 |
| V1.2 | 2026-08-29 | incorporate ADR-0022：HEAT 计算完成自动创建出口物流（HEAT_EXCHANGE，独立物流链） | 联合项目组 |
| V1.3 | 2026-09-03 | incorporate SUP-008 V1.1 + SUP-009 V1.0 + SUP-010 V1.1：关联文档加 SUP-008/009/010；新增 P5-OPEN-005（relief_results + column_sizing + two_phase_results + mixer_results + heat_results 39 字段 + ache_params + 4 张蒸汽/汽包表 + design_stage 下沉）；新增 P5-OPEN-006（HEAT 旧字段清洗 + ADR-0027）；主体 §3.2 模块需求不动，仅扩展结果表与数据模型 | 联合项目组 |

