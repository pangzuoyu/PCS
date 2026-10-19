"""alembic 漂移闸门（ORM ↔ 迁移漂移）—— P9-Prep PP-5。

退出码观测走 `scripts.run_gate`（cerebrum TODO-050 已立法，本仓闸门共用一个观测层）。
**全程不比较 255 或 1**，只判 `rc == 0` / `rc != 0` —— 255 这个码已进过 CLAUDE.md，
值得用代码约束而不是注释提醒。

四条分支：

    rc == 0                  → 放行
    输出含 "not up to date"   → 阻断 + 提示先 upgrade head（守门没跑 ≠ 通过）
    输出含连不上特征          → 放行 + 醒目告警（DB 不在就拦所有 commit，
                               会训练出「一律 --no-verify」，那等于没有闸门）
    其余非 0                 → 阻断，判为检出漂移

⚠️ 本闸只对 DATABASE_URL 指向的那个库成立（开发库 pcs）。
   pcs_test 的漂移不在视野内；要声称两库都干净，必须在 pcs_test 上单独跑一次。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 直接执行 `python scripts/gate_alembic_check.py` 时 scripts/ 自身在 sys.path 上，
# 但父目录不在；补上才能 `import scripts.run_gate`（命名空间包，无需 __init__.py）。
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.run_gate import run_capture  # noqa: E402

_UNREACHABLE = (
    "could not connect",
    "connection refused",
    "operationalerror",
    "does not exist",
)


def main(argv: list[str] | None = None, *, runner=run_capture) -> int:
    """跑 `alembic check` 并判定。返回 0 放行 / 1 阻断。

    `runner` 是注入点：测试传假 runner，不碰真 alembic（见 tests/scripts/）。
    """
    rc, out = runner(["uv", "run", "alembic", "check"], cwd=str(BACKEND_DIR))

    if rc == 0:
        print("[PP-5] ✅ 无 ORM↔迁移漂移")
        return 0

    # 守门拒跑（DB revision 落后 code head）：这是「没跑」，不是「通过」。
    if "not up to date" in out:
        print("[PP-5] ⚠️  DB revision 落后 code head —— 闸门本次未真正运行")
        print("       先执行：cd pcs-backend && uv run alembic upgrade head")
        print("       依据 CLAUDE.md §测试前检查：守门没报，可能是因为它根本没跑。")
        return 1

    low = out.lower()
    if any(tok in low for tok in _UNREACHABLE):
        print(f"[PP-5] ⚠️  alembic check 跑不起来（rc={rc}），本次放行")
        print(out)
        print("       提醒：本闸只覆盖 DATABASE_URL 指向的那个库（pcs）。")
        return 0

    print(f"[PP-5] ❌ 检出 ORM↔迁移漂移（rc={rc}），commit 阻断")
    print(out)
    print("       修法：补 ORM 声明 或 写迁移，二选一。")
    print("       注意 remove_constraint 的字面意思与正确处置恰好相反（见 CLAUDE.md）。")
    print("       紧急绕过：git commit --no-verify（需登记到 backlog）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
