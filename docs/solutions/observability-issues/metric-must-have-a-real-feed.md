---
module: pcs-backend 可观测性（app/core/metrics.py · app/api/v1/status.py · deploy/prometheus）
date: 2026-11-24
problem_type: observability_issue
component: monitoring
severity: medium
symptoms:
  - "Prometheus 面板上 `pcs_signatures_pending 0.0` ⇒ ⇒ 读成「**没有待签署**」⇒ ⇒ 而真相是「**根本没人测**」"
  - "「队列积压 > 50」告警**永不触发** ⇒ ⇒ 队列真的堆到 5000 也**不响**"
  - "Redis 挂了 ⇒ ⇒ 队列深度报 **0** ⇒ ⇒ 「测不到」被读成「队列空」"
  - "`/status` **匿名可读** ⇒ ⇒ 队列深度 / worker 心跳 / LDAP 主机 / DB 与 Redis 延迟 ⇒ ⇒ 一张**内部拓扑图**"
root_cause: metric_defined_but_never_fed
resolution_type: design_and_code_fix
framework_version: prometheus-client 0.26 / FastAPI 0.141 / ARQ
related_components:
  - monitoring
  - api
---

# 指标「定义了」≠「有值」—— 三种**假零**

## 一句话

`prometheus_client` 的**无标签** Gauge **创建即报 `0.0`**
⇒ ⇒ ⇒ 一个从来没人 `.set()` 过的 gauge ⇒ ⇒ ⇒ `/metrics` 上是 `xxx 0.0`
⇒ ⇒ ⇒ 面板上**看起来「一切正常」** ⇒ ⇒ ⇒ 而真相是「**根本没测**」。

⇒ ⇒ ⇒ **假零比没有这个指标更坏**：没有 ⇒ ⇒ ⇒ 面板上**缺一条线**（一眼看见）；
有 ⇒ ⇒ ⇒ 面板上**一条 0**（看着正常）。

## 三种形状（本仓实测）

| # | 形状 | 症状 | 处置 |
|---|---|---|---|
| ① | **定义了但没人喂** | `xxx 0.0` 常驻 | **删掉**（口径没人裁 ⇒ ⇒ 没人喂 ⇒ ⇒ **先不放**）⇒ ⇒ 登记 TODO |
| ② | **事件驱动地喂**（只在有人访问某个页面时 `.set()`）| 没人访问 ⇒ ⇒ 永远是 0 ⇒ ⇒ **告警永不触发** | 改 **collector**（`collect()` 在 **scrape 时**现读）⇒ ⇒ 端点声明成 **`def`（同步）** ⇒ ⇒ FastAPI 丢 threadpool ⇒ ⇒ 阻塞读**不进事件循环** |
| ③ | **读不到时兜底成 0** | Redis 挂 ⇒ ⇒ 报 0 ⇒ ⇒ 「测不到」= 「队列空」| **不产出序列** ⇒ ⇒ 「测不到」与「真的是 0」**可区分** ⇒ ⇒ 配一条 `absent()` 告警 |

## 判定清单（写新指标前逐条过）

- [ ] 这个 gauge 的**喂点在哪个函数里**？写不出来 ⇒ ⇒ **别定义它**
- [ ] 喂点是**状态**还是**事件**？事件 ⇒ ⇒ ⇒ 用 **collector**
- [ ] 读不到时**产出序列吗**？产出 ⇒ ⇒ ⇒ 那是**假零**
- [ ] 这个「读」会不会**阻塞**？会 ⇒ ⇒ ⇒ 端点要 **`def`**（同步）⇒ ⇒ 或用异步 collector
- [ ] 有**超时**吗？redis-py **默认不超时** ⇒ ⇒ ⇒ Redis 被黑洞掉 ⇒ ⇒ ⇒
      一个 scrape **永久挂住** ⇒ ⇒ ⇒ Prometheus 把目标标 down ⇒ ⇒ ⇒ 整个监控瞎掉

## 附带一条：**标签用路由模板**

`scope["route"].path` 是**模板**（`/psychro/results/{record_id}`）⇒ ⇒ 基数有上界；
原始 URL（`/psychro/results/9f3c-…`）当标签 ⇒ ⇒ ⇒ **每条记录一条序列** ⇒ ⇒ ⇒ 被打爆。

⚠️ **FastAPI 懒挂载的副作用**：`scope["route"].path` **不含** `/api/v1` 前缀
⇒ ⇒ ⇒ `/api/v1/psychro/...` 的标签是 `/psychro/...` ⇒ ⇒ ⇒ **拼不回来**
（`scope["root_path"]` 是空的）⇒ ⇒ ⇒ ⇒ **文档化**，别让人猜。

## 附带一条：**只读 ≠ 匿名**

「状态页是只读的 ⇒ ⇒ 无需角色闸」被读成了「**无需登录**」
⇒ ⇒ ⇒ 而端点吐的是**运维内部信息**（队列深度 / worker 心跳 / LDAP 主机 / 延迟）
⇒ ⇒ ⇒ 匿名可读 = 给外人一张**内部拓扑图**。

⇒ ⇒ ⇒ **恒 200** 说的是「**组件**挂了仍 200」⇒ ⇒ ⇒ 不是「匿名也 200」。
⇒ ⇒ ⇒ 只读 ⇒ ⇒ ⇒ 无需**角色**闸（要**登录**）。

## 相关

- `pcs-backend/app/core/metrics.py`（`ARQQueueDepthCollector` 的 docstring 记着全部理由）
- `pcs-backend/app/api/v1/status.py`（`current_user` 依赖 + 「恒 200 的范围」）
- `deploy/prometheus/rules.yml`（「队列测不到」那条 `absent()` 告警）
- `.wolf/buglog.json` bug-2201 / bug-2202
