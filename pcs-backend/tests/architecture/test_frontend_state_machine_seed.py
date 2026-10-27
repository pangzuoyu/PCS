"""前端 MSW 的状态机 seed ↔ 后端真身（P9B-2 · T10 · R-19）。

## 为什么要有这条

前端 `src/mocks/seed/meta.state-machine.json` 是**操作栏按钮的数据源**
（`GET /meta/state-machine`）。此前它是**手写的** ⇒ 后端改了状态机，前端
**不知道** ⇒ 两种失败：

- **按钮藏着**：后端允许 `REVERSAL_PENDING → OBSOLETE`，手写 seed 里没有
  ⇒ 前端把「撤销审批中」的作废按钮**藏掉** ⇒ 用户**没法**作废一条待批撤销
  的记录（后端明明允许）。
- **按钮可点但吃 403**：`allowed_roles` 与后端不一致 ⇒ 按钮亮着、点了 403。

⇒ seed 改成**后端生成**的 JSON，本测试逐条比对 ⇒ 漂移即红。

## ⚠️ 跨包耦合 ⇒ **skipif**（不是失败）

本测试读 `pcs-frontend/src/mocks/seed/meta.state-machine.json`
⇒ **后端-only 的检出**（只 clone 了 `pcs-backend/`）里没有这个文件 ⇒
那种检出应当**跳过**，而不是**失败**（否则后端单独跑测试永远是红的）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.meta_service import get_state_machine

#: 仓库根 = 本文件的上三级（tests/architecture/ → tests/ → pcs-backend/ → 根）
_REPO_ROOT = Path(__file__).resolve().parents[3]
#: 前端 seed 文件（**相对**路径 ⇒ 不写死绝对路径）
_SEED_REL = Path("pcs-frontend") / "src" / "mocks" / "seed" / "meta.state-machine.json"

pytestmark = pytest.mark.skipif(
    not (_REPO_ROOT / _SEED_REL).is_file(),
    reason="前端 seed 不在本次检出里（后端-only 检出 ⇒ 跳过，不是失败）",
)


def test_frontend_state_machine_seed_matches_backend() -> None:
    """前端 seed 与后端 `get_state_machine()` **逐条一致**。"""
    seed = json.loads((_REPO_ROOT / _SEED_REL).read_text(encoding="utf-8"))
    backend = get_state_machine()

    assert seed == backend, (
        "前端状态机 seed 与后端漂移："
        f"前端 {len(seed.get('transitions', []))} 条迁移 / "
        f"后端 {len(backend['transitions'])} 条迁移。"
        "⇒ 重新生成："
        "`uv run python -c \"import json;from pathlib import Path;"
        "from app.services.meta_service import get_state_machine;"
        f"Path('{_SEED_REL}').write_text(json.dumps(get_state_machine(),"
        "ensure_ascii=False, indent=2) + '\\n')\"`"
    )


def test_seed_contains_the_transition_the_handwritten_version_missed() -> None:
    """回归守卫：**手写版漏掉的那条**必须在 seed 里。

    ⚠️ 这条单独立一条：主断言失败时 pytest 只给一个「不相等」⇒ 修的人
    还得自己去 diff ⇒ 把**具体漏了什么**钉在这里，省掉那一步。
    """
    seed = json.loads((_REPO_ROOT / _SEED_REL).read_text(encoding="utf-8"))
    pairs = {(t["from"], t["action"]) for t in seed["transitions"]}
    assert ("REVERSAL_PENDING", "OBSOLETE") in pairs, (
        "REVERSAL_PENDING → OBSOLETE 缺失 ⇒ 前端会藏掉「撤销审批中」的作废按钮"
    )
