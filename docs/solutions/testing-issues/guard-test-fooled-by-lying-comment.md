---
module: pcs-backend + pcs-frontend 测试有效性
date: 2026-10-19
problem_type: testing_issue
component: testing_framework
severity: high
symptoms:
  - "A guard test asserting 'module X derives its constant from the single source' stays GREEN on a module that hardcodes a literal — the literal and the comment above it contain the same words"
  - "A structural test keyed on `str(stmt.whereclause)` never fires, because SQLAlchemy renders that attribute as an empty string"
  - "A mock that is stale relative to the contract is treated as a dev-only nuisance; it is in fact the only reason a production page still looks right"
  - "Two API endpoints that mean the same thing ship different output-format whitelists, and a third file's docstring claims it derives from the canonical list while hardcoding the same values"
root_cause: observation_method_defeated_by_the_thing_under_test
resolution_type: test_and_source_fix
framework_version: pytest / SQLAlchemy 2.0.52 / vitest 2.1.9 / React 18
related_components:
  - testing_framework
  - contract
  - frontend
tags:
  - false-green
  - observation-point
  - guard-test
  - comment-beats-guard
  - msw
  - contract-drift
  - single-source-of-truth
---

# 守门测试会被它所守护的那行注释骗过

`docs/solutions/testing-issues/sqlite-staticpool-hides-uncommitted.md`
列了三级假绿。第三级的变体在这里：**功能从未执行**，而击穿观测方法的
不是 fixture，是**源码里的注释文本**。

## 1. 内容相等 ≠ 派生

四份输出格式白名单（评审 #19）里，有一份写的是：

```python
#: 支持的输出格式。**取自 `watermark.EXPORT_FORMATS`** —— b8 落地 CSV 后
#: 曾经有三份清单，改漏一处就是「某个格式选得到但跑不了」。
SUPPORTED_FORMATS = frozenset({"pdf", "xlsx", "docx", "csv"})
```

注释是**愿望**，代码是字面量。第一版守门测试断言
`SUPPORTED_FORMATS == frozenset(EXPORT_FORMATS)` —— **绿的**。
内容今天相等，加第 5 种格式时字面量不会动，而那正是 #19 的缺陷形状。

⇒ 断言必须是**结构**的。

## 2. 字符串匹配 ≠ 派生 —— 它被注释本身骗过

第二版改用 `inspect.getsource(module)` 找 `'EXPORT_FORMATS'` 子串。
**还是绿的**，而代码依然是硬编码字面量 —— 因为那句**说谎的注释**
正好写着「取自 `watermark.EXPORT_FORMATS`」，子串命中了。

守门测试被它所守护的那行注释击败。

⇒ 别扫文本，走 AST：

```python
def _references_export_formats(module) -> bool:
    tree = ast.parse(inspect.getsource(module))
    return any(
        (isinstance(n, ast.Attribute) and n.attr == "EXPORT_FORMATS")
        or (isinstance(n, ast.Name) and n.id == "EXPORT_FORMATS")
        for n in ast.walk(tree)
    )
```

注释进不了 AST。**凡是「证明 A 引用了 B」的断言，都不该用文本匹配。**

## 3. 同一形状的第二例：`str(stmt.whereclause)`

测试并发 upsert 的事务边界时，用
`"content_hash" in str(stmt.whereclause)` 判断「这是不是那次
content_hash 查询」。SQLAlchemy 2.0 上该属性是**空串**，条件恒不命中：

短路从未发生 → `existing` 被查到 → 走**早返回分支** →
`except IntegrityError` 根本没执行 → 自然没有 `rollback()` →
自然没有数据丢失 → **测试绿**。

把「测试通过」读成「事务没被回滚」，实际是「**回滚从未被触发**」。
两个都叫绿，含义相反。

⇒ 判据要打在**引擎保证**上（调用序数、对象身份、AST 节点），
不要打在**渲染产物**上。

## 4. mock 漂移会**遮住**生产缺陷，不只是自身变脏

评审 #24 说「mock 落后于契约」。做标注时发现落后的是 mock，
但漂移的后果不止于 mock：

```
mocks/seed/pipe-classes.ts   返 {pipe_class_id, code, ...}
契约 PipeClassResponse       返 {class_id, class_name, material_standard, ...}
```

页面读 `record.pipe_class_id`（`rowKey` 也用它）。真后端下是 `undefined` ——
**管道等级页在生产上就是坏的，是这份 mock 一直在替它遮着。**

推论：**mock 与契约一致是正确性的一部分**，不是开发体验问题。
mock 越宽松，它替页面/后端扛的越多，而那些差异平时不可见。

### 找出这类的低成本手法

给 seed 加一条编译期断言，让 `tsc` 去比：

```ts
const _conforms: PipeClassResponse[] = seedPipeClasses;
void _conforms;
```

一次跑出 5 处真漂移。方向只能是 **seed → 契约**；
反向不成立（手写类型可多带页面私有字段）。

### 断言在修完之前是**探针**

不是每条不一致都能当场修（pipe-classes 那条要动页面 = TODO-039）。
那就只保留它在成立的那处，把不成立的换成**文档注释**指向发现 ——
留一个红的 `tsc` 等于把构建变红，留一句注释等于把原因留下。

## 5. 同款：注释比代码乐观（本会话第三次出现）

| 文件 | 注释说 | 代码是 |
|---|---|---|
| `report_service.py` | 「取自 `watermark.EXPORT_FORMATS`」 | 硬编码字面量 |
| `report_builder.py` | 「两边不再各持一份」 | 只并了两份中的两份 |
| `handlers.ts` | 「OpenAPI drift 校验覆盖」 | 该校验只比 `required` 数组 |

三条注释各自都在描述一个**意图**，且都在**方向上误导**下一个人。
⇒ 注释里出现「已消除」「唯一来源」「覆盖」这类断言时，
把它当成一条待验证的代码事实，而不是既成结论。
MDEOF