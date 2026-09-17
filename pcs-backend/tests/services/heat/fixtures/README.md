# HEAT 重量估算 golden 基准数据（P5-4-4 / Task 22）

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md V1.8 决策：

## 数据来源

- **BEM 算例**（固定管板 / Floating Head 简化版）：plan V1.0 §Task 22 Step 1
  给定 D_shell=1m, L=5m, t_shell=0.012m 算例手算 + 简化工程经验系数。
  - shell_cylinder_weight_kg = **1,480**（薄壁圆筒展开面积 × 壁厚 × 密度，ρ=7850）
  - shell_heads = 300（2× 椭圆封头 2:1 + h_straight=25mm 简化）
  - shell_flanges = 300（2× ASME B16.5 DN600 300# 估算）
  - shell_nozzles = 75（4× DN100 接管 + 补强）
  - shell_saddles = 225（2× NB/T 47065 DN600 鞍座）
  - **shell_total = 2,380** kg
- **AEM 算例**（U 型管）：同上量级，tube 部分独立计算（无 baffle 壳程）。
  简化量级：shell_total ≈ 2,200，tube ≈ 950（300 根 × 6m × OD19.05 × 1.65mm）。

## 偏差阈值

按 plan V1.0：
- **shell_cylinder**：±1%（直接几何计算，不应有大偏差）
- **total_weight**：±10%（vs 商业软件 HTRI / Aspen EDR 报告）

## ChEDL 限制（V1.8 决策）

`fluids.chemicals` **无换热器重量计算函数**，本 task 全部自研。
不引入 ChEDL 包装层（V1.8 F-13-2 决策）。

## 公式参考

- **cylinder**：薄壁圆筒展开面积 × 壁厚 × 密度（直接几何计算）
- **heads**：GB/T 25198-2010 / ASME VIII-1 UG-32 椭圆封头 2:1
  `W = π × ρ × t × [(D + t)²/4 × (2/3 + h_straight/D)]`
- **flanges**：ASME B16.5 / HG/T 20592 法兰重量表（Type + Class + Size）
- **nozzles**：ASME B16.9 接管尺寸 + 工程经验补强系数（×1.4）
- **saddles**：NB/T 47065-2018 / HG/T 21574 鞍座标准（D_shell 查表）
- **tube / baffle / channels**：直接几何 × 密度 × 件数
