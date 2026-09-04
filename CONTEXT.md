# PCS（工艺专用综合计算软件）

工艺室的 Web 版工艺计算平台：模拟数据读取 → 工艺计算 → 校审签章 → 计算书自动生成。本文件是项目唯一术语表（ubiquitous language），实现细节一律不写此处。

## Language

### 两层模型（根基，见 ADR-0001）

**计算记录（Record）**:
单条工程计算数据——一条管道、一台泵、一个安全阀的计算结果。只携带数据正确性门禁，不携带 Rev。
_Avoid_: 版本化数据、签署单元、结果行

**交付物（Deliverable）**:
面向外发布的文档单元——管道一览表、泵数据表、计算书。Rev、版本目的、完整签署矩阵只作用于交付物，从不作用于计算记录。
_Avoid_: 文档（泛指）、报表（与 REPORT 引擎输出混淆）

**记录门禁状态（Record sign_status）**:
计算记录的数据正确性批准状态，共 9 态：DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE。是数据门禁，不是文档发布签署。
_Avoid_: 四级签署（那是交付物层的事）

**批准深度（Approval Depth）**:
记录类型配置的批准步骤数（1–4 级，可含客户代录步骤），存于项目模板 record_approval_config，按模块差异化（如 PSV 4 级、PIPE 2 级、FLASH 中间计算 1 级）。设备记录从来源计算记录继承批准深度。
_Avoid_: 签署矩阵（那是交付物层的 SUP-005 机制）

**批准中（IN_APPROVAL）**:
记录批准流程进行中的复合状态，内部以 approval_step / approval_depth / approval_role 追踪多步进度。全部步骤通过即 CHECKED。
_Avoid_: CHECKING（旧模型状态，已并入 IN_APPROVAL）

**校核通过态（CHECKED）**:
该记录类型配置的全部批准步骤已通过——可被交付物绑定的唯一状态。仅 CHECKED 可绑定；DRAFT / IN_APPROVAL / CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING 一律拒绝。
_Avoid_: 校核通过（字面过窄，深度可以是多级）

**变更前快照（Pre-change Snapshot）**:
记录进入 STALE 或 CHANGE_PENDING 时系统自动保存的数据快照，供哈希比对与撤销回滚使用。
_Avoid_: 交付物快照（那是发布时的 record_hash 绑定）

**撤销（Reversal）**:
以"变更是否已对外生效"为界的分级回退：CHANGE_PENDING 中设计人自行放弃；CHANGED 经 REVERSAL_PENDING 由撤销批准链（按签署矩阵层级取 Reviewer/Approver）批准；已凭生效的变更只能发起反向新变更（CHANGE_REVERSAL 变更单）。STALE 无需撤销——上游恢复后重算哈希不变即自动回 CHECKED。
_Avoid_: 退回（那是校核退回 CHECK_REJECTED）

### 许可

**演示版（Demo License）**:
限制"同时存活的记录数"而非终身创建数：模块配额按活记录（sign_status ≠ OBSOLETE）计数，弃用返还配额，可创建→弃用→再创建循环。交付物与变更单不限量（签署体验是演示核心价值），报表定义独立限 3，CONFIG 只读、EQUIP_LIB 沉淀禁用、输出带水印、仅 FORMAL 工作区、AI 禁用。
_Avoid_: 试用版 TRIAL（限时授权，v1 不实现，仅枚举预留）

**即席导出（Ad-hoc Export）**:
REPORT_BUILDER 查询导出件——不是交付物：无 Rev、无签署，带"非发布件"水印。需要正式发布时经"固化为交付物"转为 CUSTOM_REPORT 交付物走签署矩阵。
_Avoid_: 交付物（导出件是查询快照，不经签署）

**数据存疑（STALE）**:
已被交付物绑定的 CHECKED 记录被上游变更波及后的只读状态，等待设计人确认重算。
_Avoid_: 已变更（CHANGED 是确认后结果确实变了）、受影响（那是交付物层标记）

**实质变更（Substantive Change）**:
以重算后结果哈希是否变化为准（数值规范化舍入后比对），不以上游数据是否变动为准。哈希不变即无变更，无需凭证。
_Avoid_: 上游变更（那只是触发信号）

**变更中（CHANGE_PENDING）**:
已被交付物绑定的记录获准修改、正在修改并重新校核的状态。入口有两个：设计人主动发起（ADR-0002），或 STALE 重算后哈希变化（ADR-0003）。
_Avoid_: 回退 DRAFT（DRAFT 是从未发布过的新建，语义不同）

**已变更（CHANGED）**:
变更修改已完成校核、等待关闭凭证（新版交付物 Rev 或变更单）的状态。旧交付物 Rev 的快照仍保留变更前哈希。
_Avoid_: 已校核（与 CHECKED 混淆）

**变更单（Change Notice）**:
交付物的一种（deliverable_type=CHANGE_NOTICE），已发布数据小规模修改的关闭凭证。签署、编号、Rev、快照全复用交付物机制，特有信息（变更原因/类型）在 1:1 扩展表；APPROVED 后自动关闭全部绑定记录的 CHANGED 状态。大规模修改走普通交付物升 Rev。
_Avoid_: 独立签署实体、设计变更单 DCN（外部概念）、ECN

**代录（Proxy Recording）**:
客户批准的录入方式：客户在系统外批准（邮件/信函/EDMS/签字文件），内部授权人（项目负责人/文控/审定）在系统内代录——凭证附件（必填）+ 客户姓名 + 批准日期 + 代录人二次认证。审计明确区分"代录"与本人签署。
_Avoid_: 客户签署（客户不在系统内操作，v1 无外部链接）

### 血缘与历史

**血缘（Lineage）**:
只追加的依赖边：source（record_id + 计算时哈希）→ target（record_id + 结果哈希），附 formula_version 与 config_version。变更检测 = 血缘哈希与上游当前 record_hash 比对，逐级在重算时传播。
_Avoid_: 版本链（记录无版本，身份用 record_id、数据状态用 record_hash 锚定）

**三处历史**:
变更前快照 record_change_snapshots（回滚）、交付物版本 deliverable_versions + bindings（发布固化，仅哈希）、审计日志 audit_logs（行为流水）。xxx_History 快照流水表全部废除。
_Avoid_: 快照流水（与上述三处职责重叠）

**物流（Stream）**:
管段的标识——一条物流=一个管段，经过设备后物流号更换（S-101→泵→S-102）。来源含模拟导入与手动创建（三种数据模式，ADR-0019），走简化门禁（独立 4 态：DRAFT / IN_APPROVAL / CHECKED / OBSOLETE）：初次引入须校对，DRAFT 不可被计算记录引用。CHECKED 后的修改不重新校对——限权 + 强制原因 + 影响预览，状态保持 CHECKED 并触发 CIA。
_Avoid_: 计算记录（设计成果，9 态门禁）、试算数据

### 物流与设备连接（ADR-0019~0022）

**状态点（StatePoint）**:
同一物流在不同工况（NORMAL / MIN / MAX / ALTERNATE）下的数据快照——独立 T/P/相态/气液分率/组成/物性/record_hash。T/P 变化通过新建状态点表达，不修改原状态点；位置变化用不同物流表达。
_Avoid_: 位置点（POSITION 已移除）、工况点混称

**设备连接（Equipment Link）**:
物流之间的因果连接：{上游物流}--[设备]-->{下游物流}，记录在 streams 表 upstream_stream_id + upstream_equipment_id。设备是物流间的转换函数，不是一条物流的内部环节。
_Avoid_: 状态点连接（ADR-0021 已替代——物流不贯穿多设备）

**出口物流（Outlet Stream）**:
设备（PUMP/CV/PIPE/HEAT/RESTRICTION/FLASH）计算完成后自动创建的下游物流：source_type=DEVICE_CALCULATED、sign_status=DRAFT、需走校对流程。change_type 标记转换性质（等焓/摩擦压降/换热/泵功）。
_Avoid_: 下游状态点（位置变化=新物流，不是状态点）

**虚拟组分（Pseudo-Component）**:
炼油工业按沸程切割的拟组分（如"石脑油段 IBP-150°C"），由馏程+API+分子量定义，替代复杂烃类混合物；支持手动输入或系统自动切割（每 25°C 一段）。
_Avoid_: 纯物质组分

**数据模式（Data Mode）**:
物流数据的三种输入模式：CHEMICAL（常规化工：组成+T/P+流量）、PETROLEUM（炼油油品：馏程/SARA 四组分/元素分析/金属含量/API）、SOLID（固体颗粒：堆积密度/粒径/休止角/真密度）。缺失物性由 chemicals/thermo 估算并标记 estimated。
_Avoid_: 物流类型（不是分类标签，是输入模式）

**受影响（AFFECTED）**:
交付物某一 Rev 的标记：其快照哈希与所绑记录的当前数据不一致，或所绑记录处于变更中。
_Avoid_: 作废（OBSOLETE 是记录/交付物的终结，AFFECTED 是暂时不一致标记）

**已作废（OBSOLETE）**:
记录的人工弃用终点状态，只能由设计人主动发起，不再自动触发（上游变更走 STALE）。未绑定记录免凭证直接弃用；被交付物绑定的记录须走变更单（RECORD_CANCELLATION）。
_Avoid_: 版本替换（记录无版本）、上游变更回退（那是 STALE）

**位号终身唯一（Tag Lifetime Uniqueness）**:
管道号/设备位号一旦在项目中分配过即终身占用——唯一约束覆盖含 OBSOLETE 在内的全部记录，弃用不释放、永不复用；替代记录必须分配新号。参数变化走 CHANGED 流程，不弃用重建。
_Avoid_: 位号释放、同位号重建

**变更关闭凭证（Change Closure）**:
CHANGED 记录回到 CHECKED 的依据：新版交付物（DELIVERABLE:Rev N）或变更单（CHANGE_NOTICE:CN-xxx）。
_Avoid_: 变更审批（审批是过程，凭证是结果）

**签署矩阵（Signature Matrix）**:
交付物发布时按序执行的签署步骤配置（1–6 级，可含客户批准），驱动交付物的动态状态机。
_Avoid_: 固定四级签署流程

**Rev（版次）**:
交付物的版本代码，由项目版本序列配置生成：A/B/C（开发）→ 0/1/2（正式）→ AS-BUILT（竣工）；X = 作废；后缀 R = 拆除类，A = 正式版后内部检查。
_Avoid_: V主.次.修订（旧方案，已废弃）

**版本目的（Issue Purpose）**:
交付物每次发布必选的目的（Issued for Design / Construction / Use 等），决定该次发布适用的签署矩阵。
_Avoid_: 版本描述（那是自由文本 description）

**编号模板（Numbering Template）**:
项目模板中配置的交付物 doc_no 生成规则：段（项目字段/交付物字段/序号/固定值/手动/日期）+ 分隔符 + 按 scope 的原子序号分配。同类型交付物可按装置等拆分范围创建多份，各自独立 Rev 序列。
_Avoid_: 文件标识（PCS-REQ/DICT/SPEC 是规格文档体系，不是项目交付物编号）、Rev（Rev 独立于 doc_no）

**快照绑定（Snapshot Binding）**:
交付物某一 Rev 对一组计算记录的引用 + 记录哈希（record_hash）。被绑定的记录即锁定，不可原地修改。
_Avoid_: 引用（无哈希防篡改含义）

### 工作区

**工作区（Workspace）**:
三类隔离的数据环境：FORMAL（正式项目）、PERSONAL（个人）、TEMPORARY（临时）。门禁、交付物、变更单只存在于 FORMAL。
_Avoid_: 项目（正式工作区挂在项目下，个人/临时区独立于项目）

**试算数据（Trial Data）**:
个人/临时工作区中的记录，永远 DRAFT。可只读快照引用正式区 CHECKED 数据（不自动同步、不参与变更影响分析）；正式区反向引用试算数据被禁止。导入正式区 = 复制新记录从 DRAFT 重新走门禁，原记录保留并标记已导入。
_Avoid_: 草稿（正式区的 DRAFT 与试算数据语义不同）

### 设备表

**设备记录（Equipment Record）**:
设备表中的记录，是计算记录的一种。设计参数由来源计算记录在 CHECKED 时同步生成并随后者状态联动；商务/采购/图纸/交付/安装/重量字段不受门禁控制、不参与哈希，可直接编辑。
_Avoid_: 设备表（EQUIP_LIST 是交付物，不是记录集合的称呼）

**联动（State Propagation）**:
来源计算记录的状态变化（STALE / CHANGE_PENDING / CHANGED / 变更关闭）自动传导至由它同步出的设备记录。设计参数变更的凭证可由来源记录关闭连带生效。
_Avoid_: 同步（同步是 CHECKED 时复制设计参数，联动是状态传导）
