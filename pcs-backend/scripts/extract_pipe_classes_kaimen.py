"""kaimen SPC-0004 管道等级种子重生成工具（P2-OPEN-001 第二数据源）。

用法（IFC 升版后重跑）：
  1. libreoffice --headless --convert-to xlsx "Attachment-1 Pipe service index.xls" --outdir /tmp/pipedoc
     并 cp SPC-0004 PDF 为 /tmp/pipedoc/spc.pdf（文件名含空格时 pdftotext/libreoffice 需短名）
  2. python3 scripts/extract_pipe_classes_kaimen.py   # 在仓库根，产物写 app/seeds/
数据源（NAS）：
  .../kaimen project/Construction/07_Turn-Over(woking)/IFC Drawings/PI/PI SPC/
    20048A-0000-MD-SPC-0004_C1 Pipe Class.pdf（215 页）
    Pipe Service Index/20048A-0000-MD-LST-0001_C1 Attachment-1 Pipe service index.xls
"""

import os
OUT = os.environ.get('PCS_SEEDS', 'app/seeds/')

"""kaimen SPC-0004 C1 管道等级批量提取：TOC→逐级页→头部KV+管子行+夹套表2；并 PSI 包络。"""
import json, re, subprocess
from collections import defaultdict

def pdf_pages(a, b):
    out = subprocess.run(["pdftotext", "-layout", "-f", str(a), "-l", str(b), "spc.pdf", "-"],
                         capture_output=True, text=True).stdout
    return out

# ---- 1. TOC ----
toc_txt = pdf_pages(1, 3)
entries = []
for m in re.finditer(r"Piping Class:\s*(.+?)\s*\.{3,}\s*(\d+)", toc_txt):
    raw, page = m.group(1).strip(), int(m.group(2))
    entries.append((raw, page))
print("TOC entries:", len(entries))

NPS2DN = {"½":15,"3/4":20,"¾":20,"1":25,"1¼":32,"1 1/4":32,"1½":40,"1 1/2":40,"2":50,
 "2½":65,"2 1/2":65,"3":80,"4":100,"6":150,"8":200,"10":250,"12":300,"14":350,"16":400,
 "18":450,"20":500,"24":600,"28":700,"30":750,"32":800,"34":850,"36":900,"40":1000,
 "44":1100,"48":1200,"52":1300,"56":1400,"60":1500}
def nps_token(t):
    t = t.strip().replace("“","").replace("”","").replace("\"","")
    return NPS2DN.get(t)
def nps_range(s):
    s = s.replace("–","-").replace("“","").replace("”","").replace("\"","").strip()
    parts = [p.strip() for p in s.split("-") if p.strip()]
    if len(parts)==1:
        return (nps_token(parts[0]),)*2
    if len(parts)==2:
        a,b = nps_token(parts[0]), nps_token(parts[1])
        return (a,b)
    return (None,None)

MAT = re.compile(r"^(API\s*5L|A\s?\d{3}|S\d{4,5}|B66|20#|06Cr\w+|Q\d{3}|GB/?T?\d*|SH/?T?\d*|HG/?T?\d*|HDPE|UPVC|CPVC|PP|PVC|PE\d|304|316|A312|A358|B564)", re.I)
THK = re.compile(r"^(SCH|STD-?|XS$|XXS|\d+(\.\d+)?\s?mm$|SN\d+(\.\d+)?|CL\s?\d{3,4}|S\d\w*|\d+(\.\d+)?\s?in)$", re.I)
END = re.compile(r"^(BE|BW|SW|PE|TH|TOE|PLE|PLE\s?x|RSE|PN\d+|CL\s?\d{3,4}|SW/BN)", re.I)

def parse_section(lines):
    """一段（单个 Piping Class 标题之后）→ dict"""
    d = {}
    kv_pat = [(r"Use in line class:|USE IN Line class:", "line_classes"),
              (r"Fluid Service", "fluid_service"),
              (r"Design Codes:", "design_code"),
              (r"Rating:", "rating"),
              (r"Basic Material:", "basic_material"),
              (r"Corrosion\s+Allowance:?", "ca"),
              (r"Design Condition", "design_cond")]
    txt = "\n".join(lines)
    for pat, key in kv_pat:
        m = re.search(pat + r"\s*(.+)", txt)
        if m and m.group(1): d[key] = m.group(1).strip()[:80]
    # Design Condition：标签行与 core/Jacket 值行错位（值可能在上行），取上下文窗口
    for i, ln in enumerate(lines):
        if re.match(r"\s*Design Condition\s*$", ln):
            d["design_cond"] = " ".join(x.strip() for x in lines[max(0,i-1):i+3] if x.strip())[:160]
            break
    # 管子行：在 管子/PIPE 后、第一个 弯头/ELBOW/异径管 前
    pipes, in_pipe = [], False
    STOP = re.compile(r"(弯头|三通|异径管|管帽|管接头|法兰|垫片|螺柱|阀门|ELBOW|TEE|REDUCER|CAP|COUPLING|FLANGE|GASKET|STUD|VALVE|短管|NIPPLE|Swages|活接头|UNION)")
    PRODUCE = {"SMLS","SAWL,","SEAM,","SEAM","WELDED","LR-SMLS","LR-WELDED","SR-SMLS","SR-WELDED","ONE","LONGITUDINAL","Ej=0.95","L=100mm","L=300mm"}
    ENDS = {"BE","BW","SW","PE","TH","TOE","PLE","x","RSE","POEX","SW/TH"}
    NPSLIKE = re.compile(r"^[½¾0-9]")
    for ln in lines:
        first = ln.split()[0] if ln.split() else ""
        if first in ("管子", "卡套管"):
            in_pipe = True; continue
        if first == "PIPE" and not in_pipe:
            in_pipe = True; continue
        if not in_pipe:
            continue
        if first and STOP.search(first):
            break
        toks = ln.split()
        if not toks: continue
        mat_i = next((i for i,t in enumerate(toks) if MAT.match(t)), None)
        if mat_i is None: continue
        # 材料串：mat_i 起到 produce/end/thk 边界
        j = mat_i + 1
        mat_toks = [toks[mat_i]]
        while j < len(toks):
            t = toks[j]
            if t in PRODUCE or t in ENDS or THK.match(t) or NPSLIKE.match(t):
                break
            mat_toks.append(t); j += 1
        # thk：右侧最后一个匹配
        thk = ""
        for ti, t in reversed(list(enumerate(toks))):
            if THK.match(t):
                thk = t
                if t == "SCH" and ti + 1 < len(toks) and re.match(r"^\d+$", toks[ti+1]):
                    thk = "SCH " + toks[ti+1]
                elif t == "STD" and ti + 1 < len(toks) and toks[ti+1] == "-":
                    thk = "STD-"
                break
        # nps：mat_i 之前去掉 produce 词
        pre = [t for t in toks[:mat_i] if t not in PRODUCE and t not in ENDS]
        rng = " ".join(pre)
        a, b = nps_range(rng) if rng else (None, None)
        std = ""
        for t in toks + [x for l in lines[i:i+2] for x in l.split()] if False else toks:
            if t.upper().startswith(("ASME","GB/","SH/","HG/","MSS","B36")): std = t
        pipes.append({"nps": rng, "dn": [a,b], "material": " ".join(mat_toks), "thk": thk, "std": std})
    d["pipes"] = pipes
    # 夹套表2：Pipe size (DN) 行 + Pipe Thickness sa (mm) 行
    jacket = {}
    rows = {}
    for i, ln in enumerate(lines):
        if "dn" not in rows and re.match(r"\s*Pipe size\s*\(DN\)", ln):
            rows["dn"] = [int(x) for x in re.findall(r"\b\d{2,4}\b", ln.split(")")[1] if ")" in ln else ln)]
        if "thk" not in rows and re.search(r"Pipe Thickness\s*$", ln) and i + 1 < len(lines):
            rows["thk"] = re.findall(r"\d+(?:\.\d+)?", lines[i+1])
        elif re.search(r"Pipe Thickness\s*sa\s*\(mm\)", ln):
            rows["thk"] = re.findall(r"\d+(?:\.\d+)?", ln.split(")")[1] if ")" in ln else ln)
    if "dn" in rows and "thk" in rows and len(rows["dn"])==len(rows["thk"]) and rows["dn"]:
        jacket = dict(zip([str(x) for x in rows["dn"]], [t+"mm" for t in rows["thk"]]))
    d["jacket_core_walls"] = jacket
    return d

# ---- 2. 逐级解析 ----
sections = {}
for idx, (raw, page) in enumerate(entries):
    nxt = entries[idx+1][1] if idx+1 < len(entries) else min(page+8, 215)
    body = pdf_pages(page, nxt-1 if nxt-1>page else page)
    # 按 Piping Class: 标题切段（夹套组合页含 core/jacket 两套表？——实测一页一组合）
    seg_lines = body.splitlines()
    info = parse_section(seg_lines)
    # class_id：取主码（去掉括注）
    code = re.split(r"\s*\(", raw)[0].strip()
    note = raw[len(code):].strip(" ()")
    info["code"] = code; info["note"] = note; info["page"] = page
    info["combo_raw"] = raw
    sections[code] = info

print("parsed sections:", len(sections))
miss = [c for c,i in sections.items() if not i["pipes"] and not i["jacket_core_walls"]]
print("no-pipe sections:", miss)
json.dump(sections, open("kaimen_sections.json","w"), ensure_ascii=False, indent=1)
for c in list(sections)[:3]:
    s = sections[c]
    print(c, "|", s.get("basic_material"), "| CA:", s.get("ca"), "| pipes:", len(s["pipes"]), s["pipes"][:2])


# ===== 组装 =====
"""合并 kaimen_sections.json（PDF 明细）+ PSI（xls 包络）→ 种子 JSON+XLSX。"""
import json, re
from collections import defaultdict
from openpyxl import load_workbook

secs = json.load(open('kaimen_sections.json'))

# PSI 包络（重跑一遍精简版）
wb = load_workbook('psi.xlsx', data_only=True)
ws = wb['PSI']
def val(r, c):
    v = ws.cell(r, c).value
    return str(v).strip() if v is not None and str(v).strip() else None
psi = defaultdict(lambda: {"T": [], "P": [], "fluids": set(), "lines": set()})
lc = None; fl = None
for r in range(8, ws.max_row + 1):
    if val(r, 1): lc = val(r, 1)
    fl = val(r, 4) or fl
    code = val(r, 20)
    if not code: continue
    key = re.split(r'[\s(]', code)[0]
    d = psi[key]
    t_raw = re.sub(r'\[\d+\]', '', val(r, 11) or '')
    p_raw = re.sub(r'\[\d+\]', '', val(r, 16) or '')
    if 'AMB' in t_raw.upper(): d["T"].append(38.0)
    for m in re.findall(r'-?\d+(?:\.\d+)?', t_raw):
        d["T"].append(float(m))
    if 'ATM' in p_raw.upper() or 'GRAVITY' in p_raw.upper():
        d["P"].append(0.0)
    for m in re.findall(r'-?\d+(?:\.\d+)?', p_raw):
        d["P"].append(float(m))
    if fl: d["fluids"].add(fl.split('\n')[0].split()[0] if fl.split('\n')[0].split() else '')
    if lc: d["lines"].add(lc)

def env(d, jacket=False):
    ts = d["T"] or ([38.0] if not d["P"] else [])
    ps = d["P"]
    tmax = max(ts) if ts else 38.0
    pmax = max([p for p in ps if p >= 0], default=0.0)
    if pmax == 0: pmax = 0.1   # 真空/常压/重力占位
    return tmax, pmax / 10.0   # bar→MPa

FACE = {"RF": "RF", "RS": "RS", "RT": "RT", "FF": "FF", "B1": "BW", "E": "BW", "X": "SE", "U": "SW"}
RATING = {"150": "150Lb", "300": "300Lb", "600": "600Lb", "1500": "1500Lb",
          "100": "100bar", "63": "63bar", "40": "40bar", "25": "25bar", "10": "10bar"}

def ca_float(ca):
    m = re.search(r'(\d+(?:\.\d+)?)', ca or '')
    return float(m.group(1)) if m else 0.0

DNALL = [15,20,25,32,40,50,65,80,100,125,150,200,250,300,350,400,450,500,600,700,750,800,850,900,1000,1100,1200,1300,1400,1500]
def expand(a, b, thk):
    out = {}
    if a and b and thk:
        for dn in DNALL:
            if a <= dn <= b: out[str(dn)] = thk
    elif a and thk:
        out[str(a)] = thk
    return out

seed = []
seen = set()
for code, s in secs.items():
    if code in seen: continue
    seen.add(code)
    d = psi.get(code, psi.get(code.split('(')[0], {"T": [], "P": [], "fluids": set(), "lines": set()}))
    tmax, pmax = env(d)
    # 夹套：design_cond 直接给（如 core 16 bar @ 350 ℃）
    dc = s.get("design_cond", "")
    dc_pairs = [(int(a)/10.0, float(b)) for a, b in
                re.findall(r'(\d+)\s*bar\s*@\s*(\d+)', dc)]
    if dc_pairs:
        pmax = max(p for p, _ in dc_pairs); tmax = max(t for _, t in dc_pairs)
    sch, dnlo, dnhi = {}, None, None
    for p in s["pipes"]:
        a, b = p["dn"]
        if a is None or b is None:   # DN/ID 直给（塑料类）
            mm = re.findall(r'\d+', p["nps"] or '')
            if len(mm) >= 2: a, b = int(mm[0]), int(mm[1])
        sch.update(expand(a, b, p["thk"]))
        for x in (a, b):
            if x: dnlo = x if dnlo is None else min(dnlo, x); dnhi = x if dnhi is None else max(dnhi, x)
    if s["jacket_core_walls"]:
        sch.update(s["jacket_core_walls"])
        ks = [int(k) for k in s["jacket_core_walls"]]
        dnlo = min(ks) if dnlo is None else dnlo; dnhi = max(ks) if dnhi is None else dnhi
    if dnlo is None: dnlo, dnhi = 15, 100
    mats = [p["material"] for p in s["pipes"] if p["material"]]
    mat0 = mats[0] if mats else (s.get("basic_material") or "")
    rating = RATING.get(re.match(r'(\d+)', code).group(1), "")
    face = next((v for k, v in FACE.items() if code.endswith(k)), "")
    flange = f"{rating}/{face}" if rating and face else (rating or "N/A")
    fluids = sorted(f for f in d["fluids"] if f)[:8]
    note = "; ".join(x for x in [
        s.get("note") or "", s.get("design_code") or "",
        f"line class {','.join(sorted(d['lines'])[:6])}" if d["lines"] else "",
        "夹套组合，组合表见 SPC-0004 p%d" % s["page"] if "/" in s.get("combo_raw", "") else "",
    ] if x)
    seed.append(dict(
        class_id=code[:20], class_name=f"{code} {s.get('basic_material','')}"[:200],
        material_standard=mat0[:100] or "N/A",
        corrosion_allowance=ca_float(s.get("ca")),
        design_pressure=round(pmax, 3), design_temperature=tmax,
        fluid_service=",".join(fluids)[:100] or None,
        dn_series_json={"min": dnlo, "max": dnhi},
        sch_series_json=sch, flange_class=flange[:20] or "N/A",
        fitting_type="BW",
        branch_table_json={"design_code": s.get("design_code"), "source": "20048A-SPC-0004-C1", "page": s["page"]},
        note=note[:200]))

# PSI-only 码（TOC 没有：S01D* 特殊 + 夹套伴管码）
psi_only = [k for k in psi if k not in seen and not k.startswith(tuple(seen))]
for k in psi_only:
    d = psi[k]
    tmax, pmax = env(d)
    seed.append(dict(
        class_id=k[:20], class_name=f"{k}（PSI 索引级，明细未在 SPC TOC）"[:200],
        material_standard="N/A", corrosion_allowance=0.0,
        design_pressure=round(pmax, 3), design_temperature=tmax,
        fluid_service=",".join(sorted(f for f in d["fluids"] if f)[:8])[:100] or None,
        dn_series_json={"min": 15, "max": 100}, sch_series_json={},
        flange_class="N/A", fitting_type=None,
        branch_table_json={"source": "PSI Attachment-1"},
        note=f"仅 PSI 出现；line class {','.join(sorted(d['lines'])[:6])}"[:200]))

print(f"seed entries: {len(seed)} (TOC {len(seen)} + PSI-only {len(seed)-len(seen)})")
meta = {
  "source": "INEOS Styrolution Kaimen 60万吨/年 ABS 项目 IFC：20048A-0000-MD-SPC-0004_C1 Pipe Class（215页）+ LST-0001_C1 Attachment-1 Pipe Service Index",
  "source_path": "/media/pangzy/F8A6CB1CA6CAD9F01/nas/work/project/kaimen project/Construction/07_Turn-Over(woking)/IFC Drawings/PI/PI SPC/",
  "project_no": "LCC2012F1048A / 20048A", "version": "SPC-0004-C1",
  "design_envelope": "PSI 行级索引取各等级 max(T)/max(P)；真空/常压/重力 design_pressure 取 0.1MPa 占位",
  "extracted": "2026-09-05",
}
json.dump({"meta": meta, "pipe_classes": seed}, open(OUT + 'pipe_classes_kaimen_20048a.json', 'w'), ensure_ascii=False, indent=1)

from openpyxl import Workbook
HEADERS = ["class_id", "class_name", "material_standard", "corrosion_allowance",
           "design_pressure", "design_temperature", "dn_min", "dn_max",
           "sch_series(JSON)", "flange_class", "source", "version"]
w2 = Workbook(); sh = w2.active; sh.title = "pipe_classes"
sh.append(HEADERS)
for pc in seed:
    sh.append([pc["class_id"], pc["class_name"], pc["material_standard"],
               pc["corrosion_allowance"], pc["design_pressure"], pc["design_temperature"],
               pc["dn_series_json"]["min"], pc["dn_series_json"]["max"],
               json.dumps(pc["sch_series_json"], ensure_ascii=False),
               pc["flange_class"], "PROJECT", "SPC-0004-C1"])
w2.save(OUT + 'pipe_classes_kaimen_20048a.xlsx')
print("xlsx rows:", len(seed))
for pc in seed[:4]: print(pc["class_id"], pc["flange_class"], pc["design_temperature"], pc["design_pressure"], len(pc["sch_series_json"]))
