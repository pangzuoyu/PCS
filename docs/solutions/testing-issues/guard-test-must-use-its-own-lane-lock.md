---
module: pcs-backend 守门测试（tests/scripts/test_pytest_pg_gate.py）
date: 2026-11-17
problem_type: testing_issue
component: testing_framework
severity: medium
symptoms:
  - "真车道正在跑时，守门测试**红**，但报的是「另一条车道正在跑」⇒ ⇒ 测的不是它声称的那几条闸门"
  - "守门测试「测的是锁，不是闸门」⇒ ⇒ 闸门坏了也发现不了（它被挡在门外，从没进去过）"
  - "开发者于是学会「等车道跑完再跑守门测试」⇒ ⇒ 守门从「每次提交」退化成「偶尔想起来」"
root_cause: guard_test_shares_the_mechanism_it_guards
resolution_type: test_and_source_fix
framework_version: pytest / bash / flock
related_components:
  - testing_framework
  - concurrency
tags:
  - guard-test
  - isolation
  - false-red
  - lane-lock
---

# 守门测试必须与**它守护的那把锁**隔离

## 1. 现象

`scripts/pytest_pg.sh`（PG 车道与 E2E 车道共用的入口）加了**车道互斥锁**
（`flock -n 9`）⇒ ⇒ 真车道在跑时，`tests/scripts/test_pytest_pg_gate.py`
里那几条守门测试**红**——但报的是

```
FAIL: 另一条车道（PG 车道 / E2E 车道）正在跑 ⇒ 同一个库不能并发建 schema
```

⇒ ⇒ 它们**测的是锁**，不是**闸门**（收集到 0 个 / 全部 skip / 部分 skip）。

## 2. 根因：守门测试**走了同一条路**

⇒ 守门测试调的是**真脚本** ⇒ ⇒ 真脚本抢真锁 ⇒ ⇒ 抢不到就退出 ⇒ ⇒
守门测试在一个**被锁挡住**的进程里断言 ⇒ ⇒ 它验证的分支**不是**它声称的分支。

⚠️ 这是**假红**（不是假绿）⇒ ⇒ 但危害一样：**它让人不再相信守门测试**
⇒ ⇒ 守门测试一旦变成噪声，就等于没有。

## 3. 形状（可复用）

> **守门测试必须与被守护的机制隔离** —— 否则它测的是「机制挡住了我」。
> ⇒ 机制要能被**换一份实例**（锁文件、临时目录、假端口、假 DB）。

⇒ 修法：脚本支持**用环境变量覆盖锁文件**
（`PCS_PGTEST_LANE_LOCK`）⇒ ⇒ 守门测试用**自己的**锁文件
（per-PID 临时文件）⇒ ⇒ 与真车道**互不干扰**。

⚠️ **代价要记账**：默认锁路径（`/tmp/pcs-pgtest-lane.lock`）因此**从未被测过**
⇒ ⇒ 「默认锁路径也有效」这件事只能靠**读代码 + 真车道实测**保证
⇒ ⇒ 已登记在评审报告的 residual risk 里。

## 4. 同族的另一条：断**可执行部分**，不是断文本

⇒ 同一个文件里另有一条守卫用 `_body()` **剥掉注释**再匹配 ⇒ 理由是
「注释里提到 `uv run pytest` 是**说明** ⇒ 断『脚本有没有做这件事』必须断
**可执行部分**」⇒ ⇒ 详见
`docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`。

⇒ ⚠️ **同一个文件里两套口径**（一条剥注释、一条不剥）⇒ ⇒ 至少要**一致**。

## 5. 怎么发现这类问题

⇒ 守门测试**并发**跑一次（真车道在跑时）⇒ ⇒ 若它红了且理由是
「机制挡住了我」⇒ ⇒ 它没在测它声称的东西。
⇒ ⇒ 这也说明：**守门测试必须能在真机制缺席时独立地跑**。
