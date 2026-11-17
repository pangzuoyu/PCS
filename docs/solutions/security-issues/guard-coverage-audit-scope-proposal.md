---
module: pcs-backend app/api/v1 — 守卫覆盖审计
date: 2026-11-18
problem_type: security_issue
component: security / authorization
severity: medium
tags: [guard-coverage, audit, authorization, TODO-129, P10-F, F3-T1]
---

# 守卫覆盖审计 · **范围提案 + 初判**（F3-T1 · TODO-129）

> ⚠️ **本文件只是「提案 + 初判」** ⇒ ⇒ **范围由人裁决**（主计划 Q10）
> ⇒ ⇒ 审计范围批下来之后才开 F3-T2 / F3-T3 ⇒ ⇒ 本文件**不**替人定范围。

## 一、为什么要有这次审计

P10-B 评审（#7）给真后端通道加了一条「**路由可达性扫描**」⇒ ⇒ 它扫的是
**物流面**（`/streams` · `/projects` · `/piping` …）⇒ ⇒ 物流面外的模块
（`config.py` · `report_builder.py` · `psychro.py` …）的守卫覆盖面
**从来没被审过** ⇒ ⇒ 一个「跨项目访问」可能在那里畅通 ⇒ ⇒
**「未审即没问题」不是结论，是空白**。

⇒ ⇒ 本次审计的产出应当是**结论**（已覆盖 / 缺口），不是「看起来没问题」。

## 二、候选范围（**待人裁决**）

全仓 `app/api/v1/` 共 **54 个模块 · 313 个端点**（本文件用 AST 枚举，
端点清单可复跑）。按「与项目/租户数据的关系」分四档：

| 档 | 含义 | 候选模块（端点数） | 建议 |
|---|---|---|---|
| **A · 强隔离相关** | 读写**项目级**业务数据 ⇒ 跨项目访问 = 越权 | `config.py`（12）· `report_builder.py`（9）· `psychro.py`（13）· `records.py`（6）· `report.py`（10） | ⭐ **第一批**（计划点名的那三个 + 两个同族） |
| **B · 工作区 / 身份面** | 资源属主维度（owner）⇒ 越权 = 看到别人的工作区 | `workspaces.py`（4）· `admin_users.py` · `user_projects.py` · `grants.py` | 第二批 |
| **C · 纯计算 / 公共字典** | 无用户数据（物性库 · 公式库 · 枚举）⇒ 越权无意义 | `common.py`（5）· `toe_conversion` · `safety` · `allowable-stress` | 第三批（或**不审**，需人定） |
| **D · 全局 / 系统面** | 系统参数 · 审计 · 队列 · 健康 | `meta.py` · `audit.py` · `health.py` · `tasks.py` | 第四批（或**不审**） |

⚠️ **候选清单是「按名字与端点数数出来的」，不是「审过的」** ⇒ ⇒
**每一条的最终判定都要在 F3-T2/T3 里逐个读端点得出**。

## 三、初判（**机器枚举的结果，不是审计结论**）

枚举口径：对每个端点，取它的**函数体**，看有没有出现下列守卫调用之一 ——
`check_project_access_or_404` · `check_project_access` · `require_roles` ·
`require_formal_project_workspace` · `current_actor`。
⇒ ⇒ **「没出现」≠「没守卫」**（守卫可能在 service 层、或用了别的名字）
⇒ ⇒ ⇒ **这只能当「候选缺口清单」用**。

### 3.1 带资源 id 却**没在端点里**出现守卫调用的端点（**候选缺口**）

| 模块 | 端点 | 初判 |
|---|---|---|
| `report_builder.py` | `GET/PUT /report-builder/definitions/{def_id}` | ⚠️ **报告定义**是项目级资源 ⇒ 跨项目改别人��定义 = 越权 ⇒ **优先审** |
| `report_builder.py` | `POST /report-builder/definitions/{def_id}/execute` | ⚠️ 同上（执行） |
| `report_builder.py` | `GET /report-builder/executions/{task_id}` | ⚠️ 任务 id **不可猜** ⇒ 泄露风险低但仍要审 |
| `report.py` | `GET /report/{report_file_id}/status` · `/download` · `/hash` · `GET /report/verify/{id}` | ⚠️ 报表文件是项目级产物 ⇒ **优先审**（下载别人的报表 = 越权） |
| `report.py` | `GET /report/styles` · `GET/PATCH /report/styles/{style_id}` | ⚠️ 样式是**全局**资源 ⇒ 越权语义待定（需人定：全局资源算不算越权） |
| `records.py` | `GET /records/piping` · `GET /records/piping/{pipe_id}` · `/snapshots` | ⚠️ **记录是项目级** ⇒ 疑似真缺口 ⇒ **优先审** |
| `workspaces.py` | `POST /workspaces` · `GET /workspaces` · `GET /workspaces/{workspace_id}` | ⚠️ 工作区 id **本身就是访问令牌语义**（见该端点 docstring）⇒ 越权语义待定 |

### 3.2 初判**看不出问题**的模块（候选 A 档里没上榜的）

- `config.py`（12 端点）：端点层都出现了守卫调用 ⇒ **初判「已覆盖」** ⇒
  ⇒ 但计划点名的正是它 ⇒ ⇒ **F3-T2 要逐条读**（守卫到底判的是**哪个 id**、
  ⇒ 以及未授权时**返回什么**）。
- `psychro.py`（13 端点）：13 个端点里只有 `results` 那几个带 `record_id` ⇒
  ⇒ 其余 9 个是**纯计算**（`humidity-ratio` · `dew-point` · …）⇒ ⇒
  ⇒ **初判「无越权面」** ⇒ ⇒ 但 `POST/GET/PATCH/DELETE /psychro/results*`
  ⇒ ⇒ 那 4 个是**记录** ⇒ ⇒ 要审。
- `common.py`（5 端点）：纯公共字典 ⇒ 初判「无越权面」。

## 四、要人裁决的 4 件事

| # | 问题 | 为什么必须人裁 |
|---|---|---|
| 1 | **审计范围**：只审 A 档（34+ 端点）？还是 A+B？还是全仓 313 个？ | 范围决定工作量与风险面 ⇒ **人定**（主计划 Q10） |
| 2 | **全局资源算不算越权面**（报告样式 · 系统参数 · 审计日志）？ | 这是**产品/安全语义**问题 ⇒ 机器判不了 |
| 3 | **「工作区 id = 访问令牌」这个既有语义**要不要保留？ | 若保留 ⇒ 工作区相关端点**不进**越权审计范围 |
| 4 | **判据先写死**（计划 D6：每个端点必答 4 问）要不要照用？ | 影响 F3-T2/T3 的产出格式 ⇒ 人定 |

## 五、审计方法（F3-T2/T3 用 ⇒ **待范围确定后展开**）

每个端点必答 4 问（缺任一问 ⇒ 即算缺口）：

1. 端点从哪个参数拿到**资源 id**？
2. 该 id 是否**按当前用户/项目**做授权判定？
3. 未授权时**返回什么**？（404 = 与「不存在」同形 ✓ · 403 ⚠️ 泄露存在性 · **200** ⇒ 缺口）
4. 授权判定发生在**哪一行**？

⇒ ⇒ 输出**一张统一表格** ⇒ ⇒ 缺口逐条登记 TODO ⇒ ⇒
⇒ ⇒ **已覆盖**的必须给出**断言位置**（「代码里有守卫调用」**不等于**「有断言」）⇒ ⇒
⇒ ⇒ 再从「已覆盖」里**抽样 ≥ 3 个**做**变异实测**（删掉守卫 ⇒ 断言必须红）
⇒ ⇒ ⇒ 变异后**无人应答** ⇒ ⇒ 那本身就是缺口。

## 六、状态

- **2026-11-18**：F3-T1 完成（范围提案 + 初判 + 要人裁决的 4 件事）⇒ ⇒
  ⇒ **等范围批复** ⇒ ⇒ F3-T2 / T3 未开。
- **归属**：P10-F（F3）· TODO-129。
