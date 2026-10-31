---
module: pcs-backend signature_matrix_service
date: 2026-10-31
problem_type: database_issue
component: database / concurrency
severity: medium
tags: [get-or-create, unique-constraint, savepoint, IntegrityError, race, P9B-2]
symptoms: 并发首建时 POST /projects 随机 500（UNIQUE constraint failed …），整个项目创建回滚；同文件兄弟方法同场景却正常
root_cause: lock-free「SELECT 见空 ⇒ INSERT」的 get-or-create：READ COMMITTED 下两个并发事务都见空、都插入，输家撞 `(matrix_name, status)` 唯一约束且无人捕获；且调用方的业务 INSERT 与它同事务 ⇒ 整体回滚
---

# get-or-create 默认行的并发兜底：savepoint 内插 + 撞约束重读赢家

## 形状

「首次触发才建全局默认行」（默认矩阵 / 默认模板 / 默认配置）的 get-or-create，
在**库为空 + 并发首建**时必然出现窗口。症状是偶发 500（难复现），而单测
（SQLite StaticPool 单连接）永远串行 ⇒ 测不出。

## 解法（`_get_or_create_default_record_matrix`，bug-2062 修正版模式）

```python
try:
    async with db.begin_nested():      # ⚠️ savepoint：输家只回滚这一段
        db.add(row)                    # ⚠️ add 必须在 savepoint **之内**
        await db.flush()
except IntegrityError:
    winner = (await db.execute(select(Model).where(<唯一键>))).scalars().first()
    if winner is None:
        raise                          # 撞的不是预期的唯一约束 ⇒ 别吞
    return winner                      # 只读不写：不覆盖赢家的任何列
```

三个缺一不可的细节：

1. **`db.add` 在 `begin_nested()` 之内** —— savepoint 建立时会先 flush 一次
   pending，外面的 INSERT 不受保护（bug-2062 的原坑：写了 savepoint 但 add
   在外面 ⇒ 整个事务照旧中止）；
2. **恢复分支只读不写** —— 撞约束后重读赢家返回，绝不 update（否则把赢家
   的列改回自己的版本 = 第二种数据损坏）；
3. **别用裸 `db.rollback()`** —— 调用方（如 POST /projects 的项目 INSERT）
   与本插入同事务，裸 rollback 会把人家的行一起回滚掉。

## 检测

真并发在 SQLite 上不可表达（见 [[midflight-config-rebind-defeeds-one-shot-guards]]）
⇒ 用 execute 拦截注入竞态：patch `db.execute`，让方法自己的 SELECT 返回空、
同时插进「对手行」⇒ 方法的 INSERT 撞约束 ⇒ 断言返回赢家的行且全表仍只有
一行（`test_get_or_create_default_matrix_recovers_from_concurrent_insert`）。

## 教训

- 同文件已有修好的同族方法（`_ensure_binding`）而新方法没抄 —— **评审时按
  「模式 grep」查同文件的同形方法**，别只看单方法；
- 这是本仓 solutions 语料第二次记同族（前次：`dialect-options-invisible-on-sqlite`
  symptom 2）⇒ 新写 get-or-create 时直接来查这条。
