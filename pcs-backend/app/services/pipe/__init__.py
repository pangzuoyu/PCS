"""Pipe 计算服务包（P4-2+）。

子模块：
- sizing_service：P4-2-1 管道选型（预定流速法 + 设定压力降法）
- wall_thickness_service：P4-2-2 壁厚计算（ASME B31.3 §304.1.2 直管壁厚 +
  Sch 系列圆整 + 许用应力温度插值）
- 后续 P4-2-3+ 实现单相压降等
"""