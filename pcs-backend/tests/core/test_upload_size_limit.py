"""P3.2 SIM-13：上传文件大小限制测试（闭环审计 D-2）。

覆盖：
1. 恰好 10MB 通过
2. 10MB+1 字节超限 → 413 STREAM_IMPORT_FILE_TOO_LARGE
3. 1KB 通过
4. 错误消息含文件名标签 + 实际大小
"""
from __future__ import annotations

import pytest

from app.core.errors import PcsError
from app.core.upload_size_limit import MAX_UPLOAD_BYTES, enforce_upload_size


def test_exactly_max_size_passes():
    """恰好 10MB 通过（边界值包含）。"""
    enforce_upload_size(MAX_UPLOAD_BYTES, label=".inp")  # 不抛


def test_one_byte_over_max_raises():
    """10MB+1 字节 → 413。"""
    with pytest.raises(PcsError) as exc_info:
        enforce_upload_size(MAX_UPLOAD_BYTES + 1, label=".inp")
    assert exc_info.value.code == "STREAM_IMPORT_FILE_TOO_LARGE"
    assert exc_info.value.status == 413
    msg = str(exc_info.value.message)
    assert ".inp" in msg
    assert str(MAX_UPLOAD_BYTES + 1) in msg


def test_small_size_passes():
    """1KB 通过。"""
    enforce_upload_size(1024, label=".xlsx")  # 不抛


def test_error_message_mentions_mb_limit():
    """错误消息含 10 MB 提示。"""
    with pytest.raises(PcsError) as exc_info:
        enforce_upload_size(20 * 1024 * 1024, label=".out")
    assert "10" in str(exc_info.value.message)
    assert "MB" in str(exc_info.value.message)


def test_zero_size_passes():
    """空文件（0 bytes）通过（enforce_upload_size 不挡空文件，端点单独 check）。"""
    enforce_upload_size(0, label=".xlsx")  # 不抛


def test_max_bytes_constant_is_10mb():
    """MAX_UPLOAD_BYTES = 10 * 1024 * 1024。"""
    assert MAX_UPLOAD_BYTES == 10 * 1024 * 1024
