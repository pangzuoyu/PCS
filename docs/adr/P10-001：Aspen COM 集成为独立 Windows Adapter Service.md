P10-001：Aspen COM 集成为独立 Windows Adapter Service
项	内容
ADR 编号	P10-001
标题	Aspen COM 集成为独立 Windows Adapter Service
状态	Proposed
日期	2026-10-12
决策人	架构负责人 / 项目经理
关联文档	P10 SPEC V1.3、开发计划 V1.4 §10.6、P8-004、SUP-001 §3.3.13、SUP-002 V1.4、SUP-003、SPEC-P3（SIM）、SPEC-P4（FLASH/PIPE/PIPE_NET/PUMP）、SPEC-P5（VESSEL/SEP_EQUIP/PSV/HEAT）
影响范围	架构扩展点、AI 预留接口、SIM 数据来源、部署拓扑、CI/CD、运维、审计
实施阶段	P10 只预留接口与本 ADR；Adapter Service 实现规划为后续独立阶段
1. 背景与问题
1.1 业务背景
工艺专用综合计算软件需要引入 Aspen Plus / HYSYS 作为外部工艺模拟计算引擎，用于：

复杂流程模拟与收敛求解；

物流物性、相平衡、反应数据的高精度来源；

与 SIM 模块现有 PRO/II 解析结果交叉验证；

为 FLASH、PIPE、PUMP、VESSEL、PSV、HEAT 等下游模块提供权威输入。

同时，未来希望引入 AI 辅助（自然语言生成 Aspen 输入、解释输出、异常诊断、参数推荐），但 AI 不参与确定性计算，不替代签署动作。

1.2 技术约束
Aspen Plus / HYSYS 的自动化接口为 COM（ActiveX Automation），具有以下约束：

约束	说明
Windows-only	COM 是 Windows 技术，Aspen 运行于 Windows Server / 桌面
进程外服务器	Aspen COM Server 可以是进程外（apwn.exe），支持外部程序通过 COM 通信
许可证	Token 制许可，并发实例消耗许可证，存在并发上限
稳定性	Aspen 进程可能崩溃、内存泄漏、弹窗阻塞
版本敏感	Aspen 版本、模型文件、Python 解释器位数（32/64 位）必须匹配
性能	单次计算可能耗时数分钟，需异步执行
1.3 主后端现状
主后端架构为：

Linux Docker 容器

FastAPI + Gunicorn

ARQ Worker 后台任务

PostgreSQL 16 + pgvector

Redis（缓存、任务队列、编辑锁、AI 审计队列）

PgBouncer 连接池

Nginx 反向代理

Prometheus / Grafana / ELK 可观测性

1.4 问题
如果直接在 FastAPI 后端进程内调用 Aspen COM：

问题	后果
后端必须运行于 Windows	破坏 Docker/Linux 部署，CI/CD 不可行
COM 调用阻塞主进程	API 响应变慢，影响 ≥200 并发
Aspen 崩溃传染	后端进程受影响，可用性下降
许可证并发冲突	与 Web 并发模型不匹配
跨平台测试困难	CI 无 Aspen，E2E 无法自动执行
安全边界模糊	Aspen 文件、许可证、内网访问需隔离
AI 辅助难接入	AI 与 COM 耦合，无法复用 OutboundAIClient
2. 决策
将 Aspen COM 自动化封装为独立的 Windows Adapter Service，主后端通过异步队列与 Adapter 通信。AI 仅做辅助，走现有 OutboundAIClient，人工确认后才执行或写入。

具体决策：

独立 Windows Adapter Service：作为独立进程/服务运行于 Windows Server，独占 COM 句柄与 Aspen 许可证。

异步通信：主后端通过 ARQ 任务队列提交计算请求，Adapter 执行后写回结果。必要时提供内部 HTTP 健康检查与状态查询。

进程隔离：每个 Aspen 计算任务使用独立 Aspen 进程，避免任务间干扰；Adapter 管理进程池与许可证。

稳定性保障：看门狗、超时、重试、崩溃自动重启、弹窗抑制（suppress_dialogs(True)）。

AI 辅助边界：

AI 不直接调 Aspen COM；

AI 调用经 OutboundAIClient，递归脱敏，写 ai_audit_log；

AI 响应固定 requires_confirmation: true；

AI 生成的 Aspen 输入必须人工确认后才由 Adapter 执行。

数据接入：Aspen 结果作为物流/设备/能耗数据来源，导入现有 Streams、EquipmentList、UtilSummary 等表，进入现有两层状态机与数据血缘。

审批与签署：Aspen 结果不绕过签署、审批、变更单、哈希锚定。

CI/CD 策略：CI 使用 Mock Adapter；真实 Aspen E2E 在专用 Windows 测试环境执行。

文件生命周期：复用 P8-004 的任务队列与文件生命周期决策，Aspen 输入/输出文件纳入统一文件管理与归档策略。

P10 阶段范围：P10 只预留 AI 接口与 ADR，不实现 Aspen Adapter；接口契约在本 ADR 中冻结。

3. 备选方案
方案 A：后端直接调用 COM
在 FastAPI 后端进程内使用 pywin32 / win32com.client 调用 Aspen。

否决理由：

后端必须运行于 Windows，破坏 Docker/Linux 部署；

COM 阻塞主进程，无法支撑 ≥200 并发；

Aspen 崩溃传染后端，可用性下降；

CI/CD 无法自动执行；

许可证并发不可控；

安全边界模糊。

方案 B：Windows 上跑完整后端
后端整体部署到 Windows Server，直接调 COM。

否决理由：

部署分裂，与现有 Linux Docker 架构冲突；

CI/CD、容器化、PgBouncer、Prometheus/Grafana/ELK 生态不匹配；

运维成本高，跨平台测试困难；

AI 预留接口无法复用现有中间件。

方案 C：独立 Windows Adapter Service（采纳）
主后端保持 Linux Docker；

Adapter Service 独立部署于 Windows Server；

通过 ARQ 队列/内部 HTTP 异步通信；

AI 走 OutboundAIClient，人工确认。

采纳理由：隔离 Windows/Linux，许可证与并发可控，崩溃隔离，CI 用 Mock，真实 E2E 在专用环境，AI 辅助可扩展，安全边界清晰。

方案 D：云端 Aspen 服务
使用第三方 Aspen 云服务。

否决理由：

私有化强制，禁止外部 API；

数据脱敏与内网 CIDR 要求；

许可证、版本、模型文件不可控；

与公司安全策略冲突。

4. 理由
架构隔离：Windows 与 Linux 分离，主后端不变，Docker/CI/CD 不受影响。

许可证可控：Adapter 独占 COM 句柄与许可证，实现许可感知队列。

稳定性：崩溃隔离、看门狗、超时、重试、自动重启。

可观测：Adapter 暴露健康检查与指标，纳入 Prometheus/Grafana。

AI 辅助可扩展：AI 走现有 OutboundAIClient，审计、脱敏、CIDR 校验、人工确认一致。

数据血缘一致：Aspen 结果进入现有两层状态机、哈希锚定、变更影响分析。

测试策略清晰：CI 用 Mock，真实 E2E 在专用 Windows 环境。

文件生命周期复用：P8-004 的任务队列与文件管理策略可直接复用。

私有化合规：Aspen 与 LLM 均内网部署，禁止外部 API。

5. 后果
5.1 正面后果
主后端架构不变，Docker/Linux 部署、CI/CD、可观测性保持。

Aspen 计算异步执行，不阻塞 API。

许可证与并发可控，避免耗尽。

崩溃隔离，Adapter 可自动重启。

AI 辅助接口可复用现有中间件。

结果进入现有审批、签署、变更影响分析。

5.2 负面后果
新增 Windows 节点与运维成本。

新增 Adapter Service 代码库与部署流程。

需要新增数据表与接口契约。

需要专用 Windows 测试环境。

Aspen 版本、Python 位数、许可证需固定管理。

CI 依赖 Mock，真实集成测试需专用环境。

5.3 需要新增/修改的内容
类别	内容
数据表	aspen_runs、aspen_results、aspen_files、aspen_audit（或复用 P8-004 文件表扩展）
接口	Adapter 内部 API 契约（提交、查询、取消、健康）
AI 接口	/api/v1/ai/aspen/generate-input、/explain-output、/diagnose、/recommend（P10 返回 501）
部署	Windows Adapter 部署文档、许可证配置、看门狗服务
监控	Adapter 健康检查、许可证使用、任务队列深度
文档	架构文档、Runbook、管理员手册、用户手册（Aspen 章节）
ADR	本 ADR；引用 P8-004
CI/CD	Mock Adapter、契约测试、专用 Windows E2E 环境
6. 风险与缓解
风险	影响	缓解措施
许可证 Token 不足	任务排队或失败	许可感知队列；与 IT 确认 Token 数；监控许可证使用
Aspen 崩溃	任务失败、进程泄漏	看门狗、超时、自动重启、任务隔离
COM 弹窗阻塞	任务挂起	suppress_dialogs(True)；进程级隔离
版本 / 32-64 位不匹配	COM 注册失败	固定 Aspen 与 Python 版本；环境版本管理
AI 幻觉生成错误输入	计算错误或安全风险	人工确认；禁止自动执行；审计
数据泄露	合规风险	递归脱敏、内网 CIDR、审计、文件访问控制
跨平台通信故障	任务失败	异步队列、重试、幂等、死信队列
文件生命周期混乱	磁盘膨胀、归档失败	复用 P8-004 文件生命周期决策
测试环境缺失	真实集成无法验证	专用 Windows 测试环境；Mock 覆盖 CI
运维复杂度上升	故障响应慢	Runbook、监控、应急联系人、自动重启
7. 实施约束
P10 阶段范围：

只预留 AI 接口（返回 501）与本 ADR；

不实现 Aspen Adapter Service；

不修改 P10 SPEC V1.3 正文。

接口契约先冻结：

Adapter 内部 API 契约在本 ADR 中定义；

Mock 契约与真实契约一致；

契约变更走 ADR 或变更单。

不绕过现有架构：

Aspen 结果进入现有两层状态机；

不绕过签署、审批、变更单、哈希锚定；

AI 走 OutboundAIClient。

文件生命周期复用 P8-004：

Aspen 输入/输出文件纳入统一文件管理；

保留、归档、清理策略复用 P8-004。

私有化强制：

Aspen 与 LLM 均内网部署；

禁止外部 API；

内网 CIDR 校验。

许可证合规：

与 IT 确认许可证策略；

许可感知队列；

监控与告警。

8. Adapter Service 接口契约（草案）
8.1 通信方式
主后端通过 ARQ 任务队列提交计算请求；Adapter 通过 Redis 消费任务，执行后写回结果。

备选：内部 HTTP API（仅内网），用于状态查询与健康检查。

8.2 任务模型
json
{
  "task_id": "uuid",
  "project_id": "uuid",
  "user_id": "uuid",
  "aspen_version": "V14",
  "model_file": "path/to/model.bkp",
  "input_file": "path/to/input.inp",
  "input_hash": "sha256:...",
  "ai_assisted": false,
  "ai_request_id": null,
  "requires_confirmation": true,
  "created_at": "2026-10-12TXX:XX:XXZ"
}
8.3 结果模型
json
{
  "task_id": "uuid",
  "status": "SUCCESS | FAILED | TIMEOUT | CANCELLED",
  "started_at": "...",
  "finished_at": "...",
  "aspen_version": "V14",
  "output_files": ["path/to/output.json", "path/to/output.csv"],
  "output_hash": "sha256:...",
  "streams": [...],
  "equipment": [...],
  "energy": [...],
  "warnings": [...],
  "errors": [...],
  "log_file": "path/to/aspen.log"
}
8.4 健康检查
端点	说明
GET /health	Adapter 存活
GET /health/aspen	Aspen COM 可用性
GET /health/license	许可证状态
GET /metrics	Prometheus 指标
8.5 状态查询
端点	说明
GET /tasks/{task_id}	任务状态
POST /tasks/{task_id}/cancel	取消任务
9. AI 辅助接口（P10 预留）
接口	说明	P10 状态
POST /api/v1/ai/aspen/generate-input	自然语言生成 Aspen 输入	501
POST /api/v1/ai/aspen/explain-output	解释 Aspen 输出	501
POST /api/v1/ai/aspen/diagnose	异常诊断	501
POST /api/v1/ai/aspen/recommend	参数推荐	501
约束：

全部走 OutboundAIClient；

递归脱敏；

写 ai_audit_log；

内网 CIDR 校验；

响应固定 requires_confirmation: true；

人工确认后才由 Adapter 执行或写入。

10. 数据模型（草案）
10.1 aspen_runs
字段	类型	说明
run_id	UUID	主键
project_id	UUID	项目
user_id	UUID	触发用户
task_id	UUID	任务 ID
aspen_version	TEXT	Aspen 版本
model_file	TEXT	模型文件路径
input_file	TEXT	输入文件路径
input_hash	TEXT	输入哈希
output_hash	TEXT	输出哈希
status	TEXT	SUCCESS/FAILED/TIMEOUT/CANCELLED
started_at	TIMESTAMPTZ	开始时间
finished_at	TIMESTAMPTZ	结束时间
ai_assisted	BOOLEAN	是否 AI 辅助
ai_request_id	TEXT	AI 请求 ID
created_by	UUID	TimestampMixin
created_at	TIMESTAMPTZ	TimestampMixin
updated_at	TIMESTAMPTZ	TimestampMixin
10.2 aspen_results
字段	类型	说明
result_id	UUID	主键
run_id	UUID	关联 aspen_runs
result_type	TEXT	STREAM/EQUIPMENT/ENERGY
payload_json	JSONB	结果数据
created_at	TIMESTAMPTZ	创建时间
10.3 aspen_files
复用 P8-004 文件生命周期决策，或扩展：

字段	类型	说明
file_id	UUID	主键
run_id	UUID	关联 aspen_runs
file_type	TEXT	INPUT/OUTPUT/LOG
file_path	TEXT	路径
file_hash	TEXT	哈希
retention_until	TIMESTAMPTZ	保留截止
created_at	TIMESTAMPTZ	创建时间
10.4 aspen_audit
字段	类型	说明
log_id	UUID	主键
run_id	UUID	关联 aspen_runs
user_id	UUID	用户
action	TEXT	SUBMIT/CANCEL/CONFIRM
ai_request_id	TEXT	AI 请求 ID
timestamp	TIMESTAMPTZ	时间
11. 部署拓扑
text
┌──────────────────────────────────────────────────────┐
│              主后端（Linux Docker）                    │
│  FastAPI + Gunicorn + ARQ Worker + PostgreSQL         │
│  Redis + PgBouncer + Nginx + Prometheus/Grafana/ELK   │
└──────────────────────┬───────────────────────────────┘
                       │ ARQ 队列 / 内部 HTTP
                       ▼
┌──────────────────────────────────────────────────────┐
│        Aspen Adapter Service（Windows Server）         │
│  - 独占 COM 句柄与 Aspen 许可证                        │
│  - 许可感知队列、看门狗、超时、重试                     │
│  - 健康检查与 Prometheus 指标                          │
└──────────────────────┬───────────────────────────────┘
                       │ COM
                       ▼
┌──────────────────────────────────────────────────────┐
│              Aspen Plus / HYSYS                       │
│              （独立进程，按任务隔离）                   │
└──────────────────────────────────────────────────────┘

预留（后续阶段）：
┌──────────────────────────────────────────────────────┐
│  GPU 服务器 / Ollama/vLLM / LangChain                  │
│  AI 辅助，走 OutboundAIClient，人工确认                │
└──────────────────────────────────────────────────────┘
12. CI/CD 与测试策略
环境	策略
CI（Linux）	使用 Mock Adapter，契约测试
测试环境（Linux）	Mock Adapter，E2E 覆盖 AI 501、审计
专用 Windows 测试环境	真实 Aspen，E2E 覆盖 Aspen 计算
生产环境	Adapter Service + Aspen，监控与告警
Mock Adapter 契约与真实契约一致，契约变更走 ADR 或变更单。

13. 未来演进
支持 HYSYS、Aspen Dynamics：Adapter 扩展多引擎适配。

gRPC 替代 HTTP：若性能或流式需求增加。

AI Agent 编排：AI 生成输入 → 人工确认 → Adapter 执行 → AI 解释输出。

Aspen 版本管理：多版本共存与切换。

许可证池化：多 Adapter 节点共享许可证池。

云化评估：若私有化政策变化，评估云端 Aspen。

与 P8-004 深度整合：文件生命周期、任务队列统一。

数据血缘扩展：Aspen 结果纳入哈希链，上游变更触发 STALE。

14. 与现有 ADR 的关系
ADR	关系
P8-004（报表任务队列与文件生命周期）	引用，不修改；Aspen 文件生命周期复用其决策
ADR-0003 / ADR-0005（变更影响分析）	引用，不修改；Aspen 结果纳入哈希链与变更影响分析
P10 SPEC V1.3	不修改正文；本 ADR 作为扩展点
开发计划 V1.4 §10.6	本 ADR 作为知识转移交付物
15. 落地建议
不修改 P8-004，也不修改 P10 SPEC V1.3 正文。

在 开发计划 V1.4 §10.6 知识转移中新增交付物：P10-001 Aspen COM Adapter ADR。

在 架构文档中引用 P10-001。

若必须让 P10 SPEC 引用，走变更单出 V1.4 勘误，只加一行“Aspen Adapter 预留见 P10-001”。

后续阶段启动 Aspen Adapter 实施前，本 ADR 状态从 Proposed 升为 Accepted。

实施前确认 P10-OPEN-001（GPU 资源）、P10-OPEN-010（内网 CIDR）、Aspen 许可证策略、Windows 测试环境。

16. 状态变更记录
日期	状态	说明
2026-10-12	Proposed	初始版本，P10 阶段预留
待定	Accepted	后续阶段实施前确认
待定	Deprecated	若被新方案替代
待定	Superseded	若被新 ADR 取代
17. 附录：参考
P10 SPEC V1.3（AI 预留与测试部署）

开发计划 V1.4 §10.6（知识转移）

P8-004（报表任务队列与文件生命周期）

SUP-001 §3.3.13（大模型 AI 辅助功能预留接口）

SUP-002 V1.4 §4.1（AI 预留接口 Python 技术栈调整）

SUP-003（Python 计算引擎规范）

SPEC-P3（SIM）

SPEC-P4（FLASH/PIPE/PIPE_NET/PUMP）

SPEC-P5（VESSEL/SEP_EQUIP/PSV/HEAT）

Aspen Plus COM Automation 文档

py2aspen 社区库

P10-001 ADR 完。
