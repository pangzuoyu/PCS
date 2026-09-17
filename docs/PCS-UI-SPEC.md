PCS-UI-SPEC.md
yaml
文件标识: PCS-UI-SPEC-2026-002
当前版本: V1.0
发布日期: 2026-09-15
适用对象: 前端开发（Claude Code）、UI 走查、测试
依据文档:
  - PCS-REQ-2026-002-SPEC-P0 V1.2
  - PCS-REQ-2026-002-SPEC-P1 V1.2
  - PCS-REQ-2026-002-SPEC-P2 V1.4
  - PCS-REQ-2026-002-SPEC-P3 V1.6
  - PCS-REQ-2026-002-SPEC-P4 V1.5
  - HT-REQ-2026-002 V2.2
  - HT-REQ-2026-002-SUP-001~010
  - HT-REQ-2026-DICT-001 / DICT-002
状态: 冻结，无 TBD
0. 文档目的
本文档是 PCS 前端编码的唯一依据。所有页面、组件、状态、权限、门禁、表单字段、数值格式均以本文档为准。字段类型、接口结构、枚举取值以 OpenAPI 3.1 + Pydantic JSON Schema 为准。本文档与 OpenAPI 冲突时，以 OpenAPI 为准，并在本文档修订记录中登记。

Claude Code 不得自行发明字段、状态、颜色、文案。

1. 设计语言
1.1 定位
PCS 是工艺工程计算工具，不是消费级产品、不是 BI 看板、不是 SaaS 营销页。

设计定位：

工业仪表盘 + 精密仪器面板 + 工程计算软件

三个关键词：

关键词	含义	反例
精密	数值、单位、有效数字、哈希全部精确呈现	四舍五入模糊显示、单位省略
克制	颜色只用于语义，不用于装饰	渐变按钮、彩色卡片、装饰插画
高密度	单屏承载尽可能多的工程数据	大留白、大圆角、大图标
科技感来自：深色底、等宽数字、细网格、状态色、哈希锚定、实时进度，不来自霓虹、玻璃拟态、粒子动效。

1.2 设计原则
数据优先：任何像素让位于数据可读性。

状态可见：任何记录的 9 态门禁、批准进度、哈希、假设标记必须一屏可见。

门禁前置：不可执行的操作直接禁用并给出原因，不做“点击后报错”。

单一事实源：字段、枚举、状态、权限全部来自 Schema，不硬编码。

工程留痕：哈希、版本、Rev、签署人、时间戳在详情页始终可见。

无装饰动效：动效只用于状态变化提示，时长 ≤ 200ms。

1.3 主题
默认深色主题，亮色主题为可选项（P0 不实现，预留令牌）。

深色主题是工程工具的标准形态：长时间盯屏、低亮度环境、数据密度高。

2. 设计令牌（Design Tokens）
所有令牌定义于 src/styles/tokens.css，通过 CSS 变量暴露。禁止在组件中硬编码色值。

2.1 色彩
2.1.1 背景层
令牌	值	用途
--bg-canvas	#0B0F14	应用最底层背景
--bg-panel	#111820	面板、卡片
--bg-elevated	#18222C	弹层、抽屉、下拉
--bg-inset	#0D1319	输入框、代码块、表格斑马纹
--bg-hover	#1C2833	行悬浮
--bg-active	#22303D	选中行
--bg-overlay	rgba(0,0,0,0.6)	模态遮罩
2.1.2 边框
令牌	值	用途
--border-subtle	#1A232D	分隔线
--border-default	#243040	卡片、面板边框
--border-strong	#33455A	输入框聚焦前、表头
--border-focus	#00B4D8	聚焦态
2.1.3 文字
令牌	值	用途
--text-primary	#E6EDF3	主文字
--text-secondary	#8B98A5	次要文字、标签
--text-tertiary	#5A6773	占位、禁用
--text-mono	#C9D1D9	等宽数值、哈希、位号
--text-inverse	#0B0F14	反色文字（按钮）
2.1.4 主色（Accent）
令牌	值	用途
--accent-primary	#00B4D8	主操作、聚焦、链接
--accent-hover	#22C7E8	悬浮
--accent-active	#0093B0	按下
--accent-subtle	rgba(0,180,216,0.12)	选中背景、标签底
主色为工程青，与深色底对比度高但不刺眼。

2.1.5 状态色（记录层 9 态）
状态	令牌	值	用途
DRAFT	--state-draft	#6B7681	灰
IN_APPROVAL	--state-in-approval	#2F81F7	蓝
CHECKED	--state-checked	#2EA043	绿
CHECK_REJECTED	--state-check-rejected	#F85149	红
STALE	--state-stale	#D29922	橙
CHANGE_PENDING	--state-change-pending	#A371F7	紫
CHANGED	--state-changed	#39C5CF	青
REVERSAL_PENDING	--state-reversal-pending	#E3B341	黄
OBSOLETE	--state-obsolete	#484F58	深灰
每个状态色配 -subtle 变体（rgba(...,0.15)）用于标签底色。

2.1.6 语义色
语义	令牌	值
成功	--semantic-success	#2EA043
警告	--semantic-warning	#D29922
危险	--semantic-danger	#F85149
信息	--semantic-info	#2F81F7
假设	--semantic-assumed	#D29922
冲突-BLOCK	--conflict-block	#F85149
冲突-WARN	--conflict-warn	#D29922
冲突-INFO	--conflict-info	#2F81F7
2.1.7 输入项状态色（P1 输入清单）
状态	值
NOT_STARTED	#5A6773
IN_PROGRESS	#E3B341
VERIFIED	#2EA043
ASSUMED	#D29922
NOT_APPLICABLE	#484F58（斜体）
2.2 字体
用途	字体栈
UI	Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
等宽	"JetBrains Mono", "SFMono-Regular", Consolas, monospace
中文	"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif
强制规则：

所有数值、单位、位号、哈希、管道号、设备位号、Rev、doc_no 使用等宽字体。

所有中文正文使用中文栈。

禁止使用衬线字体。

字号：

层级	字号/行高	字重	用途
Display	20/28	600	页面主标题
H1	16/24	600	面板标题
H2	14/20	600	分组标题
Body	13/20	400	正文、表单
Table	12/18	400	表格、列表
Caption	11/16	400	标注、单位、时间
Mono	12/18	400	数值、位号、哈希
2.3 间距
基准 4px。

令牌	值
--space-1	4px
--space-2	8px
--space-3	12px
--space-4	16px
--space-5	24px
--space-6	32px
--space-7	48px
2.4 圆角
工程工具偏直角。

令牌	值	用途
--radius-sm	2px	标签、按钮、输入框
--radius-md	4px	卡片、面板
--radius-lg	6px	弹层（慎用）
--radius-full	999px	仅状态点、头像
2.5 阴影
深色主题下阴影弱化，主要靠边框区分层级。

令牌	值
--shadow-panel	0 1px 0 rgba(255,255,255,0.03) inset
--shadow-elevated	0 8px 24px rgba(0,0,0,0.5)
--shadow-focus	0 0 0 2px rgba(0,180,216,0.4)
2.6 网格
页面背景可选 8px 网格线（--grid-line: rgba(255,255,255,0.02)），仅在计算模块工作区启用，作为“工程制图”氛围，不影响可读性。

表格行高 32px（紧凑）/ 40px（标准）/ 48px（宽松），默认紧凑。

表头高度 36px，固定。

2.7 图标
使用 @ant-design/icons。

尺寸：14px（表格内）/ 16px（按钮）/ 20px（导航）。

状态图标固定映射见 §4.1。

禁止使用装饰性图标、表情符号。

2.8 动效
场景	时长	缓动
悬浮/聚焦	120ms	ease-out
抽屉/弹层	200ms	cubic-bezier(0.4,0,0.2,1)
状态变化高亮	400ms	一次性脉冲
计算进度	持续	线性
禁止：视差、粒子、渐变流动、霓虹发光。

3. 布局与导航
3.1 应用骨架
text
┌──────────────────────────────────────────────────────────────────────┐
│  TopBar (48px)                                                       │
│  [Logo] [项目切换▾] [工作区▾] [单位制▾] [搜索] [通知•] [AI] [用户▾]  │
├────────────┬─────────────────────────────────────────────────────────┤
│            │  PageHeader (56px)                                       │
│  SideNav   │  [面包屑] 页面标题          [状态徽章] [操作区]          │
│  (240px    ├─────────────────────────────────────────────────────────┤
│   可折叠   │                                                          │
│   至 56px) │  Content                                                 │
│            │                                                          │
│            │                                                          │
│            ├─────────────────────────────────────────────────────────┤
│            │  StatusBar (28px)                                        │
│            │  [记录哈希] [版本] [保存状态] [最后更新] [连接状态]      │
└────────────┴─────────────────────────────────────────────────────────┘
3.2 TopBar
元素	行为
Logo	点击回项目总览
项目切换	下拉，显示最近项目 + 搜索
工作区切换	FORMAL 绿标 / PERSONAL 灰标 / TEMPORARY 灰斜体；切换后全局刷新
单位制	显示当前单位制，只读（在 PMS 中修改）
全局搜索	位号 / 物流号 / 管道号 / 设备位号；结果分组
通知	未读数红点；点击打开通知中心抽屉
AI	打开 AI 助手抽屉（P10 预留，先禁用并提示）
用户	用户名 + 角色标签；菜单：个人设置 / 切换主题 / 登出
门禁：非 FORMAL 工作区时，TopBar 显示橙色横幅“试算工作区 · 数据不可签署”。

3.3 SideNav
按 P 阶段分组，可折叠。默认展开当前模块所属分组。

text
▾ 项目中心
   总览
   输入清单
   BEDD
▾ 基础数据
   物流 (SIM)
   物性库 (COMMON)
   管道等级 (PIPE_CLASS)
▾ 计算模块
   闪蒸 (FLASH)
   管道 (PIPE)
   管网 (PIPE_NET)
   机泵 (PUMP)
   容器 (VESSEL)
   分离设备 (SEP_EQUIP)
   安全阀 (PSV)
   换热器 (HEAT)
   调节阀 (CV)
   节流装置 (RESTRICTION)
   火炬系统 (FLARE_SYS)
   冷却塔 (COOL_TOWER)
   湿空气 (PSYCHRO)
   明渠 (OPEN_CHANNEL)
▾ 集成
   设备表 (EQUIP_LIST)
   公用工程 (UTIL)
   复用设备库 (EQUIP_LIB)
   供应商数据
▾ 交付物
   交付物
   变更单
   报表
   报表构建器
▾ 配置 (CONFIG)
   项目模板
   公式
   经验系数
   模板文件
   标准数据库
   复用设备库
▾ 系统
   用户管理
   角色权限
   审计日志
   AI 配置
   系统参数
权限：菜单项按权限隐藏；无权限分组整个隐藏。

徽章：模块名后显示待办数（如 管道 (PIPE) •3）。

3.4 PageHeader
左侧：面包屑 + 页面标题 + 状态徽章。
右侧：操作区，按优先级从右到左排列。

操作按钮规范：

主操作：实心，--accent-primary

次操作：描边

危险操作：红色描边，二次确认

门禁操作：禁用 + Tooltip 说明原因

3.5 StatusBar
固定在内容区底部，等宽字体，显示当前记录上下文：

text
record_hash: a3f9...c21e │ Rev: B │ 保存: 已保存 14:32:08 │ 公式版本: F-REV-2026-03 │ 连接: 正常
点击哈希复制完整值；点击公式版本跳转 CONFIG 对应版本。

3.6 响应式
目标分辨率 ≥ 1920×1080。

最低支持 1366×768：SideNav 自动折叠，表格允许横向滚动。

不支持移动端。

4. 路由表
text
/login
/workspaces
/projects
/projects/:projectId/overview
/projects/:projectId/checklist
/projects/:projectId/pms/bedd
/projects/:projectId/sim/streams
/projects/:projectId/sim/streams/:streamId
/projects/:projectId/sim/import
/projects/:projectId/common/materials
/projects/:projectId/pipe-classes
/projects/:projectId/pipes
/projects/:projectId/pipes/:pipeId
/projects/:projectId/pipe-net
/projects/:projectId/pipe-net/:netId
/projects/:projectId/pumps
/projects/:projectId/pumps/:pumpId
/projects/:projectId/vessels
/projects/:projectId/vessels/:vesselId
/projects/:projectId/sep-equip
/projects/:projectId/psv
/projects/:projectId/psv/:psvId
/projects/:projectId/heat
/projects/:projectId/heat/:heatId
/projects/:projectId/cv
/projects/:projectId/cv/:cvId
/projects/:projectId/restriction
/projects/:projectId/flare
/projects/:projectId/cool-tower
/projects/:projectId/psychro
/projects/:projectId/open-channel
/projects/:projectId/flash
/projects/:projectId/flash/:flashId
/projects/:projectId/equip-list
/projects/:projectId/equip-list/:equipId
/projects/:projectId/util
/projects/:projectId/equip-lib
/projects/:projectId/supplier-data
/projects/:projectId/deliverables
/projects/:projectId/deliverables/:deliverableId
/projects/:projectId/change-notices
/projects/:projectId/change-notices/:noticeId
/projects/:projectId/lineage
/projects/:projectId/notifications
/config/assets
/config/project-templates
/config/formulas
/config/formulas/:formulaId
/config/coefficients
/config/templates
/config/standard-db
/config/pipe-classes
/config/equip-lib
/admin/users
/admin/roles
/admin/audit
/admin/ai
/admin/settings
/reports
/reports/builder
/reports/builder/:reportDefId
/ai/assistant
路由守卫：

未登录 → /login

无项目权限 → 项目选择页

无模块权限 → 403 页

非 FORMAL + 访问交付物/变更单路由 → 403 页并提示“试算工作区不支持”

5. 权限与门禁
5.1 权限组件
tsx
<Can permission="PIPE.CALCULATE">
  <Button>计算</Button>
</Can>
无权限时：

场景	表现
主操作按钮	禁用 + Tooltip 原因
菜单项	隐藏
页面	403 页
表格列	隐藏
权限码从 OpenAPI x-permission 读取，前端不硬编码。

5.2 状态门禁
记录编辑权限由 sign_status 决定：

状态	可编辑	可批注	可签署	可弃用
DRAFT	设计	全部	—	设计
IN_APPROVAL	否	当前步骤	当前步骤	—
CHECKED	否	全部	—	设计/项目负责人
CHECK_REJECTED	设计	全部	—	—
STALE	否（只读）	全部	—	—
CHANGE_PENDING	设计	全部	批准链	—
CHANGED	否	全部	撤销链	—
REVERSAL_PENDING	否	全部	撤销批准链	—
OBSOLETE	否	查看	—	—
STALE 状态下整个表单只读，顶部橙色横幅：

text
⚠ 上游数据已变更，当前结果可能失效。请确认重算后再提交。
5.3 工作区门禁
操作	FORMAL	PERSONAL	TEMPORARY
编辑数据	✅	✅	✅
提交批准	✅	❌ 403	❌ 403
创建交付物	✅	❌ 403	❌ 403
创建变更单	✅	❌ 403	❌ 403
签署	✅	❌	❌
导入正式项目	—	✅	✅
非 FORMAL 时，PageHeader 操作区仅保留“保存”“导入正式项目”。

5.4 物流引用门禁
引用物流时：

物流状态	前端表现
DRAFT	下拉中置灰，Tooltip“物流未校对”
IN_APPROVAL	下拉中置灰，Tooltip“物流校对中”
CHECKED	可选
OBSOLETE	置灰
后端 403 为兜底。

6. 跨模块核心组件
6.1 StateBadge
用途：显示记录/交付物状态。

Props：

ts
interface StateBadgeProps {
  status: RecordSignStatus | DeliverableStatus | StreamSignStatus;
  size?: 'sm' | 'md';
  showIcon?: boolean;   // default true
  showStep?: boolean;   // IN_APPROVAL 时显示 Step n/N
  step?: number;
  depth?: number;
}
渲染：

text
[● CHECKED]                    // sm
[● IN_APPROVAL · Step 2/3]     // md, showStep
样式：

高度：sm 20px / md 24px

圆角：--radius-sm

背景：状态色 -subtle

文字：状态色

左侧 6px 圆点：状态色实心

状态字典（9 态）：

value	label	icon	color
DRAFT	草稿	EditOutlined	state-draft
IN_APPROVAL	批准中	LoadingOutlined	state-in-approval
CHECKED	已批准	CheckCircleOutlined	state-checked
CHECK_REJECTED	已退回	CloseCircleOutlined	state-check-rejected
STALE	数据存疑	WarningOutlined	state-stale
CHANGE_PENDING	变更中	EditOutlined	state-change-pending
CHANGED	已变更	SwapOutlined	state-changed
REVERSAL_PENDING	撤销中	UndoOutlined	state-reversal-pending
OBSOLETE	已作废	StopOutlined	state-obsolete
模块激活子集：

P3 模块（SIM）：DRAFT / IN_APPROVAL / CHECKED / OBSOLETE

P4+ 模块：9 态全集

未激活状态不出现在下拉、过滤器、迁移按钮中。

6.2 ApprovalStepBar
用途：显示批准链进度。

Props：

ts
interface ApprovalStepBarProps {
  currentStep: number;
  totalSteps: number;
  role: string;
  steps: Array<{
    step: number;
    role: string;
    roleLabel: string;
    approver?: string;
    approvedAt?: string;
    decision?: 'APPROVED' | 'REJECTED';
  }>;
}
渲染：

text
①校核 ✓ ── ②审核 ● ── ③审定 ○
当前步骤脉冲高亮；已完成绿色；未开始灰色；退回红色。

6.3 操作按钮组 RecordActions
按状态渲染：

状态	按钮
DRAFT	提交批准 / 保存 / 弃用
IN_APPROVAL	通过 / 退回（当前步骤角色）
CHECKED	变更申请 / 弃用 / 创建交付物
CHECK_REJECTED	修改 / 重新提交
STALE	确认并重算 / 手动调整 / 查看变更详情
CHANGE_PENDING	保存 / 提交变更批准 / 放弃变更
CHANGED	发起撤销 / 关闭凭证
REVERSAL_PENDING	撤销批准 / 撤销驳回
OBSOLETE	只读
按钮权限由 Can 包裹。

6.4 HashBadge
用途：显示 record_hash。

Props：

ts
interface HashBadgeProps {
  hash: string;
  label?: string;
  copyable?: boolean;  // default true
}
渲染：

text
hash: a3f9…c21e  [复制]
等宽字体

短哈希：前 4 + … + 后 4

悬浮显示完整 64 位

点击复制完整值

哈希不匹配时红色

6.5 SnapshotDrawer
用途：查看变更前快照。

内容：

快照时间

快照人

触发原因（STALE / CHANGE_PENDING）

快照数据（只读 JSON 树）

与当前值 diff 视图

按钮：恢复（仅撤销/放弃路径可用）

6.6 LineageGraph
用途：数据血缘可视化。

节点类型：

类型	形状	颜色
物流	圆角矩形	蓝
状态点	小圆	青
设备	六边形	紫
计算记录	矩形	绿
交付物	文档形	橙
假设节点	矩形 + 橙色描边	橙
边类型：

类型	样式
引用	实线
公式计算	虚线
手动覆盖	点线
估算	点划线
DEVICE_TRANSFORMATION	粗实线 + 设备标签
交互：

滚轮缩放

拖拽平移

点击节点：右侧详情面板

双击节点：跳转对应记录

工具栏：向上追溯 / 向下追溯 / 居中 / 导出 PNG

哈希不匹配边：红色高亮

图例：左上角固定。

6.7 ChangeImpactPanel
用途：变更影响分析。

布局：

text
┌─────────────────────────────────────────────┐
│ ⚠ 上游数据已变更                              │
│ 变更源: 物流 S-101 · 流量 50 → 60 m³/h        │
│ 变更人: 张三 · 2026-09-15 14:32              │
├─────────────────────────────────────────────┤
│ 受影响记录 (3)                               │
│ ┌─────────────────────────────────────────┐ │
│ │ ● PIPE  P-101  压降结果    [确认重算]    │ │
│ │ ● PUMP  PU-101 扬程结果    [确认重算]    │ │
│ │ ● UTIL  电耗汇总           [确认重算]    │ │
│ └─────────────────────────────────────────┘ │
├─────────────────────────────────────────────┤
│ [批量确认重算]  [全部暂不处理]                │
└─────────────────────────────────────────────┘
受影响行橙色左边框 + 警告图标。

6.8 InputChecklistPanel
用途：输入清单仪表盘。

顶部统计：

text
完成 42/58  ████████████░░░░  72%
REQUIRED 38/40  CONDITIONAL 4/8  OPTIONAL 0/10
假设 3  未验证 5
列表列：

列	说明
模块	PMS/SIM/PIPE...
输入项	名称
分类	REQUIRED/CONDITIONAL/OPTIONAL
当前值	等宽
单位	
来源	SIM导入/标准库/手动/假设/默认值
状态	颜色标签
验证人	
操作	编辑/验证
筛选：按状态、模块、分类。

假设数据清单：可展开，列出所有 ASSUMED 项及理由。

6.9 WorkspaceSwitcher
下拉项：

text
● 正式项目 · 炼油项目 A          [FORMAL]
○ 我的工作区 · 张三               [PERSONAL]
○ 临时试算 · 2026-09-15           [TEMPORARY]
选择 PERSONAL/TEMPORARY 后：

TopBar 橙色横幅

交付物/变更单菜单隐藏

记录操作区仅保留保存

6.10 ConflictResolver
用途：SIM 物性冲突展示。

三级：

级别	颜色	行为
BLOCK	红	阻止保存，必须处理
WARN	黄	提示，可继续
INFO	蓝	提示
卡片：

text
[BLOCK] 分子量冲突
  用户输入: 58.12 kg/kmol
  计算值:   58.08 kg/kmol
  偏差: 0.07%
  [采用用户值] [采用计算值]
字段优先级：

用户值优先：物性类

计算值优先：molecular_weight / total_mass_flow / total_molar_flow

6.11 AssumedDataMarker
用途：假设数据标识。

渲染：字段旁橙色三角 △

Tooltip：

text
该结果基于假设输入：
年平均气温 = 17.2 °C
来源：默认值
签署确认：签署弹窗顶部显示假设数据清单，必须勾选“已知悉并接受上述假设数据”。

6.12 NumericCell
用途：数值单元格统一渲染。

Props：

ts
interface NumericCellProps {
  value: number | null;
  unit?: string;
  precision?: number;       // 有效数字，默认 6
  precisionType?: 'significant' | 'decimal';
  align?: 'left' | 'right'; // default right
  status?: 'normal' | 'assumed' | 'stale' | 'conflict';
  monospace?: boolean;      // default true
}
渲染：

text
  1.23457e+05  kPa
规则：

默认 6 位有效数字

货币 2 位小数

单位小一号，次要色

null 显示 —

假设：橙色三角

存疑：橙色文字

冲突：红色文字

6.13 UnitLabel
用途：单位展示。

小一号（11px）

次要色

不换行

与数值间距 4px

6.14 EmptyState
用途：空状态。

text
┌─────────────────────┐
│      [图标]         │
│   暂无管道记录       │
│  点击"新建"开始      │
│   [新建管道]        │
└─────────────────────┘
禁止使用插画，使用线性图标。

6.15 LoadingState
表格：骨架屏，3 行

面板：居中 Spin

计算：进度条 + 取消按钮

长任务：后台计算提示 + 可切换模块

6.16 ErrorState
text
┌─────────────────────────────┐
│  [错误图标]                  │
│  加载失败                    │
│  错误码: PCS-4031            │
│  物流未校对，不可引用         │
│  [重试]  [查看详情]          │
└─────────────────────────────┘
错误码必须显示，便于排障。

6.17 DiffViewer
用途：版本对比、快照对比。

左旧右新

字段级 diff

数值：变化高亮

公式：数学表达式 diff

表格：行列 diff

6.18 RevTimeline
用途：交付物 Rev 历史。

text
● Rev C  2026-09-15 14:30  ISSUED_FOR_CONSTRUCTION
│  签署: 校核 李四 ✓ · 审核 王五 ✓ · 审定 赵六 ✓
│  快照: a3f9…c21e  [查看]
● Rev B  2026-09-10 09:15  ISSUED_FOR_REVIEW  [AFFECTED]
│  ...
● Rev A  2026-09-01 10:00  ISSUED_FOR_DESIGN
AFFECTED 标记红色。

6.19 SignatureMatrix
用途：签署矩阵渲染。

列数随矩阵动态

每列显示角色 + 签署状态

已签署显示姓名 + 时间 + 哈希

代录显示“（代录：X）”

当前待签列脉冲高亮

6.20 NotificationCenter
抽屉，右侧滑出，宽 420px。

分组：待办 / 变更 / 系统 / 全部

消息结构：

text
[变更] 物流 S-101 流量已变更
       影响 3 条下游记录
       2026-09-15 14:32
       [查看]
未读左侧蓝点。

7. 模块 UI 规格
7.1 登录页
布局：居中卡片，宽 380px。

元素：

Logo

标题“工艺专用综合计算软件”

用户名输入

密码输入

登录按钮

错误提示

开发/测试环境：显示角色下拉（Mock 认证）。

禁止：注册、找回密码、第三方登录。

7.2 工作区页
列表：卡片或表格。

列	说明
名称	
类型	FORMAL/PERSONAL/TEMPORARY
所有者	
项目	
最后活跃	
保留天数	
操作	进入/导入/删除
7.3 项目列表
列	说明
项目编号	等宽
项目名称	
业主	
地点	
类型	
设计阶段	
单位制	
状态	
创建时间	
操作	进入
操作：新建项目、复制、归档。

7.4 项目总览
卡片区：

项目信息摘要

输入清单进度

待办

最近变更

模块完成度

模块完成度：横向条形图，按模块显示记录数 / 已批准数。

7.5 PMS / BEDD
项目创建向导（4 步）：

模板选择

基本信息

BEDD 录入

确认

BEDD 编辑：分组 Tab。

Tab	内容
气象	温度/湿度/气压/风/降雨/雪/蒸发/雷暴/雾/日照/太阳辐射/土壤/粉尘/海拔
水文地质	潮汐/河流/地质
地震	设防烈度/加速度/分组/场地类别
公用工程	蒸汽/水/空气/氮气/燃料气/燃料油/氢气/化学品/导热油/凝液/电气
排放限值	气体/焚烧/粉尘/废水/噪声/工作区空气
设计准则	设计寿命/操作/运输/噪声
安全消防	消防泵/消防车/泡沫/喷淋/探测/隔离阀/安全淋浴
火炬	背压/辐射
界面条件	进出界区条件表
表单：SchemaForm 驱动（见 §8）。

单位制切换：顶部下拉，切换后所有数值实时转换，弹出提示“已按 1 bar = 100 kPa 转换”。

7.6 输入清单
见 §6.8。

7.7 SIM 物流
7.7.1 物流列表
列	说明
物流号	等宽
名称	
工况	case_type: 正常/末期/开车/调节
相态	
温度	NumericCell
压力	NumericCell
质量流量	NumericCell
状态	StateBadge
来源	SIM导入/手动/Excel/化验
引用	📎×N
操作	查看/校对/变更
筛选：工况、相态、状态、来源。
工具栏：导入 / 新建物流 / 提交校对 / 导出。

7.7.2 物流详情
Tab：

基本信息

组成

物性

状态点

设备连接

血缘

校核记录

基本信息：物流号、名称、描述、相态、工况、来源、状态。

组成：表格，组分名 / 分子式 / 摩尔分率 / 质量分率 / 体积分率；底部合计校验（100±0.5%）。

物性：分组表，来源标记（实验值/估算值/标准值），估算值标 estimated=true。

状态点：

列	说明
标签	
类型	NORMAL/MIN/MAX/ALTERNATE
温度	
压力	
相态	
汽化分率	
操作	查看/编辑
设备连接：上游物流 / 设备类型 / 设备 ID / change_type。

血缘：LineageGraph 局部视图。

7.7.3 导入向导
步骤：

选择格式（PRO/II / 手工 / Excel；HYSYS/Aspen/HTRI 置灰标“后置 P4”）

上传文件

解析预览

列映射（Excel）

校验结果

写入 DRAFT

提交校对

校验结果：

通过项绿色

警告项黄色

错误项红色

阻断项必须处理

Excel 列映射：模板库下拉 + 手动映射 + 保存为模板。

7.8 COMMON 物性库
搜索：名称 / CAS / 分子式。

结果表：

列	说明
名称	
CAS	等宽
分子式	
分子量	
临界温度	
临界压力	
来源	实验值/估算值/标准值
许用应力查询：材料 + 温度 → 插值结果。

毒性/爆炸极限：分类 + 上下限。

7.9 PIPE_CLASS
7.9.1 公司级等级列表
列	说明
ClassID	等宽
ClassName	
MaterialStandard	
CorrosionAllowance	
DesignPressure	
DesignTemperature	
DN 范围	
Sch	
来源	COMPANY_STD/PROJECT
状态	5 态
操作	查看/编辑/作废
7.9.2 等级详情
字段分组：

基本信息

许用应力

DN 系列

Sch 系列

法兰/管件

支管表

版本

许用应力表：可覆盖 COMMON 值，覆盖需审计。

7.9.3 项目级等级
完全继承：引用公司级

基于公司级 fork：snapshot + override

项目新建：source_class_id = NULL

effective 值获取：调用 /effective 端点，不依赖 pipe_class 字段。

7.9.4 符号表管理
列	说明
符号	
描述	
介质	
来源	公司/项目
操作	
7.9.5 管道代码格式设计器
拖拽式段编辑器：

段类型：

类型	说明
enum	枚举段
stream_symbol	物流符号
auto_increment	自增序号
free_text	自由文本
constant	常量
delimiter	分隔符
预览：实时生成示例代码。

校验：9 条 FMT 规则实时提示。

7.10 CONFIG
7.10.1 资产列表
按 6 类分组，卡片或表格。

列	说明
名称	
类别	CATEGORY_1~6
当前版本	
状态	草稿/审批中/已发布/已作废
更新人	
更新时间	
操作	查看/编辑/审批/版本
7.10.2 公式编辑器
布局：左编辑右预览。

编辑区：

公式名

模块

表达式（代码编辑器，语法高亮）

参数表（名称/单位/描述/默认值）

preconditions 列表

标准来源

单元测试用例

预览区：

LaTeX 渲染

输入测试参数 → 实时结果

单元测试运行结果

preconditions 编辑：

变量来源：input.* / params.* / result

违反策略：REJECT（V1 固定）

溯源校验：params.* 必须可溯源到系数库

不支持：跨字段算术约束可视化编辑。

7.10.3 系数表编辑器
表格编辑

条件分行

批量修改

来源标注

版本对比

7.10.4 模板文件管理
上传 .dotx / .xltx

占位符自动解析

缺失映射提示

版本列表

7.10.5 标准数据库
Excel 导入向导

数据预览

来源标注

版本管理

7.10.6 项目模板
输入清单模板

默认单位制

默认模块

默认管道等级

BEDD 默认结构

版本序列配置

签署矩阵绑定

记录批准深度

物流校对深度

编号模板

客户代录配置

撤销批准角色

7.10.7 审批面板
待审批列表

版本对比

审批意见

双重审批标记（公式）

7.11 P4 计算模块
7.11.1 FLASH
输入：

物流选择（仅 CHECKED）

热力学方法（PR/SRK/NRTL/IAPWS-IF97）

计算类型（PT/PH/PS/泡点/露点）

T/P 或 H/S

结果：

汽化分率

气液相组成

焓熵

K 值表

操作：写回状态点 / 保存 / 提交批准。

不收敛时：红色警告 + 建议切换方法。

7.11.2 PIPE
输入表单：

分组	字段
物流	物流选择、状态点
管道	管道号、长度、起点、终点、PID 引用
管件	管件类型 / 数量 / 尺寸
设计条件	设计压力、设计温度、腐蚀裕量
等级	管道等级（来自项目绑定）
绝热	绝热代号、厚度、伴热
其他	粗糙度、允许压降
计算结果 Tab：

管径

壁厚

压降

流速/流型

两相流（如有）

管道一览表

管道一览表列（完整）：

序号 / 管道号 / 尺寸 / 材料等级 / 介质代号 / 介质名称 / 相态 / 流体分类 / 毒性级别 / 管道级别 / 绝热代号 / 绝热厚度 / 涂漆代号 / 伴管类型 / 维持温度 / PID 图号 / 起点 / 终点 / 正常操作压力 / 最大操作压力 / 正常操作温度 / 最大操作温度 / 备用工况 / 设计压力 / 真空 / 设计温度 / 设计最小温度 / 压力管道类别 / 试验介质 / 试验压力 / NDT 方法 / NDT 比例 / NDT 技术等级 / 泄漏试验介质 / 泄漏试验压力 / 检查等级 / 清洗方法 / 应力分析级别 / 备注。

design_stage：

BASIC：≤30 列简化

DETAIL：完整列

默认 BASIC，切换器在工具栏。

出口物流：计算完成提示“已创建出口物流 S-102（DRAFT，待校对）”。

7.11.3 PIPE_NET
拓扑编辑器：

画布

节点（设备/分支）

管段（管道号/管径/管长/管件）

从 EQUIP_LIST 自动生成

结果：

收敛日志

流量分配

各管段压降

迭代次数

不收敛：红色 + 最后迭代状态。

7.11.4 PUMP
输入：

吸入侧：容器压力、液位、管径、管件

排出侧：容器压力、静压头、管径、管件

物性：来自 SIM

流量：正常/最小/设计

效率：泵效率、电机效率

控制阀：压降分配

结果 Tab：

扬程

NPSH

功率

设计压力

控制阀

等效长度

压降明细

泵数据表

design_stage：

BASIC：≤30 列

DETAIL：完整（684 行 × 43 列）

出口物流：创建 PUMP_WORK 类型出口物流。

7.12 设备计算（P5/P6）
统一页面模式：

text
PageHeader: [状态徽章] [提交批准] [弃用]
├── 输入表单（SchemaForm）
├── 计算按钮
├── 结果卡片区
├── 结果表格
└── 血缘 / 同步设备表
各模块特有字段以 OpenAPI Schema 为准。

7.13 EQUIP_LIST
列表：

列	说明
位号	等宽
类型	TypeCode
描述	
包号	
单元	
来源	PUMP/VESSEL/HEAT/PSV/CV/MANUAL
计算状态	
签署状态	StateBadge
实际数据状态	
操作	
筛选：类型 / 来源 / 状态 / 包号 / 单元。

详情 Tab：

设计参数

采购

交付

安装

图纸

实际数据

血缘

同步按钮：从各模块同步。

沉淀按钮：提交到 EQUIP_LIB。

7.14 供应商数据
录入：手动 / Excel 批量。

比对结果：

列	说明
设备位号	
对比项	
设计值	
实际值	
偏差	
结论	合格/警告/不合格
偏差报告：导出 PDF/Excel。

不合格：红色，禁止标记“已确认”。

校核流程：设计提交 → 校核通过 → 更新下游。

7.15 UTIL
Tab：

电耗汇总

热负荷汇总

公用工程平衡

综合能耗

冷却塔

排水

表格：按介质分组，设计值 / 实际值切换。

7.16 EQUIP_LIB
检索：

工艺条件模糊搜索

参数区间

相似度计算

结果：

列	说明
设备类型	
规格	
材质	
重量	
标准图号	
相似度	
原项目	
投用日期	
相似度 ≥90% 推荐，80~90% 需校核，<80% 仅展示。

limit ≤ 200，分页。

7.17 REPORT
生成：

选择模板

选择数据范围

预览

生成

下载

输出：

Word

Excel

PDF（含二维码）

假设数据声明页

签署页

7.18 REPORT_BUILDER
布局：三栏。

text
┌──────────┬──────────────┬──────────────┐
│ 数据源树  │ 已选字段      │ 过滤条件      │
│ + 字段    │ 拖拽排序      │ AND/OR 分组   │
│          │ 别名/显隐     │ 操作符选择    │
├──────────┴──────────────┴──────────────┤
│ 预览（前 N 条）                          │
├──────────────────────────────────────────┤
│ [保存] [发布] [导出]                      │
└──────────────────────────────────────────┘
操作符：EQ / NEQ / GT / GTE / LT / LTE / IN / NOT_IN / CONTAINS / STARTS_WITH / ENDS_WITH / IS_NULL / IS_NOT_NULL / BETWEEN / LIKE。

报表定义管理：列表 + 版本 + 共享范围。

7.19 签署 / 变更 / 血缘
7.19.1 签署
记录层：见 §6.3

交付物层：RevTimeline + SignatureMatrix

代录客户批准：弹窗 + 附件 + 二次认证 + “（代录：X）”标注

批注面板：右侧抽屉

状态时间线：底部

待办：独立页

通知中心：见 §6.20

7.19.2 变更
受影响橙色高亮

变更清单

对比面板

确认与重算

7.19.3 血缘
见 §6.6。

7.20 ADMIN
用户管理（AD 同步）

角色分配

审计日志（查询 + 导出）

AI 开关

系统参数

Prompt 模板

7.21 AI 助手
右下角悬浮入口

抽屉对话面板

意图识别 / 知识检索 / 相似设备 / 解释 / 文档解析

结果必须人工确认

审计留痕

P10 前禁用，Tooltip“AI 功能未启用”。

8. 表单 Schema 驱动
8.1 事实来源
Pydantic Schema 为唯一事实来源。

DICT Markdown 仅为参考，不作为字段依据。

前端从 model_json_schema() 获取字段定义。

uiSchema 独立控制布局，不侵入业务模型。

8.2 组件
tsx
<SchemaForm
  schema={jsonSchema}
  uiSchema={uiSchema}
  value={value}
  onChange={setValue}
/>
8.3 控件映射
JSON Schema	控件
string	Input
string + format=date	DatePicker
string + format=date-time	DateTimePicker
string + enum	Select
number	InputNumber + 单位
integer	InputNumber
boolean	Switch
array	Table / List
object	Collapse / Card
object + x-json	JsonEditor
string + x-mono	Input（等宽）
8.4 uiSchema 扩展
json
{
  "field": {
    "ui:group": "设计条件",
    "ui:order": 10,
    "ui:widget": "select",
    "ui:unit": "MPaG",
    "ui:readonly": true,
    "ui:help": "来自 PMS"
  }
}
8.5 CI 硬性
表单 ↔ Pydantic Schema 静态对比

漂移即 fail

禁止硬编码字段名，除非 ≤3 且永不变化

9. API 契约与 Mock
9.1 必需资料
Claude Code 编码前必须拿到：

OpenAPI 3.1 完整文件（按模块拆分）

Pydantic JSON Schema + uiSchema

枚举字典 JSON（value/label/color/icon/order）

状态机迁移表（含权限、前置条件、副作用）

权限矩阵 CSV

统一错误码表

请求/响应示例

Mock Server + Seed 数据

文件上传/异步任务/通知规范

前端契约冻结清单

9.2 枚举字典格式
json
{
  "RecordSignStatus": [
    { "value": "DRAFT", "label": "草稿", "color": "#6B7681", "icon": "EditOutlined", "order": 1 },
    { "value": "IN_APPROVAL", "label": "批准中", "color": "#2F81F7", "icon": "LoadingOutlined", "order": 2 }
  ]
}
9.3 统一响应
json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "warnings": [],
  "request_id": "..."
}
9.4 错误结构
json
{
  "code": "PCS-4031",
  "message": "物流未校对，不可引用",
  "field": "stream_id",
  "request_id": "..."
}
9.5 分页
json
{
  "items": [],
  "total": 100,
  "page": 1,
  "page_size": 50
}
9.6 Mock 覆盖
每个状态至少一条样本：

项目、BEDD、物流、状态点

管道、泵、容器、换热器、安全阀

设备表、供应商数据、UTIL

配置资产、公式、系数、模板、管道等级、符号表、代码格式

用户、角色、签署矩阵、变更单、血缘图

10. 裁决结论（无 TBD）
项	结论	UI 落地
StreamSignStatus	9 态全集；P3 活跃 4 态；P4 起 9 态	StateBadge 统一字典，按模块过滤
case_type	双层不合并：streams 物流级；state_points 状态点级	列表按 streams.case_type；详情状态点 Tab 按 state_points.case_type
design_stage	BASIC/DETAIL，默认 BASIC	PUMP/VESSEL/PSV 表头切换
P4-OPEN-008	采纳 SUP-008 V1.1：piping_results +12、pump_results +4、two_phase_results 13	结果表新增列 + 两相流 Tab
P3-OPEN-005	采纳 Excel 导入，5 类 Sheet	导入向导 Excel 入口
preconditions	REJECT-only；不支持跨字段	公式编辑器 preconditions 区
INT-2 契约	pipe_class 恒 null 不作为依赖；改用 /effective	项目等级详情调 effective
equip-lib limit	≤200，分页	检索组件默认 50
假设数据	ASSUMED/NOT_STARTED 视为假设	橙色三角 + 签署确认
工作区门禁	非 FORMAL 隐藏批准/交付物/变更单	全局门禁
AI 结果	必须人工确认	确认填入按钮
P0-OPEN-003	静默刷新 + 失败弹窗	请求拦截器
P1-OPEN-001	统一二次认证弹窗	签署/代录
P1-OPEN-002	归档前 7 天提醒	通知中心
P1-OPEN-003	变更后 1 分钟内扫描	通知延迟
P2-OPEN-003	不支持会签	单人审批面板
P3-OPEN-001	P3 仅 PRO/II + 手工 + Excel；HYSYS/Aspen/HTRI 后置 P4	导入格式置灰
P3-OPEN-004	Pydantic Schema 为事实来源；uiSchema 用 x-rjsf-*	SchemaForm
P4-OPEN-002	HI 9.6.7-2015	PUMP 结果
P4-OPEN-003	Dukler I 首选，L-M 交叉验证	PIPE 两相流 Tab
P4-OPEN-004	粗糙度默认 0.046mm，CONFIG 可配	PIPE 默认值
11. 编码顺序与验收
11.1 阶段划分
阶段	内容	验收
S0	壳工程：布局、路由、主题、令牌、权限、错误页	页面可访问、路由正确、主题令牌生效
S1	跨模块组件：StateBadge、ApprovalStepBar、HashBadge、LineageGraph、ChangeImpactPanel、InputChecklistPanel、WorkspaceSwitcher、ConflictResolver、AssumedDataMarker、NumericCell、RevTimeline、SignatureMatrix、NotificationCenter	组件独立可测，Storybook 全覆盖
S2	PMS / BEDD / 输入清单	向导可用、SchemaForm 驱动
S3	SIM / COMMON	列表/详情/导入/校对可用
S4	PIPE_CLASS	等级/符号表/格式设计器
S5	CONFIG	六类资产 + 审批 + 版本 diff
S6	P4 计算模块	FLASH/PIPE/PIPE_NET/PUMP
S7	P5/P6 计算模块	设备计算
S8	EQUIP_LIST / UTIL / EQUIP_LIB / 供应商	集成
S9	REPORT / REPORT_BUILDER	报表
S10	签署 / 变更 / 血缘	工作流
S11	ADMIN / AI	系统
11.2 每阶段验收
页面可访问

权限正确

状态正确

Mock 数据完整

与 OpenAPI 类型一致

无硬编码字段

无硬编码色值（用令牌）

数值/单位/哈希等宽

门禁前置

空/加载/错误三态齐全

11.3 禁止事项
发明字段、状态、颜色、文案

硬编码字段名（除 ≤3 且永不变化）

硬编码色值

使用非令牌间距

使用装饰性图标、插画

使用渐变、玻璃拟态、粒子

自动提交 AI 结果

在非 FORMAL 工作区显示签署操作

12. 附录
12.1 状态图标映射
状态	图标
DRAFT	EditOutlined
IN_APPROVAL	LoadingOutlined
CHECKED	CheckCircleOutlined
CHECK_REJECTED	CloseCircleOutlined
STALE	WarningOutlined
CHANGE_PENDING	EditOutlined
CHANGED	SwapOutlined
REVERSAL_PENDING	UndoOutlined
OBSOLETE	StopOutlined
12.2 数值格式规则
类型	精度	示例
一般数值	6 位有效数字	1.23457e+05
货币	2 位小数	12345.67
温度	1 位小数	25.0
压力	3 位有效数字	1.01
流量	4 位有效数字	50.00
哈希	8 位短哈希	a3f9…c21e
位号	原样	P-101A
Rev	原样	B
doc_no	原样	3110.701.1
12.3 常用文案
场景	文案
未校对	物流未校对，不可引用
试算区	试算工作区 · 数据不可签署
STALE	上游数据已变更，当前结果可能失效
假设	该结果基于假设输入
门禁	当前状态不允许此操作
无权限	无权限执行此操作
AI 未启用	AI 功能未启用
12.4 修订记录
版本	日期	修改	编制
V1.0	2026-09-15	初始版本，冻结全部裁决	联合项目组
V1.1	2026-09-17	P5-1-4 VESSEL / P5-2-4 SEP_EQUIP / P5-3-6 PSV 设备计算 Page §7.11.3-5：①VESSEL CalculateRequest 由扁平工艺字段改为嵌套 sizing{SizingInputSchema} + hydraulics{HydraulicsInputSchema}（app/api/v1/vessel.py:46-78）；②SEP_EQUIP / PSV source_stream_id+device_type+params 扁平结构对齐后端 OpenAPI；③StateBadgeModule 扩展 +VESSEL/+SEP_EQUIP/+PSV（4 态子集）；④V1.0 SPEC §7.11.3-5 详细字段章节暂缺，本期仅落地导航与最小 Page 渲染，详细字段以 plan PCS-PLAN-P5-DEVICE-EQUIPMENT.md + 后端 OpenAPI 为准，SPEC 详细字段章节 P5-3 闭环后追加（TODO-2026-09-17-01）。	Claude Code
文档结束。

本文件为 PCS 前端编码的唯一 UI 依据。字段、类型、枚举、错误码以 OpenAPI + JSON Schema 为准。冲突时以 OpenAPI 为准，并登记修订。
