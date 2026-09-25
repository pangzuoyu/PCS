"""cv 子包：调节阀 Cv 计算引擎 + 落库 service（P6-1 Task 8/9 / P6-4 Task 5）。

子模块：
- cv_engine：IEC 60534-2-1 完整算法实现（液体 + 气体 + 噪音 SIL）
- cv_persist：落库 + outlet stream（ADR-0022）
- flashing_correction：Masonelian fl + 闪蒸蒸汽量 + 阀门厂库（C-24 P6-4 Task 5）
"""
from app.services.cv import cv_engine, cv_persist, flashing_correction

__all__ = ["cv_engine", "cv_persist", "flashing_correction"]