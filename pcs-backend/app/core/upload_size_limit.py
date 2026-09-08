"""P3.2 SIM-13：上传文件大小限制（闭环审计 D-2，Plan §D9 critical gap）。

设计要点：
- 在路由层 file.read() 拿到 bytes 后立即校验（精确字节数，避免依赖
  Content-Length 头对 multipart 多 parts 的歧义）
- 阈值：10 MB（与 Plan §D9 锁定值一致；spec §性能 ≤ 30s/1000 条
  推算 50 流约 500KB，10MB 是 20x 安全余量）
- 超限：抛 STREAM_IMPORT_FILE_TOO_LARGE 业务错（走 core.errors.PcsError
  envelope，HTTP 413）
- 应用：app/api/v1/imports.py 的 preview 端点（PRO/II × 2 文件 / Excel × 1 文件）
"""
from __future__ import annotations

from app.core.errors import PcsError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def enforce_upload_size(size: int, *, label: str) -> None:
    """上传字节数超 10MB → 413 STREAM_IMPORT_FILE_TOO_LARGE。

    在路由 file.read() 后调用，bytes 数 = 磁盘写入字节 = parser 实际消耗。

    Args:
        size: 上传字节数（file.read() 返回值）
        label: 文件标识（.inp/.out/.xlsx），错误消息用

    Raises:
        PcsError(413, STREAM_IMPORT_FILE_TOO_LARGE)
    """
    if size > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise PcsError(
            code="STREAM_IMPORT_FILE_TOO_LARGE",
            message=(
                f"{label} 文件大小 {size} bytes 超过 {mb} MB 限制"
            ),
            status=413,
        )


__all__ = ["MAX_UPLOAD_BYTES", "enforce_upload_size"]
