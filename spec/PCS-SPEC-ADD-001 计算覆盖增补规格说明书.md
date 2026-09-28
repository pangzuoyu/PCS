PCS-SPEC-ADD-001 计算覆盖增补规格说明书
文档编号：PCS-SPEC-ADD-001
版本：**V1.11**（V1.10 实施基线冻结 + V1.11 Ruling 9 wording 增补）
编制日期：2026-09-28
关联文档：PCS-PLAN V1.3、PCS-SPEC-P3-SIM V1.1、SUP-002 V1.4、SUP-007、**ADR-0030**、**ATT-02（Q2 工艺推导附件）**
目的：对现有开发计划做 C-01~C-24 全覆盖审计，将未覆盖/部分覆盖的工艺计算增补进已有模块，不新增独立模块。

0. 背景与目标
0.1 背景
现有 PCS-PLAN V1.3 已定义 P0~P10 阶段与 P3~P6 计算模块。经审计，24 项标准计算中：

已覆盖：C-01、C-02、C-04、C-07、C-11、C-14

部分覆盖：C-03、C-05、C-09、C-10、C-15、C-17、C-19、C-20、C-21、C-24

未覆盖：C-06、C-08、C-12、C-13、C-16、C-18、C-22、C-23

> **V1.4 状态清单终态（2026-09-25）**：§0.1 与覆盖表逐项对齐（V1.3 仅对齐 C-08 + C-10 + C-24 三项，遗漏 C-15）。V1.4 终态：
> - **C-24** 由"已覆盖" → "部分覆盖 50%"（V1.1 审计，与 §3.6.2 Masonelian 增补一致）
> - **C-15** 由"未覆盖" → "部分覆盖 25%"（V1.1 审计，与 §3.2.3 Beggs-Brill/Eaton-Flanning/Taitel-Dukler 增补一致）
> - **C-08** 由"已覆盖" → "未覆盖"（V1.1 审计 + V1.2 WS-CA-PR-010.xls 复核，与 §3.4.2 sizing 重写一致）
> - **C-10** 由"部分覆盖" → "部分覆盖 20%"（V1.3 口径统一）

> **V1.10 实施终态 + 冻结（2026-09-26）**：本 SPEC 审计的 24 项计算已全部实施落地，**V1.10 起冻结为 P6-4/P6-5+ 实施基线**：
> - **P6-4 批**（merge `849a1bb`）：C-06 气体热值 / C-08 两相分离器 / C-12 部分体积+润湿面积+质量迭代 / C-17 显式水含量 / C-24 Masonelian fl
> - **P6-5+ 批**（merge `f530daa`；架构组 Q1/Q2/Q3 裁决闭环 `e35064b`~`e683fed`）：C-03/C-05/C-09/C-10/C-13/C-15/C-16/C-18/C-19/C-20/C-21/C-22/C-23 共 13 项 + 4 张 compound_* CONFIG 表 + 5-min TTL 缓存
> - V1.4 审计口径下的"未覆盖/部分覆盖"状态自 V1.10 起全部翻转为**已实施**；剩余开口仅为数据源升级（SYNTHETIC_TEST_DATA → 真实厂商/GPSA 数据，P6-6+ 工艺工程师接管）
> - Q2 架构裁决增补（C1 L/V_ref=242 双层口径 + C2 MEOH=6.63 物性溯源）已并入 §3.9.1 / §3.9.3；全量推导见 **ATT-02**（PCS-SPEC-ADD-001-ATT-02 Q2 工艺推导附件）

> **V1.11 Ruling 9 wording 闭环（2026-09-28，OPEN-P6-6A-1）**：V1.10 实施基线保持冻结，V1.11 仅 wording 增补，不引入新实施项。Ruling 9 双 surface docs final：
> - **C-17 第 1 surface**（commit `cfdbe2d`）：XLS WS-CA-PR-019 natural gas 饱和 W ≠ PCS humid air 饱和 W；worley_c17_saturation_w.json fixture 5 cases 登记为 mapping_defect（OoM ≥ 10）。详见 §3.9.2 working fluid 口径澄清。
> - **C-21 第 2 surface**（commit `fddeae4`）：XLS WS-CA-PR-025 AS 1210 path formula family ≠ PCS API 521 hardcode。闭环路径：OPEN-P6-6A-5（Ruling 14 ΔH_vap fluid-specific input，commit `e72e0db`）+ OPEN-P6-6A-8（Ruling 15 fire_case_coefficient + fire_case_exponent fluid-specific，commit `bc95487`）。详见 §3.5.2 火灾泄放公式口径 + 流体特定输入。

口径定义：0% = 未覆盖；1~99% = 部分覆盖；100% = 已覆盖。

> **V1.3 背景同步（2026-09-25，仅供参考，V1.4 覆盖）**：§0.1 状态清单按 V1.1 审计 + V1.2 WS-CA-PR-010.xls 复核同步：
> - C-08 由"已覆盖"移入"未覆盖"（V1.1 审计修正，与 §3.4.2 修订一致）
> - C-10 由"部分覆盖"修正为"部分覆盖 20%"（V1.3 口径统一：0% 未覆盖，1~99% 部分覆盖，100% 已覆盖）
> - C-24 由"已覆盖"修正为"部分覆盖 50%"（V1.1 审计修正，与 §3.6.2 修订一致）

0.2 目标
24 项计算全部纳入现有 P3~P6 模块，不新增独立模块。

明确每项增补的输入、输出、算法来源、数据依赖、验收标准。

给出工时估算与里程碑影响，供排期裁决。

0.3 原则
复用优先：能合并进已有模块的，一律不新增。

数据复用：容器几何、气体物性、安全阀系数等共享。

最小扰动：仅扩展现有模块的任务描述与验收标准。

1. 覆盖审计结论

> **V1.1 增补说明（2026-09-25 审计复核）**：原 V1.0 状态判定基于模块路径假设，部分 C-XX 与实际 PCS backend 代码存在脱节。本次审计（24 个 xls 样本 + PCS backend 静态扫描）调整如下：
> - **C-08**：原"已覆盖" → **"未覆盖"**（heat/weight_estimate_service.py 为热交换器专用，vessel/ 实际 0%）
> - **C-10**：原"部分覆盖" → **"未覆盖"**（实测 20%，仅单流体颗粒沉降，缺三相/堰/油水界面）
> - **C-15**：原"未覆盖" → **"部分覆盖 25%"**（已简化 Mandhane + Chisholm void fraction）
> - **C-20**：原"部分覆盖" → **"部分覆盖 40%"**（已 normal+thermal，缺 emergency/fire）
> - **C-24**：原"已覆盖" → **"部分覆盖 50%"**（仅 flashing 布尔，缺 Masonelian fl + 闪蒸蒸汽量）
>
> 审计依据：`/tmp/cxx_coverage.json`（24 项实测）+ `/tmp/xls_metadata.json`（24 个 xls 摘要）。

> **V1.2 增补说明（2026-09-25 WS-CA-PR-010.xls 算例复核）**：V1.1 发布同日，工艺工程师基于 WS-CA-PR-010 实际算例（K 因子 + 气相 CSA + 喷嘴动量 + 仪表间距 + 停留时间）核对 §3.4.2，发现 6 处内部不一致。修正如下：
> - **§3.4.2 标题改"两相分离器尺寸计算"**：原"重量计算"标题与 §3.8.2 标的 Souders-Brown 标准矛盾；按 WS-CA-PR-010.xls 实际算法为 sizing（气相允许速度 + 蒸汽面积 + 喷嘴动量校核 + 仪表间距 + 停留时间），非壁厚→重量估算
> - **C-08 增补目标重写**：删除 `vessel_weight_estimate_service`（BEM/AEM 壁厚→重量）路径；新增 `two_phase_separator_sizing_service`（Souders-Brown K 因子 + 气相 CSA + 喷嘴动量限值 + 仪表控制高度 + 停留时间 5 段计算）
> - **§3.4.4 C-12 公共服务接口冻结**：列出 3 个公共函数签名（`calc_partial_volume` / `calc_wetted_area` / `mass_iteration_loop`），作为 C-07/C-08/C-10/C-20/C-21 调用的稳定契约
> - **§3.6.2 C-24 增补 Masonelian fl 推导**：补 FL × (1+0.5x)(1-x) / √(1-x²) (Masonelian 1973 Eq.5) + 闪蒸蒸汽量推导 (W_flash = G × x_fl) + Chapman-Jans / Tong 模型公式
> - **§3.7.1 C-09 AS 2360.1.1 细节补强**：流体单相无闪蒸假设 + 声速理想气体假设 + d<1in 触发 Limit 边界 + SI/Imperial 双单位验收
> - **§5 验收标准分级**：强公式 <0.1% / 经验拟合 <1% / 图版查表 <3%（替换原笼统 <0.1%）
> - **§6 工时修正**：C-08 由 2 天 +1~2 天（sizing 比壁厚多 K 因子表 + 喷嘴动量 + 仪表间距校核）；P5.1 VESSEL C-08/10/12 由 6~8 天调整为 7~10 天
> - **§8 解决两条 OPEN**：P6.5 模块语义裁决（保留 PSYCHRO 子包不新增 GAS_TREAT）；C-12 接口冻结日期（V1.2 发布即生效）
> - **附件评估报告同步 V1.1**：C-08 条目改为"两相分离器 sizing"，标准列 Souders-Brown 完整公式 + 喷嘴动量 + 仪表间距
>
> V1.2 修订依据：WS-CA-PR-010.xls 算例全文 + Masonelian 1973 Eq.5 原文 + AS 2360.1.1-2015 §5.3 + CSChE Manual 7th Ed. 第 8 章两相分离器节。

计算	来源	现有模块	状态	增补目标
C-01	WS-CA-PR-001	P4.2 PIPE	已覆盖	—
C-02	WS-CA-PR-002	P4.2 PIPE	已覆盖	—
C-03	WS-CA-PR-003	P4.2 PIPE	部分覆盖	增补 API 14E 冲蚀速度、C 因子
C-04	WS-CA-PR-004	P6.3 FLARE_SYS	已覆盖	—
C-05	WS-CA-PR-005	P4.2 PIPE	部分覆盖	增补 API 14E 两相流管径
C-06	WS-CA-PR-006	无	未覆盖	增补 P3.3 COMMON
C-07	WS-CA-PR-008	P5.1 VESSEL	已覆盖	明确归属
C-08	WS-CA-PR-010	P5.1 VESSEL	未覆盖（实测 0% — heat/weight_estimate_service.py 为热交换器专用；vessel/ 下无 sizing 服务）	**V1.2 重写**：增补 `two_phase_separator_sizing_service`（Souders-Brown K 因子 + 气相 CSA + 喷嘴动量限值 + 仪表控制高度 + 停留时间 5 段；输入 WS-CA-PR-010.xls 完整字段）
C-09	WS-CA-PR-007	P6.1 CV	部分覆盖	增补 AS 2360.1.1
C-10	WS-CA-PR-011	P5.1 VESSEL	**部分覆盖 20%**（sep_equip/ 仅单流体颗粒沉降 Stokes/Intermediate/Newton 三区）	增补 three_phase_separator_service（油水气三相 + 堰板 + 油水界面 + 停留时间校核）
C-11	WS-CA-PR-012	P6.3 FLARE_SYS	已覆盖	—
C-12	WS-CA-PR-013	无	未覆盖	增补 P5.1 VESSEL 公共服务
C-13	WS-CA-PR-014	无	未覆盖	增补 P4.3 PIPE_NET
C-14	WS-CA-PR-015	P4.4 PUMP	已覆盖	—
C-15	WS-CA-PR-016	P4.2 PIPE	部分覆盖 25%（已简化 Mandhane 流型 + Chisholm void fraction）	增补 Beggs-Brill 持液率 + Eaton-Flanning + Taitel-Dukler 流型图
C-16	WS-CA-PR-018	无	未覆盖	增补 P6.5 PSYCHRO
C-17	WS-CA-PR-019	P6.5 PSYCHRO	部分覆盖	增补明确水含量计算
C-18	WS-CA-PR-020	无	未覆盖	增补 P6.5 PSYCHRO
C-19	WS-CA-PR-023	P6.2 RESTRICTION	部分覆盖	增补排污孔板、Ftp、临界流
C-20	WS-CA-PR-024	P5.3 PSV	部分覆盖 40%（已 normal+thermal breathing_valve_service）	增补 API 2000 emergency/fire 分支 + 真空工况
C-21	WS-CA-PR-025	P5.3 PSV	部分覆盖	增补 AS 1210/1797、管破裂、控制阀失效
C-22	WS-CA-PR-026	无	未覆盖	增补 P6.3 FLARE_SYS
C-23	WS-CA-PR-027	无	未覆盖	增补 P6.3 FLARE_SYS
C-24	WS-CA-PR-028	P6.1 CV	部分覆盖 50%（cv_engine 仅 flashing 布尔）	增补 Masonelian fl 修正 + 闪蒸蒸汽量推导 + Chapman-Jans/Tong 模型
2. 增补方案总览
现有模块	增补计算	增补后模块名称
P3.3 COMMON	C-06	工艺常用数据库（含气体热值）
P4.2 PIPE	C-03、C-05、C-15	管道计算（含两相流、持液率、段塞）
P4.3 PIPE_NET	C-13	管道网络水力学（含浪涌压力）
P5.1 VESSEL	C-07、C-08、C-10、C-12	容器计算（含两相/三相分离器、几何公共服务）
P5.3 PSV	C-20、C-21	安全泄放计算（含储罐通风、AS 1210/1797）
P6.1 CV	C-09、C-24	调节阀与孔板计算（含 AS 2360.1.1）
P6.2 RESTRICTION	C-09、C-19	节流装置计算（含排污孔板）
P6.3 FLARE_SYS	C-04、C-11、C-22、C-23	火炬系统计算（含扩散、噪声）
P6.5 PSYCHRO	C-16、C-17、C-18	气体处理与湿空气计算（含甘醇脱水、水合物抑制）
3. 各模块增补内容
3.1 P3.3 COMMON 增补（C-06 气体热值）
增补计算：气体热值、燃烧、烟气成分

输入

各组分摩尔分数

各组分分子量

各组分净热值/总热值

空气过剩系数

输出

进料气分子量

净热值（MJ/Sm³、Btu/scf）

总热值（MJ/Sm³、Btu/scf）

化学计量空气量

烟气生成量

烟气组成（CO₂/H₂O/N₂/SO₂/Cl₂/He/HCl）

烟气分子量

算法来源：WS-CA-PR-006，GPSA Section FIG. 23-2

数据依赖

64 种化合物热值表（新增到 COMMON 库）

烟气组成归一化规则

验收标准

与 Excel 对账误差 <0.1%

覆盖甲烷、乙烷、丙烷、丁烷、戊烷、CO₂、H₂S、N₂ 等

工时估算：2 天（V1.5 修订；与 §6 P3.3 表对齐）

3.2 P4.2 PIPE 增补（C-03、C-05、C-15）
3.2.1 C-03 API 14E 两相流压降与冲蚀
输入

混合物质量流量、密度

管径、等效长度

C 因子（连续/间歇服务）

输出

截面积、体积流量、混合物速度

冲蚀速度、压降

算法来源：WS-CA-PR-003，API RP 14E

增补要点

C 因子表（连续 122、间歇 152.5、耐蚀 183~244、耐蚀间歇 305，SI）

Salama & Venkatesh 法（可选）

验收：与 Excel 对账误差 <0.1%

3.2.2 C-05 API 14E 两相流管道尺寸
输入

油/气流量、气油比、油/气比重

入口压力/温度、压缩因子

冲蚀速度常数

输出

气体体积流量、油体积流量、混合物密度

冲蚀速度、最小管径、选定管径

混合物速度、压降

算法来源：WS-CA-PR-005

验收：与 Excel 对账误差 <0.1%

3.2.3 C-15 持液率与段塞捕集器（**V1.1：原"未覆盖"修正为"部分覆盖 25%"**；**V1.3：补 Beggs-Brill + Eaton-Flanning + Taitel-Dukler 算法清单**；**V1.9：Taitel-Dukler K-H 延后，主算法 Mandhane 1975**）

> **V1.1 修正（2026-09-25）**：PCS backend `app/services/pipe/two_phase_service.py` 已实现简化 Mandhane 流型判别 + Chisholm void fraction（25%），但缺 Beggs-Brill 持液率相关式、Eaton-Flanning 流型图、Taitel-Dukler 流型判别。原 V1.0 误判为完全未覆盖。

> **V1.3 增补（2026-09-25）**：§3.2.3 增补要点与 V1.1 增补说明不一致（前者只列 Eaton + Cunliffe，后者声明包含 Beggs-Brill）。V1.3 把 §3.2.3 增补要点对齐到 V1.1 增补说明 + §5 验收标准（C-15 Beggs-Brill <1%）。

> **V1.9 修订（2026-09-26）**：基于 Beggs-Brill 1973 原文引用 + P6-5 实施约束，§3.2.3 流型判别**主算法改为 Mandhane 1975**（BUBBLE / STRATIFIED / STRATIFIED_WAVE / ANNULAR / INTERMITTENT / DISPERSED BUBBLE 共 6 区）。**Taitel-Dukler 1976 K/T/F/X 无量纲判别算法延后**：K-H 不稳定分析需 Kelvin-Helmholtz 稳定性判别 + 4 个无量纲参数（K-波动参数 / T-湍流参数 / F-惯性参数 / X-分布参数）联合求解，与 BG-B 持液率计算解耦，本批 P6-5 不实施，PRD 立项时再补。Eaton-Flanning 1967 仍作为 BG-B 适用范围校验（Fr ∈ [0.01, 10] + Lockhart-Martinelli λ 区间）。

输入

管径、压力、气/液流量、液体粘度/密度/表面张力

管长、初始/最终气量、持液率、液体流量、最大外输流量

输出

**持液率（H_L）**：
- Eaton 相关式（已有，V1.1）
- **Beggs-Brill 相关式（V1.3 新增）**：`H_L/ψ = a × λ^b / Fr^c`；λ ∈ [0.1, 1.0] 区间分 4 段（分离流/过渡流/间歇流/分散流）

**流型判别**：
- **Eaton-Flanning 流型图（V1.3 新增）**：横轴 v_SL × (ρ_L / gσ)^0.25、纵轴 v_SG × (ρ_L / gσ)^0.25；分 6 区
- **Taitel-Dukler 流型判别（V1.3 新增）**：基于 Kelvin-Helmholtz 稳定性分析（K-H 不稳定 → 段塞；K-H 稳定 → 分散波/雾状流）
- Mandhane 流型图（已有，V1.1）

**段塞捕集器**：
- Cunliffe 法（已有，V1.1）：增量液量 + 过渡期流量
- Eaton 相关式参数拟合（已有，V1.1）

算法来源：WS-CA-PR-016，Eaton 相关式 + Beggs-Brill 相关式 + Eaton-Flanning 流型图 + Taitel-Dukler 流型判别 + Cunliffe 方法

增补要点（**V1.3 同步**）

Eaton 相关式参数拟合（已有）

Cunliffe 过渡期流量、液体累积量（已有）

**Beggs-Brill 持液率相关式（V1.3 新增；§5 验收 Beggs-Brill <1%）**

**Eaton-Flanning 流型图（V1.3 新增）**

**Taitel-Dukler 流型判别（V1.3 新增）**

验收：**V1.3 分级**
- Eaton 相关式（强公式）<0.1%
- Beggs-Brill 相关式（经验拟合）<1%
- Eaton-Flanning 流型图（图版判别）<3%
- Taitel-Dukler K-H 稳定性（强公式 + 经验拟合组合）<1%

工时估算：**V1.3 修订为 2~3 天**（V1.1 估 2 天偏乐观；Beggs-Brill 分段拟合 + 流型图数值化 +1 天）

3.3 P4.3 PIPE_NET 增补（C-13 管道浪涌压力）
增补计算：管道浪涌/水锤压力

输入

液体密度、标准密度、体积模量

流量、管径、壁厚、管长

阀门关闭时间

弹性模量、泊松比、管锚固方式

输出

流速、波速、管周期

最大浪涌压力、压力增量

算法来源：WS-CA-PR-014，HTFS Handbook Section FM12

数据依赖

液体物性表（丙酮、甲醇、乙醇、甲苯、矿物油、水）

材料弹性模量/泊松比表（铸铁、钢、混凝土、PVC、GRP、铝、钛、纤维水泥）

增补要点

波速公式（含管壁弹性修正）

管周期、最大浪涌压力

三种管锚固方式

验收标准

与 Excel 对账误差 <0.1%

与手算偏差 <1%

工时估算：3~4 天（V1.5 修订；与 §6 P4.3 表对齐）

3.4 P5.1 VESSEL 增补（C-07、C-08、C-10、C-12）
3.4.1 C-07 立式两相分离器（已有，明确归属）
验收：与 Excel 对账误差 <0.1%

3.4.2 C-08 两相分离器尺寸计算（**V1.2：原"重量计算"修正为"尺寸计算（sizing）"**）

> **V1.2 修正（2026-09-25 WS-CA-PR-010.xls 算例复核）**：§3.4.2 V1.1 标题"重量计算"与 §3.8.2 标的 Souders-Brown 标准自相矛盾，且与 WS-CA-PR-010.xls 实际算法（气相允许速度 + 蒸汽面积 + 喷嘴动量校核 + 仪表间距 + 停留时间）不符。原 V1.0/V1.1 误判为"重量估算"系路径假设错误（heat/weight_estimate_service.py 是换热器 BEM/AEM，与 vessel sizing 算法无交集）。**本节按 WS-CA-PR-010 sizing 路径完整重写**。

算法来源：WS-CA-PR-010 Rev A（2 Phase Separator Sizing Spreadsheet）

输入

- 操作压力 / 温度（Psig、°F）
- 油 / 水 / 气 质量流量 + 比重 + 分子量（lb/d、SG、MW）
- 容器内径 / 长度 / L/D / 封头深度（in）
- Souders-Brown K 因子（由操作压力查表，GPSA Fig. 23-22）
- 喷嘴动量限值 N_max（lb·ft/s²，CSV/管嘴规格表）
- 仪表控制时间 t_c（s，液位控制响应时间）
- 容器布置（卧式 HORIZONTAL / 立式 VERTICAL）

输出

- 油 / 水 / 气 体积流量（bbl/d，MMscfd）
- 混合相密度 ρ_mix（lb/ft³）
- 气相允许速度 V_max = K × √((ρL − ρV) / ρV)（ft/s）
- 最小气相 CSA + 实际气相 CSA（ft²）
- 入口 / 出口喷嘴最小 ID（in）
- 控制高度 H_c、控制体积 V_c、实际停留时间 t_r（s）

增补要点

- 新建 `app/services/vessel/two_phase_separator_sizing_service.py`（与 `vessel_sizing` 平级，独立模块；不复用 `heat/weight_estimate_service.py`）
- 5 段计算：
  1. **物性换算**：bbl/d ↔ m³/h、MW ↔ kg/kmol、ρ ↔ kg/m³（SI/Imperial 双单位）
  2. **Souders-Brown K 因子查表**：按 P_op 区间插值（GPSA Fig. 23-22）
  3. **气相 CSA 校核**：A_g_min = Q_g / V_max；与 实际 A_g = π·D²/4 比较
  4. **喷嘴动量限值校核**：F = m·v ≤ N_max；推算最小喷嘴 ID
  5. **仪表间距与停留时间**：H_c = t_c · v_l；V_c = A_l · H_c；t_r = V_c / Q_l
- 输出字段标记 `sizing_method = SOUDERS_BROWN`（预留 CHAPMAN_JANS / TONG 模型接口）
- **不**修改 `heat/weight_estimate_service.py`；**不**抽取 WeightSegment；**不**在 vessel_results 加 weight_kg / weight_method 列
- C-12 公共服务（`calc_partial_volume` / `calc_wetted_area`）冻结后由本服务调用

**单位约定（V1.3 明确）**：本小节输入（Psig / °F / lb/d / SG / MW / in）沿用 WS-CA-PR-010.xls Imperial 单位；SI 输出（MPa_g / °C / kg/d / kg/m³ / kg/kmol / m）由 `app/services/unit_conversion.py` 在 API 边界统一转换，**不**在 sizing 服务内部做单位换算（避免双重换算误差）。

验收：与 WS-CA-PR-010.xls 算例对账误差 <1%（sizing 含经验拟合 K 因子，不强求 <0.1%）；Souders-Brown 公式部分误差 <0.1%

工时估算：**V1.2 修正为 3 天**（原 2 天 + K 因子表 + 喷嘴动量校核 +1 天）

3.4.3 C-10 三相分离器（**V1.5：统一口径为"部分覆盖 20%"**）

> **V1.1 修正（2026-09-25）**：PCS backend `app/services/sep_equip/gravity_separator_service.py` 仅实现单流体颗粒沉降（Stokes/Intermediate/Newton 三区），不含三相油水气、堰板位置、油水界面控制。原 V1.0 判定部分覆盖，实际为独立的全新模块。
输入

油/水/气质量流量、密度、分子量

操作压力/温度、粒径

容器直径/长度、L/D、蒸汽通过数

堰位置、控制时间

输出

分离器直径/长度、L/D

气体 CSA、液体体积

停留时间、堰位置、喷嘴最小 ID

算法来源：WS-CA-PR-011

增补要点

油/水/气三相分离

Weir 位置与堰高

仪表控制高度累积

停留时间校核（油/水分别）

喷嘴尺寸（入口/气相/油/水）

验收：与 Excel 对账误差 <0.1%

3.4.4 C-12 容器部分体积与润湿面积（**V1.2：公共服务接口冻结**）
输入

容器直径 D、T/T 长度 L

封头类型（半球 / 2:1 椭圆 / 碟形 / 平封头）

液位 H、H1/H2/H3、容器数量 n_vessels

输出

单容器/多容器部分体积、总容积

部分面积、总润湿面积

算法来源：WS-CA-PR-013

**V1.2 接口契约冻结（2026-09-25 起生效）**

```python
# app/services/vessel/vessel_service.py（vessel/ 模块公共服务）

@dataclass(frozen=True)
class PartialVolumeInput:
    D_m: float                      # 容器直径（m）
    L_m: float                      # 切线长（m）
    head_type: Literal["HEMISPHERICAL", "2:1_ELLIPTICAL", "TORISPHERICAL", "FLAT"]
    H_m: float                      # 液位高度（m）
    n_vessels: int = 1              # 并联容器数

@dataclass(frozen=True)
class PartialVolumeResult:
    partial_volume_m3: float        # 单容器部分液相体积
    total_volume_m3: float          # n_vessels 总容积
    head_volume_m3: float           # 封头部分容积（半球 = πD³/12；2:1 椭圆 = πD²L_h/12）
    cylinder_volume_m3: float       # 筒体部分液相体积 = πD²·H_cyl/4
    formula_ref: dict[str, str]

def calc_partial_volume(inp: PartialVolumeInput) -> PartialVolumeResult: ...

@dataclass(frozen=True)
class WettedAreaInput:
    D_m: float
    L_m: float
    head_type: Literal["HEMISPHERICAL", "2:1_ELLIPTICAL", "TORISPHERICAL", "FLAT"]
    H_m: float
    n_vessels: int = 1

@dataclass(frozen=True)
class WettedAreaResult:
    wetted_area_m2: float           # 单容器润湿面积
    total_wetted_area_m2: float     # n_vessels 总润湿面积
    head_area_m2: float             # 封头润湿面积
    cylinder_area_m2: float         # 筒体润湿面积 = πD·H_cyl
    formula_ref: dict[str, str]

def calc_wetted_area(inp: WettedAreaInput) -> WettedAreaResult: ...

@dataclass(frozen=True)
class MassIterationInput:
    target_mass_kg: float
    rho_L_kg_m3: float
    rho_V_kg_m3: float
    vessel_shape: Literal["VERTICAL", "HORIZONTAL", "SPHERICAL"]
    head_type: Literal["HEMISPHERICAL", "2:1_ELLIPTICAL", "FLAT"]
    initial_D_m: float = 1.0
    initial_L_m: float = 3.0
    variable: Literal["D", "L"] = "D"   # 收敛变量：D 或 L
    mass_model: Literal["EMPTY", "OPERATING"] = "OPERATING"

@dataclass(frozen=True)
class MassIterationResult:
    converged: bool
    iterations: int
    final_variable_m: float
    final_mass_kg: float
    residual_kg: float
    formula_ref: dict[str, str]    # Newton / bisection

def mass_iteration_loop(
    inp: MassIterationInput,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> MassIterationResult: ...
```

**冻结范围**：函数签名、参数 dataclass、返回 dataclass 自 V1.2 发布起 6 个月内不变。破坏性变更需走 SPEC 修订流程。

**调用方契约**（被 C-07/C-08/C-10/C-20/C-21 调用）：

| 调用方 | 使用函数 | 备注 |
|---|---|---|
| C-07 立式两相分离器 | `calc_partial_volume` + `mass_iteration_loop` | 由 `two_phase_separator_service` 调用 |
| **C-08 两相分离器（V1.2）** | `calc_partial_volume` + `mass_iteration_loop` | 由 `two_phase_separator_sizing_service` 调用 |
| C-10 三相分离器 | `calc_partial_volume` + `calc_wetted_area` | 由 `three_phase_separator_service` 调用 |
| C-20 储罐通风 | `calc_wetted_area` | 由 `breathing_valve_service` 火灾热输入分支 |
| C-21 安全阀 | `calc_wetted_area` | 由 `psv_sizing_service` 火灾工况 |

验收：与 Excel 对账误差 <1%（几何公式部分误差 <0.1%；多容器累加误差 <1%）

工时估算：**V1.2 维持 2 天**（接口冻结后实施风险降低）

3.5 P5.3 PSV 增补（C-20、C-21）
3.5.1 C-20 常压/低压储罐通风（API 2000）（**V1.1：原"部分覆盖"修正为"部分覆盖 40%"**）

> **V1.1 修正（2026-09-25）**：PCS backend `app/services/psv/breathing_valve_service.py` 已实现 normal+thermal 两分支，但 emergency（火灾/外部火源）与 fire exposure（热输入 Q + F 因子）两类 API 2000 工况完全缺失。原 V1.0 未量化覆盖度。
输入

储罐类型（卧式/立式/球罐）

直径、长度/壁高、基础标高、封头类型

设计压力、环境因子 F、汽化潜热 L

泄放温度 T、分子量

最大出液/进液、闪点/沸点、罐容

输出

润湿面积、火灾热输入 Q

紧急泄放量

正常吸入/呼出量

热吸入/呼出量

总正常通风能力

算法来源：WS-CA-PR-024，API Standard 2000 5th Ed.

增补要点

润湿面积计算（卧式/立式/球罐）

火灾热输入 Q（含 F 因子）

紧急泄放量

正常/热通风（表 2B 曲线拟合）

呼吸阀计算

验收：**V1.7 修订与 §5 分级一致** — API 2000 表 2B 热通风曲线拟合 <1%（经验拟合段）

3.5.2 C-21 火灾泄放/安全阀（API 520/521、AS 1210）
输入

设计压力、超压系数、绝热因子

泄放压力、液体/气体物性

容器尺寸、液位、壁温、材料

潜热、安全阀系数 Kd/Kb/Kv

背压、控制阀 Cv/Cf

输出

泄放量（潜热/HYSYS）

安全阀面积（API 520 液体/气体/临界/亚临界）

AS 1210/1797 尺寸

管破裂泄放

控制阀失效/堵塞出口泄放

算法来源：WS-CA-PR-025

增补要点

火灾泄放量（潜热法/HYSYS 法）

API 520 液体/气体、临界/亚临界

AS 1210/AS 1797 安全阀尺寸

管破裂泄放（临界流）

控制阀失效/堵塞出口

安全阀孔口圆整（D~T）

**火灾泄放公式口径**（Ruling 9 第 2 surface 闭环于 OPEN-P6-6A-5 + OPEN-P6-6A-8）：

- **API 521 §3.4**（PCS 默认 back-compat）：Q(W) = 43,192 · F · A^0.82（A 单位 m²，W 基准）
- **AS 1210 §4.4 路径 (a) 液化气体/液体**：m' = (7.2×10⁴ · F · A^0.82) / L（L 单位 J/kg；用户传 coeff=71866 ≈ 7.2×10⁴ 即对齐此路径）
- **AS 1210 §4.4 路径 (b) 气体/蒸汽**：m' = m · Y_p + m'_p，Y_p = 10,000 / (C_w · t · T_o)（**结构差异**，OPEN-P6-6A-9 待立项，本批不在范围）
- **Jet fire**（AS 1210 §4.4 燃烧火焰）：Y_t = 110,000 / (C_w · t · T_r)（独立路径，OPEN-P6-6A-9 待立项，本批不在范围）

**流体特定输入**（Ruling 14 ΔH_vap + Ruling 15 fire_case 系数/指数）：
- 默认 `fire_case_coefficient=43192`、`fire_case_exponent=0.82`、`ΔH_vap=2260 kJ/kg` 保持 API 521 §3.4 back-compat
- 用户传 `fire_case_coefficient=71866`（AS 1210 §4.4 7.2×10⁴）+ `fire_case_exponent=0.82` + `ΔH_vap=208 kJ/kg` 对齐 AS 1210 path (a)（XLS PR-025 G54/G55 验证 ≤0.03% 容差）

验收：**V1.7 修订与 §5 分级一致** — API 520 Kd/Kb <1%（经验拟合段），与 API 520/521 例题计算一致

工时估算：C-20 1~1.5 天 + C-21 2~2.5 天 = 3~4 天（V1.5 修订；与 §6 P5.3 表对齐）

3.6 P6.1 CV 增补（C-09、C-24）
3.6.1 C-09 流量孔板（AS 2360.1.1）（**V1.2：补流体单相/声速/d<1in/双单位 4 项边界**）

输入

流体类型、取压方式

质量流量、上游压力、压差

粘度、管道内径、密度、比热比

输出

压力比、β 比、膨胀因子

相对取压间距、雷诺数、流出系数

孔板直径、估计总压损

最大速度、声速、限值检查

算法来源：WS-CA-PR-007，AS 2360.1.1-1993（**V1.2 同步 AS 2360.1.1-2015 §5.3**）

**V1.2 增补 4 项边界条件（用户审计要求）**

1. **流体单相无闪蒸假设**：上游滞止态单相流体；不闪蒸（不出现 x > 0 的两相区）。闪蒸工况走 C-24 路径（cv_engine）。
2. **声速理想气体假设**：声速 `a = √(γ·R·T / MW)` 假设 γ = Cp/Cv 取定值；非理想气体（接近临界态）走 NIST REFPROP 校正。
3. **d < 1in 触发 Limit 边界**：当 AS 2360.1.1 流出系数公式外推到孔径 d < 1in 时，标记 `in_limit_zone=true` 并输出 WARNING（不抛错；P6-1 工艺室确认是否接受）。
4. **SI/Imperial 双单位验收**：孔径 d、管径 D 同步输出 mm 与 in 两套；β 比、ReD、τ 等无量纲数单输出。

增补要点

β 迭代求解

膨胀因子、流出系数

限值检查（τ、ReD、d、D、β、亚声速）

**V1.2 新增**

- 提取公共孔板服务（`app/services/restriction/orifice_service.py`）供 P6.1（设计）与 P6.2（校核）共用，避免重复实现
- `d < 1in` Limit 边界 WARNING 输出（不抛 422；与 API 14E 的"经验外推"标记一致）
- SI/Imperial 双单位同时输出

验收：β 比、ReD、流出系数 C 与 AS 2360.1.1-2015 例题对账误差 <0.1%（**强公式部分**）；d < 1in Limit 工况误差 <1%（经验外推，**弱验收**）

3.6.2 C-24 控制阀（Masonelian）（**V1.2：补 Masonelian fl 推导 + 闪蒸蒸汽量推导 + Chapman-Jans/Tong 模型**）

> **V1.2 增补（2026-09-25）**：在 V1.1 增补基础上补三段：① Masonelian 1973 Eq.5 闪蒸系数推导 ② 闪蒸蒸汽量 W_flash = G · x_fl 推导 ③ Chapman-Jans / Tong 模型公式。

输入

流量、比重、上游/下游压力

临界压力、蒸汽压、临界流因子 Cf

压缩因子 Z、温度、分子量

输出

压差、临界流判断

Cv（液体/气体、临界/亚临界）

闪蒸判断

**V1.2 新增输出**

- **Masonelian fl**（液体控制阀闪蒸系数，3 模型并存）：
  - **MASONELIAN_1973（默认）**：`fl = FL × (1 + 0.5·x)·(1 − x) / √(1 − x²)`（Masonelian 1973 Eq.5）
  - **CHAPMAN_JANS**：`fl = FL × (1 − x)² / (1 − x²)`（商业软件对账）
  - **TONG**：`fl = FL × √(1 − x)`（简化初算）
  - 字段标记 `masonelian_model` 区分口径
- **闪蒸蒸汽量**：`W_flash_kg_s = G × x_fl`（kg/s；G 为阀入口总质量流量，x_fl 为闪蒸分率）
- **FL / FF / Cf 阀门厂库**：6 厂商（MASONELIAN / FISHER / SAMSON / EMERSON / KOSO / YAMATAKE）× 4 阀型（GLOBE / BALL / ANGLE / PLUG）= 24 组合；`source='SYNTHETIC_TEST_DATA'`，P6-5 工艺室接管真实 Kb

算法来源：WS-CA-PR-028，Masonelian

增补要点

液体/气体双服务

临界/亚临界判断

闪蒸判断

Cf² × DPs 判据

**V1.2 新增**

- 新建 `app/services/cv/flashing_correction.py`（与 cv_engine 平级，独立模块）
- Masonelian fl 三模型并存（默认 MASONELIAN_1973）
- 闪蒸蒸汽量推导（G·x_fl）
- 阀门厂库 24 组合（`# SYNTHETIC_TEST_DATA` 标记）
- `CvResult` ORM 加 1 列 `masonelian_model`（String(16) nullable）；`fl` / `flash_steam_rate_kg_s` 走 `stream_properties_json` JSONB 容器（Do-Not-Repeat 规则）

验收：Masonelian fl 与 Excel 对账误差 <1%（拟合公式，不强求 <0.1%）；闪蒸蒸汽量推导与 WS-CA-PR-028.xls 对账误差 <0.1%

工时估算：C-09 0.5~1 天 + C-24 0.5~1 天 = 1~2 天（V1.5 修订；与 §6 P6.1 表对齐）

3.7 P6.2 RESTRICTION 增补（C-09、C-19）
3.7.1 C-09 AS 2360.1.1（**V1.3：orifice_service 归属 P6.2，P6.1 接口调用**）
说明：C-09 在 P6.1 与 P6.2 之间共享，P6.1 负责孔板设计与迭代，P6.2 负责节流装置校核。

**V1.3 公共孔板服务归属裁决**：
- **归属模块**：P6.2 RESTRICTION（`app/services/restriction/orifice_service.py`）
- **P6.1 CV 调用方式**：通过公共接口调用（`from app.services.restriction.orifice_service import calc_orifice_beta, calc_orifice_discharge_coefficient`），**不**重复实现
- **接口契约冻结**：V1.3 起 6 个月内不变；破坏性变更走 SPEC 修订流程
- **测试边界**：P6.1 测试仅覆盖调用路径；详细回归测试归 P6.2

```
# 调用契约（P6.1 → P6.2 公共孔板服务）
from app.services.restriction.orifice_service import (
    OrificeDesignInput, OrificeDesignResult,
    calc_orifice_beta,                # β 迭代求解
    calc_discharge_coefficient,       # 流出系数 C
    check_limit_zone,                 # d < 1in Limit 边界
)
```

3.7.2 C-19 排污孔板
输入

泄放压力 P1、目标下游压力 P2

泄放温度 T、泄放量 W

压缩因子 z、分子量 MW

上游管径 D、Cp/Cv k

比重 g、流出系数 C

输出

孔板直径 d、孔板面积

Ftp、临界压力、流动状态

算法来源：WS-CA-PR-023

增补要点

Ycr 计算

Ftp 迭代

临界流判断

孔板直径迭代求解

验收：与 Excel 对账误差 <0.1%

工时估算：0.5 天（V1.5 修订；与 §6 P6.2 表对齐）

3.8 P6.3 FLARE_SYS 增补（C-04、C-11、C-22、C-23）
3.8.1 C-04 火炬辐射（已有）
验收：与 Excel 对账误差 <0.1%

3.8.2 C-11 卧式火炬分液罐（已有）
验收：与 Excel 对账误差 <0.1%

3.8.3 C-22 气体扩散
输入

大气压、环境温度、烟囱温度

气体分子量、排放速率、污染物速率

烟囱直径、风速、烟囱高度

稳定度类别 A-F

下风向距离 x、横风向 y、垂直高度 z

输出

空气/气体密度

烟囱出口速度

横向/垂直扩散系数

抬升高度、有效烟囱高度

浓度系数 C1~C5

浓度 c(x,y,z)、地面浓度、最大浓度

算法来源：WS-CA-PR-026，API 931

增补要点

稳定度类别 A-F

sy/sz 曲线拟合系数

抬升高度公式

浓度计算

验收：**V1.7 修订与 §5 分级一致** — API 931 σy/σz 曲线拟合 <1%（经验拟合段）；抬升高度/有效烟囱高度强公式段 <0.1%

3.8.4 C-23 火炬噪声
输入

火炬高度 H、距火炬基础距离 X

火炬气流量、低热值 LHV

热声效率 η

低频/高频衰减梯度

A 计权修正

输出

声源距离 r

热值 QBtu/QkW

声功率 W、声功率级 PWL

倍频程 PWL

声压级 SPL、A 计权 SPL

总噪声级 SPL(A)

算法来源：WS-CA-PR-027，N.D. Narasimhan 方法

增补要点

倍频程谱

低频/高频衰减

A 计权修正

总噪声级

验收：**V1.7 修订与 §5 分级一致** — Narasimhan 热声效率经验值 <1%（经验拟合段）；声功率级/声压级强公式段 <0.1%

工时估算：C-22 2.5~3 天 + C-23 2.5~3 天 = 5~6 天（V1.5 修订；与 §6 P6.3 表对齐）

3.9 P6.5 PSYCHRO 增补（C-16、C-17、C-18）
3.9.1 C-16 甘醇脱水
输入

温度、压力、CO₂/H₂S、水含量、露点

TEG 浓度、循环量、塔型

气体分子量/流量

输出

入口/出口水含量

水露点

水脱除效率

TEG 浓度、汽提气量

塔径、TEG 循环量

传质单元数、塔高

再沸器热负荷

算法来源：WS-CA-PR-018

增补要点

Behr/Kazim 水含量算法

TEG 物性

塔径计算

传质单元数

再沸器热负荷

验收：**V1.7 修订与 §5 分级一致** — Behr/Kazim 水含量相关式 <1%（经验拟合段）；塔径/传质单元数强公式段 <0.1%

3.9.1.1 L/V_ref = 242 参考工况推导（**V1.10 增补 — Q2-1 v2 双层口径**）

> 架构组 Q2 裁决（2026-09-26）：C1 L/V_ref=242 为设计工况归一化常数（GPSA §20.4），非单表数值。v1 初稿工程圆整值（25−7=18）与曲线读数值（17.85）混写导致 4320/18=240 ≠ 242 算术不自洽；v2 改为**双层口径**。全量推导见 ATT-02。

参考设计工况（GPSA Engineering Data Book 13th Ed §20.4 "Glycol Dehydration" Fig 20-1）：

| 参数 | GPSA 曲线读数值 | 工程圆整值 | 单位 | 来源 |
|---|---|---|---|---|
| 天然气流量 | 1.0 | 1.0 | MMscf/d | GPSA §20.4 基准 |
| 进口气水含量 W_in | **25.15** | 25 | lb/MMscf | 饱和气 @ 110°F, 1000 psig |
| 出口气水含量 W_out | **7.30** | 7 | lb/MMscf | dry gas spec（露点 -10°C） |
| 水脱除量 W_removed | **17.85** | 18 | lb/MMscf | W_in − W_out |
| TEG 循环率 Q_TEG | 3.0 | 3.0 | gpm/MMscf | GPSA §20.4 推荐值 |

**口径规则**：曲线读数值（25.15/7.30/17.85）用于追溯推导；工程圆整值（25/7/18）用于正文描述；两者差异 ±0.8%，工程可接受。

推导（追溯口径）：

```
L/V_ref = (3.0 gpm/MMscf × 1440 min/d) / (17.85 lb H₂O/MMscf/d)
        = 4320 gal TEG/d / 17.85 lb H₂O/d = 242.0 gal TEG / lb H₂O
```

算术验证：4320 / 17.85 = 242.02 ≈ 242 ✓（圆整口径 4320/18 = 240，两者关系 240 ~ 242）。

**单位**：gal TEG / **lb** H₂O（brief 原文 "gal/gal" 为笔误；gal/gal 假设反推 148.9 lb/MMscf 超出饱和气水含量上限 ≤25 lb/MMscf，排除）。

**归一化公式**（实际工况校正）：

```
L/V_actual     = (Q_TEG × 1440) / W_removed      # gal TEG / lb H₂O
L/V_normalized = L/V_actual / 242.0              # 无量纲
```

**适用范围**：流量 0.5~500 MMscf/d；W_in 5~25 / W_out 0.5~7 lb/MMscf；TEG ≥98.5 wt%；塔温 60~130°F；塔压 500~1500 psig。工程精度 ±5%（曲线读数 + 工况外推）。

**实现落点**：`pcs-backend/app/services/psychro/glycol_dehydration_service.py`（C-16 P6-5+ 落地）；golden fixture 按 lb 口径对账。

3.9.2 C-17 饱和水含量（已有，明确水含量计算）
输入

温度、压力、CO₂ 浓度、H₂S 浓度

输出

饱和水含量（lb/MMscf、mg/Sm³）

限值检查（温度、压力、酸性气浓度）

算法来源：WS-CA-PR-019

增补要点

SI/Imperial 双单位

限值检查

与 C-16、C-18 联动

**working fluid 口径澄清**（Ruling 9 第 1 surface，OPEN-P6-6A-1 wording 闭环；XLS-PR-019 fixture 5 cases 登记为 mapping_defect）：

- **XLS WS-CA-PR-019**：natural gas（丙烷/丁烷重烃气相）饱和水含量，基准 GPSA Engineering Data Book / GPSA Table 20-1
- **PCS `chedl_wrapper.humid_air_humidity_ratio`**：基准为 humid air（ASHRAE RP-1845）
- **范围边界**：PCS C-17 服务仅适用于湿空气工况；natural gas / 酸性气工况饱和水含量需用专门物性表（GPSA Table 20-1 / McCabe / Campbell 系列），不在 PCS 范围。worley_c17_saturation_w.json fixture 5 cases XLS-PCS OoM ≥ 10 已登记为 mapping_defect（commit `cfdbe2d`）。

验收：与 Excel 对账误差 <0.1%

**注**：C-17 working fluid 完整范围澄清（acidic gas 修正公式 + GPSA Table 20-1 集成策略）待 OPEN-P6-6A-2 决议（独立 SPEC V1.x wording 项）。

3.9.3 C-18 水合物抑制
输入

所需水合物形成温度降

抑制剂类型、K/M 值

游离水流量、抑制剂入口浓度

输出

抑制剂在最终液相中的质量分数

所需抑制剂注入量

方程选择

算法来源：WS-CA-PR-020

增补要点

Hammerschmidt 方程（甲醇 ≤25 wt%、乙二醇 ≤60-70 wt%）

Nielsen 方程（甲醇 ≤50 wt%）

抑制剂 K/M 表（甲醇、乙二醇、乙醇、异丙醇、丙二醇、DEG）

验收：**V1.7 修订与 §5 分级一致** — Hammerschmidt 经验相关式 <3%（图版查表段）；Nielsen 经验相关式 <1%

3.9.3.1 MEOH 密度 6.63 lb/gal 物性溯源（**V1.10 增补 — Q2-2**）

> 架构组 Q2 裁决（2026-09-26）：C2 MEOH=6.63 lb/gal 为 GPSA §20.3 教科书值（20°C 基准 + 安全裕度），NIST SRD 69 交叉验证。溯源与温度敏感性全量推导见 ATT-02。

**基准值溯源**：

```
GPSA §20.3 推荐基准：20°C、0.792 g/mL
单位换算：0.792 g/mL × 8.34 lb/gal ÷ 1.0 g/mL ≈ 6.61 lb/gal
安全裕度：+0.3%（覆盖 15~25°C 环境温度波动）
工程取值：6.61 × 1.003 = 6.63 lb/gal
```

独立验算：6.63 × 0.1198 ≈ 0.794 g/mL ≈ 792 kg/m³ ✓

**密度-温度表**（NIST SRD 69 + GPSA §20.3 交叉验证）：

| 温度 (°C) | 密度 (g/mL) | 密度 (lb/gal) | 来源 |
|---|---|---|---|
| -10 | 0.810 | 6.76 | NIST SRD 69 |
| 0 | 0.801 | 6.68 | NIST SRD 69 |
| 20 | 0.792 | 6.61 | GPSA §20.3 基准 |
| 25 | 0.787 | 6.57 | NIST SRD 69 |
| 40 | 0.773 | 6.45 | NIST SRD 69 |

**温度敏感性**：dρ/dT ≈ -0.00093 /°C（-10~40°C 线性近似）。密度变化对注入率影响约为其一半（密度同时出现在 GPSA §20.3 注入率公式分子分母）：-10~40°C 全程密度 -4.6% → 注入率 -2.3%。

**温度修正公式**（工程简化）：`ρ_MEOH(T) = 6.63 × [1 − 0.00093 × (T − 20)]`（lb/gal，T in °C）；4 点验证（-10/0/20/40°C）偏差均 ≤1.0% ✓。

**精度分级**：15~25°C ±2% 直接用 6.63；-10~15 / 25~40°C ±5% 用修正公式；超范围需 NIST + HYSYS 校正；酸性气按 GPSA §20.3 溶解气修正表。

**实现落点**：`pcs-backend/app/services/psychro/hydrate_inhibition_service.py:78-84`（`_INHIBITOR_DENSITY_LB_PER_GAL["MEOH"] = 6.63`）+ `compound_hammerschmidt_K` CONFIG 表 seed（5 行，SYNTHETIC_TEST_DATA 标记，P6-6+ 工艺室接管时替换为真实期号 + confirmed_by 签字）。

工时估算：C-16 1.5 天 + C-17 1 天 + C-18 1 天 = 3.5 天（V1.5 修订；与 §6 P6.5 表对齐）

3.10 P6.5 模块语义裁决（**V1.2：保留 PSYCHRO 子包不新增 GAS_TREAT**）

> **V1.2 裁决（2026-09-25）**：团队评审后决定 P6.5 维持 PSYCHRO 子包，**不**新增独立 GAS_TREAT 模块。理由：
> 1. C-16/C-17/C-18 三项计算的输入 schema（温度 / 压力 / 水含量 / CO₂ / H₂S / TEG 浓度 / 水合物抑制剂 K/M）与 PSYCHRO 同源（湿空气物性库）
> 2. 现有 PCS 已有 `chedl_wrapper.humid_air_*` 5 个函数（饱和 W / 湿度比 / 相对湿度 / 露点 / 湿球温度），扩展到 C-16/C-17/C-18 边际成本低
> 3. 新增 GAS_TREAT 模块需新建子包 + 重复导入 chedl_wrapper + 重写 DB fixture + alembic 迁移 + frontend types regen，**不**符合 SPEC §0.3"最小扰动"原则
>
> 适用边界：
> - 甘醇脱水 / TEG 物性 / 水合物抑制 / 显式水含量统一进 `app/services/psychro/`
> - 不引入"气体处理"独立业务域
> - 若 P6.5 之后需新增 C-25（克劳斯硫回收）等独立模块，再启动 GAS_TREAT 裁决
>
> 与 ADR-0030 决策 6（chedl_wrapper 只直接库调用）一致。
>
> **V1.3 关联追溯**：ADR-0030 决策 6 + 决策 8（P6.5 PSYCHRO 边界）。如需追溯决议依据，参见 `.wolf/anatomy.md` 中 ADR-0030 章节。

3.11 数据层裁决（**V1.2 新增**）

化合物热值表 + 两相流 C 因子 + Masonelian 阀门厂库 + AS 2360.1.1 Limit 表统一进 `compound_*` CONFIG 表族（仿 `CepciIndexSeries` 模式），不引入独立元数据表。SPEC V1.2 §4 列出 14 项数据层增补；其中 4 项为强公式（API 520/521/931 + AS 1210/1797），其余为合成占位（`source='SYNTHETIC_TEST_DATA'` 标记 + `confirmed_by` 占位）。P6-5 工艺室接管真实 Kb 厂商数据。

4. 数据层增补
数据项	归属	来源	说明
64 种化合物热值表	COMMON	WS-CA-PR-006	净热值/总热值
两相流 C 因子表	COMMON	WS-CA-PR-003	连续/间歇/耐蚀
Eaton/Cunliffe 参数	COMMON	WS-CA-PR-016	持液率/段塞
液体物性表	COMMON	WS-CA-PR-014	密度/波速
材料弹性模量/泊松比表	COMMON	WS-CA-PR-014	浪涌计算
API 2000 表 2B	COMMON	WS-CA-PR-024	储罐通风
API 520/521 系数	COMMON	WS-CA-PR-025	安全阀
AS 1210/1797 参数	COMMON	WS-CA-PR-025	安全阀面积
API 931 扩散曲线系数	COMMON	WS-CA-PR-026	A-F 稳定度
Narasimhan 噪声修正	COMMON	WS-CA-PR-027	倍频程/A 计权
Masonelian 控制阀参数	COMMON	WS-CA-PR-028	Cv/Cf
容器封头几何参数	COMMON	WS-CA-PR-013	部分体积/润湿面积
水合物抑制剂 K/M 表	COMMON	WS-CA-PR-020	抑制剂
TEG 物性/热负荷参数	COMMON	WS-CA-PR-018	甘醇脱水
5. 里程碑验收标准增补（**V1.2：分级验收**）

> **V1.2 增补（2026-09-25）**：原 SPEC §5 笼统要求 <0.1% 不符合实际工艺算法经验拟合/图版查表的精度现实。V1.2 改为三级验收：
>
> | 等级 | 容差 | 适用算法 | 示例 |
> |---|---|---|---|
> | **强公式** | <0.1% | 严格推导公式 + 标准方法 | Souders-Brown 公式、SRT 几何、Beggs-Brill 持液率 |
> | **经验拟合** | <1% | 经验回归曲线 + 拟合系数 | Masonelian fl、API 2000 表 2B 拟合、API 520 Kd/Kb |
> | **图版查表** | <3% | 标准图版查表 + 插值 | AS 2360.1.1 d<1in Limit 外推、K 因子表插值、C-22 扩散 σy/σz 曲线 |
>
> **规则**：同一计算有强公式部分与经验拟合部分时，**分段验收**（强公式段 <0.1%，经验拟合段 <1%）。不允许笼统标 <0.1% 强验收。

里程碑	增补验收标准（V1.2 分级）
P3 完成	C-06 气体热值：HHV/LHV 加权公式 <0.1%；GPSA FIG. 23-2 抄录 <1%
P4 完成	C-03/C-05 强公式 <0.1%；C-15 Beggs-Brill <1%；C-13 Joukowsky 强公式 <0.1%
P5 完成	**C-07 强公式 <0.1%；C-08 强公式（Souders-Brown Vmax）<0.1%，K 因子表插值 <1%；C-10 强公式 <0.1%；C-12 几何公式 <0.1%；C-20/C-21 API 520 Kd/Kb <1%**
P6 完成	C-09 强公式 <0.1%、d<1in Limit <1%；C-19 强公式 <0.1%；C-24 Masonelian fl 经验拟合 <1%、闪蒸蒸汽量推导 <0.1%；C-22/C-23 <1%；C-16 Behr/Kazim <1%；C-17 水含量相关式 <0.1%；C-18 Hammerschmidt <3%
6. 工时估算与里程碑影响（**V1.4~V1.6：按 V1.3 表重算 + 阶段汇总 + 各小节工时对齐 + 合计中心值统一（32~40 天中心 36 天）；V1.7/V1.8 无工时变更（仅版本同步）**）
模块	增补计算	工时（天）
P3.3 COMMON	C-06	2（V1.3 实测）
P4.2 PIPE	C-03、C-05、C-15	7~8（V1.3 实测）
P4.3 PIPE_NET	C-13	3~4（V1.3 实测）
**P5.1 VESSEL**	**C-08、C-10、C-12**	**7~10（V1.3 修订；C-08 3 天 + C-10 3 天 + C-12 2 天 = 8 天中心值；C-08 sizing 比原壁厚多 1~2 天）**
P5.3 PSV	C-20、C-21	3~4（V1.3 实测）
P6.1 CV	C-09、C-24	1~2（V1.3 实测）
P6.2 RESTRICTION	C-19	0.5（V1.3 实测）
P6.3 FLARE_SYS	C-22、C-23	5~6（V1.3 实测）
P6.5 PSYCHRO	C-16、C-17、C-18	3.5（V1.3 实测）
**合计**		**32~40 天（中心 36 天；V1.3 重算后约 6.5 周）**

> **V1.3 工时表修订依据**：原 SPEC V1.0/V1.2 §6 表漏列 C-08（34.5 天错误）；V1.1 实测分布段也仅给区间未合计。V1.3 把"原估"与"V1.3 实测"对齐到一张表内。V1.4 删除旧里程碑影响段，按 V1.3 表重算。
里程碑影响（**V1.6：统一合计中心值 + 各小节工时对齐；V1.7/V1.8 无工时变更**）

> **V1.4 重算依据**：V1.3 §6 表已重算（合计 33~40 天中心 36.5 天），但里程碑影响段仍沿用 V1.0/V1.2 旧数据（P5=11.5 天、P6=15.5 天）。V1.4 按 V1.3 表里程碑级汇总。

| 里程碑 | V1.3 增补工时 | 说明 |
|---|---|---|
| P3 | +2 天 | C-06（COMMON）|
| P4 | +10~12 天 | C-03/05/15（PIPE 7~8 天）+ C-13（PIPE_NET 3~4 天）|
| P5 | +10~14 天 | **C-08/10/12（VESSEL 7~10 天）+ C-20/21（PSV 3~4 天）** |
| P6 | +10~12 天 | **C-09/24（CV 1~2 天）+ C-19（RESTRICTION 0.5 天）+ C-22/23（FLARE_SYS 5~6 天）+ C-16/17/18（PSYCHRO 3.5 天）** |
| **合计** | **32~40 天（中心 36 天）** | **约 6.5 周（V1.3 重算；若 3 worker 并行可压缩到 4~5 周）** |

> **V1.1 实测分布（2026-09-25 审计后）—— 历史参考，V1.3 表为准**：
> - P3.3 COMMON C-06：1.5 → 2 天（数据查表耗时）
> - P4.2 PIPE C-03/05/15：4 → 7-8 天（C-15 流型图 + C-03/05 API 14E 双实现）
> - P4.3 PIPE_NET C-13：2 → 3-4 天（MOC 特征线 + Joukowsky）
> - P5.1 VESSEL C-08/10/12：V1.2 由 5 → 7~10 天（C-08 由 2 天 +1~2 天：sizing 比壁厚多 K 因子表 + 喷嘴动量校核；C-10 全新 3 天；C-12 mass iteration 2 天）
> - P5.3 PSV C-20/21：6.5 → 3-4 天（C-20 减半 + C-21 微调）
> - P6.1 CV C-09/24：4 → 1-2 天（C-09 AS 2360 + C-24 Masonelian fl）
> - P6.2 RESTRICTION C-19：2 → 0.5 天（仅缺排污孔板 RO）
> - P6.3 FLARE_SYS C-22/23：4 → 5-6 天（C-22 Gaussian + 重气/轻气 + C-23 SPL）
> - P6.5 PSYCHRO C-16/17/18：5.5 → 3.5 天（C-17 显式 + C-16 TEG + C-18 Hammerschmidt）
>
> **总差**（历史）：SPEC 估 34.5 天 → V1.1 实测 30-37 天 → **V1.3 重算 33~40 天中心 36.5 天**

7. 风险与依赖（**V1.3：P6.5 风险已关闭；C-12 接口已冻结**）
风险	影响	应对
部分算法来源为经验公式/图版	复现精度	保留 Excel 为黄金标准，**V1.3 按强公式 <0.1% / 经验拟合 <1% / 图版查表 <3% 分级对账**（附件 §6.1 同步）
API 2000/520/521/931 数据量大	数据录入	用 Excel 批量导入 + 单元测试
~~P6.5 语义扩展~~	~~模块命名~~	**V1.3 已关闭**（§3.10 裁决保留 PSYCHRO 子包，不新增 GAS_TREAT）
~~C-12 作为公共服务~~	~~接口设计~~	**V1.3 已关闭**（§3.4.4 接口冻结 6 个月；calc_partial_volume / calc_wetted_area / mass_iteration_loop）
~~C-09 在 P6.1/P6.2 共享~~	~~重复实现~~	**V1.3 已关闭**（§3.7.1 明确 orifice_service 归 P6.2，P6.1 通过接口调用，接口契约 V1.3 冻结）
8. 未解决问题（**V1.7 部分解决**）

**V1.7 已解决**（V1.8 同步标题；累计自 V1.4 已解决清单扩展）：
- ✅ P6.5 PSYCHRO 是否扩展为 GAS_TREAT：保留 PSYCHRO 子包，不新增 GAS_TREAT（裁决依据见 §3.10）。
- ✅ C-12 公共服务接口契约：V1.2 §3.4.4 冻结 `calc_partial_volume` / `calc_wetted_area` / `mass_iteration_loop` 3 函数签名（生效 6 个月）。
- ✅ C-09 共享实现方式：V1.3 §3.7.1 明确 orifice_service 归 **P6.2**，P6.1 通过公共接口调用，**V1.3 接口契约冻结 6 个月**。
- ✅ C-08 sizing 重定义：V1.2 §3.4.2 重写为 `two_phase_separator_sizing_service`。
- ✅ C-09 AS 2360.1.1 4 项边界补强：V1.2 §3.6.1 流体单相 / 声速理想气体 / d<1in Limit / SI+Imperial 双单位。
- ✅ C-24 Masonelian fl 三模型 + 闪蒸蒸汽量：V1.2 §3.6.2。
- ✅ C-15 算法清单补全：V1.3 §3.2.3 Beggs-Brill + Eaton-Flanning + Taitel-Dukler。
- ✅ 验收分级：V1.2 §5 强公式 <0.1% / 经验拟合 <1% / 图版查表 <3%。
- ✅ §0.1 状态清单终态：V1.4 与覆盖表逐项对齐（C-08 移未覆盖 / C-15 移部分覆盖 25% / C-24 移部分覆盖 50% / C-10 部分覆盖 20% 口径统一）。

**V1.7 未解决**：
- ❓ API 2000/520/521/931 数据来源：Excel 内置 vs 外部数据库 — 仍待 P6.3 工艺室确认
- ❓ 工时已按 V1.3 表重算（合计 32~40 天中心 36 天，V1.6 修订），分摊方案（是否压缩 P6 其他任务或延长阶段）待项目组裁决

9. 变更记录
版本	日期	变更	作者
V1.0	2026-09-24	初稿，C-01~C-24 全覆盖审计与增补方案	工艺室（pangzy 起草）
V1.1	2026-09-25	审计复核：5 项状态修正（C-08/C-10/C-15/C-20/C-24）+ 4 项 §3 小节覆盖度注记 + §6 工时实测分布修正；依据 `/tmp/cxx_coverage.json` + `/tmp/xls_metadata.json` + 24 个 Worley xls 样本扫描	工艺室（pangzy）
**V1.2**	**2026-09-25**	**WS-CA-PR-010.xls 算例复核：§3.4.2 标题改"尺寸计算"+ C-08 重写为 `two_phase_separator_sizing_service`；§3.4.4 C-12 接口冻结；§3.6.2 C-24 增补 Masonelian fl 推导 + 闪蒸蒸汽量 + Chapman-Jans/Tong 模型；§3.6.1 C-09 增补 4 项边界（单相/声速/d<1in/双单位）；§3.10 P6.5 模块裁决（保留 PSYCHRO）；§3.11 数据层裁决；§5 验收分级（强公式<0.1% / 经验拟合<1% / 图版查表<3%）；§6 工时修正（C-08 +1~2 天）；§8 解决 P6.5 + C-12 + C-09 三条 OPEN；附件评估报告同步 V1.1（C-08 sizing 条目）**	**工艺室（pangzy）**
**V1.3**	**2026-09-25**	**微调：§0.1 背景状态清单同步（C-08 移入未覆盖 + C-24 同步部分覆盖 50% + C-10 口径统一为部分覆盖 20%）；§3.2.3 C-15 增补要点补 Beggs-Brill + Eaton-Flanning + Taitel-Dukler 算法清单；§3.7.1 C-09 公共孔板服务归属 P6.2 明确；§6 工时表补 C-08 + 重算合计（34.5 天 → 33~40 天中心 36.5 天）；§7 风险表关闭 P6.5 + C-12 + C-09 三条；附件 §6.1 对账策略同步三级验收；附件 §7.1 汇总表 C-08 标准列补喷嘴动量 + 仪表间距；附件 §7.2 加 V1.2 变更记录行；§3.10 关联 ADR-0030；§9 作者字段补全**	**工艺室（pangzy）**
**V1.4**	**2026-09-25**	**微调：§0.1 状态清单终态（C-15 移入部分覆盖 25% + C-24 移入部分覆盖 50%）；§6 里程碑影响按 V1.3 表重算（删除 P5=11.5/P6=15.5 旧数据，改为新表 + 阶段汇总）；§8 标题改 V1.4 + 补 6 条 V1.4 已解决（C-08 sizing / C-09 4 项边界 / C-24 / C-15 / 验收分级 / §0.1 终态）；附件版本号 V1.1 → V1.2；附件关联文档 V1.2 → V1.3；附件 §7.1 C-15 标准列补 Beggs-Brill + Eaton-Flanning + Taitel-Dukler；附件 §6.1 标签 V1.1 → V1.2；§6 表下方 V1.1 实测分布标注"历史参考 V1.3 表为准"；§6 修订依据 V1.0/V1.5 → V1.0/V1.2**	**工艺室（pangzy）**
**V1.5**	**2026-09-25**	**微调：§3 各小节工时与 §6 表对齐（C-06 1.5→2 天；C-13 2→3~4 天；C-20/21 6.5→3~4 天；C-09/24 4→1~2 天；C-19 2→0.5 天；C-22/23 4→5~6 天；C-16/17/18 5.5→3.5 天）；§3.4.3 C-10 标题统一口径"部分覆盖 20%"；§5 P6 C-17 标准改"水含量相关式 <0.1%"；§6 标题改 V1.4 + 里程碑 P4 修正 +7~8→+10~12 天（含 C-13 PIPE_NET 3~4 天）；附件标题版本 V1.2→V1.3，关联文档 V1.3→V1.4；附件 §6.1 标签 V1.2→V1.2/V1.3；§8 未解决问题工时项改为"已按 V1.3 表重算，分摊方案待裁决"**	**工艺室（pangzy）**
**V1.6**	**2026-09-25**	**微调：附件标题版本 V1.3→V1.4，关联文档 V1.4→V1.5；附件 §3.1 C-15 标准列补 Beggs-Brill + Eaton-Flanning + Taitel-Dukler（与 §3.2.3 + §7.1 对齐）；主文档 §8 标题 V1.4→V1.5；附件 §6.1 "V1.1 按算法类别分级验收" → "V1.2 按算法类别分级验收"（分级验收为 V1.2 引入）；§6 表合计与里程碑影响合计 33~40 天中心 36.5 → 32~40 天中心 36（与阶段汇总 P3+P4+P5+P6 = 32~40 一致）**	**工艺室（pangzy）**
**V1.7**	**2026-09-25**	**微调：附件标题版本 V1.4→V1.5，关联文档 V1.5→V1.6；主文档 §8 标题与内部标签 V1.5→V1.6；§3.5.1 C-20 / §3.5.2 C-21 / §3.8.3 C-22 / §3.8.4 C-23 / §3.9.1 C-16 / §3.9.3 C-18 共 6 处小节验收标准与 §5 分级验收一致（强公式 <0.1% / 经验拟合 <1% / 图版查表 <3%）；§6 标题追加 V1.6 统一合计中心值说明；里程碑影响标题 V1.4→V1.6**	**工艺室（pangzy）**
**V1.8**	**2026-09-25**	**微调：附件标题版本 V1.5→V1.6，关联文档 V1.6→V1.7；主文档 §8 标题与内部标签 V1.6→V1.7；附件 §6.1 标签简化（"V1.2/V1.3：同步 SPEC §5 三级验收（V1.6 修订措辞；分级验收为 SPEC §5 V1.2 引入）" → "V1.2 引入三级验收；V1.6 同步措辞"）；§6 标题追加 V1.7/V1.8 无工时变更说明；里程碑影响标题追加 V1.7/V1.8 无工时变更**	**工艺室（pangzy）**
**V1.9**	**2026-09-26**	**修订：§3.2.3 C-15 流型判别主算法 Taitel-Dukler 1976 K/T/F/X → Mandhane 1975（依据 BG-B 1973 原文引用 + P6-5 实施简化）；Taitel-Dukler 1976 延后至 PRD 立项补；Eaton-Flanning 1967 保留为 BG-B 适用范围校验（Fr 区间 + Lockhart-Martinelli）；§7.1 附件 C-15 标准列同步修订措辞；§9 作者字段 V1.9；附件标题版本 V1.6→V1.7，关联文档 V1.8→V1.9；附件 §3.1 C-15 标准列同步修订**	**工艺室（pangzy）**
**V1.10**	**2026-09-26**	**Q2 架构裁决增补 + 冻结：§3.9.1.1 新增 C1 L/V_ref=242 参考工况推导（双层口径：GPSA 曲线读数 25.15/7.30/17.85 追溯 + 工程圆整 25/7/18 正文；4320/17.85=242.02 算术自洽；单位澄清 gal/lb）；§3.9.3.1 新增 C2 MEOH=6.63 lb/gal 物性溯源（GPSA §20.3 20°C 基准 6.61 + 0.3% 裕度；NIST SRD 69 交叉验证；温度修正公式 ±1.0% 验证）；§0.1 加 V1.10 实施终态注记（P6-4/P6-5+ 全部 24 项落地，本版起冻结为实施基线）；Q2 增补文档改编号 PCS-SPEC-ADD-001-ATT-02**	**工艺室（pangzy）**
**V1.11**	**2026-09-28**	**OPEN-P6-6A-1 Ruling 9 wording 闭环（docs-only micro-revision）：§3.5.2 C-21 火灾泄放公式口径分项（API 521 §3.4 default 43192 / AS 1210 §4.4 路径 (a) 7.2×10⁴ 液化气体 / 路径 (b) m·Y_p 气体 / Jet fire 110,000 W/m²）+ 流体特定输入段（Ruling 14 ΔH_vap + Ruling 15 fire_case coeff/exp fluid-specific，OPEN-P6-6A-5/8 闭环链）；§3.9.2 C-17 working fluid 口径澄清（XLS WS-CA-PR-019 natural gas 饱和 W ≠ PCS humid air 饱和 W，worley_c17 fixture 5 cases mapping_defect OoM ≥ 10 范围边界）；§0.1 加 V1.11 wording 注记（Ruling 9 双 surface 闭环链 cfdbe2d + fddeae4 + e72e0db + bc95487）。V1.10 实施基线保持冻结，V1.11 仅 wording 增补不引入新实施项**	**工艺室（pangzy）**
本 Spec 供项目组内部评审，评审通过后并入 PCS-PLAN V1.4。**V1.10 已冻结为 P6-4/P6-5+ 实施基线。**

Excel 计算方法合理性评估报告
文档编号：PCS-SPEC-ADD-001-ATT-01
版本：**V1.7**（Draft for Review）
编制日期：2026-09-26
关联文档：PCS-SPEC-ADD-001 **V1.9**、PCS-PLAN V1.3、WS-CA-PR-001~028
目的：对现有 Excel 标准计算表的计算方法进行系统性合理性评估，为软件化开发提供对账基准与风险提示。

1. 评估范围
本报告覆盖以下 24 项标准计算所对应的 Excel 文件：

计算编号	来源文件	计算名称
C-01	WS-CA-PR-001	单相管道尺寸计算
C-02	WS-CA-PR-002	等温可压缩流压降
C-03	WS-CA-PR-003	API 14E 两相流压降与冲蚀速度
C-04	WS-CA-PR-004	火炬辐射计算
C-05	WS-CA-PR-005	API 14E 两相流管道尺寸
C-06	WS-CA-PR-006	气体热值计算
C-07	WS-CA-PR-008	立式两相分离器尺寸
C-08	WS-CA-PR-010	两相分离器尺寸
C-09	WS-CA-PR-007	流量孔板尺寸计算
C-10	WS-CA-PR-011	三相分离器尺寸计算
C-11	WS-CA-PR-012	卧式火炬分液罐尺寸计算
C-12	WS-CA-PR-013	容器部分体积与润湿面积
C-13	WS-CA-PR-014	管道浪涌压力计算
C-14	WS-CA-PR-015	泵尺寸计算
C-15	WS-CA-PR-016	持液率变化与段塞捕集器尺寸
C-16	WS-CA-PR-018	天然气甘醇脱水计算
C-17	WS-CA-PR-019	天然气饱和水含量计算
C-18	WS-CA-PR-020	水合物抑制/形成抑制计算
C-19	WS-CA-PR-023	排污孔板尺寸计算
C-20	WS-CA-PR-024	常压/低压储罐通风计算
C-21	WS-CA-PR-025	火灾泄放/安全阀尺寸计算
C-22	WS-CA-PR-026	气体扩散计算
C-23	WS-CA-PR-027	火炬噪声预测
C-24	WS-CA-PR-028	控制阀尺寸计算
2. 评估方法
2.1 评估维度
维度	说明	权重
标准符合性	是否引用公认标准（API/ASME/ISO/GPSA/AS），公式是否与标准一致	高
公式正确性	公式结构、系数、单位是否合理	高
数据来源	物性、系数、图表是否可靠	中
计算逻辑	迭代、边界、单位转换是否合理	中
验证状态	是否经过内部验证（Validated/Verified）	高
适用范围	假设条件、适用工况是否明确	中
潜在风险	经验公式、图版拟合、硬编码、错误值	中
2.2 评级标准
评级	含义
高	标准明确、公式正确、验证完整、适用范围内可靠
中高	标准明确、公式正确，但含经验拟合或简化假设
中	方法合理，但依赖图版/经验值，需对账确认
低	方法存疑，需重新评估
3. 分类评估
3.1 管道与阀门类
覆盖计算：C-01、C-02、C-03、C-05、C-09、C-13、C-15、C-19、C-24

总体评级：高

C-01 单相管道尺寸计算（WS-CA-PR-001）
项目	评估
标准	ASME B36.10（管材）、Darcy-Weisbach、Colebrook、Churchill
公式	内径 = OD - 2×WT；雷诺数 = ρVD/μ；摩擦系数 Churchill 方程；压降 = f(L/D)(ρV²/2)
数据	管材规格、管件等效长度、阀门 K 值、粗糙度表，均来自标准
验证	Validated/Verified
适用范围	单相流，管径 1/8"~42"
合理性	高。方法标准，数据完整，迭代逻辑合理。
注意事项

管件等效长度与 K 值需确认与项目管道等级库一致。

速度检查、噪声限制、冲蚀速度为附加校核，需确认阈值来源。

C-02 等温可压缩流压降（WS-CA-PR-002）
项目	评估
标准	Churchill 摩擦因子、等温可压缩流公式、GPSA
公式	压缩因子、密度、雷诺数、摩擦因子、压降、声速
数据	分子量、粘度、Cp/Cv、压缩因子
验证	Validated/Verified
适用范围	单相等温可压缩流
合理性	高。方法标准，公式正确。
注意事项

压缩因子相关式未公开（Excel 注明 undocumented），需与 HYSYS 对账。

声速公式 √(kP/ρ) 仅适用于理想气体，需注意。

C-03 / C-05 API 14E 两相流（WS-CA-PR-003 / WS-CA-PR-005）
项目	评估
标准	API RP 14E
公式	冲蚀速度 Ve = C/√ρ；压降 = f(L/D)(ρV²/2)
数据	C 因子表（连续/间歇/耐蚀）
验证	Validated/Verified
适用范围	两相流，C 因子按服务类型选取
合理性	高。API 14E 为行业标准方法。
注意事项

API 14E 冲蚀速度公式偏保守（Excel 已注明），后续研究显示可放宽。

Salama & Venkatesh 法为可选，需确认是否纳入。

Moody 摩擦因子假设 0.015，低流速时需验证（Excel 已注明）。

C-09 流量孔板（WS-CA-PR-007）
项目	评估
标准	AS 2360.1.1-1993
公式	β 迭代、膨胀因子、流出系数、雷诺数
数据	取压方式、限值表
验证	Validated/Verified
适用范围	管径 50~1200 mm，0.2≤β≤0.75，亚声速
合理性	高。标准方法，限值检查完整。
注意事项

β 迭代收敛需测试。

英制算例中 d=0.992 in < 1 in，触发 Limit，说明边界需处理。

C-13 管道浪涌压力（WS-CA-PR-014）
项目	评估
标准	HTFS Handbook Section FM12
公式	波速 = f(体积模量、弹性模量、泊松比、管壁)；最大浪涌 = ρcV
数据	液体物性表、材料弹性模量/泊松比表
验证	Validated/Verified
适用范围	液体管道，阀门关闭时间 < 管周期
合理性	高。方法标准，数据完整。
注意事项

三种管锚固方式对应不同波速修正，需正确选择。

阀门关闭时间 > 管周期时，需用其他方法（Excel 已判断 t < d/25）。

C-15 持液率与段塞捕集器（WS-CA-PR-016）
项目	评估
标准	Eaton 相关式、Beggs-Brill 相关式、Eaton-Flanning 流型图、Taitel-Dukler 流型判别、Cunliffe 方法
公式	持液率 Eaton / Beggs-Brill；流型 Mandhane / Eaton-Flanning / Taitel-Dukler；段塞 Cunliffe
数据	液体粘度、密度、表面张力
验证	未明确标注 Validated
适用范围	压力 ≤1500 psig，平坦地形，湿气管线
合理性	中高。Eaton/Cunliffe 为经验相关式，适用范围内可靠。
注意事项

Eaton 相关式为经验拟合，适用范围需强制检查。

Excel 注明可用 PIPESIM 替代，精度更高。

Cunliffe 法假设最大外输流量恒定，需确认。

C-19 排污孔板（WS-CA-PR-023）
项目	评估
标准	临界流孔板公式
公式	Ycr、Ftp 迭代、孔板直径
数据	流出系数 C、Cp/Cv
验证	Validated
适用范围	气体排污，临界流
合理性	中高。方法合理，Ftp 迭代需测试。
注意事项

Ftp 迭代收敛需验证。

临界流判断需确认。

C-24 控制阀（WS-CA-PR-028）
项目	评估
标准	Masonelian 方法
公式	Cv（液体/气体、临界/亚临界）、闪蒸判断
数据	Cf、Cv
验证	Validated
适用范围	液体/气体控制阀
合理性	高。Masonelian 为行业常用方法。
注意事项

Cf 值依赖厂家数据，需确认来源。

闪蒸判断需确认阈值。

3.2 火炬与排放类
覆盖计算：C-04、C-11、C-20、C-21、C-22、C-23

总体评级：中高

C-04 火炬辐射（WS-CA-PR-004）
项目	评估
标准	API RP 521 4th Ed.
公式	火焰中心、辐射热、距离、烟囱高度
数据	F 因子、太阳辐射、LEL
验证	Validated
适用范围	火炬辐射计算
合理性	高。API 521 标准方法。
注意事项

火焰中心位置由拟合公式得出（Excel 注明 Fitted from Fig C.2.A/C.3.A），需对账。

F 因子（辐射分数）依赖 burner 直径，需确认。

C-11 卧式火炬分液罐（WS-CA-PR-012）
项目	评估
标准	液滴沉降、拖曳系数
公式	C(Re)²、拖曳系数、沉降速度、气相空间
数据	颗粒直径、粘度
验证	Validated
适用范围	卧式分液罐
合理性	中高。方法合理，拖曳系数为经验值。
注意事项

拖曳系数 C=1.3 为假设值，需确认。

液滴沉降时间、气相空间校核需对账。

C-20 储罐通风（WS-CA-PR-024）
项目	评估
标准	API Standard 2000 5th Ed.
公式	润湿面积、Q、紧急泄放、正常/热通风
数据	表 2B、F 因子、潜热
验证	未明确标注 Validated
适用范围	常压/低压储罐（设计压力 ≤1.034 barg）
合理性	中高。API 2000 标准方法，但热通风用曲线拟合。
注意事项

热通风曲线拟合公式与图版可能有偏差（Excel 注明建议从图/表取值）。

润湿面积计算受封头类型、标高影响，需对账。

球形储罐润湿面积按 55% 总表面积，需确认。

C-21 火灾泄放/安全阀（WS-CA-PR-025）
项目	评估
标准	API 520/521、AS 1210/AS 1797
公式	泄放量、安全阀面积（液体/气体、临界/亚临界）、管破裂、控制阀失效
数据	Kd/Kb/Kv、孔口尺寸 D~T、材料
验证	未明确标注 Validated
适用范围	火灾泄放、管破裂、控制阀失效
合理性	中高。多标准、多工况，方法合理但复杂。
注意事项

管破裂、控制阀失效工况复杂，需逐项验证。

AS 1210/1797 与 API 520 并行，需确认适用条件。

安全阀孔口圆整（D~T）需确认标准。

C-22 气体扩散（WS-CA-PR-026）
项目	评估
标准	API 931 Manual
公式	扩散系数 sy/sz、抬升高度、浓度
数据	稳定度 A-F、曲线拟合系数
验证	Validated
适用范围	气体扩散，x≥100 m 更可靠
合理性	中高。API 931 标准方法，但依赖曲线拟合。
注意事项

sy/sz 曲线拟合在 x<100 m 时外推风险高（Excel 已注明 Caution）。

抬升高度公式为经验式，需对账。

稳定度类别选择需工程判断。

C-23 火炬噪声（WS-CA-PR-027）
项目	评估
标准	N.D. Narasimhan, Hydrocarbon Processing, April 1986
公式	PWL、倍频程、SPL、A 计权、总噪声
数据	热声效率 η、低频/高频衰减、A 计权表
验证	Validated
适用范围	火炬噪声预测
合理性	中高。方法标准，但热声效率为经验值。
注意事项

热声效率 η 典型值 1e-6，需确认。

低频/高频衰减梯度（8.5/2.8 dB/oct）为典型值，需确认。

PWL@500Hz 为迭代值，需确认收敛。

3.3 分离与容器类
覆盖计算：C-07、C-08、C-10、C-12

总体评级：中高

C-07 立式两相分离器（WS-CA-PR-008）
项目	评估
标准	Souders-Brown
公式	Vmax = K√((ρL-ρg)/ρg)、直径、液位、喷嘴
数据	K 因子、液位高度、喷嘴尺寸
验证	Validated/Verified
适用范围	立式两相分离器
合理性	高。标准方法，逻辑完整。
注意事项

K 因子为经验值，需按项目确认。

液位高度、喷嘴尺寸需按标准确认。

C-08 两相分离器（WS-CA-PR-010）（**V1.1：标题改"两相分离器尺寸" + 标准列补喷嘴动量 + 仪表间距**）
项目	评估
标准	**V1.1 修正**：Souders-Brown、停留时间、**喷嘴动量限值、仪表控制高度**
公式	**V1.1 修正**：Vmax = K√((ρL−ρV)/ρV)、蒸汽面积 CSA、喷嘴最小 ID、控制高度、实际停留时间
数据	**V1.1 补**：K 因子（按 P_op 区间插值 GPSA Fig. 23-22）、停留时间、**喷嘴动量限值 N_max（lb·ft/s²）、仪表控制时间 t_c（s）**
验证	Validated
适用范围	两相分离器（立式 / 卧式）
合理性	高。方法标准，逻辑完整。
注意事项

**V1.1 新增**：

- K 因子为经验值（按 P_op 查表），需按项目确认。
- **喷嘴动量限值 N_max 来自阀门/管嘴规格表**，与 C-09 AS 2360.1.1 限制流速区分。
- **仪表控制时间 t_c 来自 DCS/LIC 规格**，与 C-12 mass iteration 共享。
- 仪表间距、控制高度需按 WS-CA-PR-010 §5.3 校核。
- 蒸汽面积与液位需双重满足（强公式段 <0.1%，K 因子表插值段 <1%）。

C-10 三相分离器（WS-CA-PR-011）
项目	评估
标准	Souders-Brown、停留时间、Weir
公式	油/水/气三相、Weir、停留时间、喷嘴
数据	K 因子、停留时间、Weir 位置
验证	Validated
适用范围	三相分离器
合理性	中高。方法合理，但油水界面控制复杂。
注意事项

油水界面控制、Weir 高度为简化处理，需注意。

停留时间分油/水分别校核，需对账。

喷嘴尺寸（入口/气相/油/水）需确认。

C-12 容器部分体积与润湿面积（WS-CA-PR-013）
项目	评估
标准	几何公式
公式	部分体积、总容积、部分面积、润湿面积
数据	封头类型（半球/2:1椭圆）、K1、f(Ze)
验证	Validated
适用范围	立式/卧式/球罐
合理性	高。几何公式正确。
注意事项

封头类型需覆盖完整（平、2:1椭圆、碟形、半球）。

作为公共服务，需确保接口稳定。

3.4 泵与旋转设备
覆盖计算：C-14

总体评级：高

C-14 泵尺寸（WS-CA-PR-015）
项目	评估
标准	离心泵标准方法
公式	NPSH、扬程、功率、比转速
数据	效率假设、比转速分类
验证	Validated/Verified
适用范围	离心泵/往复泵
合理性	高。方法标准，逻辑完整。
注意事项

效率假设（离心 75%、往复 90%）为经验值，需按厂家曲线修正。

比转速、叶轮直径计算需确认。

3.5 气体处理与水合物
覆盖计算：C-06、C-16、C-17、C-18

总体评级：中高

C-06 气体热值（WS-CA-PR-006）
项目	评估
标准	GPSA Section FIG. 23-2
公式	净热值/总热值、燃烧化学计量、烟气组成
数据	64 种化合物热值表
验证	Validated
适用范围	气体热值与燃烧计算
合理性	高。方法标准，数据完整。
注意事项

64 种化合物热值表需确认来源版本。

烟气组成归一化、分子量计算需对账。

C-16 甘醇脱水（WS-CA-PR-018）
项目	评估
标准	Behr/Kazim 水含量、TEG 物性
公式	水含量、露点、TEG 循环、塔径、传质单元、热负荷
数据	TEG 物性、热值
验证	Validated
适用范围	TEG 脱水
合理性	中高。方法合理，但再沸器热负荷为估算。
注意事项

再沸器热负荷建议用 HYSYS（Excel 已注明）。

Behr/Kazim 水含量算法需确认。

TEG 损失、汽提气量为估算，需注意。

C-17 饱和水含量（WS-CA-PR-019）
项目	评估
标准	天然气水含量相关式
公式	水含量（lb/MMscf、mg/Sm³）、限值检查
数据	温度、压力、CO₂/H₂S
验证	Validated
适用范围	温度 60~300°F，压力 300~2000 psia，酸性气 <40 mol%
合理性	高。方法标准，限值检查完整。
注意事项

适用范围需强制检查（Excel 已注明）。

SI/Imperial 双单位需对账。

C-18 水合物抑制（WS-CA-PR-020）
项目	评估
标准	Hammerschmidt、Nielsen
公式	抑制剂浓度、注入量
数据	抑制剂 K/M 表
验证	Validated
适用范围	甲醇 ≤50 wt%、乙二醇 ≤60-70 wt%
合理性	高。方法标准，数据完整。
注意事项

抑制剂注入量未考虑烃相溶解和汽相蒸发（Excel 已注明）。

Hammerschmidt 与 Nielsen 适用范围不同，需正确选择。

4. 共性问题
问题	说明	影响	建议
经验拟合	Eaton、Cunliffe、API 2000 曲线、sy/sz 拟合、火焰中心拟合	精度依赖拟合质量	保留 Excel 为黄金标准，代码中注明适用范围
图版插值	部分系数来自图版	插值误差	确认拟合公式精度，必要时用查表
单位转换	SI/Imperial 双单位	转换错误	统一转换库，单元测试覆盖
异常值	#N/A、#DIV/0!、#VALUE!	输入不完整导致	非公式错误，软件中增加输入校验
硬编码	部分系数硬编码	难维护	提取到配置库
验证状态	多数标注 Validated/Verified	可作为对账基准	保留验证记录
适用范围	部分未强制检查	误用风险	软件中增加范围校验与警告
迭代收敛	β、Ftp、PWL 迭代	收敛失败	增加收敛判断与最大迭代次数
数据来源	部分系数来源不明确	可追溯性差	补充数据来源说明
5. 结论
5.1 总体结论
总体合理：24 项 Excel 标准计算表引用权威标准（API、ASME、ISO、GPSA、AS），公式正确，多数经过内部验证，方法合理。

有边界：经验公式、图版拟合、简化假设需在适用范围内使用，软件化时需增加范围校验与警告。

可软件化：适合作为开发计划的黄金标准，但需注意对账、异常处理、范围校验、迭代收敛。

建议：在增补 Spec 中明确每个计算的适用范围、假设、数据来源、验证算例，并在代码中实现限值检查与警告。

5.2 分类结论
类别	覆盖计算	评级	说明
管道与阀门	C-01、C-02、C-03、C-05、C-09、C-13、C-15、C-19、C-24	高	标准明确，公式正确
火炬与排放	C-04、C-11、C-20、C-21、C-22、C-23	中高	标准明确，含经验拟合
分离与容器	C-07、C-08、C-10、C-12	中高	方法合理，经验值需确认
泵与旋转设备	C-14	高	标准方法
气体处理与水合物	C-06、C-16、C-17、C-18	中高	方法合理，部分为估算
6. 建议
6.1 对账策略（**V1.2/V1.3：同步 SPEC §5 三级验收**）

每个计算保留 Excel 为黄金标准，软件与 Excel 逐项对账。**V1.2 按算法类别分级验收**（V1.2 引入三级验收；V1.6 同步措辞）：
- **强公式**（如 Souders-Brown Vmax、Eaton 相关式、几何公式）：误差 <0.1%
- **经验拟合**（如 Masonelian fl、API 2000 表 2B、API 520 Kd/Kb、Beggs-Brill 相关式）：误差 <1%
- **图版查表**（如 AS 2360.1.1 d<1in Limit 外推、K 因子表插值、C-22 σy/σz 曲线、Hammerschmidt）：误差 <3%

每个计算至少 5 个算例，覆盖不同工况、SI/Imperial 双单位。

边界条件测试：零流量、极值、负值、迭代失败。

**同一计算有强公式段 + 经验拟合段时，分段验收**：强公式段 <0.1%，经验拟合段 <1%（与 SPEC §5 规则一致）。

**V1.3 同步项**：C-08 两相分离器 sizing = 强公式段（Souders-Brown Vmax）+ 经验拟合段（K 因子表插值）+ 图版查表段（喷嘴动量 N_max 规格表），**三段验收**；C-15 持液率 = Eaton 强公式 <0.1% + Beggs-Brill 经验拟合 <1% + Eaton-Flanning 图版 <3%。

6.2 软件化注意事项
增加输入校验与范围检查。

增加迭代收敛判断与最大迭代次数。

增加单位转换库与单元测试。

提取硬编码系数到配置库。

保留验证记录与数据来源说明。

6.3 风险提示
风险	应对
经验公式适用范围	软件中强制检查，超范围警告
图版拟合精度	保留查表备选
迭代收敛	增加收敛判断与最大迭代次数
数据来源不明确	补充来源说明
多标准并行	明确适用条件
7. 附录
7.1 评估汇总表
计算	来源	标准	评级	验证	主要风险
C-01	WS-CA-PR-001	ASME B36.10、Churchill	高	Validated	管件 K 值
C-02	WS-CA-PR-002	Churchill、GPSA	高	Validated	压缩因子相关式
C-03	WS-CA-PR-003	API RP 14E	高	Validated	C 因子、Moody 假设
C-04	WS-CA-PR-004	API RP 521	高	Validated	火焰中心拟合
C-05	WS-CA-PR-005	API RP 14E	高	Validated	C 因子
C-06	WS-CA-PR-006	GPSA	高	Validated	数据版本
C-07	WS-CA-PR-008	Souders-Brown	高	Validated	K 因子
C-08	WS-CA-PR-010	Souders-Brown、喷嘴动量、仪表间距	高	Validated	K 因子表查表
C-09	WS-CA-PR-007	AS 2360.1.1	高	Validated	β 迭代
C-10	WS-CA-PR-011	Souders-Brown、Weir	中高	Validated	油水界面
C-11	WS-CA-PR-012	液滴沉降	中高	Validated	拖曳系数
C-12	WS-CA-PR-013	几何公式	高	Validated	封头类型
C-13	WS-CA-PR-014	HTFS FM12	高	Validated	管锚固方式
C-14	WS-CA-PR-015	离心泵标准	高	Validated	效率假设
C-15	WS-CA-PR-016	Eaton、Beggs-Brill、Eaton-Flanning、Taitel-Dukler、Cunliffe	中高	未明确	经验相关式 + 图版判别
C-16	WS-CA-PR-018	Behr/Kazim	中高	Validated	热负荷估算
C-17	WS-CA-PR-019	水含量相关式	高	Validated	适用范围
C-18	WS-CA-PR-020	Hammerschmidt、Nielsen	高	Validated	烃相溶解
C-19	WS-CA-PR-023	临界流孔板	中高	Validated	Ftp 迭代
C-20	WS-CA-PR-024	API 2000	中高	未明确	热通风拟合
C-21	WS-CA-PR-025	API 520/521、AS 1210	中高	未明确	多工况
C-22	WS-CA-PR-026	API 931	中高	Validated	曲线拟合
C-23	WS-CA-PR-027	Narasimhan	中高	Validated	热声效率
C-24	WS-CA-PR-028	Masonelian	高	Validated	Cf 来源
7.2 变更记录
版本	日期	变更	作者
V1.0	2026-09-24	初稿，24 项计算合理性评估	工艺室（pangzy）
**V1.1**	**2026-09-25**	**同步 PCS-SPEC-ADD-001 V1.2：§3.3 C-08 条目改"两相分离器尺寸"（原"两相分离器重量估算"）+ 标准列补喷嘴动量 + 仪表间距 + K 因子表查表说明；§3.3 C-12 条目提示 V1.2 接口冻结生效；§7.1 整体合理性评级不变（中高）**	**工艺室（pangzy）**
**V1.2**	**2026-09-25**	**同步 PCS-SPEC-ADD-001 V1.3：§6.1 对账策略同步三级验收（强公式 <0.1% / 经验拟合 <1% / 图版查表 <3%）；§7.1 汇总表 C-08 标准列补喷嘴动量 + 仪表间距；C-08 评级维持"高"（强公式部分），K 因子插值部分"中高"已注**	**工艺室（pangzy）**
**V1.3**	**2026-09-25**	**同步 PCS-SPEC-ADD-001 V1.4：§0.1 状态清单终态与覆盖表对齐（C-08/C-15/C-24 归位）；§6 里程碑影响按 V1.3 表重算；§8 标题 V1.4 + 补 6 条已解决；§6.1 标签 V1.1 → V1.2**	**工艺室（pangzy）**
**V1.4**	**2026-09-25**	**同步 PCS-SPEC-ADD-001 V1.5：§3 各小节工时与 §6 表对齐；§3.4.3 C-10 标题统一口径；§5 P6 C-17 标准改"水含量相关式"；§6 标题 V1.4 + 里程碑 P4 +10~12 天；标题版本 V1.2 → V1.3；关联文档 V1.3 → V1.4；§6.1 标签 V1.2 → V1.2/V1.3；§8 工时分摊项措辞调整**	**工艺室（pangzy）**
**V1.5**	**2026-09-25**	**同步 PCS-SPEC-ADD-001 V1.6：标题版本 V1.3 → V1.4；关联文档 V1.4 → V1.5；§3.1 C-15 标准列补 Beggs-Brill + Eaton-Flanning + Taitel-Dukler；§6.1 "V1.1 按算法类别分级验收" → "V1.2 按算法类别分级验收"；§6 合计 33~40 中心 36.5 → 32~40 中心 36（与阶段汇总一致）**	**工艺室（pangzy）**
**V1.6**	**2026-09-25**	**同步 PCS-SPEC-ADD-001 V1.7：标题版本 V1.4 → V1.5；关联文档 V1.5 → V1.6；主文档 §8 标题 V1.5 → V1.6；§3.5.1/§3.5.2/§3.8.3/§3.8.4/§3.9.1/§3.9.3 共 6 处小节验收标准与 §5 分级一致；§6 标题追加 V1.6 统一合计中心值说明；里程碑影响标题 V1.4 → V1.6**	**工艺室（pangzy）**
**V1.7**	**2026-09-25**	**同步 PCS-SPEC-ADD-001 V1.8：标题版本 V1.5 → V1.6；关联文档 V1.6 → V1.7；主文档 §8 标题 V1.6 → V1.7；§6.1 标签简化（"V1.2/V1.3：同步 SPEC §5 三级验收" → "V1.2 引入三级验收；V1.6 同步措辞"）；§6 标题追加 V1.7/V1.8 无工时变更说明；里程碑影响标题追加 V1.7/V1.8 无工时变更**	**工艺室（pangzy）**
本报告供项目组内部评审，评审通过后作为 PCS-SPEC-ADD-001 附件。
