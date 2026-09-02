"""ExportService — openpyxl Excel 导出（P2 Sprint 3 Task 5.3）。

职责：将 list[dict] 数据 + headers 导出为 .xlsx 字节流。
- 同步 openpyxl 用 ``async def`` 包装，保留与未来异步 IO 替换的兼容面
  （当前实现内部无 ``await``，但调用方统一用 ``await ExportService.to_excel(...)``）。
- **write_only=True 流式写入**：D28 性能预算 10k×20 ≤ 2s，普通 ``Workbook``
  的 ``ws.append`` 在 10k 行实测 ≈ 6.8s。write_only 模式直接序列化 XML，
  无内存中整表驻留，单测现已通过。
- sheet_name 限 31 字符（Excel 规范；超长截断）。
- 缺失字段输出空 cell（``row.get(h)``）。
"""

from __future__ import annotations

from io import BytesIO

import openpyxl


class ExportService:
    """Excel 导出 service。"""

    @staticmethod
    async def to_excel(
        data: list[dict],
        *,
        headers: list[str],
        sheet_name: str = "Report",
    ) -> BytesIO:
        """生成 ``.xlsx`` 字节流。

        Parameters
        ----------
        data:
            每项为 ``dict``；按 ``headers`` 顺序取值，缺失键输出空 cell。
        headers:
            列名列表；顺序即 Excel 列顺序。
        sheet_name:
            工作表名；超 31 字符截断（Excel 规范）。

        Returns
        -------
        ``BytesIO``，已 ``seek(0)``。
        """
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet(sheet_name[:31])  # Excel 限制 31 字符
        ws.append(headers)
        for row in data:
            ws.append([row.get(h) for h in headers])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf


__all__ = ["ExportService"]
