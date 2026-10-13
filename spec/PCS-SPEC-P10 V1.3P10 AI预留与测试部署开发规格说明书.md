P10 AI预留与测试部署开发规格说明书
项目	内容
文件标识	HT-REQ-2026-002-SPEC-P10
当前版本	V1.3
发布日期	2026-10-12
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库/运维）
关联文档	HT-REQ-2026-002 V2.2、SUP-001 §3.3.13、SUP-002 V1.4 §4.1、SUP-003、SUP-007、P3-SIM V1.1、SPEC-P0~P9、开发计划 V1.4
修订记录
版本	日期	修订说明
V1.0	2026-08-27	初版
V1.1	2026-09-15	根据首轮审查意见修订：AI 501 统一、SUP-007 两层状态机对齐、pgvector 不写死 1536、完整 Docker Compose、P50/P95/P99、AI 审计与 OutboundAIClient、10.0–10.7 拆分、测试与文档左移、生产就绪评审。
V1.2	2026-10-12	根据《复审结论：V1.1 方向正确，但建议升 V1.2 后再冻结》修订。修正 AI 中间件 request_id/user_id/body 读取、OutboundAIClient 501 异常链、document_chunks 重复 ALTER、内网 CIDR URL 解析、递归脱敏、WF-PATH 五类拆分、PgBouncer 与 PostgreSQL 连接数对齐、文档结构五部分；补充 AI 审计异步与索引、CI import 契约、E2E schema 一致性、登录压测拆分、Redis 指标、exporters、filebeat 固定版本、RTO≤2h、页面权限、培训材料、Runbook、interrogate gate、生产就绪演练和 Go/No-Go 模板。
V1.3	2026-10-12	根据《复审结论：V1.2 已具备冻结条件，但建议先发 V1.3 勘误》修订。修正 H1–H7：AI 中间件改为纯 ASGI 安全读 body、审计改用 ARQ/BackgroundTasks、request_id 服务端生成并另存 client_request_id、中间件不再捕获 AINotImplementedError、import-linter 只禁止 openai/ollama/vllm/langchain、E2E 统一编号 E2E-001~E2E-018、PgBouncer 容量量化。补充中优先级 1–5、8–10：JWT 验签、body hash 解析、document_chunks 未来迁移模板、INTERNAL_CIDRS 解析、TEST_VIEWER 角色、exporter/filebeat 配置、备份恢复脚本与演练模板、interrogate 配置。低优先级：固定 pgbouncer 版本、PostgreSQL 内存基线、OpenAPI 用 x-status: reserved。
V1.3 针对复审意见的修订映射
编号	V1.3 修订
H1	中间件改为纯 ASGI 中间件，包装 receive 缓存并重放 body；或由依赖注入记录审计。必须通过集成测试证明 Pydantic 仍能收到 body。
H2	审计写库改用 ARQ 队列或 BackgroundTasks，保存 task 引用；失败降级写本地日志。禁止裸 asyncio.create_task()。
H3	服务端始终生成 UUID 作为 request_id；客户端 ID 另存 client_request_id，不建唯一索引；request_id 唯一索引保留。
H4	统一由全局 handler 将 AINotImplementedError 转 501；中间件只记录响应，不捕获异常，避免双重处理。
H5	import-linter 只禁止 openai、ollama、vllm、langchain；允许 httpx，但用自定义 lint/架构测试约束仅 OutboundAIClient 可调 AI 端点。
H6	E2E 统一编号 E2E-001~E2E-018；验收写“18 个 E2E 场景全部通过”。
H7	给出 PgBouncer 容量计算：Gunicorn worker 数 × 每 worker 连接池 ≤ max_client_conn；default_pool_size + reserve_pool_size ≤ PG max_connections；压测前做连接数验证。
中1	try_extract_user_id 必须使用与认证依赖相同的 JWT 验签逻辑，验签失败返回 None。
中2	hash_sanitized(body) 先尝试 JSON 解析并递归脱敏后 hash；失败则对原始 body 做 SHA-256，不记录内容。
中3	document_chunks 补未来迁移模板注释：P10-OPEN-002 裁决后补 ALTER TABLE ... ADD COLUMN embedding vector(dim)，按维度选 HNSW/IVFFlat 索引。
中4	Settings 中将 INTERNAL_CIDRS 解析为 list[str]，处理空值、空格、IPv6。
中5	测试报告页权限映射为 SYSADMIN 或新增 TEST_VIEWER，并在 P9 权限矩阵登记。
中8	补 postgres_exporter、nginx-exporter、blackbox_exporter、Filebeat 8.15.0 配置片段。
中9	补 pg_basebackup + WAL 归档配置、恢复 Runbook、演练记录模板。
中10	补 interrogate 配置：exclude、fail-under=50，明确核心模块范围。
低	pgbouncer 固定 edoburu/pgbouncer:1.22.1；PostgreSQL 给 shared_buffers/work_mem 基线；AI 路由 OpenAPI 用 x-status: reserved，不用 deprecated。
第一部分：引言
1.1 目的
本文档定义 P10 阶段（AI 预留与测试部署）完整需求规格，明确 AI 接口预留、全流程 E2E、性能压测、部署与可观测性、用户文档、知识转移和生产就绪评审的功能需求、接口规范、测试场景和验收标准。

P10 是系统正式上线前最后阶段，确保系统在功能、性能、安全、运维、文档方面达到生产就绪状态。

本 V1.3 版为 P10 唯一有效规格版本。凡与 V1.0、V1.1、V1.2 冲突处，以本 V1.3 为准。开发计划 V1.3 中 P10 任务分解与本文档不一致的，按本文档 4.2 节 10.0–10.7 执行，开发计划须同步升版 V1.4。

1.2 文档范围
包含：

AI 预留接口：/api/v1/ai/* 路由骨架、DocumentChunks、AiAuditLog、递归数据脱敏、OutboundAIClient、内网 CIDR 校验、ARQ 异步审计、LangChain/Ollama/vLLM 可选依赖骨架、pgvector 扩展启用。

全流程 E2E：18 个核心场景、SUP-007 两层状态机、交付物 Rev、变更单、签署矩阵、权限矩阵、AI 占位与 schema 一致性。

性能压测：k6、P50/P95/P99、错误率、DB/Redis 指标、连接容量验证、瓶颈分析。

部署与可观测性：完整 Docker Compose、环境变量、迁移、Prometheus/Grafana/ELK、exporters、系统状态页、测试报告页。

用户文档：用户手册、管理员手册、FAQ≥20、培训材料。

知识转移：架构文档、模块依赖图、ADR、Runbook、核心模块注释覆盖率≥50%。

生产就绪评审：安全扫描、依赖漏洞、镜像扫描、回滚、数据迁移演练、监控告警、备份恢复、Go/No-Go。

不包含：

AI 功能实际业务实现。

生产环境实际部署执行。

用户培训执行。

1.3 定义、缩略语和术语
术语/缩写	定义
AI	Artificial Intelligence，人工智能
LLM	Large Language Model，大语言模型
RAG	Retrieval-Augmented Generation，检索增强生成
pgvector	PostgreSQL 向量扩展
Embedding	文本向量化表示
E2E	End-to-End，端到端测试
k6	性能压测工具
Docker Compose	多容器编排工具
ELK	Elasticsearch + Logstash + Kibana 日志栈
Prometheus	监控告警系统
Grafana	监控可视化面板
PgBouncer	PostgreSQL 连接池
postgres_exporter	PostgreSQL 指标导出器
redis_exporter	Redis 指标导出器
nginx-exporter	Nginx 指标导出器
blackbox_exporter	黑盒探测导出器
数据脱敏	隐藏或替换敏感信息
Ollama	本地 LLM 推理工具
vLLM	高性能 LLM 推理框架
LangChain	LLM 应用开发框架
私有化部署	模型部署在公司内网，禁止外部 API 调用
OutboundAIClient	所有出站 LLM 调用的统一封装，强制脱敏
CIDR	无类别域间路由，用于内网网段校验
SUP-007	两层签署与变更管理规范
SUP-002 V1.4	管道等级库最新版本
P3-SIM V1.1	SIM 模块最新版本
STALE	上游变更后哈希不匹配导致的失效状态
CHANGE_PENDING	变更单待处理状态
CHANGED	变更已处理状态
REVERSAL_PENDING	反转待处理状态
OBSOLETE	记录被新版本取代后的废止状态
ADR	Architecture Decision Record，架构决策记录
Runbook	运维操作手册
RPO	Recovery Point Objective，恢复点目标
RTO	Recovery Time Objective，恢复时间目标
P95/P99	95/99 百分位响应时间
interrogate	Python 注释覆盖率统计工具
import-linter	Python import 依赖契约检查工具
Go/No-Go	上线决策评审
TEST_VIEWER	内部测试报告查看角色，需在 P9 权限矩阵登记
client_request_id	客户端传入的请求 ID，仅记录，不用于唯一约束
1.4 参考文献
SUP-001 §3.3.13（大模型 AI 辅助功能预留接口）

SUP-002 V1.4 §4.1（AI 预留接口 Python 技术栈调整）

SUP-002 V1.4 §3.2.19（Python 计算引擎规范）

SUP-007（两层签署与变更管理规范）

P3-SIM V1.1（SIM 模块规格）

HT-REQ-2026-002 V2.2 §4（非功能需求——性能/安全/可靠性）

SPEC-P0 §3.2.4（AD 认证）、§3.2.5（CI/CD）

SPEC-P1（状态机/版本/血缘）

SPEC-P9（工作流与权限）

开发计划 V1.3（须升版 V1.4）

全部 SPEC-P0~P9（测试覆盖范围）

《P10 阶段计划审查意见：有条件通过，需先修订版本漂移与任务缺口》

《复审结论：V1.1 方向正确，但建议升 V1.2 后再冻结》

《复审结论：V1.2 已具备冻结条件，但建议先发 V1.3 勘误》

1.5 文档概述
本文档共五部分：

第一部分：引言、范围、术语、参考文献、文档概述。

第二部分：综合描述。

第三部分：具体需求。

第四部分：附录。

第五部分：结论。

第二部分：综合描述
2.1 产品前景
P10 是系统正式上线前收尾阶段。AI 预留接口为未来智能化扩展奠定基础；全流程测试确保端到端功能正确；性能压测验证生产负载稳定性；部署与可观测性确保可运维性；用户文档和知识转移确保可用性与可维护性；生产就绪评审确保上线风险可控。

P10 时间盒 4 周，但 SPEC 估算 8–12 人周。必须至少 2–3 人并行，并真实执行测试、文档、压测环境左移。否则 P10 成为上线前瓶颈。

2.2 产品功能
功能模块	核心能力
前置与测试左移	CI 迁移校验、docker-compose.test、种子数据、E2E 框架左移、版本对齐
AI 接口预留	路由骨架、表创建、递归脱敏、OutboundAIClient、内网校验、ARQ 异步审计、可选依赖
E2E 测试	18 核心场景、SUP-007 两层状态机、交付物 Rev、变更单、签署矩阵、权限验证
性能压测	并发测试、P50/P95/P99、错误率、DB/Redis 指标、连接容量验证、瓶颈分析
部署与可观测性	完整 Docker Compose、环境变量、迁移、Prometheus/Grafana/ELK、exporters、状态页、测试报告页
用户文档	用户手册、管理员手册、FAQ、培训材料
知识转移	架构文档、模块依赖图、ADR、Runbook、代码注释
生产就绪评审	安全扫描、依赖漏洞、镜像扫描、回滚、数据迁移演练、告警、备份恢复、Go/No-Go
2.3 用户类和特征
用户类	特征	P10 相关需求
后端开发工程师	维护和扩展系统	架构文档、代码注释、ADR、CI import 契约
前端开发工程师	维护前端界面	系统状态页、测试报告页、AI 助手占位入口
系统管理员	部署和运维	部署文档、监控配置、管理员手册、状态页
工艺工程师（最终用户）	使用系统	用户手册、FAQ
测试工程师	质量保障	E2E 测试、性能压测、测试报告页
内部测试人员	查看测试报告	TEST_VIEWER 或 SYSADMIN
数据库工程师	Schema 与迁移	迁移指南、pgvector 扩展、document_chunks
运维工程师	生产运维	Runbook、Prometheus/Grafana/ELK、备份恢复
未来 AI 开发人员	后续实现 AI 功能	AI 预留接口、OutboundAIClient、审计表
2.4 运行环境
同 SPEC-P0 §2.4，增加：

组件	规格
PostgreSQL+pgvector	P10 仅启用 vector 扩展，不写死维度；max_connections=300，shared_buffers=1GB，work_mem=8MB
PgBouncer	固定 edoburu/pgbouncer:1.22.1，transaction 池，支撑 ≥200 并发
Redis	缓存、任务队列、编辑锁
Prometheus	指标采集与告警
Grafana	监控可视化
postgres_exporter	PostgreSQL 指标
redis_exporter	Redis 指标
nginx-exporter	Nginx 指标，需 stub_status
blackbox_exporter	黑盒探测 /health、/health/db、/health/redis
Filebeat/ELK	日志采集与检索，Filebeat 固定 8.15.0，挂载容器日志
GPU 服务器（预留）	NVIDIA GPU，后续 LLM 推理
Ollama/vLLM	本地模型推理框架，P10 不实际启用
LangChain	AI 编排框架，P10 可选依赖预留
2.5 设计和实现上的限制
AI 不参与确定性计算，不替代签署。

私有化强制：LLM 必须内网部署，禁止外部云 AI API。启动时若 AI_ENABLED=true 且 AI_ENDPOINT 解析 IP 不在内网 CIDR，拒绝启动；调用时二次校验。

数据脱敏强制：所有出站 LLM 调用必须经 OutboundAIClient，递归脱敏所有字符串字段。

结果人工确认：未来响应固定 requires_confirmation: true。

性能指标强制：P95 硬性达标，P99 记录，错误率≤1%。

文档完整性：部署文档、用户文档、管理员手册、FAQ 合并前完成，设 gate。

版本对齐强制：P10 必须对齐 SUP-007、SUP-002 V1.4、P3-SIM V1.1。

AI 审计不可绕过：AI 路由挂认证依赖；501 也写 ai_audit_log；审计异步、失败降级。

依赖隔离：LangChain/Ollama/vLLM 使用可选依赖 extra。

测试与文档左移：E2E 框架、种子数据、压测环境、用户手册从 P8/P9 并行，不压到第 25–28 周。

AI_ENDPOINT 类型为 URL 或 IP；INTERNAL_CIDRS 为逗号分隔 CIDR 列表，Settings 解析为 list[str]。

禁止业务代码直接 import openai/ollama/vllm/langchain 调 AI 端点；允许 httpx，但仅 OutboundAIClient 可调 AI 端点，CI 用 import-linter + 自定义架构测试约束。

request_id 由服务端生成 UUID；客户端 X-Request-ID 仅存 client_request_id，不建唯一索引。

审计写库使用 ARQ 队列或 BackgroundTasks，禁止裸 asyncio.create_task()。

2.6 假设和依赖
依赖 P0~P9 全部完成。

依赖 SUP-007 已冻结。

依赖 SUP-002 V1.4 已冻结。

依赖 P3-SIM V1.1 已冻结。

假设有 GPU 或可申请 GPU 资源。

假设公司有标准 Docker 镜像仓库。

假设 Prometheus/ELK 基础设施可部署。

假设有真实项目数据可用于 E2E。

假设 IT 可提供内网 CIDR 清单。

假设 P8/P9 可并行启动 E2E 框架、种子数据、压测环境和用户手册编写。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
界面	规格	权限
AI 助手入口（预留）	右下角悬浮图标，占位，显示“AI功能即将上线”	登录用户
测试报告页	展示 E2E 与性能测试报告	SYSADMIN 或 TEST_VIEWER
系统状态页	服务、数据库、Redis、AI not_configured 状态	SYSADMIN
系统状态页、测试报告页必须加权限控制。TEST_VIEWER 需在 P9 权限矩阵登记。

3.1.2 软件接口
AI 预留接口：

所有 AI 路由必须：

挂认证依赖；未认证返回 401/403，不返回 501。

返回 HTTP 501。

响应体含 code=AI_NOT_IMPLEMENTED。

记录 ai_audit_log，包括 501 请求。

OpenAPI 标记 x-status: reserved，不使用 deprecated，避免前端生成器报错。

接口组	端点	说明	状态
意图识别	POST /api/v1/ai/intent	自然语言指令→意图+实体	501
知识库检索	POST /api/v1/ai/knowledge/search	RAG 语义检索	501
设备推荐	POST /api/v1/ai/equipment/recommend	相似设备推荐	501
自然语言解释	POST /api/v1/ai/explain	变更自然语言描述	501
文档解析	POST /api/v1/ai/document/extract	PDF/图片字段提取	501
健康检查接口：

接口组	端点	说明
服务健康	GET /api/v1/health	后端服务状态
数据库健康	GET /api/v1/health/db	数据库连通性
Redis 健康	GET /api/v1/health/redis	Redis 连通性
AI 健康	GET /api/v1/health/ai	AI 服务状态，返回 not_configured
3.2 功能需求
3.2.0 前置与测试左移
需求编号：P10-PRE-001

（1）版本对齐

确认 SUP-007、SUP-002 V1.4、P3-SIM V1.1 已冻结。

P10 SPEC V1.3 与上述基线对齐后进入开发。

开发计划 V1.3 升版 V1.4，P10 任务按 10.0–10.7 执行。

左移 gate 写入开发计划 V1.4：

P1/P2：E2E 框架搭好。

P8/P9：种子数据、压测环境、用户手册启动。

P10 开始前：SUP-007、SUP-002 V1.4、P3-SIM V1.1 冻结。

（2）CI 迁移校验

yaml
- name: Alembic upgrade on pcs
  run: alembic upgrade head
  env:
    DATABASE_URL: ${{ secrets.PCS_DATABASE_URL }}

- name: Alembic upgrade on pcs_test
  run: alembic upgrade head
  env:
    DATABASE_URL: ${{ secrets.PCS_TEST_DATABASE_URL }}
CI 自动执行 alembic upgrade head，覆盖 pcs 与 pcs_test，解决 schema 漂移。

（3）docker-compose.test

包含：PostgreSQL+pgvector、Redis、mock AD、backend、worker、frontend。

（4）种子数据与测试账号

准备 18 个 E2E 场景所需项目、物流、设备、角色矩阵、测试账号。

（5）E2E 框架左移

P1/P2 起搭 E2E 框架；P8/P9 并行种子数据、压测环境、用户手册。

验收标准：

版本对齐确认。

CI 覆盖 pcs 与 pcs_test 迁移。

docker-compose.test 可启动。

种子数据可自动生成。

E2E 框架 P1/P2 已搭建。

开发计划 V1.4 发布。

3.2.1 AI 预留接口
需求编号：P10-AI-001

（1）AI 路由骨架与 501 统一
统一使用 JSONResponse(status_code=501) 或 AINotImplementedError + 全局 handler。request_id 由中间件写入 request.state.request_id，路由从 Request 取；缺失时全局异常处理器兜底生成。

python
# app/api/v1/ai/__init__.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

ai_router = APIRouter(prefix="/api/v1/ai")

def ai_not_implemented_response(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "code": "AI_NOT_IMPLEMENTED",
            "message": "AI功能即将上线",
            "request_id": request_id,
        },
    )

@ai_router.post("/intent", openapi_extra={"x-status": "reserved"})
async def ai_intent(request: Request, payload: AiIntentRequest, user=Depends(current_user)):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return ai_not_implemented_response(request_id)
所有 AI 路由均按此模式处理。OpenAPI 使用 x-status: reserved，不用 deprecated。

（2）数据表预留
document_chunks：

P10 建表不含 embedding 字段。P10 只启用 pgvector 扩展。待 P10-OPEN-002 裁决后再补迁移。

字段	类型	说明
chunk_id	UUID	主键
document_id	UUID	文档 ID
content	TEXT	切片内容
source	TEXT	来源
created_at	TIMESTAMPTZ	创建时间
未来迁移模板注释（P10-OPEN-002 裁决后）：

sql
-- 当 P10-OPEN-002 确定维度 dim 后执行：
-- ALTER TABLE document_chunks ADD COLUMN embedding vector(dim);
-- 按 dim 选择索引：
--   dim <= 2000 建议 HNSW: CREATE INDEX ... USING hnsw (embedding vector_cosine_ops);
--   dim > 2000 建议 IVFFlat: CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
ai_audit_log：

字段	类型	说明
log_id	UUID	主键
request_id	TEXT	服务端生成 UUID，唯一索引
client_request_id	TEXT	客户端 X-Request-ID，可空，不唯一
user_id	UUID	可为空，认证失败为 None
endpoint	TEXT	AI 端点
status_code	INT	含 501
duration_ms	INT	耗时
sanitized_request_hash	TEXT	脱敏后请求哈希
response_summary	TEXT	响应摘要
model_version	TEXT	模型版本
timestamp	TIMESTAMPTZ	时间，与 endpoint 建组合索引
索引：

sql
CREATE UNIQUE INDEX ux_ai_audit_log_request_id ON ai_audit_log(request_id);
CREATE INDEX ix_ai_audit_log_endpoint_timestamp ON ai_audit_log(endpoint, timestamp);
system_settings：

保存 ai_enabled、ai_model_version、ai_endpoint、ai_timeout、ai_max_tokens、ai_temperature。

pgvector 扩展：

P10 只执行：

sql
CREATE EXTENSION IF NOT EXISTS vector;
禁止在 P10 写死 vector(1536)，禁止重复 ALTER TABLE document_chunks ADD COLUMN embedding。

（3）递归脱敏、AINotImplementedError 与 OutboundAIClient
python
# app/core/ai_sanitizer.py
import re, json, hashlib

ENABLE_PERSON_NAME_MASK = False  # 默认关闭，可配置

SENSITIVE_PATTERNS = [
    (r'\b[A-Z]{2,4}-\d{3,5}[A-Z]?\b', '[EQUIPMENT_TAG]'),
    (r'\b\d{4}\.\d{3}\.\d{3}\b', '[PROJECT_NO]'),
    (r'\b[A-Z]{2}-\d{3}\b', '[LINE_NO]'),
    (r'\b[\u4e00-\u9fa5]{2,4}(?:公司|集团|厂)\b', '[CUSTOMER_NAME]'),
    (r'\b[\w.+-]+@[\w-]+\.[\w.]+\b', '[EMAIL]'),
    (r'\b1[3-9]\d{9}\b', '[PHONE]'),
    (r'\b[\u4e00-\u9fa5]{2,}(?:省|市|区|县|路|街|号)\b', '[ADDRESS]'),
]

if ENABLE_PERSON_NAME_MASK:
    SENSITIVE_PATTERNS.append((r'\b[\u4e00-\u9fa5]{2,3}\b', '[PERSON_NAME]'))

def _sanitize_text(text: str) -> str:
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text

def sanitize_for_ai(value):
    """递归脱敏 dict/list/str 中所有字符串字段"""
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        return {k: sanitize_for_ai(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_for_ai(v) for v in value]
    if isinstance(value, tuple):
        return tuple(sanitize_for_ai(v) for v in value)
    return value

def hash_sanitized(body: bytes) -> str:
    """body 为 bytes。先尝试 JSON 解析并递归脱敏后 hash；失败则对原始 body 做 SHA-256，不记录内容。"""
    try:
        data = json.loads(body.decode("utf-8"))
        sanitized = sanitize_for_ai(data)
        normalized = json.dumps(sanitized, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return "sha256:" + hashlib.sha256(normalized).hexdigest()
    except Exception:
        return "sha256:" + hashlib.sha256(body).hexdigest()
AINotImplementedError 与全局 handler：

python
class AINotImplementedError(Exception):
    pass

@app.exception_handler(AINotImplementedError)
async def ai_not_implemented_handler(request: Request, exc: AINotImplementedError):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return JSONResponse(
        status_code=501,
        content={
            "code": "AI_NOT_IMPLEMENTED",
            "message": "AI功能即将上线",
            "request_id": request_id,
        },
    )
OutboundAIClient：

python
class OutboundAIClient:
    def __init__(self, endpoint: str, timeout: int):
        self.endpoint = endpoint
        self.timeout = timeout

    async def call(self, payload: dict) -> dict:
        validate_ai_endpoint(self.endpoint, settings.INTERNAL_CIDRS)  # 调用时二次校验
        sanitized = sanitize_for_ai(payload)
        await self._audit(sanitized)
        raise AINotImplementedError()

    async def _audit(self, payload: dict) -> None:
        # P10 占位：可写 ai_audit_log 或 no-op；不得抛异常
        return None
业务代码禁止直接 import openai、ollama、vllm、langchain。允许 httpx，但仅 OutboundAIClient 可调 AI 端点。CI 使用 import-linter + 自定义架构测试：

ini
[importlinter]
root_package = app

[importlinter:contract:no-direct-ai-sdk]
name = No direct AI SDK outside OutboundAIClient
type = forbidden
source_modules =
    app.modules
    app.services
    app.api
forbidden_modules =
    openai
    ollama
    vllm
    langchain
自定义 lint/架构测试：扫描 httpx 调用，若目标 URL 匹配 AI 端点白名单，仅允许 app.core.outbound_ai_client。

（4）AI 审计中间件（纯 ASGI，安全读 body）
修正 H1：不使用 BaseHTTPMiddleware 直接 await request.body()。采用纯 ASGI 中间件，包装 receive 缓存并重放 body；或由依赖注入记录审计。必须通过集成测试证明 Pydantic 仍能收到 body。

修正 H2：审计写库使用 ARQ 队列或 BackgroundTasks，保存 task 引用；失败降级写本地日志。禁止裸 asyncio.create_task()。

修正 H3：服务端始终生成 UUID 作为 request_id；客户端 ID 另存 client_request_id，不建唯一索引。

修正 H4：中间件不捕获 AINotImplementedError，统一由全局 handler 转 501；中间件只记录响应。

python
# 纯 ASGI 中间件示意
class AIAuditMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/ai/"):
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        client_request_id = None
        for k, v in scope.get("headers", []):
            if k.lower() == b"x-request-id":
                client_request_id = v.decode("latin-1")
                break

        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        scope["state"]["client_request_id"] = client_request_id
        scope["state"]["user_id"] = try_extract_user_id_from_scope(scope)  # JWT 验签，失败 None

        body_chunks = []
        async def receive_cached():
            message = await receive()
            if message["type"] == "http.request":
                body_chunks.append(message.get("body", b""))
            return message

        start = time.perf_counter()
        status_code = None

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive_cached, send_wrapper)
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            body = b"".join(body_chunks)
            sanitized_hash = hash_sanitized(body) if len(body) <= 1024 * 1024 else None
            await enqueue_ai_audit_log(
                request_id=request_id,
                client_request_id=client_request_id,
                user_id=scope["state"].get("user_id"),
                endpoint=scope["path"],
                status_code=status_code,
                duration_ms=duration_ms,
                sanitized_request_hash=sanitized_hash,
                response_summary="AI_NOT_IMPLEMENTED" if status_code == 501 else None,
            )
enqueue_ai_audit_log 使用 ARQ 队列；失败降级写本地日志。try_extract_user_id_from_scope 必须使用与认证依赖相同的 JWT 验签逻辑，验签失败返回 None。

（5）私有化强制校验
AI_ENDPOINT 类型为 URL 或 IP；INTERNAL_CIDRS 为逗号分隔 CIDR 列表，Settings 解析为 list[str]，处理空值、空格、IPv6。

python
from urllib.parse import urlparse
import ipaddress, socket

def parse_cidrs(value: str) -> list[str]:
    if not value:
        return []
    return [c.strip() for c in value.split(",") if c.strip()]

def ip_in_cidrs(ip: str, cidrs: list[str]) -> bool:
    addr = ipaddress.ip_address(ip)
    return any(addr in ipaddress.ip_network(c) for c in cidrs)

def resolve_ai_endpoint_ips(endpoint: str) -> list[str]:
    parsed = urlparse(endpoint)
    host = parsed.hostname or endpoint
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        return list({item[4][0] for item in socket.getaddrinfo(host, None)})

def validate_ai_endpoint(endpoint: str, cidrs: list[str]) -> None:
    ips = resolve_ai_endpoint_ips(endpoint)
    if not ips:
        raise RuntimeError("AI_ENDPOINT DNS resolution failed")
    if not all(ip_in_cidrs(ip, cidrs) for ip in ips):
        raise RuntimeError("AI_ENDPOINT must resolve to internal CIDR")
启动时：

python
if settings.AI_ENABLED:
    if not settings.AI_ENDPOINT:
        raise RuntimeError("AI_ENABLED=true but AI_ENDPOINT is empty")
    validate_ai_endpoint(settings.AI_ENDPOINT, settings.INTERNAL_CIDRS)
（6）人工确认标记
未来 AI 响应固定加 requires_confirmation: true。

（7）OpenAPI 标记
AI 路由加 x-status: reserved，不使用 deprecated。

（8）依赖隔离
toml
[project.optional-dependencies]
ai = [
    "langchain>=0.2",
    "ollama>=0.3",
    "vllm>=0.5",
]
默认安装不 import 失败。

（9）AI 功能开关
json
{
  "ai_enabled": false,
  "ai_model_version": null,
  "ai_endpoint": null,
  "ai_timeout": 30,
  "ai_max_tokens": 4096,
  "ai_temperature": 0.1
}
验收标准：

AI 路由返回 501，响应体含 AI_NOT_IMPLEMENTED。

request_id 服务端生成 UUID，客户端 ID 存 client_request_id，无唯一冲突。

user_id 认证成功写入，认证失败为 None，审计仍记录；JWT 验签逻辑与认证依赖一致。

纯 ASGI 中间件读 body 后下游 Pydantic 仍能收到 body，集成测试通过。

OutboundAIClient 抛 AINotImplementedError，全局 handler 转 501。

DocumentChunks、AiAuditLog、system_settings 已创建。

pgvector 扩展已启用，未写死 1536，无重复 embedding 列。

递归脱敏覆盖嵌套字段；人员名默认关闭。

内网 CIDR 校验支持 URL/IP/IPv6，启动时和调用时二次校验。

501 请求进入 ai_audit_log，审计 ARQ 异步且失败降级。

/health/ai 返回 not_configured。

OpenAPI 标记 x-status: reserved。

AI 可选依赖隔离。

CI import-linter 禁止 openai/ollama/vllm/langchain；httpx 仅 OutboundAIClient 可调 AI 端点。

3.2.2 全流程 E2E 测试
需求编号：P10-TST-001

（1）核心 E2E 测试场景（统一编号 E2E-001~E2E-018）
场景编号	场景	覆盖模块	预期
E2E-001	项目创建→BEDD 录入→输入清单生成	PMS + CONFIG + 输入清单	项目创建成功，清单自动生成
E2E-002	SIM 导入→物流验证	SIM + FLASH	解析正确，物性补全
E2E-003	PIPE 计算→管道一览表	PIPE + PIPE_CLASS + SIM	计算结果正确，管表输出
E2E-004	PUMP 计算→泵数据表	PUMP + PIPE + SIM	泵选型正确
E2E-005	PSV 计算→安全阀数据表	PSV + VESSEL + FLASH	泄放面积正确
E2E-006	VESSEL 计算→容器数据表	VESSEL + SIM	尺寸计算正确
E2E-007	EQUIP_LIST 汇总	EQUIP_LIST + 各计算模块	设备表完整
E2E-008	UTIL 能耗汇总	UTIL + EQUIP_LIST	能耗计算正确
E2E-009	REPORT 生成→计算书	REPORT + 全部数据	计算书生成正确
E2E-010	记录层审批	全部 + SUP-007 记录层	记录层状态正确
E2E-011	交付物 Rev	全部 + SUP-007 交付物	Rev 升版正确
E2E-012	签署矩阵与代录	全部 + SUP-007 签署矩阵	代录客户批准正确
E2E-013	上游变更影响分析	SIM + 全部下游	STALE 哈希判定 + 确认重算
E2E-014	供应商数据录入与核算	EQUIP_LIST + UTIL	偏差报告和实际值更新
E2E-015	自定义报表执行	REPORT_BUILDER + EQUIP_LIST	数据提取正确
E2E-016	用户权限验证	ADMIN + 全部	越权操作被拒绝，按新签署矩阵
E2E-017	AI 占位与审计	AI 路由 + ai_audit_log	返回 501，响应体 AI_NOT_IMPLEMENTED，审计有记录
E2E-018	Schema 一致性	Alembic + pcs/pcs_test	pcs 与 pcs_test alembic 版本一致
（2）状态机按 SUP-007 两层重写
废止旧 7 态路径。按 SUP-007 两层：记录层 9 态、交付物 Rev、变更单、签署矩阵。记录层 9 态具体名称以 SUP-007 冻结版为准。

WF-PATH 拆为五类：

路径编号	路径类型	覆盖
WF-PATH-01A	正向	记录层从初始到生效/批准的正向路径
WF-PATH-01B	驳回	校核/审核/批准驳回后回退重走
WF-PATH-01C	变更闭环	上游变更→STALE→CHANGE_PENDING→CHANGED→确认重算→关闭
WF-PATH-01D	撤销/反转	REVERSAL_PENDING→反转→原记录恢复/废止
WF-PATH-01E	废止	OBSOLETE
WF-PATH-02	交付物 Rev	Rev 升版与签署矩阵
WF-PATH-03	变更单/代录	变更单自动关闭、代录客户批准
WF-PATH-04	权限	权限矩阵与签署矩阵一致性
（3）权限矩阵验证
按 SUP-007 新签署矩阵验证：

测试	操作	角色	预期
AUTH-E2E-01	编辑草稿	DESIGNER	200
AUTH-E2E-02	编辑草稿	CHECKER	403
AUTH-E2E-03	校核通过	CHECKER	200
AUTH-E2E-04	校核通过	DESIGNER	403
AUTH-E2E-05	审定通过	APPROVER	200
AUTH-E2E-06	审定通过	DESIGNER	403
AUTH-E2E-07	查看审计日志	SYSADMIN	200
AUTH-E2E-08	查看审计日志	DESIGNER	403
AUTH-E2E-09	代录客户批准	授权代录人	200
AUTH-E2E-10	变更单审批	按签署矩阵	200/403
AUTH-E2E-11	查看测试报告页	TEST_VIEWER	200
AUTH-E2E-12	查看测试报告页	DESIGNER	403
（4）E2E 实现
方法	说明
后端测试	pytest + httpx + Mock 认证切换
前端测试	Playwright + Mock 登录页
数据准备	种子脚本自动生成标准测试项目数据
执行方式	PR 跑关键 E2E；nightly 跑全量 E2E
环境	docker-compose.test
AI 断言	501、响应体 AI_NOT_IMPLEMENTED、ai_audit_log 有记录
Schema 断言	pcs 与 pcs_test alembic 版本一致
验收标准：

18 个 E2E 场景全部通过。

SUP-007 两层状态机五类路径全部覆盖。

权限矩阵关键验证全部通过，含 TEST_VIEWER。

E2E 在 CI 中可自动执行。

PR 跑关键 E2E，nightly 跑全量 E2E。

AI 501 不破坏 E2E，审计有记录。

pcs 与 pcs_test schema 版本一致。

3.2.3 性能压测
需求编号：P10-PRF-001

（1）性能指标
P10 补充定义 P95/P99；若 V2.2 §4.1 未定义百分位，须同步修订 V2.2 或作为 P10 补充指标。

操作类型	P95 要求	P99	错误率
页面切换、Tab 切换	≤500ms	记录	≤1%
单次计算	≤2s	记录	≤1%
复杂报表生成	≤10s	记录	≤1%
登录认证（预生成 JWT）	≤1s	记录	≤1%
登录认证（真实 AD）	≤1s	记录	≤1%
设备表查询	≤2s	记录	≤1%
签署操作	≤1s	记录	≤1%
数据库并发连接池	≥200 并发用户	—	—
（2）压测场景
场景	并发	时长	说明
登录-预生成 JWT	200	5 分钟	压系统，验证 ≥200 并发容量
登录-真实 AD	20 或按 AD 能力	5 分钟	压认证链路，不作为 200 并发达标依据
项目浏览	100	10 分钟	P95≤500ms
PIPE 计算	50	10 分钟	P95≤2s
报表生成	20	5 分钟	P95≤10s
设备表查询	100	10 分钟	P95≤2s
签署操作	50	5 分钟	P95≤1s
登录压测口径：200 并发由预生成 JWT 场景验证系统容量；真实 AD 场景验证认证链路，不作为 200 并发达标依据。

（3）PgBouncer 容量计算
Gunicorn worker 数 × 每 worker 连接池 ≤ PgBouncer max_client_conn。

PgBouncer 到 PostgreSQL 的 default_pool_size + reserve_pool_size ≤ PostgreSQL max_connections。

示例：4 workers × 50 = 200 ≤ max_client_conn=500；default_pool_size=50 + reserve_pool_size=10 = 60 ≤ max_connections=300。

压测前做连接数验证：SELECT count(*) FROM pg_stat_activity; 与 PgBouncer SHOW POOLS;。

（4）Redis 指标目标
指标	目标
命中率	≥90%
P95 延迟	≤5ms
连接数	不超过最大连接数 80%
（5）压测工具
k6、Playwright、PostgreSQL 监控、Redis 监控、Prometheus/Grafana。

（6）压测报告
含 P50/P95/P99、错误率、DB/Redis 指标、连接容量验证、瓶颈与优化建议、结论。

验收标准：

所有场景 P95 达标。

P99 已记录并分析。

错误率≤1%。

Redis 指标达标。

连接容量计算与验证通过。

数据库无性能瓶颈。

压测报告完整，明确 200 并发由预生成 JWT 场景验证。

3.2.4 部署与可观测性
需求编号：P10-DEP-001

（1）完整 docker-compose.prod.yml
必须包含：

nginx

frontend

backend

worker

redis

postgres+pgvector

pgbouncer

alembic job

prometheus

grafana

postgres_exporter

redis_exporter

nginx-exporter

blackbox_exporter

filebeat（固定 8.15.0）

关键配置：

yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    command: >
      postgres -c max_connections=300
               -c shared_buffers=1GB
               -c work_mem=8MB
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes: ["pg-data:/var/lib/postgresql/data"]

  pgbouncer:
    image: edoburu/pgbouncer:1.22.1
    environment:
      - DB_HOST=postgres
      - DB_USER=${POSTGRES_USER}
      - DB_PASSWORD=${POSTGRES_PASSWORD}
      - POOL_MODE=transaction
      - MAX_CLIENT_CONN=500
      - DEFAULT_POOL_SIZE=50
      - RESERVE_POOL_SIZE=10
    depends_on: [postgres]

  alembic:
    image: process-calc-backend:latest
    command: alembic upgrade head
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    depends_on: [postgres]
    restart: "no"

  postgres_exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      - DATA_SOURCE_NAME=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}?sslmode=disable
    depends_on: [postgres]

  nginx-exporter:
    image: nginx/nginx-prometheus-exporter:latest
    command: ["-nginx.scrape-uri=http://nginx:8080/stub_status"]

  blackbox_exporter:
    image: prom/blackbox-exporter:latest
    volumes:
      - ./blackbox.yml:/etc/blackbox_exporter/config.yml

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.15.0
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
说明：

PostgreSQL max_connections=300，shared_buffers=1GB，work_mem=8MB。

PgBouncer transaction 模式，default_pool_size=50，max_client_conn=500，reserve_pool_size=10。

Alembic 直连 postgres，不经过 PgBouncer。

backend/worker 经 PgBouncer。

postgres_exporter 直连 PostgreSQL 监控真实连接数。

nginx-exporter 需 stub_status。

blackbox_exporter 探测 /health、/health/db、/health/redis。

Filebeat 固定 8.15.0，挂载容器日志。

监控连接数 >80% 最大连接数告警。

（2）环境变量清单
变量	说明	默认值
ENV	环境标识	production
DATABASE_URL	数据库连接串	—
REDIS_URL	Redis 连接串	—
JWT_SECRET	JWT 签名密钥	—
AD_LDAP_SERVER	AD 服务器地址	—
AD_DOMAIN	AD 域名	—
CORS_ORIGINS	允许的跨域来源	—
ALLOWED_HOSTS	允许的主机	—
SMTP_HOST	邮件服务器	—
SMTP_PORT	邮件端口	587
SMTP_USER	邮件用户名	—
SMTP_PASSWORD	邮件密码	—
ENCRYPTION_KEY	加密密钥	—
BACKUP_DIR	备份目录	/backup
BACKUP_RETENTION_DAYS	备份保留天数	30
BACKUP_NOTIFY	备份通知对象	—
AI_ENABLED	AI 功能开关	false
AI_ENDPOINT	AI 服务端点，URL 或 IP	—
INTERNAL_CIDRS	内网 CIDR，逗号分隔，Settings 解析 list	—
AI_TIMEOUT	AI 超时秒数	30
LOG_LEVEL	日志级别	INFO
SESSION_TIMEOUT	会话超时（分钟）	30
GRAFANA_PASSWORD	Grafana 管理员密码	—
（3）数据库迁移指南
Alembic 版本化 Schema。

提供升级和回滚命令。

包含数据备份和恢复步骤。

CI 覆盖 pcs 与 pcs_test。

P10 迁移包含：CREATE EXTENSION IF NOT EXISTS vector;、document_chunks、ai_audit_log、system_settings。

P10 不建 document_chunks.embedding，不写死 1536。

若 P9 已创建 system_settings，P10 只做 seed；若未创建，P10 建表。迁移指南明确分支，避免重复建表。

数据迁移演练纳入 10.7。

（4）监控告警
监控项	工具	阈值
服务存活	Prometheus/blackbox	连续 3 次失败
CPU	Prometheus	>80% 持续 5 分钟
内存	Prometheus	>85% 持续 5 分钟
数据库连接数	postgres_exporter	>80% 最大连接数
磁盘	Prometheus	>80%
错误日志	ELK	Error 级别
页面响应	Prometheus	P95>500ms 持续 10 分钟
计算响应	Prometheus	P95>2s 持续 10 分钟
报表响应	Prometheus	P95>10s 持续 10 分钟
Redis	redis_exporter	命中率<90%、P95>5ms、连接数>80%
Nginx	nginx-exporter	5xx 比例异常
黑盒探测	blackbox_exporter	/health、/health/db、/health/redis 失败
（5）备份恢复脚本与演练
RPO≤30min，RTO≤2h。

每日全量 + 每 15 分钟 WAL。

pg_basebackup + WAL 归档配置示例：

bash
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /backup/wal/%f'
bash
# 每日全量
pg_basebackup -h postgres -D /backup/base/$(date +%F) -Ft -z -P
恢复 Runbook：停止应用 → 恢复 base → 重放 WAL 至目标时间 → 启动验证。

演练记录模板：

项目	内容
演练时间	
备份集	
恢复目标	
RPO 实测	
RTO 实测	
问题	
结论	
（6）前端页面权限
系统状态页：仅 SYSADMIN。

测试报告页：SYSADMIN 或 TEST_VIEWER。

AI 助手入口：登录用户可见，占位。

验收标准：

Docker Compose 可启动全部服务。

环境变量清单完整，INTERNAL_CIDRS 解析正确。

迁移指南可执行，system_settings 分支明确。

监控告警配置正确。

exporters、filebeat 8.15.0 正常，配置片段完整。

状态页、测试报告页权限正确，TEST_VIEWER 已登记。

备份恢复演练通过，RPO≤30min，RTO≤2h，演练记录模板已填写。

3.2.5 用户文档
需求编号：P10-DOC-001

（1）用户手册
章节	内容
系统简介	系统概述、功能模块
快速入门	登录、项目创建、基本操作
各模块操作	PMS/SIM/PIPE/PUMP/PSV/VESSEL/HEAT/CV/UTIL
报表生成	计算书/数据表
签署流程	按 SUP-007 两层签署重写，含记录层、交付物 Rev、签署矩阵、代录
常见问题	FAQ
（2）管理员手册
章节	内容
系统部署	环境要求、部署步骤
用户管理	AD 同步、角色分配
配置管理	公式/系数/模板/标准库
审计日志	查询和分析
备份恢复	备份和恢复流程
故障排查	常见诊断与解决
（3）FAQ
覆盖登录认证、计算错误、签署流程、导入导出、权限、AI 未启用、状态页、备份恢复等，≥20 条。

（4）培训材料
明确材料清单：

PPT 课件。

操作视频脚本。

练习数据。

讲师手册。

验收标准：

用户手册覆盖所有模块。

签署章节按 SUP-007 两层签署重写。

管理员手册覆盖 AD 同步、配置、审计、备份、故障排查。

FAQ≥20 条。

培训材料清单全部交付。

合并前 gate：文档未完成不得合并 P10。

3.2.6 知识转移
需求编号：P10-KT-001

交付物	说明
架构文档	系统组件和交互
模块依赖图	模块依赖可视化
ADR	架构决策记录
Runbook	日常运维、故障处理、应急
代码注释	interrogate 统计，核心模块≥50%，CI gate
Runbook 必须增加：

AI_ENABLED 切换。

CIDR 校验失败处理。

pgvector 迁移失败处理。

PgBouncer 故障处理。

备份恢复。

回滚。

interrogate 配置：

toml
# pyproject.toml
[tool.interrogate]
ignore-init-module = true
ignore-init-method = true
ignore-magic = true
ignore-semiprivate = true
ignore-private = true
ignore-property-decorators = true
ignore-module = false
ignore-nested-functions = true
fail-under = 50
exclude = ["tests", "migrations", "venv", ".venv"]
核心模块范围：app/core、app/modules、app/services、app/api。

验收标准：

架构文档完整。

模块依赖图完成。

ADR 覆盖关键决策。

Runbook 覆盖上述场景。

interrogate CI gate 通过，核心模块注释≥50%。

3.2.7 生产就绪评审
需求编号：P10-REL-001

评审项	说明
安全扫描	SAST/DAST，无高危
依赖漏洞	Python/npm/Docker 基础镜像漏洞，无高危
容器镜像扫描	镜像漏洞扫描
回滚演练	版本回滚流程
数据迁移演练	迁移与回滚数据兼容性
监控告警演练	告警触发、静默、升级
备份恢复演练	RPO≤30min，RTO≤2h
应急联系人	明确联系人
上线检查清单	输出清单
Go/No-Go	输出会议纪要模板
验收标准：

安全扫描通过。

依赖漏洞扫描通过。

容器镜像扫描通过。

回滚演练成功。

数据迁移演练成功。

监控告警演练成功，静默与升级验证。

备份恢复演练成功，记录模板完整。

应急联系人明确。

上线检查清单和 Go/No-Go 模板输出。

全部通过后才允许上线。

3.3 非功能需求
3.3.1 性能需求
指标	要求
系统启动	≤30 秒
数据库迁移	≤5 分钟
并发用户	≥200
可用性	MTBF≥720 小时
页面 P95	≤500ms
计算 P95	≤2s
报表 P95	≤10s
错误率	≤1%
P99	记录并分析
Redis 命中率	≥90%
3.3.2 安全性需求
指标	要求
AI 数据脱敏	强制，递归，OutboundAIClient
AI 审计	所有 AI 请求含 501，ARQ 异步，失败降级
AI 私有化	禁止外部 API，CIDR 启动与调用校验
AI 结果确认	requires_confirmation: true
部署安全	密钥环境变量注入
页面权限	状态页 SYSADMIN，测试报告页 SYSADMIN/TEST_VIEWER
CI 契约	禁止 openai/ollama/vllm/langchain；httpx 仅 OutboundAIClient 可调 AI 端点
3.3.3 可维护性需求
指标	要求
架构文档	完整
模块依赖图	完成
ADR	覆盖关键决策
代码注释	interrogate 核心模块≥50%
部署自动化	Docker Compose 一键启动
监控覆盖	核心指标全部覆盖
Runbook	覆盖 AI/CIDR/pgvector/PgBouncer
3.4 数据需求
P10 创建/修改：

表	说明
document_chunks	不含 embedding，P10 只启用扩展
ai_audit_log	含 request_id 唯一索引、client_request_id 非唯一、endpoint+timestamp 索引
system_settings	系统参数，P9 已建则 seed，未建则 P10 建
启用 pgvector：

sql
CREATE EXTENSION IF NOT EXISTS vector;
禁止 P10 写死 1536，禁止重复 ALTER 添加 embedding。未来迁移模板见 3.2.1(2)。

第四部分：附录
4.1 AI 预留接口详细定义
4.1.1 意图识别接口
http
POST /api/v1/ai/intent
请求：

json
{
  "text": "帮我把泵P-101的流量设为50 m3/h",
  "context": {
    "projectId": "uuid",
    "module": "PUMP",
    "recordId": "uuid"
  }
}
当前响应：

http
HTTP/1.1 501 Not Implemented
Content-Type: application/json
X-Request-ID: req-...
json
{
  "code": "AI_NOT_IMPLEMENTED",
  "message": "AI功能即将上线",
  "request_id": "req-..."
}
未来响应：

json
{
  "intent": "FILL_FORM",
  "entities": {
    "field": "flow",
    "value": 50,
    "unit": "m3/h"
  },
  "confidence": 0.95,
  "requires_confirmation": true
}
4.1.2 知识库检索接口
http
POST /api/v1/ai/knowledge/search
请求：

json
{
  "query": "API 520 火灾工况润湿面积修正系数",
  "topK": 5
}
当前响应同 501 结构。未来响应增加 requires_confirmation: true。

4.1.3 AI 功能开关
json
{
  "ai_enabled": false,
  "ai_model_version": null,
  "ai_endpoint": null,
  "ai_timeout": 30,
  "ai_max_tokens": 4096,
  "ai_temperature": 0.1
}
4.1.4 AI 审计字段
json
{
  "log_id": "uuid",
  "request_id": "服务端UUID",
  "client_request_id": "客户端X-Request-ID或null",
  "user_id": "uuid-or-null",
  "endpoint": "/api/v1/ai/intent",
  "status_code": 501,
  "duration_ms": 12,
  "sanitized_request_hash": "sha256:...",
  "response_summary": "AI_NOT_IMPLEMENTED",
  "model_version": null,
  "timestamp": "2026-10-12TXX:XX:XXZ"
}
4.2 开发计划 P10 修订版任务分解
任务	内容	左移
10.0 前置与测试左移	CI alembic 覆盖 pcs/pcs_test、docker-compose.test、种子数据、E2E 框架、版本对齐	P1/P2 搭 E2E；P8/P9 种子与压测
10.1 AI 预留接口	路由、501、认证、ARQ 异步审计、递归脱敏、OutboundAIClient、CIDR、迁移、健康检查、前端占位	—
10.2 全流程 E2E	18 场景、SUP-007 五类路径、权限矩阵、PR/nightly	P8/P9 并行
10.3 性能压测	k6、P95/P99、错误率、Redis、PgBouncer 容量、报告	P8/P9 环境
10.4 部署与可观测性	完整 compose、exporters、Prometheus/Grafana/ELK、状态页、测试报告页、备份演练	—
10.5 用户文档	用户手册、管理员手册、FAQ、培训材料，合并前 gate	P8/P9 启动
10.6 知识转移	架构、依赖图、ADR、Runbook、interrogate gate	—
10.7 生产就绪评审	安全、漏洞、镜像、回滚、数据迁移、告警、备份、Go/No-Go	—
关键路径：

text
10.0 前置与测试左移
  → 10.1 AI 预留
  → 10.2 全流程 E2E
  → 10.7 生产就绪评审

10.4 部署与可观测性、10.5 用户文档、10.6 知识转移并行
左移 gate 写入开发计划 V1.4：

P1/P2：E2E 框架搭好。

P8/P9：种子数据、压测环境、用户手册启动。

P10 开始前：SUP-007、SUP-002 V1.4、P3-SIM V1.1 冻结。

4.3 部署架构图
text
┌─────────────────────────────────────────────────────────┐
│                 生产部署架构                             │
└─────────────────────────────────────────────────────────┘

                    ┌─────────────┐
                    │   用户浏览器 │
                    └──────┬──────┘
                           │ HTTPS (TLS 1.3)
                    ┌──────▼──────┐
                    │    Nginx     │
                    │ 反向代理/SSL │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  FastAPI后端  │  │  ARQ Worker   │  │  前端静态文件  │
│  (Gunicorn)   │  │  (后台任务)    │  │  (frontend)   │
└───────┬───────┘  └───────┬───────┘  └───────────────┘
        │                  │
        │                  │
┌───────▼──────────────────▼───────────────────────────┐
│                       Redis                           │
│              缓存 / 任务队列 / 编辑锁 / AI审计队列      │
└──────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────┐
│                    PgBouncer                          │
│   transaction / max_client_conn=500 / pool=50+10       │
└────────────────────────┬──────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────┐
│                 PostgreSQL 16 (主从复制)               │
│  max_connections=300 / shared_buffers=1GB / work_mem=8MB│
│  业务数据 + 配置 + 血缘 + 工作区 + 审计 + pgvector扩展  │
│  P10 不建 document_chunks.embedding，不写死 1536        │
└──────────────────────────────────────────────────────┘

可观测性：
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Prometheus   │  │   Grafana     │  │  Filebeat/ELK │
│  指标采集      │  │  监控可视化    │  │  日志采集      │
└───────────────┘  └───────────────┘  └───────────────┘
       │
       ├── postgres_exporter
       ├── redis_exporter
       ├── nginx-exporter
       └── blackbox_exporter

预留组件（后续启用）：
GPU服务器 / Ollama/vLLM / LangChain
4.4 待确定问题列表
编号	问题	影响	建议	责任人	截止日期	状态
P10-OPEN-001	GPU 资源是否申请？	AI 后续	与 IT 确认	项目经理	P10 启动前	待确认
P10-OPEN-002	pgvector 维度	Embedding	P10 不写死，后续迁移	数据库工程师	P10 结束前	待确定
P10-OPEN-003	SMTP 服务器	通知	与 IT 确认	运维工程师	P10 启动前	待确认
P10-OPEN-004	备份策略	数据安全	每日全量+15 分钟 WAL，RPO≤30min	运维工程师	已确认	已确认
P10-OPEN-005	告警通知对象	运维	系统管理员+值班运维	运维工程师	P10 启动前	待确认
P10-OPEN-006	移动端 E2E	测试	仅桌面	测试工程师	已确认	已确认
P10-OPEN-007	用户手册语言	文档	中文为主，必要时英文	文档工程师	已确认	已确认
P10-OPEN-008	开发计划升版	计划	升 V1.4，按 10.0–10.7	项目经理	P10 启动前	待确认
P10-OPEN-009	左移计划	进度	P8/P9 并行	项目经理	P8 启动前	待确认
P10-OPEN-010	内网 CIDR 清单	AI 校验	IT 提供	运维工程师	P10 启动前	待确认
P10-OPEN-011	RTO 目标	备份	RTO≤2h	运维工程师	已确认	已确认
P10-OPEN-012	培训材料范围	文档	交付材料，不执行培训	文档工程师	已确认	已确认
P10-OPEN-008/009/010 为 P10 启动前置条件，未确认不得启动 P10。

4.5 工作量估算
模块	估算
10.0 前置与测试左移	0.5–1 人周，左移
10.1 AI 预留	0.5–1 人周
10.2 E2E	2–3 人周，部分左移
10.3 压测	1–1.5 人周，环境左移
10.4 部署与可观测性	1.5–2 人周
10.5 用户文档	1–2 人周，左移
10.6 知识转移	0.5–1 人周
10.7 生产就绪评审	0.5–1 人周
合计	约 8–12 人周
P10 时间盒 4 周，必须至少 2–3 人并行，并真实左移。

4.6 上线检查清单与 Go/No-Go 模板
4.6.1 上线检查清单
□ P10 SPEC V1.3 冻结。
□ 开发计划 V1.4 发布。
□ SUP-007、SUP-002 V1.4、P3-SIM V1.1 冻结。
□ CI 迁移 pcs/pcs_test 通过。
□ AI 501、审计、脱敏、CIDR 校验通过。
□ 纯 ASGI 中间件集成测试通过。
□ E2E 18 场景全量通过。
□ 性能 P95 达标，P99 记录，错误率≤1%。
□ PgBouncer 连接容量验证通过。
□ Docker Compose 全服务启动。
□ 监控告警演练通过。
□ 备份恢复 RPO≤30min，RTO≤2h。
□ 安全扫描、依赖漏洞、镜像扫描无高危。
□ 回滚演练、数据迁移演练通过。
□ 用户文档、管理员手册、FAQ、培训材料完成。
□ Runbook 完成。
□ 应急联系人明确。
4.6.2 Go/No-Go 会议纪要模板
项目	内容
会议时间	
参会人	
版本	P10 SPEC V1.3 / 开发计划 V1.4
上线范围	
检查清单结果	
遗留风险	
回滚方案	
决策	Go / No-Go
决策人	
备注	
第五部分：结论
V1.3 已修订复审 H1–H7，并吸收中优先级 1–5、8–10 及低优先级编辑项。修订后：

AI 中间件改为纯 ASGI 安全读 body，审计改用 ARQ，request_id 服务端生成，client_request_id 另存，中间件不再捕获 AINotImplementedError。

import-linter 只禁止 openai/ollama/vllm/langchain，httpx 由自定义架构测试约束。

E2E 统一编号 E2E-001~E2E-018，验收口径一致。

PgBouncer 容量量化，PostgreSQL 内存基线明确，pgbouncer 版本固定。

JWT 验签、body hash、document_chunks 未来迁移、INTERNAL_CIDRS 解析、TEST_VIEWER、exporters/filebeat、备份恢复、interrogate 配置均已补齐。

日期填实，OPEN 项责任人/截止日期明确，OpenAPI 使用 x-status: reserved。

完成上述修订后，P10 SPEC V1.3 可作为唯一有效规格冻结，并同步开发计划 V1.4。冻结前置条件：SUP-007、SUP-002 V1.4、P3-SIM V1.1、开发计划 V1.4 全部冻结后，P10 才启动。

P10 SPEC V1.3 完。


