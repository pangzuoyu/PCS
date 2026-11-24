# DMC 装置 10 条组分 CAS 号 —— 工艺签字确认表

**关联条目**：`TODOS.md` · `TODO-196`（DMC 专用组分的 CAS 号待工艺室签字）
**代码位置**：`pcs-backend/app/services/component_cas.py::CAS_BY_COMPONENT`（第 100~110 行）
**别名来源**：`pcs-backend/app/services/alias_registry.py`（第 93~105 行）
**归档类型**：**人工确认完毕**版（2026-11-24）

---

## 一、为什么需要这张表

PRO/II 的 DMC `.inp`（`sample/dmc.inp`）的 `COMPONENT DATA` 段用的是**装置缩写**
（`PO` / `PROPCARB` / `DMCARB` / `12PG` / `DIPRPGLY` / `TPG` / `AA` / `OXYLENE` /
`MOXYPROH` / `PROPALD`）⇒ ⇒ ⇒ 别名表里没有 ⇒ ⇒ ⇒ 组成落不到 CAS
⇒ ⇒ ⇒ 「**导入 ⇒ 物性补全**」那条链断在这里。

⇒ ⇒ 本表把这 10 条的 **CAS 号**逐条定案 ⇒ ⇒ ⇒ 落进
`component_cas.py` + `alias_registry.py`（两条一起 ⇒ ⇒ 缩写能落到规范名 ⇒ ⇒ 再落到 CAS）。

⚠️ **为什么要人工确认**：**CAS 错 ⇒ ⇒ 组成错 ⇒ ⇒ 闪蒸算出错的结果**
⇒ ⇒ ⇒ 错组成比没组成**危险得多**。

---

## 二、逐条确认表

| # | PRO/II 缩写 | 规范名 | 中文名 | CAS 号 | 分子量 | 核对来源 |
|---|---|---|---|---|---|---|
| 1 | `PO` | `PROPYLENE_OXIDE` | 环氧丙烷 | **75-56-9** | 58.079 | PubChem |
| 2 | `PROPCARB` | `PROPYLENE_CARBONATE` | 碳酸丙烯酯 | **108-32-7** | 102.089 | PubChem |
| 3 | `DMCARB` | `DIMETHYL_CARBONATE` | 碳酸二甲酯 | **616-38-6** | 90.078 | PubChem |
| 4 | `12PG` | `PROPYLENE_GLYCOL` | 丙二醇 | **57-55-6** | 76.094 | PubChem |
| 5 | `DIPRPGLY` | `DIPROPYLENE_GLYCOL` | 二丙二醇 | **25265-71-8** | 134.174 | **CAS Common Chemistry 官方 + OECD SIDS + NOAA CAMEO**（曾有错号 ⇒ 见 §三）|
| 6 | `TPG` | `TRIPROPYLENE_GLYCOL` | 三丙二醇 | **24800-44-0** | 192.253 | **OECD SIDS + CAMEO + Sigma-Aldrich**（曾有错号 ⇒ 见 §三）|
| 7 | `AA` | `ACRYLIC_ACID` | 丙烯酸 | **79-10-7** | 72.063 | PubChem |
| 8 | `OXYLENE` | `O_XYLENE` | 邻二甲苯 | **95-47-6** | 106.165 | PubChem |
| 9 | `MOXYPROH` | `METHOXYPROPANOL` | 甲氧基丙醇 | **107-98-2** | 90.121 | PubChem |
| 10 | `PROPALD` | `PROPIONALDEHYDE` | 丙醛 | **123-38-6** | 58.079 | PubChem |

⇒ ⇒ 「PubChem」= `scripts/verify_component_cas.py` 的**双向查**
（CAS → PubChem 反查名称 + 名称 → CAS 正查 ⇒ ⇒ 双向对上才算过）
⚠️ ⚠️ **CAS Common Chemistry 自 2025 起要 API key（401）** ⇒ ⇒ ⇒
**别把 401 当「查不到」** ⇒ ⇒ ⇒ 那 3 条因此改用 OECD SIDS / CAMEO / Sigma-Aldrich 交叉确认。
⚠️ **三丙二醇 PubChem 无独立记录** ⇒ ⇒ ⇒ 只能用 SIDS / CAMEO ⇒ ⇒ ⇒ 这就是第 6 行要三源交叉的原因。

⚠️ **分子量是「核对用的旁证」**：每个 CAS 经 `chemicals` 取回的 MW
⇒ ⇒ ⇒ 与该物质的化学式**逐条相符**
（环氧丙烷 C3H6O=58.08 · 碳酸丙烯酯 C4H6O3=102.09 · 碳酸二甲酯 C3H6O3=90.08 ·
丙二醇 C3H8O2=76.09 · 二丙二醇 C6H14O3=134.17 · 三丙二醇 C9H20O4=192.25 ·
丙烯酸 C3H4O2=72.06 · 邻二甲苯 C8H10=106.17 · 甲氧基丙醇 C4H10O2=90.12 ·
丙醛 C3H6O=58.08）⇒ ⇒ ⇒ **编号没串行**。

⚠️ 环氧丙烷与丙醛**分子式相同**（都是 C3H6O）⇒ ⇒ ⇒ MW 也相同（58.079）
⇒ ⇒ ⇒ ⇒ 这两条**光看 MW 分不开** ⇒ ⇒ ⇒ 靠的是**编号本身**（75-56-9 vs 123-38-6）。

---

## 三、⚠️ 上一轮**查出并修掉**的 3 条错号（bug-2197）

| 组分 | 原写（错） | 错在哪 | 正号 |
|---|---|---|---|
| `ISO_BUTANE` | `106-98-3` | **CAS 校验位就不对** | `75-28-5` |
| `DIPROPYLENE_GLYCOL` | `25265-29-4` | 校验位**过**，但**无源指向**该物质 | `25265-71-8` |
| `TRIPROPYLENE_GLYCOL` | `2463-75-4` | 校验位**过**，但无源指向该物质 | `24800-44-0` |

⇒ ⇒ ⇒ **后两条正落在本表第 5 / 6 行** ⇒ ⇒ ⇒ ⇒ 本表里的号 = 修正后的号。

**影响分级**（比原 TODO 说得准）：
- 错号**取不到 MW** ⇒ ⇒ ⇒ 组成**静默作废** ⇒ ⇒ ⇒ 那些流**闪蒸算不了**
  （**安全的失败**）⇒ ⇒ ⇒ 只有「真号指向别的物质」才算出**错**结果
  ⇒ ⇒ ⇒ ⇒ 本表第 5 / 6 行曾属后者 ⇒ ⇒ ⇒ ⇒ 已修。

---

## 四、兜底机制（**不依赖本表**）

任何一条 CAS 认不出来 ⇒ ⇒ ⇒ 该流的组成**整个作废**
（`composition_json = None`）+ 告警 ⇒ ⇒ ⇒ **不会**带着错 CAS 落库。

⇒ ⇒ ⇒ 即使将来又发现某条号错了 ⇒ ⇒ ⇒ 最坏结果是「**算不出来**」
⇒ ⇒ ⇒ 而不是「**算错**」。

---

## 五、确认

| 项 | 内容 |
|---|---|
| **确认范围** | 上表 §二 的 **10 条** CAS 号（含 §三 修正后的第 5 / 6 行） |
| **确认日期** | **2026-11-24** |
| **确认人** | **pangzy**（本项目负责人 · 仓库 `git user`） |
| **确认方式** | 本会话内**逐条人工核对**上表（CAS 号 + 分子量旁证 + 公开源） |
| **状态** | ✅ **已确认** ⇒ ⇒ ⇒ `TODO-196` **关闭** |

⚠️ **签署性质（别误读）**：本次确认由**项目负责人代签**
⇒ ⇒ ⇒ **不是**工艺室出具的独立签字文件
⇒ ⇒ ⇒ 若工艺室要求**独立签署** ⇒ ⇒ ⇒ 请在本表下方**追加签署栏**：

```
工艺室签署：____________________   日期：____________
```

⚠️ **本表的效力边界**：
① 确认的是**编号本身**（这一条登记号指向这个物质）⇒ ⇒ ⇒ **不是**对
   「这套 DMC 组成的配方与工况正确」的确认；
② 确认**不解除**「未确认 CAS 照常落库、照常过送审门禁」那个人裁
   （2026-11-19 人裁 · 维持现状）⇒ ⇒ ⇒ 兜底仍只有 §四 那一条。

---

## 六、关联

- `TODOS.md` · `TODO-196`
- `docs/solutions/domain-data/cas-numbers-must-be-verified-not-recalled.md`
  （**核过的**号怎么核 · 为什么不能靠记忆）
- `pcs-backend/app/services/component_cas.py`（CAS → MW 的查表处）
- `pcs-backend/tests/services/test_component_cas.py`（**离线棘轮** 95 条断言
  —— 校验位关 + `chemicals` 存在关 + 11 条分子量钉死 ⇒ ⇒ ⇒ 号码被改会红）
