#!/usr/bin/env python
"""Behr coefficient FORM DECISION + FIT script — Day-0 Gate (T1 Step 0).

v5.1 修订 (B-2 + P-1 落实): v5 plan 阶段给的 4-param log10 二次形式系数
(A0=1.3520/A1=0.00780/A2=0.0000052/A3=-0.9800) 经架构组独立验算在 T=120, P=1000
下预测 W=0.2648 vs spot check 70 (264× 偏差)；v3 形式 A 系数也失败。

本脚本作为形式决策 + 拟合脚本，用于：
  (a) 比较 3 种候选形式的 max_rel_err：4-param log10 二次 / Katz 3-param / Behr 原式非线性
  (b) 选定 max_rel_err < 5% 的形式；用 numpy lstsq / scipy curve_fit 拟合
  (c) 写实际拟合系数入 JSON sidecar + 打印残差表

Usage: cd pcs-backend && uv run python scripts/dev/calibrate_behr_coefficients.py
Output:
  - 形式 A/B/C 的 max_rel_err 对比表
  - 选定形式的实际拟合系数、残差表
  - 若 3 种形式全 > 5% → halt + 报架构组（**不**写 JSON）
"""
import sys

import numpy as np
from scipy.optimize import curve_fit

# 8 GPSA Fig 20-2 spot checks (v5.1: 4T × 2P 矩阵抽样)
SPOTS = [
    (60, 1000, 16), (80, 1000, 31), (100, 1000, 50), (120, 1000, 70),
    (140, 1000, 95), (160, 1000, 130),
    (120, 500, 147), (120, 1500, 47),
]
T_SPOTS = np.array([s[0] for s in SPOTS], dtype=float)
P_SPOTS = np.array([s[1] for s in SPOTS], dtype=float)
W_SPOTS = np.array([s[2] for s in SPOTS], dtype=float)


def fit_form_A_log10_quadratic() -> tuple[dict, float]:
    """形式 A：log10(W) = A0 + A1·T + A2·T² + A3·log10(P)（numpy lstsq）。"""
    X = np.column_stack([
        np.ones_like(T_SPOTS),
        T_SPOTS,
        T_SPOTS ** 2,
        np.log10(P_SPOTS),
    ])
    y = np.log10(W_SPOTS)
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    A0, A1, A2, A3 = coeffs
    w_pred = 10 ** (A0 + A1 * T_SPOTS + A2 * T_SPOTS ** 2 + A3 * np.log10(P_SPOTS))
    max_rel_err = float(np.max(np.abs(w_pred - W_SPOTS) / W_SPOTS))
    return {"A0": float(A0), "A1": float(A1), "A2": float(A2), "A3": float(A3)}, max_rel_err


def fit_form_B_katz() -> tuple[dict, float]:
    """形式 B（Katz 3-param）：log10(W) = a − b/T + c·log10(P)（numpy lstsq）。"""
    X = np.column_stack([
        np.ones_like(T_SPOTS),
        -1.0 / T_SPOTS,
        np.log10(P_SPOTS),
    ])
    y = np.log10(W_SPOTS)
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    a, b, c = coeffs
    w_pred = 10 ** (a - b / T_SPOTS + c * np.log10(P_SPOTS))
    max_rel_err = float(np.max(np.abs(w_pred - W_SPOTS) / W_SPOTS))
    return {"a": float(a), "b": float(b), "c": float(c)}, max_rel_err


def fit_form_C_behr_original() -> tuple[dict, float]:
    """形式 C（Behr 原式非线性）：W = A·P^(-B)·exp(C/T)（scipy curve_fit）。"""
    def model(p_t, A, B, C):
        p, t = p_t
        return A * p ** (-B) * np.exp(C / t)
    popt, _ = curve_fit(model, (P_SPOTS, T_SPOTS), W_SPOTS, p0=[1e6, 1.0, -5000.0])
    A, B, C = popt
    w_pred = model((P_SPOTS, T_SPOTS), *popt)
    max_rel_err = float(np.max(np.abs(w_pred - W_SPOTS) / W_SPOTS))
    return {"A": float(A), "B": float(B), "C": float(C)}, max_rel_err


# 形式决策
print("=" * 60)
print("Behr 系数形式决策 — 比较 3 种候选形式")
print("=" * 60)
candidates = []
for name, fn in [
    ("A_log10_quadratic", fit_form_A_log10_quadratic),
    ("B_katz", fit_form_B_katz),
    ("C_behr_original", fit_form_C_behr_original),
]:
    coeffs, max_rel_err = fn()
    candidates.append((name, coeffs, max_rel_err))
    print(f"\n形式 {name}: max_rel_err = {max_rel_err:.3%}")
    for k, v in coeffs.items():
        print(f"  {k} = {v:.6f}")

# 选 max_rel_err < 5% 的形式
print("\n" + "=" * 60)
valid_candidates = [(n, c, e) for n, c, e in candidates if e < 0.05]
if not valid_candidates:
    print("⚠️ 3 种形式全 > 5% — HALT T1 + 报架构组")
    print("考虑工程化近似（分段线性 / 表格插值）— P6-6B 接管")
    sys.exit(1)

chosen_name, chosen_coeffs, chosen_err = min(valid_candidates, key=lambda x: x[2])
print(f"选定形式：{chosen_name}, max_rel_err={chosen_err:.3%}")
print("实际拟合系数：", chosen_coeffs)
print("\nW_actual vs W_pred 残差表：")
print(f"{'T_F':>5} {'P_psia':>8} {'W_actual':>10} {'W_pred':>10} {'rel_err':>10}")
for t, p, w_actual in SPOTS:
    if chosen_name == "A_log10_quadratic":
        log_w = (
            chosen_coeffs["A0"]
            + chosen_coeffs["A1"] * t
            + chosen_coeffs["A2"] * t ** 2
            + chosen_coeffs["A3"] * np.log10(p)
        )
        w_pred = 10 ** log_w
    elif chosen_name == "B_katz":
        log_w = chosen_coeffs["a"] - chosen_coeffs["b"] / t + chosen_coeffs["c"] * np.log10(p)
        w_pred = 10 ** log_w
    else:
        w_pred = chosen_coeffs["A"] * p ** (-chosen_coeffs["B"]) * np.exp(chosen_coeffs["C"] / t)
    rel_err = abs(w_pred - w_actual) / w_actual
    print(f"{t:>5} {p:>8} {w_actual:>10.2f} {w_pred:>10.2f} {rel_err:>10.3%}")

# TODO: T1 implementer 手动复制 chosen_coeffs 到 data/behr_coefficients.json
# (手动而非自动写文件 — 避免脚本误覆盖 JSON)
msg = (
    "\n⚠️ 请手动复制上面 '实际拟合系数' 到 data/behr_coefficients.json 的 "
    "log10_coefficients（或 coefficients）段"
)
print(msg)
