"""跑一条闸门命令并报告**它自己**的退出码（TODO-050）。

## 为什么需要它

`cmd | tail -10; echo "EXIT=$?"` 里的 `$?` 是 **`tail` 的**退出码，
不是 `cmd` 的。实测踩过：`check_openapi_payload_coverage.py` 实际 exit 1
（裸字段 71 → 73，是真回归），因为接了管道，读到 `EXIT=0` 就报告「通过」。

这是「绿灯测的不是出问题那层」的一个新变种 —— 错在**观测退出码的那一层**。
本会话已因此至少两次把红的守门报成绿的。

`set -o pipefail` 能解决，但只在**写脚本**时；agent 日常是在交互 shell 里
敲一次性命令，写脚本反而更啰嗦。所以这里给一个包装：

    uv run python scripts/run_gate.py --tail 10 -- \\
        uv run python scripts/check_openapi_payload_coverage.py

它打印命令的最后 N 行，然后打印 `EXIT=<该命令自己的码>`，并以同一个码退出。

## 陷阱

**不要**拿本脚本的输出去接管道再 `$?` —— 那就又回到原问题了。
要判断成败，直接看 `EXIT=` 那一行，或看本脚本自身的退出码。
"""
from __future__ import annotations

import argparse
import subprocess
import sys


def run(argv: list[str], *, tail: int, cwd: str | None = None) -> int:
    """跑 `argv` 并返回**它自己**的退出码。"""
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=1800,
        )
    except FileNotFoundError:
        print(f"命令不存在：{argv[0]}", file=sys.stderr)
        return 127
    except subprocess.TimeoutExpired:
        print(f"命令超时（>1800s）：{' '.join(argv)}", file=sys.stderr)
        return 124

    out = (proc.stdout or "") + (proc.stderr or "")
    lines = out.splitlines()
    if tail > 0 and len(lines) > tail:
        lines = [f"...（略去前 {len(lines) - tail} 行）"] + lines[-tail:]
    print("\n".join(lines))
    print(f"\nEXIT={proc.returncode}  ← {argv[0]} 自己的退出码")
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tail", type=int, default=15,
                    help="打印最后几行（0 = 全打印）")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="要跑的命令（用 -- 与本脚本隔开）")
    args = ap.parse_args(argv)

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        ap.error("没给命令")

    return run(cmd, tail=args.tail, cwd=args.cwd)


if __name__ == "__main__":
    raise SystemExit(main())
