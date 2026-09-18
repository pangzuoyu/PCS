"""cv 子包：调节阀 Cv 计算引擎（P6-1 Task 8）。

子模块：
- cv_engine：IEC 60534-2-1 完整算法实现（液体 + 气体 + 噪音 SIL）
"""
from app.services.cv import cv_engine

__all__ = ["cv_engine"]