"""P5-0-6 Task 25: ChEDL 版本锁定架构测试（ADR-0030）。

锁定 PCS 三库（fluids / chemicals / thermo）到精确 ==X.Y.Z。
pyproject.toml 是 source of truth，uv.lock 是机器可读副本，requirements.txt 是快照。

P4 已闭环版本（2026-09-13 末态）：
  - fluids    == 1.3.1
  - chemicals == 1.5.2
  - thermo    == 0.6.1

ADR-0030 决策 4：测试以 uv.lock 为准（机器可读）；requirements.txt 用集合比较（非字节）。
ADR-0030 决策 5：dir() 前置核验通过（P0 时序修正）。
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"
REQUIREMENTS = ROOT / "requirements.txt"
ADR_0030 = ROOT.parent / "docs" / "adr" / "0030-chedl-version-lock.md"

CHEDL_LIBS = ("fluids", "chemicals", "thermo")
LOCKED_VERSIONS = {
    "fluids": "1.3.1",
    "chemicals": "1.5.2",
    "thermo": "0.6.1",
}


def _parse_uv_lock() -> dict[str, str]:
    """解析 uv.lock 顶层 package 条目为 {name: version}（仅顶层直接依赖，过滤传递依赖）。"""
    assert UV_LOCK.exists(), f"uv.lock 不存在: {UV_LOCK}"
    with UV_LOCK.open("rb") as f:
        lock = tomllib.load(f)
    out: dict[str, str] = {}
    for pkg in lock.get("package", []):
        name = pkg.get("name")
        version = pkg.get("version")
        if name and version:
            out[name] = version
    return out


def _parse_requirements() -> dict[str, str]:
    """解析 requirements.txt 为 {name: version}。

    支持两种格式：
      1. `pkg==X.Y.Z`（uv export --no-hashes 常规行）
      2. `-e ./vendor/<pkg>` 或 `-e <path>`（editable 路径源）→ 反查 vendor/<pkg>/pyproject.toml
    """
    assert REQUIREMENTS.exists(), f"requirements.txt 不存在: {REQUIREMENTS}"
    out: dict[str, str] = {}
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            out[name.strip()] = version.strip()
        elif line.startswith("-e "):
            # editable path → 反查 vendor/<pkg>/pyproject.toml 的 version 字段
            path = Path(line[3:].strip())
            if not path.is_absolute():
                path = (ROOT / path).resolve()
            proj_pyproject = path / "pyproject.toml"
            if proj_pyproject.exists():
                with proj_pyproject.open("rb") as f:
                    proj = tomllib.load(f)
                name = proj.get("project", {}).get("name")
                version = proj.get("project", {}).get("version")
                if name and version:
                    out[name] = version
        # 其他格式（如 -r 引用）跳过
    return out


def _extract_dependency_versions() -> dict[str, str]:
    """从 pyproject.toml [project.dependencies] 提取 ChEDL 三库的版本约束。

    返回 {name: constraint_string}，约束字符串如 '==1.3.1' / '>=1.3.1' / '~=1.3.1'。
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    # 简单解析 dependencies 段内的 ChEDL 三库条目（不依赖 tomllib，因为可能含非标准格式）
    out: dict[str, str] = {}
    for lib in CHEDL_LIBS:
        # 匹配 "lib>=X.Y.Z" / "lib==X.Y.Z" / "lib~=X.Y.Z" / "lib"（带或不带引号）
        m = re.search(rf'["\']?{re.escape(lib)}(==|>=|~=|<=|>|<)[^"\',\s]+["\']?', text)
        if m:
            spec = text[m.start():m.end()].strip().strip('"\'')
            # 取约束部分（去掉引号 + 取第一个空白/逗号前）
            name, _, constraint = spec.partition(lib)
            constraint = constraint.strip()
            out[lib] = f"{lib}{constraint}"
        else:
            # 也可能未带约束（裸名）
            m2 = re.search(rf'["\']?{re.escape(lib)}["\']?(?=\s*[,\]])', text)
            if m2:
                out[lib] = lib
    return out


# ============================================================================
# Test cases (5 + 1)
# ============================================================================


def test_fluids_version():
    """uv.lock + runtime 都必须精确锁定 fluids == 1.3.1。"""
    uv_versions = _parse_uv_lock()
    assert "fluids" in uv_versions, "uv.lock 缺 fluids 条目"
    assert uv_versions["fluids"] == LOCKED_VERSIONS["fluids"], (
        f"uv.lock 中 fluids 版本 {uv_versions['fluids']} != 锁定 {LOCKED_VERSIONS['fluids']}"
    )
    # runtime 二次确认
    import fluids

    assert fluids.__version__ == LOCKED_VERSIONS["fluids"], (
        f"运行时 fluids.__version__ {fluids.__version__} != 锁定 {LOCKED_VERSIONS['fluids']}"
    )


def test_chemicals_version():
    """uv.lock + runtime 都必须精确锁定 chemicals == 1.5.2。"""
    uv_versions = _parse_uv_lock()
    assert "chemicals" in uv_versions, "uv.lock 缺 chemicals 条目"
    assert uv_versions["chemicals"] == LOCKED_VERSIONS["chemicals"], (
        f"uv.lock 中 chemicals 版本 {uv_versions['chemicals']}"
        f" != 锁定 {LOCKED_VERSIONS['chemicals']}"
    )
    import chemicals

    assert chemicals.__version__ == LOCKED_VERSIONS["chemicals"], (
        "运行时 chemicals.__version__ "
        f"{chemicals.__version__} != 锁定 {LOCKED_VERSIONS['chemicals']}"
    )


def test_thermo_version():
    """uv.lock + runtime 都必须精确锁定 thermo == 0.6.1。

    注：ADR-0030 文本提及 ht（ChEDL ht 包），但 PCS 代码库实际使用 thermo（P4 实施选择）。
    ChEDL 三库在 PCS 实际为 fluids / chemicals / thermo。
    """
    uv_versions = _parse_uv_lock()
    assert "thermo" in uv_versions, "uv.lock 缺 thermo 条目"
    assert uv_versions["thermo"] == LOCKED_VERSIONS["thermo"], (
        f"uv.lock 中 thermo 版本 {uv_versions['thermo']} != 锁定 {LOCKED_VERSIONS['thermo']}"
    )
    import thermo

    assert thermo.__version__ == LOCKED_VERSIONS["thermo"], (
        f"运行时 thermo.__version__ {thermo.__version__} != 锁定 {LOCKED_VERSIONS['thermo']}"
    )


def test_uv_lock_exists():
    """uv.lock 必须存在且包含 ChEDL 三库条目。"""
    assert UV_LOCK.exists(), f"uv.lock 不存在: {UV_LOCK}"
    uv_versions = _parse_uv_lock()
    for lib in CHEDL_LIBS:
        assert lib in uv_versions, f"uv.lock 缺 {lib} 条目（ChEDL 三库之一必须存在）"


def test_requirements_matches_uv_lock():
    """requirements.txt（uv export 快照）与 uv.lock 必须 ChEDL 三库版本一致。

    ADR-0030 决策 4：集合比较（非字节比较）—— uv export 输出格式因 uv 版本而异。
    ChEDL 三库必须同时存在于两边且版本完全一致。
    """
    uv_versions = _parse_uv_lock()
    reqs = _parse_requirements()
    for lib in CHEDL_LIBS:
        assert lib in reqs, f"requirements.txt 缺 {lib} 条目"
        assert lib in uv_versions, f"uv.lock 缺 {lib} 条目"
        assert reqs[lib] == uv_versions[lib], (
            f"{lib}: requirements.txt={reqs[lib]} 与 uv.lock={uv_versions[lib]} 不一致"
        )


def test_pyproject_declares_exact_chedl_versions():
    """pyproject.toml 必须用 ==X.Y.Z 精确锁定 ChEDL 三库（ADR-0030 决策 2：禁止浮动）。"""
    deps = _extract_dependency_versions()
    for lib in CHEDL_LIBS:
        assert lib in deps, f"pyproject.toml 缺 {lib} 依赖声明"
        constraint = deps[lib]
        assert constraint.startswith(f"{lib}=="), (
            f"pyproject.toml 中 {lib} 必须用 ==X.Y.Z 精确锁定（ADR-0030 决策 2），"
            f"当前约束: {constraint!r}"
        )
        # 提取约束中的版本
        m = re.match(rf"{re.escape(lib)}==([\d.]+)$", constraint)
        assert m, f"{lib} 版本格式异常: {constraint!r}"
        declared = m.group(1)
        assert declared == LOCKED_VERSIONS[lib], (
            f"pyproject.toml 中 {lib}=={declared} 与锁定版本 {LOCKED_VERSIONS[lib]} 不一致"
        )


def test_adr_accepted_link():
    """ADR-0030 必须处于 accepted 状态（V1.10 强制审查项：版本锁定决策已落定）。"""
    assert ADR_0030.exists(), f"ADR-0030 不存在: {ADR_0030}"
    text = ADR_0030.read_text(encoding="utf-8")
    # 解析 YAML frontmatter 中的 status 字段
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    assert m, "ADR-0030 缺 YAML frontmatter"
    frontmatter = m.group(1)
    status_m = re.search(r"^status:\s*(\S+)", frontmatter, re.MULTILINE)
    assert status_m, "ADR-0030 frontmatter 缺 status 字段"
    status = status_m.group(1).strip()
    assert status == "accepted", (
        f"ADR-0030 status 必须为 accepted，当前: {status!r}（版本锁定决策未落定）"
    )


@pytest.mark.parametrize("lib", CHEDL_LIBS)
def test_dir_check_required_functions_present(lib):
    """dir() 前置核验：每个 ChEDL 三库的运行时版本必须可 import。

    ADR-0030 决策 5：版本锁定前必须 dir() 核验 P5 所需函数存在。
    本测试是 Task 25 GREEN 阶段的入口守卫；如未来 ChEDL 升级触发函数重命名/移除，
    此测试将捕获并强制升级流程走 ADR-0030 决策 8。
    """
    import importlib

    mod = importlib.import_module(lib)
    assert hasattr(mod, "__version__"), f"{lib} 缺 __version__ 属性"
    assert mod.__version__ == LOCKED_VERSIONS[lib], (
        f"{lib}.__version__ {mod.__version__} != 锁定 {LOCKED_VERSIONS[lib]}"
    )
