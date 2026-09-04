P10 AI预留与测试部署开发规格说明书
文件标识	PCS-REQ-2026-002-SPEC-P10
当前版本	V1.1
发布日期	2026-08-27（V1.1 修订 2026-08-28，incorporate SUP-007）
编制部门	工艺部 / 信息化联合项目组
适用对象	内部开发团队（后端/前端/测试/数据库/运维）
关联文档	PCS-REQ-2026-002 V2.2、SUP-001 §3.3.13、SUP-002 §4.1、SUP-003~007、SPEC-P0~P9
第一部分：引言
1.1 目的
本文档定义P10阶段（AI预留与测试部署）的完整需求规格，明确AI接口预留、全流程端到端测试、性能压测、部署文档和用户文档的详细功能需求、接口规范、测试场景和验收标准。P10阶段是系统正式上线的最后阶段，确保系统在功能、性能、安全和运维方面达到生产就绪状态。

1.2 文档范围
包含：

AI预留接口：/api/v1/ai/*路由骨架、DocumentChunks表与pgvector支持、AiAuditLog表、数据脱敏中间件、LangChain集成骨架

全流程E2E测试：完整业务场景测试、状态机全路径覆盖、权限矩阵验证

性能压测：并发用户测试、响应时间验证、数据库负载测试

部署文档：Docker Compose配置、环境变量清单、数据库迁移指南、监控告警配置

用户文档：用户手册、管理员手册、常见问题FAQ

知识转移：代码注释整理、架构文档

不包含：

AI功能的实际业务实现（仅预留接口，不实现具体模型逻辑）

生产环境实际部署（仅提供部署文档和配置）

用户培训执行（仅提供培训材料）

1.3 定义、缩略语和术语
术语/缩写	定义
AI	Artificial Intelligence，人工智能
LLM	Large Language Model，大语言模型
RAG	Retrieval-Augmented Generation，检索增强生成
pgvector	PostgreSQL向量扩展
Embedding	文本向量化表示
E2E	End-to-End，端到端测试
k6	性能压测工具
Docker Compose	多容器编排工具
ELK	Elasticsearch + Logstash + Kibana日志栈
Prometheus	监控告警系统
数据脱敏	隐藏或替换敏感信息
Ollama	本地LLM推理工具
vLLM	高性能LLM推理框架
LangChain	LLM应用开发框架
私有化部署	模型部署在公司内网，禁止外部API调用
1.4 参考文献
SUP-001 §3.3.13（大模型AI辅助功能预留接口）

SUP-002 §4.1（AI预留接口Python技术栈调整）

SUP-002 §3.2.19（Python计算引擎规范）

HT-REQ-2026-002 V2.2 §4（非功能需求——性能/安全/可靠性）

SPEC-P0 §3.2.4（AD认证）、§3.2.5（CI/CD）

SPEC-P1（状态机/版本/血缘）

SPEC-P9（工作流与权限）

全部SPEC-P0~P9（测试覆盖范围）

1.5 文档概述
本文档共四个部分。第一部分说明目的、范围和术语。第二部分描述P10阶段的定位和功能。第三部分详细定义AI预留接口、测试、部署和文档的需求。第四部分为附录，包含AI接口详细定义、E2E测试场景清单、部署架构和待确定问题。

第二部分：综合描述
2.1 产品前景
P10阶段是系统正式上线前的收尾阶段。AI预留接口为系统未来的智能化扩展奠定技术基础（不实现具体AI功能）；全流程测试确保系统端到端的功能正确性；性能压测验证系统在生产负载下的稳定性；部署文档和用户文档确保系统的可运维性和可用性。

2.2 产品功能
功能模块	核心能力
AI接口预留	路由骨架、数据库表、脱敏中间件、模型服务接口
E2E测试	全流程业务场景、状态机路径、权限验证
性能压测	并发测试、响应时间、数据库负载
部署文档	Docker配置、环境变量、迁移指南、监控配置
用户文档	用户手册、管理员手册、FAQ
知识转移	架构文档、代码注释
2.3 用户类和特征
用户类	特征	P10阶段相关需求
后端开发工程师	维护和扩展系统	架构文档、代码注释
系统管理员	部署和运维	部署文档、监控配置
工艺工程师（最终用户）	使用系统	用户手册、FAQ
测试工程师	质量保障	E2E测试、性能压测
未来AI开发人员	后续实现AI功能	AI预留接口文档
2.4 运行环境
同SPEC-P0 §2.4，增加以下AI预留组件环境：

组件	规格
GPU服务器（预留）	NVIDIA GPU（如A100/A10），用于LLM推理
Ollama/vLLM	本地模型推理框架
pgvector	PostgreSQL扩展，支持向量存储和相似度检索
Redis	缓存和任务队列
2.5 设计和实现上的限制
AI不参与确定性计算：LLM不参与任何数值计算，不替代签署动作。

私有化强制：所有LLM模型必须部署于公司内网，禁止调用外部云AI服务。

数据脱敏强制：发送给LLM的文本必须经过脱敏处理。

结果人工确认：AI输出的任何建议/数据需用户手动确认后方可写入。

性能指标强制：所有性能指标必须达到SPEC V2.2 §4.1的要求。

文档完整性：部署文档和用户文档必须在代码合并前完成。

2.6 假设和依赖
依赖P0~P9全部完成：所有功能模块已开发并通过单元测试。

假设：有GPU服务器或可申请GPU资源（用于后续AI功能）。

假设：公司有标准的Docker镜像仓库。

假设：监控告警基础设施（Prometheus/ELK）已部署或可部署。

假设：有真实项目数据可用于E2E测试。

第三部分：具体需求
3.1 外部接口需求
3.1.1 用户界面
P10阶段交付的UI组件：

界面	规格
AI助手入口（预留）	右下角悬浮图标，点击弹出对话面板（占位，不可用状态显示"AI功能即将上线"）
测试报告页	展示E2E测试结果和性能测试报告（开发内部使用）
系统状态页	展示服务健康状态、数据库状态、Redis状态（管理员使用）
3.1.2 软件接口
AI预留接口：

接口组	端点	说明	状态
意图识别	POST /api/v1/ai/intent	自然语言指令→意图+实体	返回501
知识库检索	POST /api/v1/ai/knowledge/search	RAG语义检索	返回501
设备推荐	POST /api/v1/ai/equipment/recommend	相似设备推荐	返回501
自然语言解释	POST /api/v1/ai/explain	变更自然语言描述	返回501
文档解析	POST /api/v1/ai/document/extract	PDF/图片字段提取	返回501
健康检查接口：

接口组	端点	说明
服务健康	GET /api/v1/health	后端服务状态
GET /api/v1/health/db	数据库连通性
GET /api/v1/health/redis	Redis连通性
GET /api/v1/health/ai	AI服务状态（预留，返回not_configured）
3.2 功能需求
3.2.1 AI预留接口
需求编号：P10-AI-001

功能描述：为未来引入LLM辅助功能预留技术接口、数据结构和安全约束。当前版本不实现具体AI功能，但预留设计须在开发中落实。

（1）AI路由骨架

在FastAPI后端增加/api/v1/ai/*路由组：

python
# app/api/v1/ai/__init__.py
from fastapi import APIRouter

ai_router = APIRouter(prefix="/api/v1/ai")

@ai_router.post("/intent")
async def ai_intent(request: AiIntentRequest):
    """意图识别与指令分发（预留）"""
    return {"status": "not_implemented", "message": "AI功能即将上线"}

@ai_router.post("/knowledge/search")
async def ai_knowledge_search(request: AiKnowledgeSearchRequest):
    """知识库检索（预留）"""
    return {"status": "not_implemented"}

@ai_router.post("/equipment/recommend")
async def ai_equipment_recommend(request: AiEquipmentRecommendRequest):
    """相似设备推荐（预留）"""
    return {"status": "not_implemented"}

@ai_router.post("/explain")
async def ai_explain(request: AiExplainRequest):
    """自然语言解释（预留）"""
    return {"status": "not_implemented"}

@ai_router.post("/document/extract")
async def ai_document_extract(request: AiDocumentExtractRequest):
    """文档解析（预留）"""
    return {"status": "not_implemented"}
（2）数据表预留

表名	字段	说明
document_chunks	chunk_id, document_id, content, vector_id, source, created_at	文档切片存储，pgvector向量
ai_audit_log	log_id, user_id, timestamp, request_summary, response_summary, model_version	AI调用审计
pgvector扩展启用：

sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE document_chunks ADD COLUMN embedding vector(1536);
（3）数据脱敏中间件

python
# app/core/ai_sanitizer.py
SENSITIVE_PATTERNS = [
    (r'\b[A-Z]{2,4}-\d{3,5}[A-Z]?\b', '[EQUIPMENT_TAG]'),  # 设备位号
    (r'\b\d{4}\.\d{3}\.\d{3}\b', '[PROJECT_NO]'),          # 项目编号
    (r'\b[A-Z]{2}-\d{3}\b', '[LINE_NO]'),                  # 管线号
]

def sanitize_for_ai(text: str) -> str:
    """对发送给LLM的文本进行脱敏"""
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text
（4）模型服务接口预留

组件	预留方式	说明
LangChain	依赖声明（暂不安装）	后续启用时安装
Ollama	配置预留	内网端点配置
vLLM	部署预留	GPU服务器配置
pgvector	数据库扩展启用	用于Embedding存储
（5）AI功能开关

在ADMIN系统参数中增加：

ai_enabled：全局开关，默认false

ai_model_version：模型版本标识

ai_endpoint：内网模型服务端点

ai_timeout：推理超时时间（秒）

验收标准：

AI路由返回501（未实现）

DocumentChunks和AiAuditLog表已创建

pgvector扩展已启用

数据脱敏中间件可用于后续使用

AI功能开关可配置

健康检查/health/ai返回not_configured

3.2.2 全流程E2E测试
需求编号：P10-TST-001

功能描述：实现覆盖完整业务流程的端到端测试。

（1）核心E2E测试场景

场景编号	场景	覆盖模块	预期
E2E-001	项目创建→BEDD录入→输入清单生成	PMS + CONFIG + 输入清单	项目创建成功，清单自动生成
E2E-002	SIM导入→物流验证	SIM + FLASH	解析正确，物性补全
E2E-003	PIPE计算→管道一览表	PIPE + PIPE_CLASS + SIM	计算结果正确，管表输出
E2E-004	PUMP计算→泵数据表	PUMP + PIPE + SIM	泵选型正确
E2E-005	PSV计算→安全阀数据表	PSV + VESSEL + FLASH	泄放面积正确
E2E-006	VESSEL计算→容器数据表	VESSEL + SIM	尺寸计算正确
E2E-007	EQUIP_LIST汇总	EQUIP_LIST + 各计算模块	设备表完整
E2E-008	UTIL能耗汇总	UTIL + EQUIP_LIST	能耗计算正确
E2E-009	REPORT生成→计算书	REPORT + 全部数据	计算书生成正确
E2E-010	完整签署流程（两层）	全部 + 状态机	记录 DRAFT→IN_APPROVAL→CHECKED；交付物选版本目的→Rev 0→签署矩阵→APPROVED（含客户代录）
E2E-011	上游变更影响分析	SIM + 全部下游	已绑定记录 STALE；哈希不变恢复、变化走 CHANGE_PENDING→CHANGED
E2E-012	供应商数据录入与核算	EQUIP_LIST + UTIL	偏差报告和实际值更新
E2E-013	自定义报表执行	REPORT_BUILDER + EQUIP_LIST	数据提取正确（即席导出带非发布件水印）
E2E-014	用户权限验证	ADMIN + 全部	越权操作被拒绝
E2E-015	变更单闭环	交付物机制（CHANGE_NOTICE）	变更单签署→绑定记录 CHANGED→CHECKED，change_resolved_by 正确
E2E-016	位号终身唯一	任一计算模块	OBSOLETE 记录位号新建复用被 403 拒绝
E2E-017	撤销与放弃	记录层	CHANGE_PENDING 放弃恢复快照；CHANGED 撤销经 REVERSAL_PENDING 批准回滚
E2E-018	工作区隔离	P1 工作区	个人区提交批准/创建交付物 403；导入后新记录从 DRAFT 起步
（2）状态机全路径覆盖

路径编号	状态迁移路径（V1.1 两层模型）	覆盖场景
WF-PATH-01	DRAFT→IN_APPROVAL(step=1..N)→CHECKED	记录批准正向全流程
WF-PATH-02	DRAFT→IN_APPROVAL→CHECK_REJECTED→DRAFT→…→CHECKED	批准退回后重走
WF-PATH-03	CHECKED(锁定)→STALE→重算哈希不变→CHECKED	上游变更无实质影响
WF-PATH-04	CHECKED(锁定)→STALE→重算哈希变化→CHANGE_PENDING→CHANGED→变更单/新Rev→CHECKED	上游变更实质影响闭环
WF-PATH-05	CHANGED→REVERSAL_PENDING→批准回滚CHECKED / 驳回回CHANGED	分级撤销
WF-PATH-06	交付物：DRAFT→选版本目的→Rev→签署矩阵（含 CUSTOMER_PENDING→代录 PROXIED）→APPROVED	交付物发布
WF-PATH-07	未绑定记录→OBSOLETE（免凭证）/ 已绑定→RECORD_CANCELLATION 变更单→OBSOLETE	弃用（位号终身锁定）
（3）权限矩阵验证

测试	操作	角色	预期
AUTH-E2E-01	编辑草稿	DESIGNER	200
AUTH-E2E-02	编辑草稿	CHECKER	403
AUTH-E2E-03	校核通过	CHECKER	200
AUTH-E2E-04	校核通过	DESIGNER	403
AUTH-E2E-05	审定通过	APPROVER	200
AUTH-E2E-06	审定通过	DESIGNER	403
AUTH-E2E-07	查看审计日志	SYSADMIN	200
AUTH-E2E-08	查看审计日志	DESIGNER	403
（4）E2E测试实现

方法	说明
后端测试	pytest + httpx + Mock认证切换
前端测试	Playwright + Mock登录页
数据准备	种子脚本自动生成标准测试项目数据
执行方式	CI中自动执行，或手动触发
验收标准：

18个核心E2E场景全部通过

状态机7条关键路径全部覆盖

权限矩阵8个关键验证全部通过

E2E测试在CI中可自动执行

3.2.3 性能压测
需求编号：P10-PRF-001

功能描述：验证系统在生产负载下的性能表现。

（1）性能指标要求（来自SPEC V2.2 §4.1）：

操作类型	响应时间要求
页面切换、Tab切换	≤500ms
单次计算（如管径迭代）	≤2秒
复杂报表生成	≤10秒
数据库并发连接池	≥200并发用户
（2）压测场景

场景	并发用户数	持续时间	验证指标
登录认证	200	5分钟	响应时间≤1s，成功率≥99%
项目浏览	100	10分钟	响应时间≤500ms
PIPE计算	50	10分钟	响应时间≤2s
报表生成	20	5分钟	响应时间≤10s
设备表查询	100	10分钟	响应时间≤2s
签署操作	50	5分钟	响应时间≤1s
（3）压测工具

工具	用途
k6	HTTP API压测
Playwright	前端页面性能
PostgreSQL监控	数据库负载
Redis监控	缓存性能
（4）压测报告

内容	说明
场景结果	每场景的P50/P95/P99响应时间
错误率	每场景错误百分比
数据库指标	连接数、CPU、内存、IO
瓶颈分析	性能瓶颈和建议优化方向
结论	是否达到生产就绪标准
验收标准：

所有场景达到响应时间要求

错误率≤1%

数据库无性能瓶颈

压测报告完整

3.2.4 部署文档
需求编号：P10-DEP-001

功能描述：提供完整的生产部署文档和配置。

（1）Docker Compose配置

yaml
# docker-compose.prod.yml
version: '3.8'
services:
  nginx:
    image: nginx:1.25-alpine
    ports: ["443:443"]
    volumes: ["./nginx.conf:/etc/nginx/nginx.conf", "./certs:/etc/nginx/certs"]
    
  backend:
    image: process-calc-backend:latest
    environment:
      - ENV=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET=${JWT_SECRET}
      - AD_LDAP_SERVER=${AD_LDAP_SERVER}
      - AI_ENABLED=false
    depends_on: [redis]
    
  redis:
    image: redis:7-alpine
    volumes: ["redis-data:/data"]
    
  worker:
    image: process-calc-backend:latest
    command: arq app.worker.WorkerSettings
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on: [redis]
（2）环境变量清单

变量	说明	默认值
ENV	环境标识	production
DATABASE_URL	数据库连接串	—
REDIS_URL	Redis连接串	—
JWT_SECRET	JWT签名密钥	—
AD_LDAP_SERVER	AD服务器地址	—
AD_DOMAIN	AD域名	—
AI_ENABLED	AI功能开关	false
AI_ENDPOINT	AI服务端点	—
LOG_LEVEL	日志级别	INFO
SESSION_TIMEOUT	会话超时（分钟）	30
（3）数据库迁移指南

使用Alembic迁移，版本化数据库Schema

提供升级和回滚命令

包含数据备份和恢复步骤

（4）监控告警配置

监控项	工具	告警阈值
服务存活	Prometheus	连续3次探测失败
CPU使用率	Prometheus	>80%持续5分钟
内存使用	Prometheus	>85%持续5分钟
数据库连接数	PostgreSQL监控	>80%最大连接数
磁盘使用	Prometheus	>80%
错误日志	ELK	Error级别日志
API响应时间	Prometheus	P95>2秒持续10分钟
验收标准：

Docker Compose配置可启动全部服务

环境变量清单完整

数据库迁移指南可执行

监控告警配置正确

3.2.5 用户文档
需求编号：P10-DOC-001

功能描述：提供完整的用户手册、管理员手册和FAQ。

（1）用户手册

章节	内容
系统简介	系统概述、功能模块介绍
快速入门	登录、项目创建、基本操作流程
各模块操作指南	PMS/SIM/PIPE/PUMP/PSV/VESSEL/HEAT/CV/UTIL操作说明
报表生成	计算书/数据表生成方法
签署流程	提交/校核/审核/审定操作说明
常见问题	FAQ
（2）管理员手册

章节	内容
系统部署	环境要求、部署步骤
用户管理	AD同步、角色分配
配置管理	公式/系数/模板/标准库管理
审计日志	日志查询和分析
备份恢复	数据备份和恢复流程
故障排查	常见问题诊断和解决
（3）FAQ

覆盖以下类别：

登录和认证问题

计算错误处理

签署流程问题

数据导入导出问题

权限问题

验收标准：

用户手册覆盖所有模块

管理员手册覆盖运维场景

FAQ覆盖常见问题≥20条

3.3 非功能需求
3.3.1 性能需求
指标	要求
系统启动时间	≤30秒
数据库迁移执行	≤5分钟
并发用户数	≥200
系统可用性	MTBF≥720小时
3.3.2 安全性需求
指标	要求
AI数据脱敏	强制启用
AI审计日志	记录所有AI请求响应
AI模型私有化	禁止外部API调用
部署配置安全	密钥通过环境变量注入，不硬编码
3.3.3 可维护性需求
指标	要求
架构文档	完整记录系统组件和交互
代码注释	核心模块注释覆盖率≥50%
部署自动化	Docker Compose一键启动
监控覆盖	核心指标全部覆盖
3.4 数据需求
P10阶段创建/修改以下表：

document_chunks（AI预留）

ai_audit_log（AI预留）

system_settings（系统参数，如P9未创建）

启用pgvector扩展（PostgreSQL）：

sql
CREATE EXTENSION IF NOT EXISTS vector;
第四部分：附录
4.1 AI预留接口详细定义
4.1.1 意图识别接口
text
POST /api/v1/ai/intent

请求体：
{
  "text": "帮我把泵P-101的流量设为50 m3/h",
  "context": {
    "projectId": "uuid",
    "module": "PUMP",
    "recordId": "uuid"
  }
}

当前响应（P10阶段）：
{
  "status": "not_implemented",
  "message": "AI功能即将上线",
  "code": "AI_NOT_IMPLEMENTED"
}

未来响应（后续阶段）：
{
  "intent": "FILL_FORM",
  "entities": {
    "field": "flow",
    "value": 50,
    "unit": "m3/h"
  },
  "confidence": 0.95
}
4.1.2 知识库检索接口
text
POST /api/v1/ai/knowledge/search

请求体：
{
  "query": "API 520 火灾工况润湿面积修正系数",
  "topK": 5
}

当前响应（P10阶段）：
{
  "status": "not_implemented",
  "message": "AI功能即将上线"
}

未来响应（后续阶段）：
{
  "results": [
    {
      "docId": "STD-API520-2014",
      "content": "...",
      "source": "规范库",
      "score": 0.92
    }
  ]
}
4.1.3 AI功能开关配置
在ADMIN系统参数中增加：

json
{
  "ai_enabled": false,
  "ai_model_version": null,
  "ai_endpoint": null,
  "ai_timeout": 30,
  "ai_max_tokens": 4096,
  "ai_temperature": 0.1
}
4.2 部署架构图
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
│  FastAPI后端  │  │  ARQ Worker   │  │  静态文件      │
│  (Gunicorn)   │  │  (后台任务)    │  │  (前端构建)    │
└───────┬───────┘  └───────┬───────┘  └───────────────┘
        │                  │
        │                  │
┌───────▼──────────────────▼───────────────────────────┐
│                       Redis                           │
│              缓存 / 任务队列 / 编辑锁                   │
└──────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────┐
│                 PostgreSQL 16 (主从复制)               │
│  ┌─────────────────────────────────────────────────┐  │
│  │  业务数据 + 配置数据 + 血缘 + 工作区 + 审计日志   │  │
│  │  + pgvector扩展（AI向量预留）                     │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘

预留组件（后续阶段启用）：
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  GPU服务器     │  │  Ollama/vLLM  │  │  LangChain    │
│  (AI推理)      │  │  (模型服务)    │  │  (AI编排)     │
└───────────────┘  └───────────────┘  └───────────────┘
4.3 待确定问题列表
编号	问题	影响	建议解决方案	状态
P10-OPEN-001	GPU服务器资源是否已申请？	AI后续开发	需与IT部门确认GPU资源可用性	待确认
P10-OPEN-002	pgvector的向量维度选择？	Embedding存储	如使用OpenAI Embedding为1536，本地模型可能不同	待后续确定
P10-OPEN-003	邮件通知使用哪个SMTP服务器？	通知功能	需与IT确认	待确认
P10-OPEN-004	生产环境的备份策略是否已有标准？	数据安全	每日全量+每15分钟WAL日志，RPO≤30min	已确认
P10-OPEN-005	监控告警通知发送给谁？	运维响应	系统管理员+值班运维	待确认
P10-OPEN-006	E2E测试是否需要覆盖移动端？	测试范围	系统仅支持桌面浏览器，无需移动端	已确认
P10-OPEN-007	用户手册的语言版本？	文档编写	中文为主，必要时补充英文	已确认
4.4 工作量估算
模块	自研内容	估算工作量
AI接口预留	路由骨架、表创建、脱敏中间件	0.5-1人周
E2E测试	14个核心场景、状态机路径、权限验证	2-3人周
性能压测	k6脚本、执行、报告分析	1-1.5人周
部署文档	Docker配置、环境变量、迁移指南、监控配置	1-1.5人周
用户文档	用户手册、管理员手册、FAQ	1-2人周
知识转移	架构文档、代码注释整理	0.5-1人周
合计		约6-10人周
P10 SPEC完。 本文档与SPEC-P0至SPEC-P9合并，构成完整的《工艺专用综合计算软件》分阶段开发规格说明书体系（共11份文档）。

全体系文档清单
编号	文档	版本	状态
P0	项目初始化与基础设施开发规格说明书	V1.2	完整
P1	横切关注点框架开发规格说明书	V1.2	完整
P2	CONFIG配置中枢开发规格说明书	V1.2	完整
P3	基础数据层开发规格说明书	V1.2	完整
P4	核心计算引擎（第一批）开发规格说明书	V1.2	完整
P5	设备计算模块（第二批）开发规格说明书	V1.2	完整
P6	高级计算模块（第三批）开发规格说明书	V1.2	完整（含补完）
P7	集成模块开发规格说明书	V1.1	完整
P8	报表与输出开发规格说明书	V1.1	完整
P9	工作流与权限开发规格说明书	V1.2	完整
P10	AI预留与测试部署开发规格说明书	V1.1	完整

## 版本历史（本文档）

| 版本 | 日期 | 修改内容 | 编制人 |
|---|---|---|---|
| V1.0 | 2026-08-27 | 初始版本 | 联合项目组 |
| V1.1 | 2026-08-28 | incorporate SUP-007：E2E 场景扩至 18 个（变更单闭环/位号终身唯一/撤销/工作区隔离）、状态机路径改为两层模型 7 条；文件标识改 PCS 前缀 | 联合项目组 |
