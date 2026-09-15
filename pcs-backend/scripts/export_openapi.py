#!/usr/bin/env python3
"""导出 OpenAPI 3.1 spec 到 docs/openapi.json（不启 uvicorn，直接调 app.openapi）。

CI / 本地开发统一入口。前端 scripts/gen-api-types.sh 读此文件。

用法：
    cd pcs-backend
    uv run python scripts/export_openapi.py

或：
    python scripts/export_openapi.py --output ../docs/openapi.json
"""
import argparse
import json
import sys
from pathlib import Path

# 把 pcs-backend 加入 sys.path，让 `from app.main import app` 能解析
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def export(output: Path) -> None:
    # 延迟 import 避免无 deps 环境直接崩
    from app.main import app

    spec = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding='utf-8')
    paths = len(spec.get('paths', {}))
    components = len(spec.get('components', {}).get('schemas', {}))
    print(f'OK openapi.json: {paths} paths, {components} schemas ({output})')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path(__file__).parent.parent / 'docs' / 'openapi.json',
        help='output path (default: pcs-backend/docs/openapi.json)',
    )
    args = parser.parse_args()
    export(args.output)
    return 0


if __name__ == '__main__':
    sys.exit(main())