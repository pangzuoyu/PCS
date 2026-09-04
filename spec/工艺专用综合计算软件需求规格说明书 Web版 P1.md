P1 横切关注点框架开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P1
当前版本	V1.2
发布日期	2026-08-27（V1.2 修订 2026-08-29，incorporate SUP-004/005/007 + ADR-0019~0022）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库）
关联文档	PCS-REQ-2026-002 V2.2、SUP-001~007、DICT-001/002、SPEC-P0
第一部分：引言
1.1 目的
本文档定义P1阶段（横切关注点框架）的完整需求规格，明确状态机、版本管理、数据血缘、输入清单和工作区管理五大横切能力的详细功能需求、接口规范和非功能要求。本文档是P1阶段设计、编码、测试和验收的唯一依据。

1.2 文档范围
包含：

状态机引擎（V1.1 起为两层：记录层 9 态数据门禁 + 交付物层签署矩阵状态机，见 SUP-007 §3）

交付物与变更单管理（Rev 版本序列（SUP-004）、编号模板、快照绑定、变更单=交付物子类型）

数据血缘框架（3.3.5节血缘记录与溯源，V1.1 起哈希锚定）

项目输入清单管理（3.3.14节）

工作区管理（3.3.15节，V1.1 起门禁仅正式区）

变更影响分析引擎（3.3.9节，V1.1 起哈希不匹配检测 + STALE 路径）

不包含：

CONFIG配置中枢（P2阶段）

具体计算模块（P4–P6阶段）

报表生成（P8阶段）

签署流程前端UI完整实现（P9阶段）

AI功能（P10阶段）

1.3 定义、缩略语和术语
术语/缩写	定义
横切关注点	跨多个模块共用的能力，如状态管理、版本控制、数据血缘
状态机	两层：记录层 RecordSignStatus（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE）；交付物层由签署矩阵动态生成（SUP-005）
Rev	交付物版本代码（A/B/C→0/1/2→AS-BUILT，X 作废），由版本序列配置生成（SUP-004），记录无 Rev
record_hash	记录数据哈希（SHA-256，规范化舍入后计算），记录数据状态的唯一锚定
血缘	数据之间的依赖关系链（record_id + record_hash 锚定），记录数据从何而来
输入清单	项目级结构化数据，定义项目所需的全部输入项及完备性状态
工作区	隔离的数据环境，分为正式项目、个人工作区和临时工作区
变更影响分析	上游数据变更后自动扫描并标记受影响下游记录
CTE	Common Table Expression，SQL递归查询
ASSUMED	输入项状态，表示已填写但来源为假设/经验值
1.4 参考文献
HT-REQ-2026-002 V2.2 §3.3.5（数据血缘）、§3.3.8.3（状态机）、§3.3.9（变更影响）、§3.3.10（版本管理）、§3.3.14（输入清单）、§3.3.15（工作区）

HT-REQ-2026-002-SUP-001 §3.3.14、§3.3.15

SPEC-P0（基础设施）

HT-REQ-2026-DICT-001 §3.14–§3.16（血缘/输入清单/工作区表定义）

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述P1阶段的产品定位、功能和约束。第三部分详细定义各横切关注点的功能需求、接口和数据需求。第四部分为附录，包含状态机迁移图和待确定问题。

第二部分：综合描述
2.1 产品前景
P1阶段构建的横切关注点框架是后续所有业务模块（P4–P7）运行的基础设施。它不面向工艺工程师直接提供业务价值，但决定了整个系统的数据治理能力、流程严谨性和可追溯性。本阶段完成后，任何计算模块的开发都可以直接复用状态机、版本管理、血缘追踪等能力。

本阶段的核心价值在于：

流程严谨性：两层签署（记录层数据门禁 + 交付物层签署矩阵）确保设计成果经过完整校审流程（V1.1 修订）

数据可追溯性：数据血缘让任何输出字段都能追溯到原始输入（record_id + 哈希锚定）

数据完备性：输入清单管理确保项目数据的完整性和假设数据的透明化

变更可控性：变更影响分析（哈希不匹配检测）确保上游变更不会遗漏下游影响

灵活性与隔离：工作区机制允许个人试算与正式项目数据隔离（门禁仅正式区）

2.2 产品功能
功能模块	核心能力
状态机引擎	记录层 9 态门禁（批准深度可配置 1~4 级）、IN_APPROVAL 复合状态、状态变更审计
交付物与变更单	Rev 生成（SUP-004 序列）、编号模板、快照绑定、变更单（交付物子类型）
数据血缘	哈希锚定血缘记录自动写入、向上/向下追溯、血缘图可视化数据
输入清单	清单生成、状态管理、完备性检查、假设数据标识与传播
工作区	三类工作区管理、数据隔离、数据导入项目流程
变更影响分析	影响扫描、记录标记、状态回退、用户确认机制
2.3 用户类和特征
用户类	特征	P1阶段相关需求
设计（Designer）	创建和维护计算数据，响应退回意见	版本创建与修改、工作区使用、变更确认
校核（Checker）	对设计成果进行全面校核	状态流转（校核通过/退回）
审核（Reviewer）	对设计原则和方案进行审核	状态流转（审核通过/退回）
审定（Approver）	最终成果合规性审定	状态流转（审定通过/退回）
系统管理员	不参与签署，负责系统维护	审计日志查询、工作区清理
后端开发者	后续开发复用横切能力	API接口的易用性和完整性
2.4 运行环境
同SPEC-P0 §2.4。

2.5 设计和实现上的限制
状态机分两层且均可配置：记录层批准深度按记录类型在项目模板 record_approval_config 配置（1~4 级，可含客户代录步骤）；交付物层由签署矩阵（SUP-005）驱动。V1.0 的"四级不可定制"限制作废。

Rev 系统自动生成：按版本序列配置自动计算，允许用户在有效序列内手动指定（SUP-004）。记录无版本号。

血缘数据只追加：DataLineage记录不允许修改或删除。

工作区隔离强制：个人/临时工作区数据不可被正式项目直接引用；门禁/交付物/变更单仅存在于 FORMAL 工作区（非 FORMAL 提交批准、创建交付物、创建变更单一律 403）。

异步处理：变更影响分析必须异步执行，不得阻塞用户操作。

位号终身唯一：(project_id, tag_number/line_no) 唯一约束覆盖含 OBSOLETE 的全部记录，弃用不复用。

2.6 假设和依赖
依赖P0：数据库Schema、认证系统、项目骨架已就绪。

假设：Redis可用（用于缓存和异步任务队列）。

假设：ARQ后台任务队列已配置。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
P1阶段交付以下UI组件（作为后续业务模块的通用组件）：

组件	规格
状态标签	显示当前状态（DRAFT/IN_APPROVAL/CHECKED/STALE等），带颜色标识；IN_APPROVAL 显示 Step n/N 进度
版本时间线	交付物 Rev 时间线（版本目的、签署摘要），支持点击查看快照
血缘面板	模态框，展示数据来源链（含各环节哈希），支持逐级展开
输入清单仪表盘	项目首页组件，展示输入项完成进度
工作区切换器	顶部工具栏下拉菜单，切换正式项目/个人/临时工作区；非 FORMAL 区隐藏批准/交付物操作
变更通知面板	通知中心组件，展示 STALE 待确认清单与撤销审批待办
3.1.2 软件接口
接口组	端点	说明
记录批准API	POST /api/v1/records/{module}/{record_id}/submit-approval	提交批准（DRAFT→IN_APPROVAL，按 record_approval_config 走步）
POST /api/v1/records/{module}/{record_id}/approval-step	当前步骤通过/退回（IN_APPROVAL 内推进，全部通过→CHECKED）
POST /api/v1/records/{module}/{record_id}/abandon-change	放弃变更（CHANGE_PENDING→CHECKED，恢复变更前快照）
POST /api/v1/records/{module}/{record_id}/request-reversal	发起撤销（CHANGED→REVERSAL_PENDING）
POST /api/v1/records/{module}/{record_id}/reversal-decision	撤销批准/驳回（撤销批准链）
POST /api/v1/records/{module}/{record_id}/obsolete	弃用（未绑定免凭证；已绑定须走变更单 RECORD_CANCELLATION）
GET /api/v1/records/{module}/{record_id}/status	查询当前状态（含 approval_step/depth）
交付物API	POST /api/v1/deliverables	创建交付物/变更单（绑定记录须全部 CHECKED；非 FORMAL 工作区 403）
POST /api/v1/deliverables/{id}/issue	选版本目的→生成 Rev→走签署矩阵
GET /api/v1/deliverables/{id}/versions	Rev 历史
GET /api/v1/deliverables/{id}/versions/{rev}/snapshot	快照（record_hash 绑定明细）
POST /api/v1/deliverables/{id}/customer-approval/proxy	代录客户批准（ADR-0007，凭证附件+二次认证）
血缘API	GET /api/v1/lineage/{module}/{record_id}/upstream	向上追溯
GET /api/v1/lineage/{module}/{record_id}/downstream	向下追溯
GET /api/v1/lineage/{module}/{record_id}/graph	血缘图数据
输入清单API	GET /api/v1/checklist/{project_id}	获取项目输入清单
GET /api/v1/checklist/{project_id}/completeness	完备性检查
PUT /api/v1/checklist/{project_id}/item/{input_id}	更新输入项
工作区API	GET /api/v1/workspaces	列出用户工作区
POST /api/v1/workspaces	创建工作区
POST /api/v1/workspaces/{workspace_id}/import-to-project	导入到正式项目（新 record_id，从 DRAFT 起步）
变更影响API	GET /api/v1/change-impact/{module}/{record_id}	查询影响范围（哈希不匹配定位）
POST /api/v1/change-impact/{module}/{record_id}/confirm-recalc	确认重算（哈希判定：不变恢复 / 变化进 CHANGE_PENDING）
3.2 功能需求
3.2.1 状态机引擎（V1.1：记录层门禁）
需求编号：P1-WF-001

功能描述：实现记录层数据门禁状态机（RecordSignStatus，9 态）与批准深度配置。交付物层状态机由签署矩阵驱动，见 SUP-005/007，不在本节。

状态定义：

状态	标识	说明
草稿	DRAFT	设计中，可编辑（试算数据恒为此态）
批准中	IN_APPROVAL	复合状态，approval_step/depth/role 追踪多步批准进度
批准完成	CHECKED	该记录类型配置的全部批准步骤通过——可被交付物绑定的唯一状态
批准退回	CHECK_REJECTED	某步骤退回，修改后重新提交
数据存疑	STALE	已绑定记录被上游变更波及，只读，等待确认重算（自动存变更前快照）
变更中	CHANGE_PENDING	获准修改已发布数据，正在修改+重新批准（自动存变更前快照）
已变更	CHANGED	变更已批准，等待关闭凭证（新版交付物 Rev 或变更单）
撤销待批准	REVERSAL_PENDING	CHANGED 的撤销审批中（撤销批准链）
已作废	OBSOLETE	人工弃用终点（未绑定免凭证；已绑定须走变更单 RECORD_CANCELLATION）

关键迁移（完整规则见 SUP-007 §3）：

路径	迁移	触发
批准	DRAFT→IN_APPROVAL→CHECKED（按 record_approval_config 逐步）	设计提交/各步批准人
上游变更（未绑定）	CHECKED→DRAFT	系统（CIA 哈希不匹配）
上游变更（已绑定）	CHECKED→STALE→（重算哈希不变）CHECKED /（变化）CHANGE_PENDING	系统+设计人确认
主动变更	CHECKED→CHANGE_PENDING→CHANGED→CHECKED	设计人+批准链+凭证
撤销	CHANGE_PENDING→CHECKED（自行放弃）；CHANGED→REVERSAL_PENDING→CHECKED/CHANGED	设计人/撤销批准链
弃用	→OBSOLETE	设计人/项目负责人（位号终身锁定）

电子签名：每个批准步骤通过时二次认证，记录签名事件（含 approval_step）。

验收标准：

所有迁移路径单元测试覆盖（含 STALE/CHANGED/REVERSAL_PENDING 全路径）

非法迁移被拒绝并返回错误（如绑定 DRAFT 记录、非 FORMAL 工作区提交批准）

状态变更记录审计日志；哈希判定（不变/变化）落审计

与AD认证集成（二次认证）；批准深度按项目模板配置生效

3.2.2 交付物与变更单管理（V1.1：替代原版本管理系统）
需求编号：P1-VER-001

功能描述：实现交付物 Rev 生成、编号、快照绑定和变更单管理。记录无版本——本节全部机制仅作用于交付物层（SUP-007 §5）。

（1）Rev 生成与校验

Rev 代码由项目模板的版本序列配置（SUP-004）驱动：A/B/C（开发）→0/1/2（正式）→AS-BUILT；X 作废；后缀 R/A。发布必选版本目的（Issue Purpose），版本目的决定签署矩阵。允许在有效序列内手动指定，越界拒绝。

（2）编号

doc_no 由项目模板级编号模板生成（段类型：项目字段/交付物字段/序号/固定值/手动/日期；序号按 scope 原子分配、不回收）。同类型交付物可按装置等拆分范围创建多份，各自独立 Rev 序列。

（3）快照绑定

交付物发布（签署矩阵走完）时对绑定记录固化 record_hash（deliverable_record_bindings）；被绑定记录即锁定。绑定准入：仅 CHECKED 记录可绑定，其余 8 态一律拒绝、整份拒发。快照与当前哈希不一致的 Rev 标 AFFECTED。

（4）变更单

变更单 = deliverable_type=CHANGE_NOTICE 的交付物（1:1 扩展表 change_notice_details 承载 change_type/reason），复用交付物状态机、编号模板与 Rev 历史。APPROVED 后系统自动将绑定记录 CHANGED→CHECKED 并写入 change_resolved_by。change_type 含 RECORD_CANCELLATION（弃用已绑定记录）、CHANGE_REVERSAL（反转已生效变更）。

（5）历史三处承载

变更前快照 record_change_snapshots（回滚）、交付物版本 deliverable_versions+bindings（发布固化，仅哈希）、审计日志（行为流水）。xxx_History 快照流水表不创建（V1.0 方案作废）。

验收标准：

Rev 生成/校验正确（含 Alpha 清理等 SUP-004 可选项）

编号模板分配无并发冲突，项目内唯一

快照绑定哈希正确，绑定准入强制生效

变更单创建/签署/自动关闭记录链路完整

仅 CHECKED 可绑定；AFFECTED 标记与清除正确

3.2.3 数据血缘框架
需求编号：P1-LIN-001

功能描述：实现血缘记录的自动写入、追溯查询和可视化数据格式转换。

血缘记录自动写入：通过装饰器或上下文管理器，在计算服务执行时自动记录：

来源类型（手动输入/公式计算/外部导入/复用设备/假设值/估算）

来源记录ID和计算时哈希（source_record_hash）

目标记录ID和结果哈希（target_record_hash）

依赖类型（引用/公式计算/手动覆盖/估算）

使用的公式版本号（formula_version，来自CONFIG）与配置版本号（config_version，如管道等级版本）

时间戳

注（V1.1）：记录无版本，血缘以 record_id + record_hash 锚定；记录修改重算后追加新血缘记录（只追加，不改旧记录）。

注（V1.2，ADR-0020/0022）：物流的锚定对象是**状态点（state_point_id + record_hash）**——引用物流的计算血缘记录其所用状态点的哈希。血缘支持**物流转换边**：{上游物流}--[设备]-->{下游物流}（dependency_type=DEVICE_TRANSFORMATION，边上的设备由 streams 表 upstream_* 字段承载），设备是物流间的转换函数。

追溯查询：

查询类型	说明
向上追溯	给定记录，查找其所有直接和间接来源
向下追溯	给定记录，查找其所有直接和间接影响的下游
图查询	获取以某记录为中心的血缘子图
验收标准：

计算服务执行后血缘记录自动写入

向上追溯返回完整来源链

向下追溯返回完整影响链

血缘图数据格式可供前端可视化使用

3.2.4 输入清单管理
需求编号：P1-CHK-001

功能描述：实现项目输入清单的生成、状态管理、完备性检查和假设数据传播。

输入项分类：

分类	说明	缺失时的行为
REQUIRED	必需项	禁止无条件输出
CONDITIONAL	条件必需项	条件满足时变为必需
OPTIONAL	可选项	使用默认值或系统估算，必须标记
输入项状态：

状态	标识	颜色
未填写	NOT_STARTED	灰色
填写中	IN_PROGRESS	黄色
已验证	VERIFIED	绿色
假设值	ASSUMED	橙色
不适用	NOT_APPLICABLE	灰色斜体
完备性检查：

检查节点	行为
设计人提交批准	REQUIRED和CONDITIONAL项必须全部VERIFIED，否则警告
交付物签署界面	显示输入完备性状态条，签署人必须确认知悉
交付物最终版生成	任何REQUIRED未完成禁止生成
假设数据传播：ASSUMED或NOT_STARTED状态输入项的值视为假设值。通过血缘自动追踪所有依赖该输入项的下游结果，并在界面强制显示橙色三角标记。

验收标准：

项目创建时自动生成清单

状态转换正确

完备性检查在签署节点生效

假设数据标识随血缘传播

3.2.5 工作区管理
需求编号：P1-WS-001

功能描述：实现三类工作区的创建、数据隔离和导入项目功能。

工作区类型：

类型	标识	数据生命周期
正式项目	FORMAL	长期保留
个人工作区	PERSONAL	90天未活动自动归档
临时工作区	TEMPORARY	7天未活动自动清理
数据隔离规则：

个人/临时工作区数据标记为"试算数据"，永远 DRAFT——无 CHECKED/STALE/CHANGED，不可提交批准、不可创建交付物与变更单（API 一律 403，P1-WS-006/007/008）

不可被正式项目直接引用；个人区可只读快照引用正式区 CHECKED 数据（不自动同步、不参与 CIA）

试算数据导入后原记录保留并标记"已导入"，防重复导入

UI上明确区分（灰色标签vs绿色标签）

导入项目流程：

用户选择个人工作区数据导入正式项目

系统创建新记录（新record_id，sign_status=DRAFT，无版本号；V1.1：记录不版本化，导入即复制）

自动关联导入时使用的上游数据版本快照

状态从DRAFT开始，走正常签署流程

血缘中记录导入来源

验收标准：

三类工作区创建和切换正常

数据隔离有效

导入流程完整

自动清理任务正常执行

3.2.6 变更影响分析引擎（V1.1：哈希不匹配检测 + STALE 路径）
需求编号：P1-CIA-001

功能描述：实现上游数据变更后的影响定位（哈希不匹配）、STALE 标记、哈希判定与凭证闭环。V1.0 的"作废重建/回退 DRAFT"规则作废（ADR-0003）。

影响定位算法：

变更记录产生新 record_hash 后，扫描 data_lineage 中 source_id=该记录 且 source_record_hash ≠ 新哈希 的条目——其 target 即直接受影响下游

级联传播在下游记录自身重算（哈希变化）时逐级发生，不做预先递归遍历

异步执行（ARQ任务队列），扫描完成后推送通知

链式传播（V1.2，ADR-0022）：物流→设备→物流→设备→物流沿独立物流链逐级传导——上游物流变更使引用它的设备计算存疑，设备重算后其出口物流（DEVICE_CALCULATED）哈希更新，再波及下游设备，直至链尾

状态路径（按下游记录是否被交付物绑定）：

下游记录情形	路径
未绑定（DRAFT/CHECK_REJECTED/CHECKED）	直接回 DRAFT 重算，不走 STALE
已绑定 CHECKED（锁定）	→STALE（只读，自动存变更前快照；绑定 Rev 标 AFFECTED）
STALE 确认重算	哈希不变→STALE 清除恢复 CHECKED（无凭证）；哈希变化→CHANGE_PENDING→批准→CHANGED→凭证关闭（变更单或新版交付物）
设备表联动	来源记录状态变化自动传导至其同步的设备记录（ADR-0005）

用户确认流程：

设计人收到报警通知

进入记录详情页查看变更详情（新旧值对比、血缘链）

确认重算 → 系统哈希判定并走上述路径；结果不变时审计记 STALE_RESOLVED_NO_CHANGE

验收标准：

上游变更后自动触发影响定位（哈希不匹配）

已绑定/未绑定记录走各自正确路径

STALE 只读与 AFFECTED 标记正确；哈希不变时免凭证恢复

CHANGE_PENDING→CHANGED→凭证关闭链路完整；设备记录联动正确

3.3 非功能需求
3.3.1 性能需求
指标	要求
状态迁移API响应时间	≤500ms
版本历史查询（100个版本）	≤1秒
血缘追溯（5层深度）	≤2秒
变更影响扫描（1000条依赖关系）	≤10秒（异步）
输入清单完备性检查	≤500ms
3.3.2 安全性需求
指标	要求
签署操作	需二次认证（AD密码或MFA）
状态迁移权限	按角色严格校验
版本历史数据	只读，不可修改
血缘数据	只追加，不可修改或删除
审计日志	所有状态变更和版本变化记录日志
3.4 数据需求
3.4.1 状态机数据
每个业务记录表需包含以下流程字段：

字段	类型	说明
sign_status	enum	当前门禁状态（RecordSignStatus 9 态）
record_hash	string	记录数据哈希（SHA-256，规范化舍入后计算）
approval_step / approval_depth / approval_role	int / int / enum	批准进度（IN_APPROVAL 复合状态追踪）
locked_by_deliverable	bool	被交付物快照锁定标记
stale_* / change_* / reversal_* / obsoleted_*	字段组	各状态时间戳、原因、关闭凭证（change_resolved_by）等
imported_from_workspace_id / imported_at	UUID / datetime	工作区导入来源
created_by	UUID	创建人
created_at	datetime	创建时间
updated_at	datetime	更新时间
3.4.2 历史存储（V1.1：三处承载，替代 xxx_History）
不创建任何 xxx_History 表。历史由三处承载、职责单一：

存储	存什么	何时写	何时读
record_change_snapshots	完整设计参数数据（JSON）	进入 STALE / CHANGE_PENDING 前	放弃变更/撤销 CHANGED 时恢复
deliverable_versions + deliverable_record_bindings	Rev 元数据 + record_hash（仅哈希）	交付物发布时	追溯"某 Rev 某记录的数据状态"
audit_logs	行为描述（谁/何时/改了什么）	每次操作	审计和流程追溯
第四部分：附录
4.1 状态机迁移图（V1.1：两层模型，旧四级单层图作废）

text
【记录层门禁（9态）】
DRAFT ──提交批准──► IN_APPROVAL(step=1..N) ──全部步骤通过──► CHECKED ──被交付物绑定──► CHECKED(锁定)
  ▲                      │                                  │                      │
  │◄─退回(CHECK_REJECTED)─┘                                  │                      │
  │                                                           │              上游变更(CIA哈希不匹配)
  │未绑定：上游变更直接回DRAFT重算 ◄──────────────────────────┤                      ▼
  │                                                           │                   STALE(只读,存快照)
  │                                                           │              确认重算──┬─────────┐
  │                                                           │                 哈希不变    哈希变化
  │                                                           │                 ▼            ▼
  │                                                           │             CHECKED    CHANGE_PENDING
  │                                                           │            (恢复,免凭证)   (存快照)
  │                                                           │                            │ 批准通过
  │                                                           │                            ▼
  │                                                           │                          CHANGED
  │                                                           │                    ┌───────┴────────┐
  │                                                           │              撤销(批准链)      凭证关闭
  │                                                           │           REVERSAL_PENDING   (变更单/新版Rev)
  │                                                           │                │                │
  │                                                           │           批准:回滚CHECKED   CHECKED(新hash)
  │                                                           │           驳回:回CHANGED          │
  │ 人工弃用（未绑定免凭证/已绑定走RECORD_CANCELLATION变更单）──────────────────────────────► OBSOLETE
  │                                                          （位号终身锁定，永不复用）
【交付物层】
deliverable(DRAFT) ──选版本目的→生成Rev──► 按签署矩阵逐步签署(含客户代录CUSTOMER_PROXIED) ──► APPROVED
     发布时快照绑定record_hash；快照≠当前哈希的Rev标AFFECTED；变更单=CHANGE_NOTICE类型交付物

4.1.1 旧四级迁移图（V1.0 留档，已作废）
text
                    ┌──────────────────────────────────────┐
                    │                                    │
                    ▼                                    │
               ┌─────────┐    SUBMIT     ┌──────────┐   │
     ┌────────►│  DRAFT  │──────────────►│ CHECKING │   │
     │         └─────────┘               └────┬─────┘   │
     │         ▲    ▲                        │          │
     │         │    │ REJECT              PASS│          │
     │         │    │                        ▼          │
     │  MODIFY │    │                   ┌──────────┐    │
     │         │    └───────────────────│CHECK_PASS│   │
     │         │                        └────┬─────┘   │
     │         │                             │ SUBMIT  │
     │         │                             ▼          │
     │         │                        ┌──────────┐    │
     │         │                        │ REVIEWING│    │
     │         │                        └────┬─────┘   │
     │         │                      PASS│   │REJECT   │
     │         │                          ▼   │         │
     │         │                   ┌──────────┐│         │
     │         │                   │REVIEW_PASS│         │
     │         │                   └────┬─────┘         │
     │         │                        │ SUBMIT         │
     │         │                        ▼                │
     │         │                   ┌──────────┐         │
     │         │                   │APPROVING │         │
     │         │                   └────┬─────┘         │
     │         │                 PASS│   │REJECT         │
     │         │                     ▼   │               │
     │         │                 ┌──────────┐            │
     │         └─────────────────│ APPROVED │            │
     │                           └────┬─────┘            │
     │                                │ UPSTREAM_CHANGE  │
     │                                ▼                   │
     │                           ┌──────────┐            │
     │                           │ OBSOLETE │            │
     │                           └──────────┘            │
     └────────────────────────────────────────────────────┘
4.2 待确定问题列表
编号	问题	影响	建议解决方案	状态
P1-OPEN-001	电子签名的MFA方式（短信/邮件/APP）？	签署流程实现	与IT部门确认现有MFA基础设施	待确认
P1-OPEN-002	个人工作区90天自动归档是否需要邮件提醒？	用户体验	建议归档前7天发送提醒	待确认
P1-OPEN-003	变更影响扫描的异步任务执行频率？	系统负载	建议变更后1分钟内启动扫描	待确认
P1-OPEN-004	版本快照是否需要支持数据恢复（回滚到历史版本）？	数据安全	P1阶段仅支持查看快照，恢复功能推迟	已确认推迟（V1.1：恢复由变更前快照在撤销/放弃路径承担）

## 版本历史

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-004/005/007：状态机拆两层（记录 9 态门禁+交付物签署矩阵）；版本管理改为交付物与变更单管理（Rev/编号模板/快照绑定）；血缘哈希锚定；工作区门禁仅正式区；CIA 改哈希不匹配+STALE 路径；删除 xxx_History | 联合项目组 |
| V1.2 | 2026-08-29 | incorporate ADR-0019~0022：血缘锚定扩展至物流状态点（state_point_id + record_hash）；新增物流转换边（DEVICE_TRANSFORMATION）；CIA 支持物流链式传播（物流→设备→物流） | 联合项目组 |

