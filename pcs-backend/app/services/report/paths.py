"""报表文件路径解析 —— **唯一**拼路径的地方。

`ReportFile.file_path` 存的是**相对** `REPORT_STORAGE_DIR` 的相对路径，
绝不存绝对路径：

- 部署目录会变（容器重建、换机器），绝对路径存进去就成了孤儿文件
- 绝对路径是实现细节，进了 DB 就成了没法迁移的历史包袱

⚠️ **ORM 里不碰 settings** —— 与其他 100+ 个模型一致（模型不 import
`get_settings`，这是全仓约定）。所以路径解析只能在 service 层做，就是本模块。

## 路径穿越防护

`resolve_path` 解析出的是磁盘真实路径，必须确认它仍在根目录内 ——
`report_files.file_path` 虽由服务端写入，但一旦有任何一条路径来自用户输入
（未来「按路径下载」接口），`../../etc/passwd` 就能读任意文件。
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.exceptions import PcsError


def storage_root() -> Path:
    return Path(get_settings().report_storage_dir).resolve()


def resolve_path(relpath: str) -> Path:
    """相对路径 → 磁盘绝对路径，并确认仍在存储根内。

    Raises:
        PcsError(REPORT_PATH_ESCAPE): 解析结果跑出了存储根。
    """
    root = storage_root()
    target = (root / relpath).resolve()
    if target != root and root not in target.parents:
        raise PcsError(
            f"报表路径逃逸出存储根：{relpath!r} → {target}（根 {root}）",
            code="REPORT_PATH_ESCAPE", status=400,
        )
    return target


def relative_path(abs_path: Path) -> str:
    """磁盘绝对路径 → 相对存储根的相对路径（入库用）。"""
    root = storage_root()
    return str(Path(abs_path).resolve().relative_to(root))


def new_file_path(content_hash: str, ext: str) -> str:
    """按内容哈希命名：`{hash[:16]}.{ext}`。

    哈希全名会让路径过长且毫无收益（前 16 位对内容寻址足够，
    冲突概率 ~2⁻⁶⁴）。
    """
    return f"{content_hash[:16]}.{ext}"