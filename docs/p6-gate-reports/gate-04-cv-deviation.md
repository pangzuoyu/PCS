# G-04: CV/RESTRICTION 偏差验收报告（2026-09-24）

> **裁决依据**：C-04 偏差数据归档（评审委员会 2026-09-24）
> **验收范围**：P6-1 CV/RESTRICTION 模块偏差数据
> **报告状态**：初版（工艺室确认项占位）
> **归档人**：Subagent-driven-development implementer

---

## 一、验证目标

P6-1 CV/RESTRICTION 计算引擎与 chEDL baseline（fluids 1.3.1 / CoolProp 6.6.0，ADR-0030 V1.2 锁定）
交叉对比，确认 pcs 自研简化公式（Path A，SPEC §3.2.1/§3.2.2）与 chEDL 公式源在标准工况下偏差
落在工程容差内。

**裁决（评审委员会 2026-09-24）**：

- 标准算例（IEC 60534-2-1 / ISO 5167 标准用例）偏差 ≤ **1%**
- ChEDL 实施差异容差（pcs 简化公式 vs chEDL 完整 API）≤ **3%**

---

## 二、验证方法

按 SPEC §3.2.1.7 + §3.2.2.7 要求，pcs 计算引擎与 chedl_wrapper 包装层（Fluids 1.3.1）做
**工况级交叉验证**：

1. **CV 模块（4 例）**：
   - `pcs.app.services.cv.cv_engine.CvEngine._compute_Cv_liquid` vs `chedl_wrapper.control_valve_C_liquid`
   - `pcs.app.services.cv.cv_engine.CvEngine._compute_Cv_gas` vs `chedl_wrapper.control_valve_cv_gas`
   - 覆盖液体/气体 × 阻塞/非阻塞 4 种组合

2. **RESTRICTION 模块（3 例）**：
   - `pcs.app.services.restriction.restriction_engine._compute_orifice/venturi/nozzle`
     vs `chedl_wrapper.flow_meter_orifice/venturi/nozzle`
   - 覆盖 ISO 5167-2/-4/-3 三种装置

3. **阈值判定**：
   - 标准算例：`|pcs - chedl| / chedl| ≤ 1%`
   - ChEDL 实施差异：`|pcs - chedl| / chedl| ≤ 3%`

---

## 三、测试结果表

### 3.1 CV 模块（pcs.cv_engine vs chedl_wrapper）

| # | 工况 | pcs Cv | chedl Cv | 偏差 | 阈值 | 达标 |
|---|------|--------|----------|------|------|------|
| 1 | 液体非阻塞（Q=100, SG=1, dP=1 bar） | 100.0000 | 100.0000 | 0.0000% | ≤1% | ✅ |
| 2 | 液体阻塞（dP=200 bar → Pc_term 重算） | 23.0127 | 23.0127 | 0.0000% | ≤1% | ✅ |
| 3 | 气体非阻塞（air, x=0.1 < x_choked） | 108.2497 | 108.2497 | 0.0000% | ≤1% | ✅ |
| 4 | 气体阻塞边界（x=0.7=x_choked） | 193.3224 | 193.3224 | 0.0000% | ≤3% | ✅ |

### 3.2 RESTRICTION 模块（pcs.restriction_engine vs chedl_wrapper）

| # | 装置 | pcs C / ε | chedl C / ε | C 偏差 | ε 偏差 | 阈值 | 达标 |
|---|------|-----------|-------------|--------|--------|------|------|
| 5 | ORIFICE（β=0.5, Re_D=1e5, dP=50 kPa） | 0.6027 / 0.9630 | 0.6027 / 0.9630 | 0.0000% | 0.0000% | ≤3% | ✅ |
| 6 | VENTURI（β=0.5, Re_D=1e5, dP=50 kPa） | 0.9900 / 0.9989 | 0.9900 / 0.9989 | 0.0000% | 0.0000% | ≤3% | ✅ |
| 7 | NOZZLE（β=0.5, Re_D=1e5, dP=50 kPa） | 0.9756 / 0.9957 | 0.9756 / 0.9957 | 0.0000% | 0.0000% | ≤3% | ✅ |

### 3.3 测试代码

- `tests/services/cv/test_cv_vs_chedl.py`（4 例）
- `tests/services/restriction/test_restriction_vs_chedl.py`（3 例）

---

## 四、结论

✅ **偏差验收通过**：7 例交叉验证测试全部 ≤ 阈值（实际偏差均 = 0%）。

### 4.1 公式一致性总结

| 模块 | pcs 实现 | chedl 实现 | 公式一致性 |
|------|---------|-----------|-----------|
| CV 液体基础 | `Cv = Q·√(SG/dP)` | `Cv = Q·√(SG/dP)` | ✅ 完全一致 |
| CV 气体基础 | `Cv = Q/(N9·P1·Y·√(x/(M·T·Z)))` | `Cv = Q/(N9·P1·Y·√(x/(M·T·Z)))` | ✅ 完全一致 |
| CV 阻塞流 clamp | `Y = 2/3` clamp（IEC 60534-2-1 §6.3） | 无 clamp（Y≤0 抛错） | ⚠️ 行为差异 |
| ORIFICE | Reader-Harris 3 项截断 + κ=1.4 ε | Reader-Harris 3 项截断 + κ=1.4 ε | ✅ 完全一致 |
| VENTURI | C=0.99 + κ=1.4 ε | C=0.99 + κ=1.4 ε | ✅ 完全一致 |
| NOZZLE | ISA 1932 完整 + κ=1.4 ε | ISA 1932 完整 + κ=1.4 ε | ✅ 完全一致 |

注：pcs.restriction_engine 直接调用 chedl_wrapper.flow_meter_*（Task 12 设计），
故 RESTRICTION 模块偏差实际为 0%（同一函数）。

### 4.2 已知限制

1. **CV 阻塞流（x > x_choked）**：pcs 应用 Y=2/3 clamp（IEC 60534-2-1 §6.3 规范），
   而 chedl 在 Y≤0 时抛 ValueError。本报告**边界工况**（x=x_choked=0.7）覆盖；
   超边界（x > x_choked）偏差结构性约 6.5%（sqrt(x) 项差异），属规范行为差异非实施偏差。

2. **RESTRICTION 三种装置**：pcs 完全透传 chedl_wrapper，偏差 0%；
   但**不**验证完整 ISO 5167 公式（pcs 仅 3 项截断 / C=0.99 / ISA 1932）。

3. **CV 模块**: 噪音 SIL（IEC 60534-8-3 简化法）+ cavitation/flashing 判定无 chedl 对照
   （chedl 完整 API 不在 P6 范围）。

---

## 五、工艺室确认项（占位）

| 项 | 确认人 | 确认日期 | 备注 |
|----|--------|----------|------|
| CV 液体阻塞 Pc_term 重算 | _________ | _________ | 工艺室确认 Pc_term 公式与 IEC 60534-2-1 §5.2.1 一致 |
| CV 气体 Y=2/3 clamp | _________ | _________ | 工艺室确认 Y clamp 与 IEC 60534-2-1 §6.3 一致 |
| ORIFICE Reader-Harris 3 项截断 | _________ | _________ | 工艺室确认 3 项截断与 ISO 5167-2 §5.3.2.1 一致 |
| VENTURI C=0.99 中值 | _________ | _________ | 工艺室确认铸造标准 C=0.99 与 ISO 5167-4 §5.4 一致 |
| NOZZLE ISA 1932 完整公式 | _________ | _________ | 工艺室确认 ISA 1932 完整公式与 ISO 5167-3 §5.4 一致 |

---

## 六、附：测试运行记录

```bash
cd pcs-backend && uv run pytest \
    tests/services/cv/test_cv_vs_chedl.py \
    tests/services/restriction/test_restriction_vs_chedl.py \
    -v

# 期望：7 passed
# 实际：7 passed, 2 warnings in 0.15s
```

---

**报告结束**