# P9-Prep 实施计划（alembic 闸门 + 4 份 ADR + P1 端点清单 + MFA 决议）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清掉阻塞 P9A 的 4 项：alembic 漂移闸门自动化、4 份 ADR 落地、《P1 实际交付面清单》、MFA 决议。本阶段不写业务代码。

**Architecture:** 产物是「4 份 ADR + 2 份 note + 1 个 Python 闸门」：① `.githooks/pre-commit` 增第二个触发段 + `pcs-backend/scripts/gate_alembic_check.py`（退出码观测走既有 `scripts/run_gate.py`，不另起一套）；② 1 份端点清单 note（`docs/`）；③ 4 份 ADR（`docs/adr/0042`~`0045`，接现有最高文件号 0041）；④ MFA 决议回写 SPEC。**无迁移、无 `app/**` 生产代码改动**；有 pytest（仅 `tests/scripts/` 两个文件的 21 个用例）。

**Tech Stack:** Python 3.12 / uv（闸门本体）、POSIX sh（hook 触发层）、alembic（漂移检测）、pytest（闸门单测）、Markdown（ADR / note）。

**Spec:** `spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md` §2（第二部分 P9-Prep）

## Global Constraints

- 本阶段**不写 `alembic/versions/*`、不写 `app/**` 生产代码**。Task 1 的探针迁移是临时文件，用完即删，不进 commit。
- ADR 编号**不接 0042**：ADR-0041 正文预留了 `ADR-0042 = 解冻机制`、`ADR-0043+ = 后续接口扩展`
  （`docs/adr/0041-c-12-vessel-6-path-coverage.md:14-15`）。本阶段产出
  **0046 / 0047 / 0048 / 0049**，把 0042 留给已写下的预留，避免两份文档占同一个号。
- ADR 格式**统一用 0041 的行内列表式**（`- Status:` / `- Date:` / `- Deciders:` / `- Related:`），不用 0030 的 YAML frontmatter —— 0040/0041 是最新两份，取最新惯例。
- ADR 交付判定：`Status: accepted` + SPEC §2.2.2 列举的每个问题都有明确裁决 + 全文无 `待定` / `TBD` / `待确认`。
- 闸门脚本退出码：**0 放行 / 1 阻断**。内部对 `uv run alembic check` 的非 0 一律判失败（它的码是 **255** 不是 1，见 Global Constraints 下的 Review Focus ①）。
- 每裁决落地后，同步回写 **SPEC §2.2.3 验收 / §2.3 状态表 / §8 待确定问题** 与 **`TODOS.md`**。不留「ADR 说已裁决、SPEC 说待定」。
- 每 task 末尾一个 commit，conventional commits，无 attribution 行。

## Review Focus

SPEC 是愿景文档，它对某类输入的沉默不等于授权该输入把程序搞坏。以下 5 条是本阶段最可能咬人的，每条已在对应 task 里落成可执行断言。

1. **`uv run alembic check` 退出码是 255，不是 1**（CLAUDE.md §测试前检查明载）。任何写成 `[ $? -eq 1 ]` 的判定会把真实漂移当通过 —— 这是 CLAUDE.md 说的「最容易被误读的守卫」。**已自动化**：`test_every_nonzero_code_is_a_failure_not_a_pass` 参数化跑 1/2/124/127/255，闸门只判 `rc != 0`，不比较具体码值。
2. **DB revision 落后 code head 时 `alembic check` 拒跑**，报 `Target database is not up to date`，同样 255。守门「没报」可能是因为它**根本没跑**。闸门对该串单独分支，给出 `uv run alembic upgrade head` 的可执行提示，而不是笼统 fail。**已自动化**：`test_stale_revision_is_blocked_not_reported_as_pass`。
3. **闸门只对当前连接的那个库成立**（`.env DATABASE_URL` → `pcs`）。它对 `pcs_test` 的漂移完全没有视野。「hook 绿」不得被读成「两库都干净」。Task 1 Step 10 把这句写进脚本文案与 README，Step 7/8 端到端时也只对开发库验。**这是本阶段唯一无法自动化的失败模式。**
4. **ADR 改了 status 但 SPEC §8 的 P9-OPEN-008/009/010 没改** → 下游仍按「待裁决」排期，静默不一致。每个 ADR task 的最后一步强制回写 §8 对应行；Task 9 Step 4 做全局 grep 自检。
5. **hook 可被 `--no-verify` 绕过**。绕过需登记（沿用 `.githooks/README.md` 既有口径）。闸门若被无代价地反复绕过会静默腐化 —— Task 1 Step 10 保留该登记要求。

> 补充（2026-10-19 审查新增）：第 1~2 条此前只有手工验证步骤，现已转为 pytest 断言 ——
> 手工验过一次就消失的保护不是保护。

---

### Task 1: PP-5 — alembic 漂移闸门自动化

**Files:**
- Create: `pcs-backend/scripts/gate_alembic_check.py`
- Create: `pcs-backend/tests/scripts/test_gate_alembic_check.py`
- Modify: `pcs-backend/scripts/run_gate.py`（新增 `run_capture()`；`run()` 转为调用它，**行为不变**）
- Modify: `.githooks/pre-commit:16` 之后（插在 OpenAPI 段的早退 `exit 0` **之前**，否则只改迁移文件时永远走不到新段）
- Modify: `.githooks/README.md`（加 Hook 小节）

**Interfaces:**
- Consumes: `scripts.run_gate.run(argv, *, tail, cwd) -> int` —— **已存在**，`cerebrum.md:1157`（TODO-050）已立法为本仓闸门退出码的唯一观测层。本任务**不另起一套**。
- Produces:
  - `scripts.run_gate.run_capture(argv, *, cwd=None, timeout=1800) -> tuple[int, str]` —— 新增。需要检查**输出内容**（而非仅成败）的闸门用它。
  - `scripts.gate_alembic_check.main(argv=None, *, runner=run_capture) -> int` —— 新增。`0` 放行 / `1` 阻断。
  - Task 2~9 不消费它，但它是对后续任何迁移改动的强制守门。

> **为什么是 Python 不是 shell**：退出码观测必须走 `run_gate`（本仓所有闸门共用一个观测层）。
> shell 无法 `import` 它，另写一套 `RC=$?` 就是造第二个真相源 —— 而这个 bug（把 255 当通过）
> 已经进过 `CLAUDE.md`，值得用代码约束而不是注释提醒。

- [ ] **Step 1: 写失败测试（先红）**

创建 `pcs-backend/tests/scripts/test_gate_alembic_check.py`，形状照抄同目录的
`test_run_gate.py`（它就是为同一类沉默假绿写的）：

```python
"""`scripts/gate_alembic_check.py` 的测试 —— 它唯一的产出是「一个退出码」。

沿用 `test_run_gate.py` 的形状（TODO-050）：断言的是**码与文案**，
因为失效模式是沉默的假绿 —— 守门红了却被报成通过。

三条分支各有根断言：正常 / 漂移 / 「守门没跑」/ 连不上。
"""
from __future__ import annotations

import pytest

from scripts.gate_alembic_check import main


def _runner(rc: int, out: str):
    """假 runner：跳过真 alembic，直接返回预设 (退出码, 输出)。"""
    return lambda argv, *, cwd=None: (rc, out)


def test_passing_db_exits_zero():
    assert main(runner=_runner(0, "No new upgrade operations detected")) == 0


def test_real_drift_is_blocked():
    """根断言：漂移（rc 非 0）→ 阻断，且**不**因 rc 是 255 而放过。"""
    out = "Detected removal of column 'pp5_probe_col' on table 'workspaces'"
    assert main(runner=_runner(255, out)) == 1


def test_stale_revision_is_blocked_not_reported_as_pass():
    """守门没跑 ≠ 通过 —— CLAUDE.md 点名的假绿来源。"""
    assert main(runner=_runner(255, "Target database is not up to date")) == 1


def test_unreachable_db_warns_but_allows():
    """DB 不在就拦下所有 commit，会训练出「一律 --no-verify」，那等于没有闸门。"""
    out = "sqlalchemy.exc.OperationalError: connection refused"
    assert main(runner=_runner(1, out)) == 0


@pytest.mark.parametrize("rc", [1, 2, 124, 127, 255])
def test_every_nonzero_code_is_a_failure_not_a_pass(rc):
    """非 0 一律失败：闸门不比较具体码值。"""
    assert main(runner=_runner(rc, "some drift output")) == 1


def test_invokes_alembic_check_from_the_backend_dir():
    seen: dict = {}

    def runner(argv, *, cwd=None):
        seen["argv"], seen["cwd"] = argv, cwd
        return 0, "ok"

    main(runner=runner)
    assert seen["argv"] == ["uv", "run", "alembic", "check"]
    assert seen["cwd"].endswith("pcs-backend")
```

- [ ] **Step 2: 跑测试确认红**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run pytest tests/scripts/test_gate_alembic_check.py -v
```

预期：`ModuleNotFoundError: No module named 'scripts.gate_alembic_check'`（收集期就红）。

- [ ] **Step 3: 给 `run_gate.py` 加 `run_capture()`**

在 `scripts/run_gate.py` 的 `run()` **之前**插入，并把原 `run()` 主体替换为调用它
（原实现在 `run_gate.py:32-51`）：

```python
def run_capture(argv: list[str], *, cwd: str | None = None,
                timeout: int = 1800) -> tuple[int, str]:
    """跑 `argv`，返回 (它自己的退出码, 合并后的 stdout+stderr)。

    需要检查输出**内容**而不只是成败的闸门用这个 —— 例如 alembic check 要区分
    「检出漂移」与「DB revision 落后、闸门根本没跑」，两者退出码都是 255。
    """
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        msg = f"命令不存在：{argv[0]}"
        print(msg, file=sys.stderr)
        return 127, msg
    except subprocess.TimeoutExpired:
        msg = f"命令超时（>{timeout}s）：{' '.join(argv)}"
        print(msg, file=sys.stderr)
        return 124, msg
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def run(argv: list[str], *, tail: int, cwd: str | None = None) -> int:
    """跑 `argv` 并返回**它自己**的退出码（打印最后 N 行输出）。"""
    code, out = run_capture(argv, cwd=cwd)
    lines = out.splitlines()
    if tail > 0 and len(lines) > tail:
        lines = [f"...（略去前 {len(lines) - tail} 行）"] + lines[-tail:]
    print("\n".join(lines))
    print(f"\nEXIT={code}  ← {argv[0]} 自己的退出码")
    return code
```

同时把 `run_gate.py` 的模块 docstring 末尾补一句：
「需要检查输出内容（而非仅成败）的闸门用 `run_capture()`，**不要**自己 `subprocess.run`。」

**配套补 `run_capture()` 的测试**（追加进已有的 `tests/scripts/test_run_gate.py`，
沿用同文件既有的 `run` 测试风格）。既有 7 个测试覆盖的是 `run()`；
`run_capture()` 是新函数，三条分支一条都不能少 ——
其中 127 / 124 是 `run()` 改调后**透传**出来的，改错了 `run()` 的既有测试抓不到：

```python
def test_run_capture_returns_code_and_merged_output():
    rc, out = run_capture([sys.executable, "-c",
                           "import sys; print('o'); sys.stderr.write('e'); sys.exit(3)"])
    assert rc == 3
    assert "o" in out and "e" in out


def test_run_capture_missing_command_is_127():
    rc, out = run_capture(["这个命令不存在-abc"])
    assert rc == 127
    assert "命令不存在" in out


def test_run_capture_timeout_is_124():
    rc, out = run_capture(
        [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.1
    )
    assert rc == 124
    assert "超时" in out


def test_run_still_forwards_127_after_refactor():
    """回归：run() 改成转调 run_capture 后，127 必须仍然透传。"""
    assert run(["这个命令不存在-def"], tail=3) == 127
```

并在该文件的 import 行加上 `run_capture`：

```python
from scripts.run_gate import main, run, run_capture
```

- [ ] **Step 4: 验既有测试没被改坏（回归）**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run pytest tests/scripts/test_run_gate.py -v
```

预期：全绿。`run()` 行为必须与改前**完全一致**（127 / 124 / 输出顺序 / `EXIT=` 行）。

- [ ] **Step 5: 写闸门**

创建 `pcs-backend/scripts/gate_alembic_check.py`：

```python
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
```

- [ ] **Step 6: 跑测试确认变绿**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run pytest tests/scripts/test_gate_alembic_check.py tests/scripts/test_run_gate.py -v
```

预期：全绿。

- [ ] **Step 7: 端到端验「无漂移 ⇒ 放行」**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run python scripts/gate_alembic_check.py; echo "RC=$?"
```

预期：`[PP-5] ✅` + `RC=0`。
若报 `[PP-5] ⚠️ DB revision 落后` —— 先 `uv run alembic current` 对比 `uv run alembic heads`
（CLAUDE.md 读法①：守门没报可能是因为它根本没跑）。

- [ ] **Step 8: 端到端验「真漂移 ⇒ 阻断」，并把探针还原干净**

> ⚠️ **探针必须加在 ORM 模型上，不是迁移文件里。**（2026-10-19 实测更正）
> `alembic check` 比对的是 **ORM metadata ↔ 活库当前 schema**，它**不读迁移源码**。
> 往 `alembic/versions/` 里加 `add_column` 迁移既不会被检出（迁移没 apply ⇒ DB 与 ORM
> 都没有那列 ⇒ 两侧一致 ⇒ 报 ✅），还会顺带把 code head 推高一格让 DB 变成「revision 落后」，
> 于是命中 stale 分支而非漂移分支 —— **看起来红过，其实验的不是这一条**。
> 真正的漂移 = ORM 声明了 DB 里没有的列。

```bash
cd /home/pangzy/code_project/PCS/pcs-backend

cp app/models/project.py /tmp/project.py.pp5bak
python3 - <<'PY'
import pathlib
p = pathlib.Path("app/models/project.py"); s = p.read_text()
anchor = ('    workspace_id: Mapped[uuid.UUID] = mapped_column(\n'
          '        Uuid, primary_key=True, default=uuid.uuid4\n    )\n')
assert anchor in s, "锚点没命中 —— 手工插入 pp5_probe_col"
p.write_text(s.replace(anchor, anchor + "    pp5_probe_col = mapped_column(Integer, nullable=True)\n", 1))
PY
grep -n "pp5_probe_col" app/models/project.py   # 必须命中，否则中止

uv run python scripts/gate_alembic_check.py; echo "RC=$?"     # 预期 ❌ + RC=1
# 实测输出：
#   [PP-5] ❌ 检出 ORM↔迁移漂移（rc=255），commit 阻断
#   FAILED: New upgrade operations detected: [('add_column', None, 'workspaces', ...)]

# ⚠️ 探针必须还原干净。它躺在 ORM 里，一旦被提交，下一个人启动服务就会炸。
cp /tmp/project.py.pp5bak app/models/project.py && rm -f /tmp/project.py.pp5bak
git diff --quiet -- app/models/ \
  && echo "探针已还原 ✓" \
  || { echo "❌ app/models/ 仍有 diff，先手工还原再继续"; exit 1; }

uv run python scripts/gate_alembic_check.py; echo "RC=$?"     # 预期 ✅ + RC=0
```

> 上面 `git diff --quiet || exit 1` 是**硬闸**：还原不掉就停，不许继续往下走。
> 不要依赖「后面还有别的步骤会清理」—— Step 13 的 `git add -A` 会把它一起提交。

> **Step 7 若已报漂移**，说明工作区本来有漂移 —— 先查清再继续，别把两件事混在一起。

- [ ] **Step 9: 接进 `.githooks/pre-commit`**

在 `.githooks/pre-commit` 的 `cd "$REPO_ROOT" || exit 1`（第 16 行）之后、
OpenAPI 段的 `if ! git diff ...` 之前，插入：

```sh
# ---- P9-Prep PP-5: alembic 漂移闸门（独立触发条件）----
# 必须放在下面 OpenAPI 段的 `exit 0` 早退之前：
# 只改迁移文件时那条早退会先命中，新段永远走不到。
if git diff --cached --name-only | grep -qE '^pcs-backend/alembic/versions/'; then
    echo "[PP-5] alembic 漂移闸门触发（迁移文件改动）..."
    echo "----------------------------------------"
    if ! (cd "$REPO_ROOT/pcs-backend" && uv run python scripts/gate_alembic_check.py); then
        echo ""
        echo "[PP-5] ❌ 闸门 fail；commit 阻断"
        exit 1
    fi
    echo ""
fi
```

- [ ] **Step 10: 更新 `.githooks/README.md`**

末尾追加：

```markdown
### `pre-commit` 第二段 — P9-Prep PP-5 alembic 漂移闸门

**触发条件**：暂存区含 `pcs-backend/alembic/versions/` 改动。

**门禁内容**（`pcs-backend/scripts/gate_alembic_check.py`）：
1. 经 `scripts/run_gate.py` 跑 `uv run alembic check`（cwd = `pcs-backend/`）
2. 退出码判定一律「非 0 即失败」—— **不比较 255 或 1**。255 这个码进过 `CLAUDE.md`
3. DB revision 落后 code head → 闸门未真正运行，阻断并提示先 `upgrade head`
4. DB 不可达 → 放行 + 醒目告警（避免训练出 `--no-verify`）

**为什么经 run_gate**：本仓闸门共用一个退出码观测层（cerebrum TODO-050）。
另写一套 `RC=$?` 就是造第二个真相源。

**已知盲区**：本闸只对 `DATABASE_URL` 指向的那个库成立（开发库 `pcs`）。
`pcs_test` 的漂移不在视野内 —— 要声称两库都干净，必须在 `pcs_test` 上单独跑一次：

```bash
cd pcs-backend
# 口令取本地 .env / pcs-backend/.env.example，**不要**把口令写进文档
DATABASE_URL="postgresql+psycopg://<user>:<password>@localhost:5432/pcs_test" \
  uv run python scripts/gate_alembic_check.py
```

**绕过**：`git commit --no-verify`，需登记到 backlog。
```

- [ ] **Step 11: 端到端验 hook 触发**

```bash
cd /home/pangzy/code_project/PCS
git add pcs-backend/scripts/gate_alembic_check.py pcs-backend/scripts/run_gate.py \
        pcs-backend/tests/scripts/ .githooks/
git commit -m "chore(backend): PP-5 alembic 漂移闸门接入 .githooks（经 run_gate 观测退出码）"
```

预期：无迁移文件改动 ⇒ 新段不触发，commit 直接成功。这是正确的（闸门只在有迁移改动时跑）。

- [ ] **Step 12: 说明 PP-5 与 TODO-016 的边界**

`TODOS.md` 的 TODO-016（ARQ 失败注入）**不在**本闸范围 —— 本闸管的是 alembic 漂移，
不是 worker 失败路径。在 PP-5 条目补一句：「闸门已落地，见 `.githooks/README.md`；
ARQ 失败路径仍零覆盖，归 P9A-NOT-004」。

- [ ] **Step 13: Commit**

```bash
cd /home/pangzy/code_project/PCS
# 提交前硬闸：探针绝不能进仓库（Step 8 已删，这里是第二道）
if git status --porcelain | grep -q zz_tmp_pp5_probe; then
    echo "❌ 探针文件仍在暂存区/工作区，中止提交"; exit 1
fi
git add -A
git commit -m "chore(backend): PP-5 alembic 漂移闸门自动化（run_gate 单点观测 + 255 不比较 + 单库盲区已注明）"
```

---

### Task 2: 《P1 实际交付面清单》

**Files:**
- Create: `docs/PCS-NOTE-P9-Prep-P1端点交付面清单-2026-10-19.md`

**Interfaces:**
- Consumes: 无
- Produces: 12 行端点归属表（每行 = 端点 / SPEC 假设路径 / 实际路径 / 存在性 / 证据 file:line / 归属 P1|P9A）。Task 7 的 P9A 范围以此表为准。

- [ ] **Step 1: 确认 SPEC §2.2.3 的核实命令是坏的**

SPEC 里写 `grep -rn "submit-approval" app/api/`。`app/` 不在仓库根，而在 `pcs-backend/app/`：

```bash
cd /home/pangzy/code_project/PCS
grep -rn "submit-approval" app/api/ ; echo "RC=$?（预期 RC=1，0 命中）"
cd pcs-backend
grep -rn "submit-approval" app/api/ ; echo "RC=$?（预期 RC=1，真 0 命中）"
```

在 note 里写明这条：SPEC §2.2.3 的命令在仓库根跑会**恒 0 命中**，据此判「未交付」是假阴性。修正命令一律 `cd pcs-backend` 后执行。

- [ ] **Step 2: 枚举真实路由（不靠猜路径字符串）**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run python -c "
from app.main import app
for r in sorted(app.routes, key=lambda r: getattr(r, 'path', '')):
    p = getattr(r, 'path', None)
    if p and (p.startswith('/api') or 'deliverable' in p or 'record' in p or 'change-impact' in p):
        print(sorted(getattr(r, 'methods', []) or []), p)
"
```

把输出整段粘进 note 的「证据」附录 —— 这是本清单唯一可信的来源。

- [ ] **Step 3: 逐端点填表**

note 正文用这张表，12 行一行不少（SPEC §2.2.3 点名的 7 个 records + 4 个 deliverables + 2 个 change-impact）：

| SPEC 假设路径 | 实际路径 | 存在 | 证据 | 归属 |
|---|---|---|---|---|
| `POST /records/{module}/{id}/submit-approval` | — | ❌ | `app/api/v1/records.py` 仅 `POST /piping`(:116) 与 `POST /piping/{pipe_id}/transition`(:167) | P9A |
| `POST /records/{module}/{id}/approval-step` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/abandon-change` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/request-reversal` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/reversal-decision` | — | ❌ | 同上 | P9A |
| `POST /records/{module}/{id}/obsolete` | — | ❌ | 同上（`mixins.py:89` 只有 `obsoleted_*` 数据列，无端点） | P9A |
| `POST /records/{module}/{id}/comments` | — | ❌ | 同上 | P9A |
| `GET /deliverables/{id}/actions` | — | ❌ | — | P9A |
| `POST /deliverables/{id}/issue` | — | ❌ | — | P9A |
| `POST /deliverables/{id}/sign-step` | — | ❌ | — | P9A |
| `POST /deliverables/{id}/customer-approval/proxy` | — | ❌ | — | P9A |
| `POST /change-impact/{module}/{id}/confirm` | `POST /change-impact/{record_type}/{record_id}/confirm-recalc` | ⚠️ 存在但**不是 SPEC 要的那个** | `app/api/v1/change_impact.py:26` | 见下 |

同时把 SPEC **没列**但 P9B 要用的 4 个读端点补进表（`app/api/v1/deliverables.py`，均为 P8 前置已交付、schema 已显式声明、**零裸字段**）：

| `GET /deliverables` | `list_deliverables` | ✅ | `deliverables.py` `list_deliverables` | P1（P8 前置） |
| `GET /deliverables/{deliverable_id}` | `get_deliverable` | ✅ | 同上 | P1（P8 前置） |
| `GET /deliverables/{deliverable_id}/versions` | `list_deliverable_versions` | ✅ | 同上 | P1（P8 前置） |
| `GET /deliverables/{deliverable_id}/versions/{rev}/snapshot` | `get_deliverable_snapshot` | ✅ | 同上 | P1（P8 前置） |

- [ ] **Step 4: 给出 `confirm-recalc` 的实质裁决（不要只看路径名）**

读 `app/api/v1/change_impact.py:26` 起 60 行，它只做 `engine.scan_stale()` + `mark_stale_then_propagate()` + `commit()`。**它没有** P9A-CIA-001 要求的哈希判定分流（结果不变 → `STALE_RESOLVED_NO_CHANGE` 免凭证；结果变化 → `CHANGE_PENDING`）。

在 note 里明确写：
- `confirm-recalc` = P1 已交付的**传播触发器**，不等于 SPEC §2.2.3 假设的 `confirm`。
- **P9A-CIA-001（哈希判定分流）与 P9A-CIA-002（`manual-adjust`）均归 P9A**，`manual-adjust` 端点不存在。
- 附带发现：`confirm_recalc` 用 `response_model=dict`，会贡献裸字段。实测其对 71 基线的影响：
  ```bash
  cd /home/pangzy/code_project/PCS/pcs-backend
  uv run python scripts/check_openapi_payload_coverage.py; echo "RC=$?"
  ```
  基线仍是 71（脚本 `BASELINE_BARE_FIELDS = 71`）—— 若上涨，说明 `dict` 已被计入，把实测数字写进 note，别猜。
  > **偏差处理规则**：若实测值与 71 不符，**先记录偏差再继续，不得直接改基线数字**。
  > 实测偏低 ⇒ `check_openapi_payload_coverage.py` 的扫描逻辑可能漏了某类字段，
  > 那是脚本缺陷（登记 TODO），不是「基线本该是 70」。
  > 实测偏高 ⇒ 先查清多出来的是什么，再决定归因。
  > 两种情况下 Task 8（PP-M）都按实测值统一 SPEC，但要**在 note 里写明偏差原因**。

- [ ] **Step 5: 回写 SPEC §2.2.3 与 §8**

- §2.2.3 验收行改为「已完成，产出 `docs/PCS-NOTE-P9-Prep-P1端点交付面清单-2026-10-19.md`；归 P9A 的 9 条 + CIA-001/002 已并入 P9A SPEC 条目」。
- §8 无需新增行（CIA 归属写在 §2.2.3 即可），但 §3.2.6 的条件句「若 P9-Prep §2.2.3 核实 …不存在」改为「已核实：`confirm` 不存在，`confirm-recalc` 不含哈希判定分流 ⇒ 两项均归 P9A」。

- [ ] **Step 6: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add docs/PCS-NOTE-P9-Prep-P1端点交付面清单-2026-10-19.md
git add "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
git commit -m "docs(P9-Prep): P1 端点交付面清单（修正 SPEC §2.2.3 的仓库根 grep 假阴性）"
```

---

### Task 3: ADR-0046 用户身份模型迁移（uuid5 → users 表持久化）

**Files:**
- Create: `docs/adr/0046-user-identity-model-migration.md`

**Interfaces:**
- Consumes: 无（可与 Task 4~6 并行，互不依赖）
- Produces: ADR-0046，裁决 ①~⑤。P9A-USR-001/005/006/007 的实现依据。Task 9 依它回写 P9-OPEN-008。

- [ ] **Step 1: 采集证据（每条都要 file:line）**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
sed -n '25,40p' app/api/v1/auth.py          # _UUID5_NAMESPACE_DNS + uuid5 回退
sed -n '255,285p' app/api/v1/auth.py        # JWT 内嵌 user_id claim
sed -n '285,300p' app/api/v1/auth.py        # /auth/me 取权威 user_id
sed -n '135,160p' app/models/project.py     # User 模型字段
grep -rn "token_version" app/ alembic/ || echo "token_version：0 命中（确认绿地方）"
grep -n "user_id" app/models/project.py | head -5   # user_projects.user_id FK → users
grep -rn "uuid5\|NAMESPACE" ../pcs-frontend/src/ || echo "前端：0 命中（已不从 /auth/me 之外派生）"
```

- [ ] **Step 2: 写 ADR-0046**

格式取 0041 的行内列表式：

```markdown
# ADR-0046：用户身份模型迁移 —— uuid5(username) 派生改为 users 表持久化主键

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/api/v1/auth.py`、`app/models/project.py:135`、`app/services/ldap_client.py`
- Informed: P9A 实施者、P9B 前端
- Supersedes: —
- Superseded by: —
- Related: ADR-0007（客户凭证代录）、CLAUDE.md §测试前检查、SPEC §3.2.2 P9A-USR-001~007、P9-OPEN-008

## 背景

`app/api/v1/auth.py:31` 定义 `_UUID5_NAMESPACE_DNS = uuid.NAMESPACE_DNS`，
`_actor_user_id()`（:29-35）在 JWT 缺 `user_id` 声明时回退 `uuid5(NAMESPACE_DNS, sub)`。
即当前**没有任何代码查 `users` 表**判身份。

`users` 表模型已存在（`app/models/project.py:135`），字段含 status / roles / ad_groups /
email / department，但真库 0 行。`user_projects.user_id` 的 FK → `users.user_id`
刚由 `p7_s5_007` 补上（bug-144）—— **这意味着派生 ID 已可能指向不存在的 users 行**。

前端已在 P7-7+ 改为从 `/auth/me` 取权威 `user_id`（`pcs-frontend/src/store/auth.ts:5-6`），
不再自行派生，派生分叉风险仅存后端一处。

`token_version` 全仓 0 命中，为本 ADR 新引入。

## 决策

### ① 历史 uuid5 与 DB 主键的等价性

**DB 主键成为唯一权威。** 登录成功后查 `users`；命中则用其 `user_id` 写入 JWT
`user_id` claim（该通道已存在于 `auth.py:262-274`），此后所有请求的 actor id 取自 claim。

`uuid5` 回退**保留但降级**：仅用于签发前存量 JWT 的解析（access token TTL 30 分钟），
该窗口内若用户已被停用，靠 `token_version` 拒绝 refresh，access token 最长 30 分钟后自然失效。

### ② 是否回填历史 uuid5 为 users 行

**不批量回填。** 理由：`users` 当前 0 行，回填需为 `user_projects` / `audit_logs.created_by`
里每个 uuid5 反查 username，而派生值不可逆（`uuid5` 单向）—— 只能靠 JWT/审计里的 username
旁证，噪声大且不可验证。

改为**惰性建行**：用户首次登录时按 username upsert `users` 行。存量孤儿
（`user_projects.user_id` 无对应 users 行）在 ADR 落地时导出为一次性清单，
交由人工确认后再决定补行还是保留孤儿（**不删** —— `user_projects` 有 FK CASCADE，删行即删授权）。

### ③ 登录路径变更

`POST /auth/login` 增一步：查 `users.status`；`DISABLED` → 401 + 写 `audit_logs`
（action = `USER_LOGIN_DENIED_DISABLED`）。`users` 无行 → 视为首次登录，建 ACTIVE 行（与②一致）。

**`/mock-login` 必须走同一条签发路径。**

现状（`app/api/v1/mock_auth.py:58-68`）：mock 端点从硬编码 `MOCK_USERS` 取 role，
直接调 `create_access_token` / `create_refresh_token`，**不查 `users` 表、
不写审计、签出的令牌无 `tv` claim**。若不一并处理，三个断言会在 mock 流量下失效：

| ADR 断言 | 不处理 mock 的后果 |
|---|---|
| §③ 停用用户拒绝登录 | mock-login 是独立签发路径，停用用户在 mock 下照样拿到有效令牌 |
| §① DB 主键唯一权威 | mock 不建 `users` 行 ⇒ `_actor_user_id` 回退 uuid5 ⇒ §② 的「30 分钟收敛窗口」变成永久 |
| §⑤ 停用即刻作废 | mock 令牌无 `tv` claim ⇒ `/auth/refresh` 无从比对 ⇒ P9A-USR-004 离职处理失效 |

**裁定**：把「user_id 解析 + 惰性建行 + `tv` claim 签发 + `users.status` 判定 +
审计写入」抽成单一的 `_issue_tokens()`，**`/auth/login` 与 `/mock-login` 共用**。
两条路径的唯一差异是凭据校验方式：LDAP bind vs 查 `MOCK_USERS` 表。

这样 §①/③/⑤ 对 mock 流量（前端 QA、pytest）同样成立，不存在「只有真实登录才受保护」的裂缝。

角色来源不冲突：`/auth/login` 的角色来自 `resolve_role(user.groups)`（`auth.py:257`），
AD 同步的角色来自同一批 AD 组 —— 同源，惰性建行不会与 AD 同步互相覆盖。

### ④ token_version 引入时机

与本 ADR 同批迁移加列，`Integer NOT NULL server_default '1'`。`create_refresh_token`
写入 `tv` claim。**access token 不写 tv**（保持无状态，SPEC P9A-USR-007 明确此粒度）。

### ⑤ 停用即刻作废的实现

`POST /auth/refresh` 比对 `claim.tv == users.token_version`，不等 → 401。
停用操作（`PUT /admin/users/{id}/disable`）在同一事务里 `token_version += 1`。

## 已知边界（**不得被表述为「已解决」**）

停用后**在手 access token 仍可用至多 30 分钟**（无状态，不查库）。
这是 SPEC P9A-USR-007 明确接受的吊销粒度，不是缺陷。若业务要求秒级失效，
唯一出路是改 access token 为有状态（每次校验查库）—— 属独立裁决，本 ADR 不做。

## 后果

- `users` 表从 0 行变为登录路径的必经表 ⇒ AD 同步（P9A-USR-002）成为必需而非可选。
- 历史 JWT 在 30 分钟窗口内 actor id 仍可能是 uuid5 值 ⇒ 该窗口内不得启用
  「按 users 行判停用」的强拦截以外的新逻辑。
- 迁移纪律：新表列走 `TimestampMixin` 三列纪律；本 ADR 涉及的列变更需手写迁移
  （`use_alter=True` **不会**自动生成迁移，见 bug-146）。
```

- [ ] **Step 3: 校验 ADR 无占位**

```bash
cd /home/pangzy/code_project/PCS
grep -nE "待定|TBD|待确认|待补" docs/adr/0046-user-identity-model-migration.md; echo "RC=$?（预期 1 = 干净）"
grep -c "^### " docs/adr/0046-user-identity-model-migration.md   # 预期 5（①~⑤）
```

- [ ] **Step 4: 回写 SPEC（Review Focus ④）**

- §8 表 `P9-OPEN-008` 行：状态 `（无）` → `已裁决：ADR-0046 accepted（2026-10-19）`，归属列 `P9-Prep` → `~~P9-Prep~~ 已关闭`。
- §2.2.2 的 ADR-A 行状态标 ✅ 并注明落点文件。
- **P9A 交接**：ADR-0046 §③ 给 P9A 增加一项 SPEC 原条目没有的工作 ——
  把签发逻辑抽成 `_issue_tokens()` 并让 `/mock-login` 共用（否则 §①/③/⑤ 对 mock 流量失效）。
  写进 SPEC §3.2.2 的 P9A-USR-005 条目。

- [ ] **Step 5: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add docs/adr/0046-user-identity-model-migration.md
git add "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
git commit -m "docs(adr): ADR-0046 用户身份模型迁移（uuid5 → users 表主键 + token_version）"
```

---

### Task 4: ADR-0047 workflow_progress 观测层

**Files:**
- Create: `docs/adr/0047-workflow-progress-observation-layer.md`

**Interfaces:**
- Consumes: 无（与 Task 3/5/6 并行）
- Produces: ADR-0047，裁决 ①~④。P9A-OBS-001~004 的实现依据。Task 9 依它回写 P9-OPEN-007。

- [ ] **Step 1: 采集证据**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
grep -rn "workflow_progress" app/ alembic/ || echo "workflow_progress：0 命中（绿地方）"
grep -n "^class \|^    def \|^    async def \|commit()\|flush()" app/services/state_machine.py | head -40
grep -n "def \|commit()\|rollback" app/core/commit_or_rollback.py
sed -n '135,141p' app/models/mixins.py   # TimestampMixin 三列纪律参照
```

- [ ] **Step 2: 写 ADR-0047**

```markdown
# ADR-0047：workflow_progress 观测层 —— 写入点、同步性与事务边界

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/services/state_machine.py`、`app/core/commit_or_rollback.py`
- Informed: P9A 实施者、P9B 甘特图组件
- Supersedes: —
- Superseded by: —
- Related: SUP-008 V1.1 §2.6、P9-OPEN-007、SPEC §3.2.3 P9A-OBS-001~004

## 背景

SPEC P9-OPEN-007 要求 P9A 交付 `workflow_progress` 表（8 字段 + 5 态枚举）与读 API，
并有硬指标「流程状态变更到持久化 ≤ 500ms」。全仓 0 命中，属绿地方。

`app/services/state_machine.py`（404 行）承载状态转移，是既有事务边界所在。

## 决策

### ① 写入点清单

三个工作流各一处，共 3 个写入点：

1. **签署**：`sign-step` 推进 / 退回时，写被推进的那一步
2. **变更单**：`deliverable_type=CHANGE_NOTICE` 的创建与自动关闭
3. **代录批准**：`customer-approval/proxy` 的状态变更

不写「打开页面」「查看」等读行为 —— 本表是**流程进度**，不是访问日志。

### ② 同步写 vs 异步写

**同步写，与业务状态在同一事务内。**

SPEC 的 500ms 是**上界**不是目标。异步（ARQ）引入的是「已提交但未入队」的丢失窗口与
「已入队但队列挂了」的延迟不可控 —— 观测层恰恰是出问题时要信的东西，它不能自己变成
不确定的。同步写的成本（多一次 INSERT）远低于观测层不可信的成本。

（ARQ 仍留给通知清理任务，见 ADR-0048。）

### ③ 与 P1 状态机事务的边界

**不设独立边界。** `workflow_progress` 写入发生在**调用方**的状态机事务内，
即由发起状态变更的那个事务负责写，不由 `state_machine.py` 内部埋点。

理由：埋点式写入会把观测代码耦合进状态机核心路径，让 P1 已验收的状态机承担 P9 的变更风险；
调用方写入则让「谁触发流程」与「流程进度记哪」在同一个可读的事务里。

失败语义：**与主事务同生共死** —— 观测写失败则整个状态变更回滚。

### ④ 与计算模块事务的关系

**无关。** 计算结果落库（各 `*_persist_service`）不产生流程进度，不写本表。

## 后果

- 表结构 8 字段 + 5 态枚举（PENDING/IN_PROGRESS/COMPLETED/SKIPPED/FAILED）由 P9A-OBS-001 落迁移。
- 500ms 验收（P9A-OBS-004）用同步写达成，无需异步管道。
- 读 API 供 P9B 甘特图消费，其响应 schema 必须显式声明（P9A-DLV-010 零裸字段约束）。
```

- [ ] **Step 3: 校验 ADR 无占位**

```bash
cd /home/pangzy/code_project/PCS
grep -nE "待定|TBD|待确认|待补" docs/adr/0047-workflow-progress-observation-layer.md; echo "RC=$?（预期 1）"
grep -c "^### " docs/adr/0047-workflow-progress-observation-layer.md   # 预期 4（①~④）
```

- [ ] **Step 4: 回写 SPEC（Review Focus ④）**

- §8 `P9-OPEN-007` 行：`待启动` → `已裁决：ADR-0047 accepted（2026-10-19），同步写 + 同事务`
- §2.2.2 的 ADR-B 行标 ✅ 并注明落点。

- [ ] **Step 5: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add docs/adr/0047-workflow-progress-observation-layer.md
git add "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
git commit -m "docs(adr): ADR-0047 workflow_progress 观测层（同步写 + 与状态机同事务）"
```

---

### Task 5: ADR-0048 编辑锁存储与续期

**Files:**
- Create: `docs/adr/0048-edit-lock-storage.md`

**Interfaces:**
- Consumes: 无（与 Task 3/4/6 并行）
- Produces: ADR-0048，裁决 ①~⑤。P9A-LCK-001~005 的实现依据。Task 9 依它回写 P9-OPEN-009。
- 额外产出：`TODOS.md` 新增一条**已发现的独立缺陷**（见 Step 2 末段），本阶段只登记不修。

- [ ] **Step 1: 采集证据**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
grep -n "pg_advisory_xact_lock\|hashtext\|abs(hash" app/services/advisory_lock.py
grep -rn "redis" app/core/config.py app/workers/worker.py | head
grep -rn "class .*RedisSettings\|REDIS_URL" app/core/config.py
```

- [ ] **Step 2: 写 ADR-0048**

```markdown
# ADR-0048：编辑锁 —— Redis 为主 + DB 审计留痕

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/services/advisory_lock.py`、`app/core/config.py`、`app/workers/worker.py`
- Informed: P9A 实施者、P9B 并发控制前端
- Supersedes: —
- Superseded by: —
- Related: P9-OPEN-009、SPEC §3.2.5 P9A-LCK-001~005、
  **ekris-redis-lock-degradation（2026-04-09，user-stated）—— 见 §⑤ 的显式关系声明**

## 背景

`app/services/advisory_lock.py` 提供两个 `pg_advisory_xact_lock` 封装，但它们
**都不能直接当编辑锁**：事务结束即释放，无 TTL、无持有者身份、无心跳、无续期。
编辑锁需要「跨请求存活 30 分钟并在超时后自动释放」。

Redis 已在栈内（`app/workers/worker.py`、`app/services/report/arq_queue.py`、
`app/core/config.py` 均依赖），不是新引入的基础设施。

## 决策

### ① 存储：Redis

Redis 存锁（`lock:edit:{record_type}:{record_id}`，value = 持有者 user_id + 获取时刻），
**理由**是编辑锁的语义是「租约」，天然需要 TTL 与原子续期 —— 这正是 Redis 的形状。
DB 表做不到「30 分钟后自动过期」而不写清理任务。

**DB 保留审计留痕**：锁的 acquire/release 写 `audit_logs`，供 P9B 审计页与事后追溯。
审计记录**不参与**锁判定（审计可延迟，锁不能）。

### ② 自动续期

前端心跳默认 60s 一次（SPEC §2.5），打 `POST /locks/{type}/{id}/renew`，
后端 `SET key value EX 30 NX` 语义下的 compare-and-expire 重置 TTL。

心跳频率取 60s 而非更短：TTL 30min 对 60s 心跳有 30 倍余量，网络抖一次不会失锁；
而 10s 心跳在多人编辑时是白烧的往返。**心跳停止 = 30 分钟后自动释放**，不需客户端显式解锁。

### ③ 超时清理

Redis TTL 30 分钟自动清理，无需定时任务。

### ④ 与状态机事务的关系

**解耦。** 编辑锁是 UX 层的互斥（防两人同时改一版），不是业务正确性的保证。
状态机转移的正确性由 `state_machine.py` + `audit_logs` 负责，**不依赖编辑锁存在**。

因此：持有锁不提交状态变更 ⇒ 不阻塞他人；他人无锁提交状态变更 ⇒ 合法。
推论：**不得**把「无编辑锁」当作状态转移的前置条件。

### ⑤ Redis 不可用时的降级 —— 两层锁：Redis 是体验层，DB 是正确性层

> **本条与 `ekris-redis-lock-degradation`（2026-04-09，user-stated，confidence 9/10）的关系**
>
> 该 learning 原文：「If Redis unavailable, must return 503 immediately.
> **No lockless concurrent allowed.**」
>
> **裁定已作出（2026-10-19，用户）**：该 learning 的语义为「禁止**无保护**下的并发」
> 而非「必须事前拒绝」—— 事后检测（乐观比对）同样构成并发保护，不是 lockless。
> 故采纳下面的双层方案，而非 fail-closed。
>
> **本条的可证伪条件**：若用户日后把该 learning 改判为「必须事前拒绝」
> （事后检测不算），则 §⑤ 作废、改为 fail-closed（503），§⑥/§⑦ 随之作废。
> 此条件已由用户裁定，不留给后续 ADR 作者重新解释。

```
        ┌──────────────────────────────────────────────┐
Redis   │ 编辑锁（悲观，事前拒绝）                      │
层      │  体验：他人持锁时直接只读，看得到持锁人是谁     │
        │  失效后果：无（仅体验降级）                   │
        └──────────────────────────────────────────────┘
                            ↓ Redis 不可用时才落到这层
        ┌──────────────────────────────────────────────┐
DB      │ record_hash 比对（乐观，事后检测）            │
层      │  正确性：保存时发现已被他人改动 → 409          │
        │  失效后果：无（完全不依赖 Redis）             │
        └──────────────────────────────────────────────┘
```

**Redis 不可用时：编辑锁降级**（前端横幅「锁服务不可用，保存时可能冲突」），
**保存路径仍由 DB 层兜底**。不是无锁放行 —— 放行的是**体验**，拦住并发的是 DB。

告警走日志 ERROR + P9B 前端顶栏横幅（与上文一致）。

推论（对 §④ 的加强）：**不得**把「持有编辑锁」当作任何写入的前置条件；
正确性由 §⑥ 的比对保证，不由锁保证。

### ⑥ 兜底粒度：per-record，复用 `record_hash`（零迁移）

**令牌 = `RecordMixin.record_hash`**（`app/models/mixins.py:61-66`），**不新增列**。

三条已核实的事实支撑这个选择：

1. `record_hash` 由 `RecordMixin` 共享 ⇒ 多数业务结果表**零迁移**。
   > ⚠️ **执行时实测更正（2026-10-19）**：不是「全部」。29 张 `*_result(s)` 表里只有
   > **19 张**有 `record_hash`；`sim_*`(8) / `util_results` / `cost_est_results` 没有，
   > `two_phase_results` 有 hash 但**无 `updated_at`** ⇒ 这 11 张要并发保护需要新列。
   > 已落进 ADR-0048 §⑥ 的覆盖表与其「尚未解决」1。
2. **比对范式已存在**：`app/services/cia_engine.py:101` 已在做「当前 record_hash 与
   data_lineage 最新 hash 比对」（change-impact 用）。复用同一范式，不新造概念。
3. `updated_at` 带 `onupdate=func.now()`（`app/models/mixins.py:38-40`）⇒ 每次 UPDATE 都会刷新，
   可作第二档比对令牌（见下方退化处理）。

> ⚠️ **「唯一收口」是错的，2026-10-19 核实后更正。**
> `finalize_calc_record`（`app/services/calc_lineage.py:166`）**不是** `record_hash` 的唯一写入点。
> 实证的旁路：
>
> | 路径 | 行为 |
> |---|---|
> | `cv/cv_persist.py:189`、`restriction/restriction_persist.py:184`、`heat/thermosiphon_persist_service.py:166` | 直接调 `compute_record_hash()`，不经 `finalize_calc_record` |
> | `pump/pump_chain_persist.py:191`、`pipe/pipe_chain_persist.py:200`、`pipe_net/pipe_net_persist.py:113` | persist 时先 `record_hash = ""`，指望后续 finalize 填充 |
>
> **结论不变，但理由变了**：三类旁路里，前一类仍写入**正确**的 hash（兜底照常生效）；
> 后一类把 hash 置空 ⇒ 落到下方退化的 `updated_at` 分支。
> 也就是说 **`updated_at` 不是罕见边角，而是 pump / pipe / pipe_net 三类记录的常态路径**。
> 实施时这三类记录的冲突检测依赖 `onupdate`，不是依赖 hash。

**粒度 = per `{module}/{record_id}`**，与 Redis 锁粒度一致。
不做「事务内多行独立 version」—— 交付物侧 `issue` 跨表事务
（改 Deliverable + 写 DeliverableVersion + 写绑定 + 写 workflow_progress）
的并发控制已由 **P9A-DLV-003 的 doc_no 原子序号分配**承担，
不需要 record_hash 重复覆盖。

**已知覆盖缺口（写明，不掩盖）**：`record_hash` 注释写明「仅设计参数参与」，
且 `compute_record_hash` 排除自身与生命周期列（`created_at` / `created_by` / `updated_at`）。
因此它**不检测** `sign_status` / `approval_step` 等批准状态字段的变化。

这是**正确的职责切分**：编辑锁保护「设计内容正在被改」，不保护「批准状态」。
批准状态的并发由状态机事务 + `pg_advisory_xact_lock`（`app/services/advisory_lock.py`）
负责，两者不重叠。

**退化处理（必须实现，不得省略）**：`record_hash` 是 `nullable=False, default=""`，
**未计算过的记录是空串**。两个空串相等 ⇒ 冲突检测失效。
且如上所述，pump / pipe / pipe_net 三类记录**常态**就是空 hash。故：

```
保存请求带 expected_hash（+ expected_updated_at）
  ├─ 当前 record_hash != "" 且 != expected_hash  → 409 CONFLICT (basis=record_hash)
  ├─ 当前 record_hash == expected_hash           → 放行（正常路径）
  └─ 当前 record_hash == ""                      ← pump/pipe/pipe_net 常态
       ├─ updated_at != expected_updated_at  → 409 CONFLICT (basis=updated_at)
       ├─ updated_at == expected_updated_at   → 放行
       └─ 两者都为空（记录从未被写）          → 409 (basis=no_baseline)
```

⚠️ `updated_at` 是 `nullable` 且只在 UPDATE 时刷新（`mixins.py:38-40`，`onupdate=func.now()`）。
新建后从未被 UPDATE 过的记录 `updated_at` 为 NULL ⇒ 必须走 `no_baseline` 分支，
**不得**把 NULL 当「相等」放行 —— 那会让从未计算过的记录完全无保护。

### ⑦ 409 冲突响应契约

冲突是**预期路径**，不是异常。契约必须让前端知道该做什么。

**状态码** `409`。**不得** 500（用户无从下手），**不得** 200 + 空体。

**响应体**（受 P9A-DLV-010 零裸字段约束，字段必须显式声明）：

```json
{
  "error_code": "RECORD_EDIT_CONFLICT",
  "message": "该记录已被他人修改，请刷新后重新编辑",
  "conflict": {
    "record_type": "PipingResult",
    "record_id": "…uuid…",
    "your_expected_hash": "…16 hex…",
    "current_hash": "…16 hex…",
    "changed_by": "…uuid… 或 null…",
    "changed_at": "2026-10-19T10:22:31+08:00 或 null",
    "basis": "record_hash | updated_at | no_baseline"
  }
}
```

- `basis` 三值对应 §⑥ 三条判定分支 —— 让前端能区分「别人改了」（刷新有用）
  与「记录没基线」（刷新没用，应联系管理员）。
- `changed_by` / `changed_at` 取自 `audit_logs` 该记录最近一条写入。
  取不到置 `null`，**不得**因此报错。

**审计**：409 本身**不写** `audit_logs`（读侧拒绝，非状态变更）。
但**无锁期间保存成功且 `expected_hash` 与库中上一值不符**时，
必须写一条 `action = RECORD_EDIT_OVERWROTE_STALE_BASELINE`。
这条审计是事后能看见「谁在锁失效期间覆盖了别人」的**唯一**途径。

**前端交互**：409 → 弹窗「该记录已被 X 于 Y 修改」，两个动作：
「查看差异」/「放弃我的修改并刷新」。**不得自动重试**（会无限循环覆盖）。

## 顺带发现的独立缺陷（本 ADR 只登记，不在 P9-Prep 修）

`app/services/advisory_lock.py:36-37` 的 `acquire_record_lock` 用
`abs(hash(record_table))` / `abs(hash(record_id))` 取 classid/objid。
**Python 的 `str.__hash__` 默认按进程随机加盐（`PYTHONHASHSEED`）**，
多 worker 部署下同一 `(table, id)` 在不同进程得到不同 key ⇒ **跨进程根本不串行**，
`pg_advisory_xact_lock` 静默失效。

同文件 `acquire_equip_list_lock` 用的是 PG 侧 `hashtext(:key)`，跨进程一致 —— 是对的。

**处置**：本 ADR 不改（属 P7 状态机范畴，且改动面在已验收代码里）。
登记到 `TODOS.md`，归属 P9A-LCK 或独立修复。裁定方向：**统一到 `hashtext()`**。
```

- [ ] **Step 3: 校验 ADR 无占位**

```bash
cd /home/pangzy/code_project/PCS
grep -nE "待定|TBD|待确认|待补" docs/adr/0048-edit-lock-storage.md; echo "RC=$?（预期 1）"
grep -c "^### " docs/adr/0048-edit-lock-storage.md   # 预期 7（①~⑤ 回答 SPEC ADR-C 五问 + ⑥⑦ 兜底粒度与 409 契约）
grep -n "ekris-redis-lock-degradation" docs/adr/0048-edit-lock-storage.md   # 必须命中 ≥2（Related 行 + §⑤ 引用块）
```

> §⑥/§⑦ 是 SPEC ADR-C 五问之外的**新增内容**（兜底粒度 + 冲突契约）。
> 它们不是「多答了两题」，是 §⑤ 选了双层方案后必须补齐的落地约束 ——
> 2026-10-19 审查时确认：只写 §⑤ 会留下「乐观锁粒度未定」「409 返回什么未定」两个洞。

- [ ] **Step 4: 登记 `hashtext` 缺陷到 TODOS.md**

在 `TODOS.md` 追加：

```markdown
### TODO-047: advisory_lock.acquire_record_lock 跨进程不串行（Python hash 加盐）

`pcs-backend/app/services/advisory_lock.py:36-37` 用 `abs(hash(record_table))` /
`abs(hash(record_id))` 作 `pg_advisory_xact_lock` 的 classid/objid。
Python `str.__hash__` 默认按进程随机加盐（PYTHONHASHSEED），多 worker 部署下
同一 `(table, id)` 在不同进程算出不同 key ⇒ 锁静默失效、并发状态转移不被串行化。

同文件 `acquire_equip_list_lock` 用 PG `hashtext()`，是正确的。
裁定方向：统一到 `hashtext()`（ADR-0048 §背景 已登记）。
- **发现**：2026-10-19，P9-Prep 编写 ADR-0048 时
- **归属**：P9A-LCK 或独立修复；**不在 P9-Prep 修**（改动面在 P7 已验收代码）
- **严重度**：HIGH（并发正确性，且失败无声）
```

- [ ] **Step 5: 回写 SPEC（Review Focus ④）**

- §8 `P9-OPEN-009` 行：`（无）` → `已裁决：ADR-0048 accepted（2026-10-19），Redis + 30min TTL + DB record_hash 兜底`
- §2.2.2 的 ADR-C 行标 ✅ 并注明落点。
- **P9A 交接**：ADR-0048 §⑥/§⑦ 给 P9A 增加了三项 SPEC 原条目里没有的工作 ——
  ① 编辑保存路径的 `expected_hash` 比对（`records.py` 现无 PUT/PATCH，该路径 P9A 全新建）
  ② `RECORD_EDIT_CONFLICT` 409 响应 schema（受 P9A-DLV-010 零裸字段约束）
  ③ `RECORD_EDIT_OVERWROTE_STALE_BASELINE` 审计 action 枚举
  这三项**在有 `record_hash` 的 19 张表上不新增迁移**（另 11 张需新列，见 ADR-0048 §⑥ 覆盖表）。
  把它们写进 SPEC §3.2.5 的 P9A-LCK 条目，否则 P9A 排期时看不到这份欠账。

- [ ] **Step 6: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add docs/adr/0048-edit-lock-storage.md TODOS.md
git add "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
git commit -m "docs(adr): ADR-0048 编辑锁（Redis 体验层 + record_hash 兜底层）+ 登记 TODO-047"
```

---

### Task 6: ADR-0049 通知与待办数据模型

**Files:**
- Create: `docs/adr/0049-notification-and-todo-data-model.md`

**Interfaces:**
- Consumes: 无（与 Task 3/4/5 并行）
- Produces: ADR-0049，裁决 ①~④。P9A-NOT-001~005 的实现依据。Task 9 依它回写 P9-OPEN-010。

- [ ] **Step 1: 采集证据**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
grep -rn "notifications\|__tablename__ = \"todos\"" app/ alembic/ || echo "两表：0 命中（绿地方）"
ls app/workers/
grep -rn "arq\|ARQ" app/services/report/arq_queue.py | head -5
grep -n "TODO-016" ../TODOS.md
sed -n '135,141p' app/models/mixins.py
```

- [ ] **Step 2: 写 ADR-0049**

```markdown
# ADR-0049：通知与待办数据模型 —— 通知建表 / 待办实时计算

- Status: **accepted**
- Date: 2026-10-19
- Deciders: PCS 架构组（单人开发，用户裁决）
- Consulted: `app/workers/`、`app/services/report/arq_queue.py`、`TODOS.md` TODO-016
- Informed: P9A 实施者、P9B 通知中心 / 待办栏
- Supersedes: —
- Superseded by: —
- Related: P9-OPEN-010、ADR-0047（观测层）、SPEC §3.2.4 P9A-NOT-001~005

## 背景

通知与待办两表在 P0 清单中均无，P9A 需新建。SPEC 给了两个候选形态（建表 / 实时计算）
并要求两者都 ≤500ms。ADR-0007（客户凭证代录）已引入「通知」语义（签署事件需通知他人）。

**结论先行：两者形态不同，不该统一。** 待办的真值随签署矩阵推进而自动变化，
通知是离散发生过的事实。

## 决策

### ① notifications：建表

通知是**发生过的事实**（某人某时被退回、某单被审批），无法从当前状态反推 ——
「你被退回过」在记录已改正后依然成立，但实时计算会返回空。

建 `notifications` 表。`GET /notifications` 按 `recipient_id + read_at` 索引，
`PUT /notifications/{id}/read` 标记已读。写侧异步（ARQ 已在栈内），不影响主链路。

### ② todos：实时计算

待办的真值是「**当前**谁被卡住」，它由签署矩阵的当前步骤决定，随每次签署推进自动改变。

建表意味着每次推进都要 UPDATE 全部下游步骤的 todo 行 —— 写放大，且引入了
「todo 表与 matrix 表不一致」的窗口。实时计算直接查
`SignatureMatrix.steps_json` 中当前步骤的 role × 当前用户角色 → 命中即一条待办。

**没有一行会过期**，因为它每次查询都从真值重算。

### ③ ≤500ms 的索引支撑

- 待办（实时计算）：走 `deliverables` 现有索引 + `steps_json` 内存解析，无 JOIN 大表。
  验收以 `EXPLAIN ANALYZE` 确认无全表扫为准（P9A-NOT-003 验收）。
- 通知（建表）：`ix_notifications_recipient_unread (recipient_id, read_at)`
  部分索引 `WHERE read_at IS NULL`。这是 500ms 指标的全部支撑 —— 该索引必须进迁移。

### ④ 通知保留 30 天清理：ARQ 任务 + 失败路径覆盖

清理任务挂 ARQ（`app/workers/`，与既有 worker 同栈）。

**必须补失败注入测试**（TODO-016 显示 ARQ 失败路径覆盖率为零）：
构造 worker 抛异常 → 断言任务被重试/进 DLQ，而非静默消失。
P9A-NOT-004 验收明确要求这条测试存在。

## 后果

- 迁移纪律：新表走 `TimestampMixin` 三列纪律（created_by / created_at timezone+server_default /
  updated_at nullable）；`drop_table` 只出现在 `downgrade()` 且带 `if_exists`。
- `todos` 不建表 ⇒ SPEC §3.2.4 P9A-NOT-002 记为「按本 ADR 走实时计算，无迁移」。
- 待办/通知的响应 schema 仍受 P9A-DLV-010 零裸字段约束。
```

- [ ] **Step 3: 校验 ADR 无占位**

```bash
cd /home/pangzy/code_project/PCS
grep -nE "待定|TBD|待确认|待补" docs/adr/0049-notification-and-todo-data-model.md; echo "RC=$?（预期 1）"
grep -c "^### " docs/adr/0049-notification-and-todo-data-model.md   # 预期 4（①~④）
```

- [ ] **Step 4: 回写 SPEC（Review Focus ④）**

- §8 `P9-OPEN-010` 行：`（无）` → `已裁决：ADR-0049 accepted（2026-10-19），通知建表 / 待办实时计算`
- §2.2.2 的 ADR-D 行标 ✅ 并注明落点。
- §3.2.4 的 P9A-NOT-002「todos 表」改为「**按 ADR-0049 走实时计算，不建表**」。

- [ ] **Step 5: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add docs/adr/0049-notification-and-todo-data-model.md
git add "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
git commit -m "docs(adr): ADR-0049 通知建表 / 待办实时计算（混合方案）"
```

---

### Task 7: MFA 决议（P9-OPEN-001，硬阻塞）

**Files:**
- Create: `docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md`
- Modify: `spec/…P9…（修订版）.md` §2.2.4 + §8 `P9-OPEN-001`

**Interfaces:**
- Consumes: Task 3 的 ADR-0046（代录二次认证依赖登录/停用路径，结论②③决定 fallback 能否复用同一入口）
- Produces: MFA 路径裁决（A 或 B）+ 强制审计 action 名。P9A-DLV-008（代录后端）依赖此结论开工。

> **本 task 含一个必须由人做的裁决。** Agent 不得代选 —— SPEC §2.2.4 要求「确认公司 MFA 方案」
> 或「Fallback」，前者是组织事实（公司买没买 TOTP 短信服务），不是代码能推导的。
> 本 task 的职责是把决策材料备齐、呈给用户、记录裁决。停在 Step 4 等用户答复是**正确终点**，不是失败。

- [ ] **Step 1: 采集现状证据**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
wc -l app/services/ldap_client.py
grep -n "def \|bind\|ldap" app/services/ldap_client.py | head -15
sed -n '217,285p' app/api/v1/auth.py    # login 全流程
grep -rn "CUSTOMER_APPROVAL_PROXIED\|SIGN_2FA" app/ ../docs/adr/0007*.md | head
grep -n "P9-ADM-001\|二次认证\|MFA" ../spec/PCS-REQ-2026-002-SPEC-P9*.md | head
```

- [ ] **Step 2: 起草决策备忘**

在 `docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md` 写两条路径的对照，逐条给事实依据：

| 维度 | 路径 A：真 MFA（TOTP / 短信 / 硬件令牌） | 路径 B：Fallback（AD 密码二次输入） |
|---|---|---|
| 外部依赖 | 公司已有 MFA 服务或需采购 + 发放流程 | 无（复用既有 LDAP 通道） |
| 与 ADR-0046 的关系 | 独立（不依赖 users 表） | 复用二次输入入口，需与 ADR-0046 §③ 的停用判定协同 |
| 代录场景（ADR-0007） | 需在 `customer-approval/proxy` 内嵌 TOTP 校验 | 复用 LDAP 再认证 |
| 审计 | `SIGN_2FA_OK` | `SIGN_2FA_FALLBACK`（SPEC §2.2.4 路径 B 指定名） |
| 失败处理 | 校验失败拒签 | 校验失败拒签 |
| 实施成本 | 高（采购/接入/前端 enrollment） | 低（一次再认证调用） |
| 后续替换成本 | — | 需二次改造代录链路 |
| **mock 下的二次认证** | 不适用（mock 本就不做二次认证） | **已裁决：mock 会话豁免**（见下） |

> ### ✅ 裁决（2026-10-19，用户）：**路径 B —— AD 密码二次输入 + 强制审计**
>
> P9-OPEN-001 关闭。落地约束四条：
>
> 1. **审计 action = `SIGN_2FA_FALLBACK`**（SPEC §2.2.4 路径 B 指定名），
>    写入 `audit_logs`。**不得**复用 `SIGN_2FA_OK` —— 后者会掩盖「我们没上真 MFA」这个事实，
>    使日后审计读不出当前用的是降级方案。
> 2. **二次输入验证的是操作者本人的 AD 密码**，走既有 `authenticate(username, password)`
>    （`app/services/ldap_client.py`）—— 不新增凭据通道。
> 3. **路径 B 是明确的过渡态，不是终态。** SPEC §2.2.4 原文即「MFA 后续替换」。
>    替换时应新增 `SIGN_2FA_OK` 与真 MFA 校验，届时 `SIGN_2FA_FALLBACK` 转为历史值。
>    **不得**在 Fallback 路径上直接改用 `SIGN_2FA_OK` 冒充已上 MFA。
> 4. **mock 会话豁免**（已裁决，见下块）。豁免范围限定在登录层，
>    `verify_secondary_auth()` 函数本身不得豁免。
>
> **P9A 交接**：P9A-DLV-008（代录客户批准后端）需新增
> `SIGN_2FA_FALLBACK` 审计枚举 + 二次认证中间件；SPEC §3.2.1（5b）与 §3.2.1 的
> 通过/退回两条链路都依赖它（SPEC §R7 把它升级为硬阻塞的理由）。
>
> **连带激活 P9-OPEN-002**：路径 B 下邮件成为通知主通道（原判断：路径 A 走短信则邮件
> 非必需，路径 B 则必需）。邮件服务器未定 ⇒ P9A-NOT-001 的写侧无出口，
> 这条从「可缓」变成 P9A 开工前必须有结论。见 Step 3。

> **裁决（2026-10-19，用户）：mock 用户豁免二次认证。**
>
> `/mock-login` 不查 LDAP，只查硬编码 `MOCK_USERS`（`app/api/v1/mock_auth.py:14-19`），
> mock 用户没有 AD 密码 —— 路径 B 的「AD 密码二次输入」在 mock 下本就无密码可输。
>
> **为什么豁免是安全的（不是「测试环境有豁免、生产没有」那种危险形态）**：
> `app/main.py:118` 是 `if not settings.is_production: app.include_router(mock_auth_router)` ——
> **mock 路由在生产环境根本不存在**。mock 会话在生产上无法产生，
> 所以「豁免」没有生产面可绕，不构成绕过二次认证的后门。
>
> **⚠️ 但豁免的范围必须限定在登录层，不是二次认证函数本身。**
>
> | | 豁免 | 不豁免 |
> |---|---|---|
> | mock 会话**触发**二次认证 | ✅ 豁免（本裁决） | — |
> | `verify_secondary_auth()` 函数本身 | — | ❌ **不得豁免** |
>
> 豁免只发生在「谁来登录」这一层。二次认证的**实现**照常存在、照常被要求。
> 因此 P9A-DLV-008（代录客户批准后端）**必须**对二次认证函数做**直接单测**，
> 绕开 mock 登录路径 —— 否则 mock 全绿会被读成「二次认证验证过了」，而它其实没跑过。
>
> **残留风险（写明，不掩盖）**：dev / QA / pytest 环境**永远**测不到
> 「真实用户走完整二次认证流程」这条端到端链路。该链路的验证责任落在
> P9A 的集成环境（需真 LDAP），不属于 mock 覆盖面。P9A 的测试计划须写明这一条。

同时写明**两条路径都无法回避的事实**：SPEC §3.2.1 的「通过/退回操作」与 §3.2.1(5b) 代录批准
两条链路都依赖它 —— 这就是 SPEC §R7 把它升级为硬阻塞的理由。

- [ ] **Step 3: 核实 P9-OPEN-002 / 004 / 006 是否被 MFA 决议连带决定**

SPEC §8 另有三条 P9-Prep 归属的待定项：邮件服务器（P9-OPEN-002）、用户同步频率（P9-OPEN-004）、
通知 WebSocket vs 轮询（P9-OPEN-006）。

```bash
cd /home/pangzy/code_project/PCS && grep -n "P9-OPEN-002\|P9-OPEN-004\|P9-OPEN-006" "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
```

在备忘里对每条给出**带依据的建议**（不代替用户裁决，只把 SPEC 已有的倾向写清）：
- P9-OPEN-002 邮件服务器：若 MFA 走短信通道则邮件非必需；若走 AD 二次输入则邮件是通知主通道。**被 MFA 结论决定。**
- P9-OPEN-004：SPEC 已给倾向「每日凌晨」，无新增依据，沿用。
- P9-OPEN-006：SPEC 已给倾向「WebSocket + 降级轮询」，无新增依据，沿用。

> ### ✅ 裁决（2026-10-19，用户）：P9-OPEN-002 —— **本版不设邮件服务器，预留接口**
>
> 邮件作为**下一版功能**，本开发版不实现投递。落地约束三条：
>
> 1. **本版通知主通道 = 站内信**（铃铛 + 待办列表）。这与 SPEC §3.1.1 的 UI 描述一致
>    （「通知中心：顶部铃铛图标，下拉展示通知列表」），且 §3.1.1 待办列表本就「登录后首页展示」
>    —— 站内信在登录模型下是自洽的，无需邮件补位。
> 2. **预留通道接口，不预留具体实现。** P9A 的通知写侧须经一个通道抽象
>    （如 `NotificationChannel` 协议 + `InAppChannel` 实现），邮件作为其未来的一个实现，
>    **本版不写** `EmailChannel`（不写空壳实现 —— 空壳会假装有邮件通道已就绪，
>    下一版接的时候才发现接口签名不对）。
>    **不得**在 service 里直接 `if 走邮件: ...`，那会让「预留」变成「临时 if」。
> 3. **用户不可达时无处可达。** 这是本决策的已知代价，写明不掩盖：
>    站内信只在用户登录时可见。离线的用户不会收到任何主动提醒，
>    直到他自己登录为止。开发版可接受；正式版上此行为前**必须**有邮件或推送通道。
>
> **连带影响（Step 5 必须写进备忘，不能只落在口头）**：
>
> | 影响面 | 变化 |
> |---|---|
> | ADR-0049 §① | 通知写侧异步的理由变了 —— 原理由是「不阻塞主链路的外部投递」，本版**没有外部投递**，异步只剩「不阻塞写库」。ADR-0049 需补记：异步与否在本版不再由投递延迟决定 |
> | P9A-NOT-004（30 天清理） | **不变**。清理是本地定时任务，与有无邮件无关 |
> | P9-OPEN-006 | **权重上升**。去掉邮件后，实时推送成了通知唯一的及时性来源 ——「WebSocket + 降级轮询」从「建议」升为**本版通知体验的关键路径** |
> | ADR-0007（代录二次认证） | 不受影响（走 AD 密码，不走邮件） |

> ### ✅ 裁决（2026-10-19，用户）：P9-OPEN-004 / P9-OPEN-006
>
> | 编号 | 裁决 | 依据 |
> |---|---|---|
> | P9-OPEN-004 用户同步定时频率 | **每日凌晨** | 沿用 SPEC 倾向，无新增依据 |
> | P9-OPEN-006 通知推送方式 | **WebSocket + 降级轮询** | 沿用 SPEC 倾向；且因邮件已移除（见上），实时推送成为通知唯一及时性来源 ⇒ 从「建议」升为**明确确认** |
>
> **P9-OPEN-006 的连带要求**：WebSocket 是本版通知体验的关键路径，不是可选增强。
> 断线时降级到轮询；**不得**在 WebSocket 不可用时直接停止推送 —— 那等于通知静默失效，
> 而通知系统失效无声正是 ADR-0047 立观测层要防的那类问题。
> 降级状态应可观测（健康端点或指标），不能只靠前端感觉。

- [ ] **Step 4: 呈给用户裁决 ⏸**

**已裁决（2026-10-19）**：mock 会话豁免二次认证 —— 见 Step 2 的裁决块。

**已裁决（2026-10-19，用户）**：
- **路径 B —— AD 密码二次输入 + `SIGN_2FA_FALLBACK` 强制审计**（见 Step 2 的裁决块）
- mock 会话豁免二次认证

**已裁决（2026-10-19，用户）**：
- **路径 B —— AD 密码二次输入 + `SIGN_2FA_FALLBACK` 强制审计**（见 Step 2 的裁决块）
- mock 会话豁免二次认证
- **P9-OPEN-002 —— 本版不设邮件服务器，预留 `NotificationChannel` 接口**（见 Step 3 的裁决块）
- **P9-OPEN-004 每日凌晨** / **P9-OPEN-006 WebSocket + 降级轮询**（见 Step 3 的裁决块）

**全部裁决已作出 —— 可以执行 Step 5。**

- [ ] **Step 5: 记录裁决并回写 SPEC**

备忘末尾写「## 裁决」段（日期 + 路径 + 审计 action 名 + 拍板人），然后：
- SPEC §2.2.4 验收行改为「已完成：**路径 B（AD 密码二次输入 + `SIGN_2FA_FALLBACK` 强制审计）**，见 `docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md`」
- SPEC §8 `P9-OPEN-001` 状态：`待确认` → `已裁决（路径 B，2026-10-19）`，归属 `~~P9-Prep~~ 已关闭`
- SPEC §8 `P9-OPEN-002` 状态：`待确认` → `已裁决（本版不设邮件服务器，预留 NotificationChannel 接口；邮件为下一版功能，2026-10-19）`
- SPEC §8 `P9-OPEN-004` 状态：`待确认` → `已裁决（每日凌晨，2026-10-19）`
- SPEC §8 `P9-OPEN-006` 状态：`待确认` → `已裁决（WebSocket + 降级轮询，2026-10-19）`
- SPEC §2.6 假设「通知渠道（站内信/邮件）已配置」需同步为「本版仅站内信；邮件为下一版功能」——
  留着会与 P9-OPEN-002 的裁决矛盾

- [ ] **Step 6: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md
git add "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
git commit -m "docs(P9-Prep): MFA 决议（路径 B）+ P9-OPEN-002/004/006 连带裁决"
```

---

### Task 8: PP-M — 统一 SPEC 裸字段基线数字（71 vs 70）

**Files:**
- Modify: `spec/…P9…（修订版）.md` §3.2.1（P9A-DLV-0XX 行 + 硬约束段）

**Interfaces:**
- Consumes: Task 2 Step 4 的实测值（`check_openapi_payload_coverage.py` 的实际输出）
- Produces: SPEC 内**唯一**一个裸字段基线数字，P9A-DLV-010 的验收阈值不再是两个值。

> **为什么单列而不是塞进 Task 9**：Task 9 的验收标准是「P9-Prep 四项交付物完成」。
> 基线数字统一是**第五件事** —— 它确实属 P9-Prep（修自己产出物的错），但不属那四项。
> 混进收口任务会让评审同时判断两件事。
>
> **为什么必须在本阶段做完**：这个数字是 **P9A-DLV-010 的验收阈值**。
> P9A 一开工就要对着它写「响应 schema 零裸字段」的守门。对着错数字开工 = 债务从 71 变 70 或 72。

- [ ] **Step 1: 实测当前基线**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run python scripts/check_openapi_payload_coverage.py 2>&1 | tail -20
grep -n "^BASELINE_BARE_FIELDS" scripts/check_openapi_payload_coverage.py
```

记下两处数字。脚本里的 `BASELINE_BARE_FIELDS` 是**代码里的权威值**，
SPEC 是文档 —— 以代码为准，SPEC 跟着代码改。

- [ ] **Step 2: 定位 SPEC 里的两处表述**

```bash
cd /home/pangzy/code_project/PCS
grep -n "70/141\|71 个\|71 是\|基线.*71\|基线.*70" "spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
```

预期至少命中两处且数字不同（§3.2.1 P9A-DLV-0XX 行写 70，硬约束段写 71）。

- [ ] **Step 3: 两处统一为实测值**

按 Step 1 的实测值改。**不要**在此把基线下调到 0 —— 71 是既有欠账，
归 P9A-DLV-0XX / SPEC §3.4 约束①，不在本阶段偿还。本阶段只保证「一个数字、且它是真的」。

- [ ] **Step 4: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add -A
git commit -m "docs(P9-Prep): PP-M 统一 SPEC 裸字段基线（70/71 二义 → 实测值）"
```

---

### Task 9: 收口同步（SPEC §2.3 状态表 + §9 开发计划 + handoff）

**Files:**
- Modify: `spec/…P9…（修订版）.md` §2.3、§9
- Modify: `docs/Web版开发计划.md`（§9 点名要同步的那份）
- Modify: `.wolf/STATUS.md`

**Interfaces:**
- Consumes: Task 1~8 的全部产物
- Produces: P9-Prep 段整体收口。无下游消费者 —— Task 9 是终点。

- [ ] **Step 1: 勾完 SPEC §2.3 的 P9-Prep 交付物表**

9 行逐行置状态，**只勾真正完成的**，其余保持 ❌ 并注明原因：

| 交付物 | 目标状态 | 依据 |
|---|---|---|
| alembic check 闸门 / git hook | ✅ | Task 1，`.githooks/README.md` 有小节 |
| ADR-A 身份模型 | ✅ | Task 3，ADR-0046 |
| ADR-B 观测层 | ✅ | Task 4，ADR-0047 |
| ADR-C 编辑锁 | ✅ | Task 5，ADR-0048 |
| ADR-D 通知/待办 | ✅ | Task 6，ADR-0049 |
| 《P1 实际交付面清单》 | ✅ | Task 2，note 文件 |
| MFA 决议 | ✅ | Task 7 —— **若用户选了路径 B，仍算已裁决**（SPEC 验收原文：「已确认」或「已 Fallback」） |

- [ ] **Step 2: 同步 `docs/Web版开发计划.md`（SPEC §9 要求）**

改 5 处：
1. P9 周期：`第 23–25 周` → `第 23–35 周`（P9-Prep 23–24 / P9A 25–30 / P9B 31–35）
2. P9 核心产出：`签署流程、变更影响分析、ADMIN` → `P9-Prep（清账+ADR）、P9A（后端交付物+身份+观测层）、P9B（前端交互）`
3. P9 依赖：`P1, P7` → `P7 收口 + P9-Prep ADR`
4. 模块依赖图：`P8 → P9` 之间的箭头改为 `P8 → P9-Prep → P9A → P9B → P10`
5. 里程碑验收标准表：P9 行拆为 P9-Prep / P9A / P9B 三行

```bash
cd /home/pangzy/code_project/PCS
grep -n "第 23\|P9\|P8 →" "docs/Web版开发计划.md" | head -30
```

先跑这条看清该文件的实际结构再改 —— 文件名/行号以上面 grep 结果为准。

- [ ] **Step 3: 补 SPEC §9「未解决问题章节」新增项**

按 SPEC §9 要求新增说明「**P9 后端交付物子系统实际未由 P1 交付**」，内容以 Task 2 的清单为据：
P1 只交付了状态机骨架与 deliverables 读面，4 个写端点 + 9 个 records 工作流端点均不存在。

- [ ] **Step 4: 全局一致性自检**

```bash
cd /home/pangzy/code_project/PCS
SPEC="spec/PCS-REQ-2026-002-SPEC-P9 P9 工作流与权限开发规格说明书（修订版）.md"
grep -n "待确认\|待启动\|P9-OPEN-008\|P9-OPEN-009\|P9-OPEN-010" "$SPEC"
```

预期：`P9-OPEN-008/009/010` 三行均显示已裁决且归属标 `已关闭`；
`待确认` 仅剩与 P9-Prep 无关的条目。

- [ ] **Step 5: 跑仓库既有闸门，确认没碰坏任何东西**

```bash
cd /home/pangzy/code_project/PCS/pcs-backend
uv run python scripts/check_openapi_payload_coverage.py; echo "RC=$?（预期 0）"
uv run alembic check; echo "RC=$?（预期 0；本阶段未动 schema）"
uv run pytest tests/scripts/ -q; echo "RC=$?（预期 0）"
uv run pytest -q; echo "RC=$?（预期 0 —— Task 1 改了 run_gate.py，须跑全量确认无回归）"
```

> Task 1 动了 `scripts/run_gate.py`（既有代码），所以本阶段**必须**跑 pytest 全量，
> 不能只跑 `tests/scripts/`。前端无改动，`npm run test` / `typecheck` / `lint` 无需跑。
> 若 `alembic check` 非 0，说明工作区本来就有未提交漂移 —— 先 `uv run alembic current`
> 对比 `uv run alembic heads`（CLAUDE.md 读法①：守门没报可能是因为它根本没跑）。

- [ ] **Step 6: 重新生成 handoff**

```
/handoff
```

`.wolf/STATUS.md` 的「Next quest」应改为 P9A，并指向本计划的 ADR 结论。

- [ ] **Step 7: Commit**

```bash
cd /home/pangzy/code_project/PCS
git add -A
git commit -m "docs(P9-Prep): 收口 —— SPEC §2.3/§9 同步 + 开发计划 P9 三段化 + STATUS handoff"
```

---

## What already exists（复用，未重建）

| 既有物 | 本计划怎么用 |
|---|---|
| `scripts/run_gate.py` | **退出码观测的唯一收敛点**（cerebrum TODO-050 已立法）。Task 1 只加 `run_capture()`，不另写 `$?` 逻辑 |
| `tests/scripts/test_run_gate.py` | Task 1 的测试形状直接照抄；新测试追加进同一文件 |
| `.githooks/pre-commit` + `core.hooksPath` | Task 1 加第二段，不改现有 A-08 段。框架未装也无需装 |
| `check_openapi_payload_coverage.py` (`BASELINE_BARE_FIELDS = 71`) | Task 8 PP-M 的权威值来源（代码为准，SPEC 跟着改） |
| `RecordMixin.record_hash` + `finalize_calc_record` + `cia_engine` 比对范式 | ADR-0048 §⑥ 的兜底令牌 —— **零迁移**，复用而非新建 version 列 |
| `users` 表模型（`project.py:135`）+ `token_version` 缺列 | ADR-0046 的迁移只加一列 |
| Redis + ARQ（`config.py:43`、`app/workers/`） | ADR-0048/0045 建在既有设施上，不引入新中间件 |
| ADR 编号空间与 0041 行内列表格式 | Task 3~6 接 **0046~0049**（**不接 0042** —— ADR-0041 预留了它），格式统一 |
| `deliverables.py` 4 个读端点（P8 前置已交付） | Task 2 判为 P1 已交付，不重复实现 |

## NOT in scope（考虑过，明确不做）

| 不做 | 理由 |
|---|---|
| 引入 pre-commit 框架 | 与「CI/CD 不做」的用户裁决冲突；`.githooks` 已覆盖同样能力 |
| `remove_constraint` 字面执行 | CLAUDE.md 记载：实测 39 条全是「DB 有、ORM 漏声明」，照字面删会删掉 DB 的安全网 |
| 修 `advisory_lock.acquire_record_lock` 的 hash 加盐 | 改动面在 P7 已验收代码里；登记为 TODO-047，不在 P9-Prep 动 |
| 补 71 个既有裸字段（TODO-039/041） | 属 P9A-DLV-0XX / P9B，不在本阶段；本阶段只保证新债为 0 |
| P9A / P9B 的实施计划 | ADR 未 accepted 前写代码级计划等于写 fiction；见「尚未解决的问题」1 |
| SPEC §4.2 mock type 描述 | 处置口径归 TODO-039/041，在 SPEC 改会产生第二个真相源；见「尚未解决的问题」6 |
| hook 级（真 git commit）端到端测试 | 闸门逻辑已由 pytest 覆盖；hook 只是薄触发层，人工验一次（Step 11）足够 |

## 失败模式（新增代码路径）

本阶段唯一的新代码路径是 `gate_alembic_check.main()` 与 `run_gate.run_capture()`。

| 失败模式 | 有测试？ | 有错误处理？ | 用户看到什么 |
|---|---|---|---|
| DB revision 落后，闸门拒跑 | ✅ `test_stale_revision_is_blocked_not_reported_as_pass` | ✅ 单独分支 | ⚠️ + `upgrade head` 命令（**不**谎报通过） |
| 真漂移但退出码不是 255 | ✅ `test_every_nonzero_code_is_a_failure_not_a_pass`（1/2/124/127/255） | ✅ 只判 `rc != 0` | ❌ 阻断 + 输出 |
| DB 不可达被误判成漂移 | ✅ `test_unreachable_db_warns_but_allows` | ✅ 独立分支 | ⚠️ 放行 + 单库盲区提醒 |
| `run_capture` 重构后 127/124 丢失 | ✅ `test_run_capture_missing_command_is_127` / `_timeout_is_124` / `test_run_still_forwards_127_after_refactor` | — | — |
| 跑在错的 cwd（`alembic.ini` 不在仓库根） | ✅ `test_invokes_alembic_check_from_the_backend_dir` | — | — |
| **两个库只验了一个** | ❌ **无自动化** | ⚠️ 仅 README + 脚本文案注明 | 无提示 —— 这是**已知盲区**，不是疏漏 |

> 最后一条是唯一的静默失败：hook 绿 ≠ 两库都干净。CLAUDE.md 读法③明载 `alembic check`
> 只对当前连接的库成立。缓解只能靠人在 `pcs_test` 上单独跑一次，无自动化手段。

## 并行执行建议

`SPEC` 文件被 Task 2/3/4/5/6/7/8/9 全部触碰 ⇒ 它是天然的串行化点。

```
Lane A（独立，可与 B 并行）
  Task 1  —— pcs-backend/scripts + tests + .githooks/，不碰 SPEC

Lane B（严格串行，全因 SPEC 争用）
  Task 2 → 3 → 4 → 5 → 6 → 7 → 8
  （若要把 ADR 正文撰写（各 Task 的 Step 1~3）并行化，
    需把所有 SPEC 回写挪到最后统一做 —— 收益小、diff 难读，不建议）

Lane C（最后）
  Task 9 —— 收口，依赖 A+B 全部产物
```

**冲突旗标**：Lane B 内部各 Task 之间**必然**在 SPEC 上冲突，只能串行。
Lane A 与 Lane B 无共享文件，可并行。

---

## 执行后记（2026-10-19，本计划已执行完毕）

9 个 task 全部完成，提交 `8708e29` → `7aa691d`。执行中修正了计划与 SPEC 的若干**事实错误**，
已就地改写本文件与 SPEC；完整决策记录见 ledger
`.superpowers/sdd/PCS-PLAN-P9-PREP/progress.md`（该目录已 gitignore）。

**ADR 编号与计划写的不同**：产出 **ADR-0046~0049**，不是 0042~0045 ——
ADR-0041 正文预留了「0042 = 解冻机制」「0043+ = 后续接口扩展」。

**三处会让验收验错东西的错误**（写下来是因为它们都很安静）：

| 错误 | 真相 | 后果 |
|---|---|---|
| Task 1 Step 8 让探针落在 `alembic/versions/` | `alembic check` 比对 **ORM ↔ 活库**，不读迁移源码 | 加一条未 apply 的迁移 ⇒ 两侧都没那列 ⇒ 报 **✅ 假绿**；且推高 code head 使命中 stale 分支，**看着红过，其实验的不是漂移** |
| Task 2 Step 2 用 `for r in app.routes` 枚举 | 本仓 FastAPI 版本把 `include_router` 包成 `_IncludedRouter` **不展开**，`app.routes` 只有 6 项 | 该步骤是计划自称的「唯一可信来源」，照做产出**空清单**。改用 `app.openapi()["paths"]` |
| ADR-0048 §⑥ 称 `record_hash` 覆盖全部结果表 | 29 张 `*_result(s)` 表里只有 **19 张**有；`sim_*`(8) / `util_results` / `cost_est_results` 没有，`two_phase_results` 有 hash 但无 `updated_at` | 兜底覆盖比声称的小 **11 张表**，P9A 要多做一次迁移决策（ADR-0048「尚未解决」1） |

另两处路径/锚点过期：Task 9 Step 2 的 `docs/Web版开发计划.md` 实际在
`spec/工艺专用综合计算软件需求规格说明书 Web版开发计划.md`；Task 7 Step 5 要同步的
SPEC §2.6「通知渠道假设」在 SPEC 里不存在。

**实测基线（执行后）**：后端 **4643 passed / 77 skipped / 0 failed**（4629 + PP-5 的 14 个）；
两库 `alembic check` 均 exit 0（**各跑一次**）；payload coverage RC=0。

---

## 尚未解决的问题

1. **P9A / P9B 的实施计划尚未编写。** 本计划只覆盖 SPEC §2。ADR-0046~0049 accepted 后，
   P9A（4–6 周）才具备可写代码级计划的前提 —— 那时按本计划同样的格式另写
   `docs/PCS-PLAN-P9A.md`，不要在本文件里追加。
   ⚠️ 写之前先读四份 ADR 各自的「尚未解决」段 —— 那几段就是 P9A 必须先答的问题。

2. **P9-OPEN-003（审计日志导出格式）归属 P9B**，本阶段未处理，SPEC §8 中仍为「已确认」，开工时直接用。

3. ~~**ADR-0046 §② 的存量孤儿清单未产出**~~ —— **执行时已补上归属**：
   ADR-0046 的「尚未解决」段与 SPEC §3.2.2 `P9A-USR-005` 都写明
   「导出 `user_projects` / `audit_logs.created_by` 中无对应 users 行的 uuid5 清单，
   交人工确认，**不删 users 行**（FK CASCADE，删即删授权）」归 P9A。
   **P9A 开工时仍需真正产出这份清单** —— 归属已定，动作未做。

4. **`confirm_recalc` 的 `response_model=dict` 占了 71 基线里的几个，无法区分。**
   Task 2 实测总数 71 与 `BASELINE_BARE_FIELDS` 一致，但该脚本**只报总数、不按端点归因**，
   所以「它算不算在里面」至今未知。建议 P9A 顺带把它显式化（P9B 拿到的是 `object`，
   与 P9A-DLV-010 零裸字段冲突），但这不阻塞 P9A 开工。

5. **pre-commit 框架未安装**（`which pre-commit` 无输出）。本计划刻意沿用仓库既有的
   `.githooks/` + `core.hooksPath` 模式而非引入 pre-commit 框架，与「CI/CD 不做」的用户裁决一致。
   若后续要引入框架，Task 1 的脚本逻辑可原样搬进 hook，本计划不受影响。

6. **SPEC §4.2 的「7 个 mock type 文件改 import 自 ./api」前提矛盾，本阶段刻意不动。**
   SPEC §4.2 自陈该前提不成立（28/31 导出 interface 在 OpenAPI 无对应 schema，字段名与单位
   都不同，如 `p_mpa` ↔ `P_Pa`）。**它不在本计划范围内** —— 处置口径归 `TODOS.md` 的
   **TODO-039 + TODO-041**（前端类型来源唯一性 / MSW 契约冻结，逾期中）。
   在 P9 SPEC §4.2 改这份描述会与那两条产生**第二个真相源**：读者不知以哪份为准，
   两处独立演化必然漂移，且 TODO-039 的「冻结」口径与 §4.2 的「重写」口径可能直接矛盾。
   > 注：审查中曾按「TODO-051」指代此事 —— 该编号在 `TODOS.md` 中**不存在**（现有编号止于
   > TODO-046），mock type 的口径实际在 TODO-039 + TODO-041。
   > ⚠️ 查现有编号别用 `grep "^### TODO-"`：条目混用 `##` 与 `###` 两种标题级别，会漏一半。
   > 用 `grep -oE "^#{2,3} TODO-[0-9]+" TODOS.md | grep -oE "TODO-[0-9]+" | sort -u`。

7. **ADR-0048 §⑥ 的「兜底只覆盖设计参数」是已知取舍，不是遗漏。**
   `record_hash` 不检测 `sign_status` / `approval_step` 等批准状态字段的变化 ——
   那些由状态机事务 + `pg_advisory_xact_lock` 负责。若 P9A 实施时发现签署流程本身
   也需要并发保护（而不只是编辑），**ADR-0048 不覆盖该场景**，需回本 ADR 修订。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 10 | CLEAR | 6 issues (2 阻塞 + 3 建议 + 1 裁决) 全部处置，0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | 无 UI 范围，不适用 |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | 不适用 |

**UNRESOLVED:** 0
**VERDICT:** ENG CLEARED — 2 条阻塞项已修入计划，4 项裁决全部作出，可执行。
**已裁决**：① MFA 路径 B（AD 密码二次输入 + `SIGN_2FA_FALLBACK`）；② mock 会话豁免二次认证（限于登录层，函数本身不豁免）；③ P9-OPEN-002 本版不设邮件服务器，预留 `NotificationChannel` 接口；④ P9-OPEN-004 每日凌晨 / P9-OPEN-006 WebSocket + 降级轮询。

### 本轮审查改了计划的什么（4 处，均由用户裁决）

| # | 问题 | 处置 |
|---|---|---|
| 1 | ADR-0048 §⑤「Redis 挂 → 无锁放行」静默覆盖 user-stated learning `ekris-redis-lock-degradation`，且会让 Redis 挂掉时静默丢用户编辑 | 改为**两层锁**（Redis 体验层 + `record_hash` 兜底层）；§⑤ 重写并显式声明与 learning 的关系；新增 §⑥ 粒度、§⑦ 409 契约 |
| 2 | ADR-0046 §③ 的停用门只挂在 `/auth/login`，`/mock-login` 是独立签发路径（`mock_auth.py:58-68`），无 `tv` claim、不查 users、不写审计 | 裁定 `/mock-login` 走同一 `_issue_tokens()` 路径，差异仅凭据校验方式 |
| 3 | Issue 3 原判「两个 alembic 闸门退出码约定会漂移」—— **前提错误**：`check_migration_idempotency.py` 是静态解析迁移文件，从不跑 alembic | 撤销该判断。改为复用**已存在**的 `scripts/run_gate.py`（cerebrum TODO-050 已立法），只加 `run_capture()` |
| 4 | Task 8 Step 4 混进两件范围外的 SPEC 编辑 | 拆：71/70 → Task 8（PP-M 独立步）；§4.2 mock type → 完全移出，归 TODO-039/041（避免第二个真相源） |

**未采纳的中间方案**：Issue 3 曾按「新增 `scripts/_alembic_gate.py` 共享常量」设计，
后查明收敛点已存在（`run_gate.py` + 其测试 + cerebrum 立法），新建即造第二个真相源。

### 第二轮：专家委员会审阅（2026-10-19）

委员会提出 2 阻塞 + 3 建议 + 1 待裁决。逐条核实后：

| # | 委员会意见 | 核实结果 | 处置 |
|---|---|---|---|
| 必修 1 | ADR-0048 §⑤ 措辞自相矛盾 | **部分成立** —— 非语义矛盾（裁定已作出 + 防未来误释是两件事），但确实给人「裁定可能还没发生」的错觉 | 已合并为「裁定已作出 + 可证伪条件」，并去掉「不得由作者单方面解释」 |
| 必修 2 | Task 1 Step 8 探针可能混入 commit | **成立** —— Step 13 的 `git add -A` 确实是泄漏窗口 | Step 8 加 `test ! -e ... \|\| exit 1` 硬闸；Step 13 加 `git status` 二次拦截 |
| 建议 1 | 「唯一收口」是未验证断言 | **成立且实质性** —— `finalize_calc_record` **不是**唯一写入点 | ADR §⑥ 已更正：列出 6 条旁路，并说明 `updated_at` 分支是 pump/pipe/pipe_net 的**常态**而非边角 |
| 建议 2 | Task 2 Step 4 缺偏差处理规则 | 成立 | 已加「先记录偏差再继续，不得直接改基线数字」 |
| 建议 3 | TODO-047 应改用 TODO-045（编号跳跃） | **不成立** —— TODO-045/046 **已被占用**（`##` 级标题，故 `^###` grep 漏掉） | 驳回，TODO-047 是正确的下一号 |
| 裁决项 | 路径 B 在 mock 下怎么做二次认证 | **成立，是真实开放问题** | Task 7 Step 2 加三选一对照表；Step 4 改为三个问题 |

**驳回建议 3 的证据**：

```
$ grep -n "TODO-045\|TODO-046" TODOS.md
513: ## TODO-045: `StrictColumns` 的数组形式不校验「段间路径」
561: ## TODO-046: 其它表的裸串词表尚未系统排查
```

（注意这两个是 `##` 级标题。委员会很可能用 `^### TODO-` grep 查，因而误判为空闲号。）

**建议 1 更正的实质**：ADR-0048 §⑥ 原本用「唯一收口」论证兜底便宜。
实测 6 条旁路后，论证改为「零迁移 + `updated_at` 带 `onupdate` 必然刷新」——
结论不变，但 pump/pipe/pipe_net 三类记录的冲突检测**依赖 `updated_at` 而非 hash**，
这个事实必须写明，否则实施者会以为 hash 覆盖全部结果表。

> **执行时又发现更正的一半（2026-10-19）**：不仅「唯一收口」错，「全部覆盖」也错 ——
> 实测 29 张 `*_result(s)` 表里只有 **19 张**有 `record_hash`。见 ADR-0048 §⑥ 覆盖表。
> 两处断言各错一半，说明写 ADR 时的数量断言都得逐表验，不能从 mixin 结构推。

### 计划规模变化

9 个 task。行数随 §⑥ 的旁路表与 Task 7 的 mock 对照表增长。
