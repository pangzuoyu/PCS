#!/usr/bin/env python
"""**联网**核对 `component_cas.py` 的 CAS 号（TODO-196 · bug-2197）。

## 为什么有这个脚本

`app/services/component_cas.py` 里 10 条 DMC 装置专用组分的 CAS 号
是 2026-11-19 **凭记忆**填的 ⇒ ⇒ 2026-11-23 用公开源逐条核对
⇒ ⇒ **查出 3 条错的**（`ISO_BUTANE` / `DIPROPYLENE_GLYCOL` / `TRIPROPYLENE_GLYCOL`
—— 前两条**校验位就不对**，第三条校验位过但**没有源**把它指向本组分）
⇒ ⇒ 错号的实际后果 = **组成被静默作废**（`mw_by_cas` 取不到 MW
⇒ ⇒ `composition_json = None`）⇒ ⇒ 那几条流**闪蒸算不了**。

CAS 号是**公开登记号** ⇒ ⇒ **可以核** ⇒ ⇒ 本脚本就是那个「核」的工具。

## 三段核对

| # | 关 | 手段 | 要网络？ |
|---|---|---|---|
| ① | **格式关** | CAS 末位是校验位 ⇒ 算术自证 | ❌ |
| ② | **存在关** | `chemicals` 离线库能取到 MW ⇒ 这个号指向真实物质 | ❌ |
| ③ | **身份关** | PubChem 双向查（名→CAS / CAS→名） | ✅ |

⇒ ⇒ ①②③ 全过 ⇒ ⇒ 这个 CAS 号**大概率**没抄错
⇒ ⇒ ①②③ 全过**也不等于**工艺室签字（那是 TODO-196 剩下的部分）。

## 权威源（2026-11-23 实测）

- **PubChem**（NIH）—— PUG-REST，公开可编程访问；**用得上的只有 8/10 条**
  （三丙二醇 PubChem **没有独立记录** ⇒ ⇒ 它的号用 OECD SIDS / NOAA CAMEO /
  Sigma-Aldrich 交叉确认）
- **CAS Common Chemistry**（cas.org 官方）—— ⚠️ **自 2025 起要 API key**
  ⇒ ⇒ 匿名调用返回 **401** ⇒ ⇒ 本脚本**不**依赖它
  ⇒ ⇒ ⚠️ **别把 401 当成「查不到」**（那是两件事）
- **OECD SIDS / HPV Chemicals** · **NOAA CAMEO** —— 工业物质的事实源

## 用法

```bash
cd pcs-backend && uv run python scripts/verify_component_cas.py        # 人读
cd pcs-backend && uv run python scripts/verify_component_cas.py --json # 机读
```

退出码：**0 = 全过** · **1 = 有不过**（⇒ ⇒ 别再凭记忆填 CAS）。

⚠️ **本脚本不是 pytest 用例**（CI 无外网 ⇒ 会假红）⇒ ⇒
离线的①②两关在 `tests/services/test_component_cas.py`（默认车道跑）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

#: (规范名 · PRO/II 缩写 · 仓库里的 CAS · 用于查 PubChem 的物质名)
#:
#: ⚠️ 这一列是**手抄**的 ⇒ ⇒ 本脚本的**首要价值**就是发现手抄错误
#: ⇒ ⇒ 名字写错 ⇒ ⇒ 查到的就不是同一条物质 ⇒ ⇒ 「反向查不到」⇒ ⇒ 报错。
ENTRIES: tuple[tuple[str, str, str, str], ...] = (
    ("PROPYLENE_OXIDE", "PO", "75-56-9", "propylene oxide"),
    ("PROPYLENE_CARBONATE", "PROPCARB", "108-32-7", "propylene carbonate"),
    ("DIMETHYL_CARBONATE", "DMCARB", "616-38-6", "dimethyl carbonate"),
    ("PROPYLENE_GLYCOL", "12PG", "57-55-6", "1,2-propanediol"),
    ("DIPROPYLENE_GLYCOL", "DIPRPGLY", "25265-71-8", "dipropylene glycol"),
    ("TRIPROPYLENE_GLYCOL", "TPG", "24800-44-0", "tripropylene glycol"),
    ("ACRYLIC_ACID", "AA", "79-10-7", "acrylic acid"),
    ("O_XYLENE", "OXYLENE", "95-47-6", "1,2-dimethylbenzene"),
    ("METHOXYPROPANOL", "MOXYPROH", "107-98-2", "1-methoxy-2-propanol"),
    ("PROPIONALDEHYDE", "PROPALD", "123-38-6", "propanal"),
)

#: 分子量相对误差上限（1e-3）
MW_RTOL = 1e-3

_CAS_RE = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")


def check_digit_ok(cas: str) -> bool:
    """CAS 校验位 —— 末位是校验位，其余位**自右往左**加权求和 mod 10。"""
    m = _CAS_RE.match(cas)
    if not m:
        return False
    body = m.group(1) + m.group(2)
    total = sum(int(d) * i for i, d in enumerate(reversed(body), start=1))
    return total % 10 == int(m.group(3))


def local_mw(cas: str) -> float | None:
    """`chemicals` 离线库取 MW（**不打网络** ⇒ `autoload=False`）。"""
    try:
        from chemicals import MW

        value = MW(cas, autoload=False)
    except Exception:  # noqa: BLE001 —— chemicals 对未知 CAS 会抛多种异常
        return None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class Row:
    canonical: str
    abbr: str
    cas: str
    query: str
    cid: int | None = None
    title: str = ""
    formula: str = ""
    pubchem_mw: float | None = None
    local_mw: float | None = None
    forward_ok: bool = False
    reverse_ok: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.forward_ok and self.reverse_ok


def _get_json(url: str, *, retries: int = 3) -> dict:
    """GET + JSON ⇒ ⇒ 失败重试（PubChem 限流 5 req/s ⇒ ⇒ 退避）。

    ⚠️ **不吞异常**：查不到就抛 ⇒ ⇒ 呼叫方把「查不到」记成 error
    ⇒ ⇒ **绝不**把「网络失败」当成「CAS 不对」（两者必须能分开）。
    """
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pcs-verify-cas/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            last = exc
        except Exception as exc:  # noqa: BLE001 —— 网络异常形态多
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET 失败: {url} ⇒ {last}")


def _cids_by_name(name: str) -> list[int]:
    url = f"{PUG}/compound/name/{urllib.parse.quote(name)}/cids/JSON"
    data = _get_json(url)
    return list(data.get("IdentifierList", {}).get("CID", []))


def _cids_by_cas(cas: str) -> list[int]:
    url = f"{PUG}/compound/name/{urllib.parse.quote(cas)}/cids/JSON"
    data = _get_json(url)
    return list(data.get("IdentifierList", {}).get("CID", []))


def _synonyms(cid: int) -> list[str]:
    url = f"{PUG}/compound/cid/{cid}/synonyms/JSON"
    data = _get_json(url)
    return list(data.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", []))


def _props(cid: int) -> dict:
    url = f"{PUG}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
    data = _get_json(url)
    return data.get("PropertyTable", {}).get("Properties", [{}])[0]


def verify_online(canonical: str, abbr: str, cas: str, query: str) -> Row:
    """③ 身份关：PubChem 双向查。

    ⇒ ⇒ 「反向查不到」**不等于**「CAS 错」⇒ ⇒ 可能只是 PubChem 没收这条物质
    （例：三丙二醇 PubChem 没有独立记录）⇒ ⇒ 分开记：
      - `forward_ok` + `reverse_ok` ⇒ ⇒ 两向都对
      - `notes` 里记「PubChem 无独立记录 ⇒ 用 OECD SIDS / CAMEO 交叉确认」
    """
    row = Row(canonical=canonical, abbr=abbr, cas=cas, query=query)
    try:
        name_cids = _cids_by_name(query)
        if not name_cids:
            row.notes.append(f"PubChem 按名 '{query}' 查不到")
            return row
        row.cid = name_cids[0]
        syns = _synonyms(row.cid)
        flat = {s.replace("-", "") for s in syns}
        row.forward_ok = cas in syns or cas.replace("-", "") in flat

        props = _props(row.cid)
        row.title = props.get("Title", "")
        row.formula = props.get("MolecularFormula", "")
        try:
            row.pubchem_mw = float(props.get("MolecularWeight"))
        except (TypeError, ValueError):
            row.pubchem_mw = None

        try:
            cas_cids = _cids_by_cas(cas)
            row.reverse_ok = bool(cas_cids)
            if not row.reverse_ok:
                row.notes.append("PubChem 反查该 CAS 无记录")
        except urllib.error.HTTPError:
            row.notes.append("PubChem 反查该 CAS 无记录（404）")

        # ⚠️ PubChem 的记录**可能是混合物**（例：二丙二醇那条是 2:1 混合物记录
        # ⇒ ⇒ 分子量是纯物质的 2 倍）⇒ ⇒ 比值不是 1 时**只记不判**
        row.local_mw = local_mw(cas)
        if row.pubchem_mw and row.local_mw:
            ratio = row.pubchem_mw / row.local_mw
            if abs(ratio - 1) <= MW_RTOL:
                pass  # 一致
            elif abs(ratio - round(ratio)) <= 0.01 * round(ratio) and round(ratio) > 1:
                row.notes.append(f"PubChem 记录是 {round(ratio)}× 混合物记录（分子量 {row.pubchem_mw}）")
            else:
                row.notes.append(f"⚠️ 分子量对不上：PubChem {row.pubchem_mw} vs 本地 {row.local_mw}")
    except urllib.error.HTTPError as exc:
        row.notes.append(f"PubChem HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        row.notes.append(str(exc))
    return row


def audit_offline() -> list[tuple[str, str, str]]:
    """①② 全表体检（零网络）⇒ ⇒ 返回 (规范名, CAS, 问题) 三元组。"""
    from app.services.component_cas import CAS_BY_COMPONENT

    problems: list[tuple[str, str, str]] = []
    for canonical, cas in sorted(CAS_BY_COMPONENT.items()):
        if not check_digit_ok(cas):
            problems.append((canonical, cas, "CAS 校验位不对 ⇒ ⇒ 不是 CAS 号"))
            continue
        if local_mw(cas) is None:
            problems.append((canonical, cas, "chemicals 离线库取不到 MW ⇒ ⇒ 这个号不指向真实登记物质"))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--offline-only", action="store_true", help="只跑离线两关（无网络也可用）")
    args = ap.parse_args()

    problems = audit_offline()
    print(f"① ② 离线体检（全表）⇒ ⇒ {'✅ 全过' if not problems else '❌ ' + str(len(problems)) + ' 条不过'}")
    for canonical, cas, why in problems:
        print(f"   ❌ {canonical:26} {cas:14} {why}")

    rows: list[Row] = []
    if not args.offline_only:
        head = f"{'规范名':<24}{'缩写':<10}{'CAS':<14}{'正向':<6}{'反向':<6}备注"
        print()
        print(head)
        print("-" * len(head))
        for canonical, abbr, cas, query in ENTRIES:
            row = verify_online(canonical, abbr, cas, query)
            rows.append(row)
            time.sleep(0.25)  # ⇒ 别超 PubChem 的 5 req/s
            note = " · ".join(row.notes) or f"{row.formula} · {row.title[:30]}"
            print(
                f"{row.canonical:<24}{row.abbr:<10}{row.cas:<14}"
                f"{'✅' if row.forward_ok else '❌':<6}"
                f"{'✅' if row.reverse_ok else '❌':<6}{note}"
            )
        bad = [row for row in rows if not row.ok]
        print()
        print(f"③ PubChem 双向 ⇒ ⇒ {len(rows) - len(bad)}/{len(rows)} 条双向命中"
              + ("" if not bad else f" · ⚠️ 未双向命中: {[r.canonical for r in bad]}"))

    if args.json:
        print(json.dumps(
            {
                "offline_problems": problems,
                "online": [row.__dict__ for row in rows],
            },
            ensure_ascii=False,
            indent=2,
        ))

    return 0 if not problems and all(row.ok for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
