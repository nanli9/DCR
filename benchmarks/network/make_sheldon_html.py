#!/usr/bin/env python3
"""Render docs/07_17_report/ into a single self-contained HTML page.

Presentation-facing (shown directly in the meeting): one-way baseline -> the
native two-way constraint (formulas + schematic) -> why a contact network
falls out -> the corner-force / ON-OFF evidence. Concepts are drawn as inline
SVG schematics in the page palette, so the file needs no external assets.

Embeds the two PNG figures as base64 data-URIs and data-drives every table
from contact_forces.json, so the page is one portable file (email it, open
anywhere). Styling mirrors two_band_coupling.html (dark cards). Doc tooling
only — no solver code touched.

Run: .venv/bin/python benchmarks/network/make_sheldon_html.py
"""
from __future__ import annotations

import base64
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(HERE))
DIR = os.path.join(_ROOT, "docs", "07_17_report")


def _b64(name):
    with open(os.path.join(DIR, name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


CSS = """
  :root{--bg:#0e1014;--panel:#161922;--panel2:#1b1f2a;--line:#272c38;--ink:#e7eaf0;
    --muted:#9aa1ad;--green:#34d399;--orange:#fb923c;--red:#e0635a;--accent:#7aa2ff;
    --yellow:#f5c451;}
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;line-height:1.5}
  .wrap{max-width:1040px;margin:0 auto;padding:34px 22px 70px}
  header h1{font-size:28px;margin:0 0 6px;letter-spacing:-.02em}
  header .sub{color:var(--muted);font-size:15.5px;margin:0 0 4px}
  header .by{color:var(--accent);font-size:12.5px;margin-top:10px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:22px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
  .card.full{grid-column:1/-1}
  .card h3{margin:0 0 10px;font-size:16px;letter-spacing:-.01em}
  .card p{margin:0 0 10px;color:#d3d8e1;font-size:14.5px}
  .card p.small{color:var(--muted);font-size:13px}
  .eq{background:#0c0f15;border:1px solid var(--line);border-radius:9px;padding:11px 13px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px;color:#e7eaf0;
    margin:8px 0;overflow-x:auto;white-space:pre;line-height:1.7}
  .eq .g{color:var(--green)}.eq .o{color:var(--orange)}.eq .m{color:var(--muted)}
  .eq .a{color:var(--accent)}.eq .y{color:var(--yellow)}
  .eq .hl{background:rgba(245,196,81,.14);border-radius:3px;padding:1px 3px;
    box-shadow:inset 0 0 0 1px rgba(245,196,81,.3)}
  .diag{background:#0c0f15;border:1px solid var(--line);border-radius:9px;
    padding:10px 12px 6px;margin:10px 0}
  .diag svg{display:block;width:100%;height:auto}
  table{width:100%;border-collapse:collapse;margin-top:6px;font-size:13.5px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
  td.k{color:var(--ink);font-weight:600;white-space:nowrap}
  td.num{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right;white-space:nowrap}
  .tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;
    border:1px solid var(--line);color:var(--muted);margin-left:6px}
  .tag.good{color:var(--green);border-color:rgba(52,211,153,.4)}
  .tag.warn{color:var(--yellow);border-color:rgba(245,196,81,.4)}
  .pos{color:var(--green)}
  .fig{margin:14px 0 4px;position:relative}
  .fig img{width:100%;display:block;border:1px solid var(--line);border-radius:10px;background:#0c0f15}
  .pin{position:absolute;width:26px;height:26px;border-radius:50%;background:#0e1014;
    border:2px solid var(--green);color:var(--green);font-weight:700;font-size:13.5px;
    display:flex;align-items:center;justify-content:center;transform:translate(-50%,-50%);
    box-shadow:0 0 0 4px rgba(52,211,153,.18);pointer-events:none}
  .cap{color:var(--muted);font-size:12.5px;margin:9px 2px 2px;line-height:1.55}
  .cap b{color:var(--ink)}.cap code{color:#cdd4e0}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em;color:#cdd4e0}
  .kpi{display:flex;gap:12px;flex-wrap:wrap;margin:6px 0 2px}
  .kpi .box{flex:1;min-width:150px;background:#0c0f15;border:1px solid var(--line);
    border-radius:10px;padding:11px 13px}
  .kpi .box .n{font-size:20px;font-weight:700;letter-spacing:-.02em}
  .kpi .box .l{color:var(--muted);font-size:12px;margin-top:2px}
  footer{margin-top:26px;color:var(--muted);font-size:12.5px;text-align:center}
  @media(max-width:760px){.grid{grid-template-columns:1fr}}
"""

_SANS = "-apple-system,'Segoe UI',sans-serif"
_MONO = "ui-monospace,Menlo,monospace"

# ── schematic 1: the one-way baseline (impulses flow right, nothing flows back)
SVG_ONEWAY = f"""<svg viewBox="0 0 920 168" xmlns="http://www.w3.org/2000/svg" font-family="{_SANS}" role="img" aria-label="one-way flow">
<defs>
<marker id="mAo" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#fb923c"/></marker>
<marker id="mAr" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#e0635a"/></marker>
</defs>
<rect x="50" y="34" width="240" height="66" rx="10" fill="#12151d" stroke="#272c38"/>
<text x="170" y="62" text-anchor="middle" fill="#e7eaf0" font-size="13" font-weight="600">rigid contact solve</text>
<text x="170" y="82" text-anchor="middle" fill="#9aa1ad" font-size="10.5">rigid bodies only — modes in no row</text>
<rect x="630" y="34" width="240" height="66" rx="10" fill="#12151d" stroke="#272c38"/>
<text x="750" y="62" text-anchor="middle" fill="#e7eaf0" font-size="13" font-weight="600">modal oscillators</text>
<text x="750" y="82" text-anchor="middle" fill="#34d399" font-size="11.5" font-family="{_MONO}">a⁺ = IIR(a, Φᵀλ)</text>
<line x1="290" y1="58" x2="441" y2="58" stroke="#fb923c" stroke-width="2"/>
<line x1="471" y1="58" x2="622" y2="58" stroke="#fb923c" stroke-width="2" marker-end="url(#mAo)"/>
<circle cx="456" cy="58" r="12" fill="#0c0f15" stroke="#f5c451" stroke-width="1.8"/>
<text x="456" y="62.5" text-anchor="middle" fill="#f5c451" font-size="12.5" font-family="{_MONO}">λ</text>
<text x="456" y="34" text-anchor="middle" fill="#fb923c" font-size="11.5">contact impulses</text>
<path d="M750,100 L750,128 L470,128" fill="none" stroke="#e0635a" stroke-width="1.6" stroke-dasharray="5 4"/>
<path d="M442,128 L170,128 L170,106" fill="none" stroke="#e0635a" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#mAr)"/>
<line x1="449" y1="121" x2="463" y2="135" stroke="#e0635a" stroke-width="2.4"/>
<line x1="463" y1="121" x2="449" y2="135" stroke="#e0635a" stroke-width="2.4"/>
<text x="456" y="156" text-anchor="middle" fill="#e0635a" font-size="11.5">no back-reaction — the modes can never change a contact force</text>
</svg>"""

# ── schematic 2: anatomy of the shared row (deformed surfaces, gap, one λ)
SVG_ROW = f"""<svg viewBox="0 0 920 344" xmlns="http://www.w3.org/2000/svg" font-family="{_SANS}" role="img" aria-label="shared contact row">
<defs>
<marker id="mBa" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#7aa2ff"/></marker>
<marker id="mBg" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#34d399"/></marker>
<marker id="mBi" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#e7eaf0"/></marker>
</defs>
<line x1="50" y1="30" x2="98" y2="30" stroke="#7aa2ff" stroke-width="1.6" stroke-dasharray="6 4"/>
<text x="106" y="34" fill="#9aa1ad" font-size="11.5">rigid surface</text>
<path d="M50,52 Q62,45 74,52 T98,52" stroke="#34d399" stroke-width="2" fill="none"/>
<text x="106" y="56" fill="#9aa1ad" font-size="11.5">deformed surface  r + Φ·a   (flex exaggerated)</text>
<text x="50" y="150" fill="#f5c451" font-size="12.5" font-weight="600">one shared multiplier λ</text>
<text x="50" y="176" fill="#7aa2ff" font-size="12" font-family="{_MONO}">±Jᵀλ → pushes the rigid poses</text>
<text x="50" y="200" fill="#34d399" font-size="12" font-family="{_MONO}">+Ĝ_Aᵀλ, −Ĝ_Bᵀλ → drive the modes</text>
<rect x="400" y="44" width="280" height="104" rx="4" fill="rgba(122,162,255,0.05)" stroke="#7aa2ff" stroke-width="1.6" stroke-dasharray="6 4"/>
<text x="418" y="68" fill="#e7eaf0" font-size="13" font-weight="600">body A</text>
<text x="418" y="86" fill="#9aa1ad" font-size="10.5" font-family="{_MONO}">pose x_A · modes a_A</text>
<path d="M400,148 Q540,176 680,148" stroke="#34d399" stroke-width="2.2" fill="none"/>
<circle cx="540" cy="162" r="4" fill="#34d399"/>
<text x="552" y="160" fill="#34d399" font-size="11.5" font-family="{_MONO}">p_A</text>
<rect x="400" y="232" width="280" height="88" rx="4" fill="rgba(122,162,255,0.05)" stroke="#7aa2ff" stroke-width="1.6" stroke-dasharray="6 4"/>
<text x="418" y="258" fill="#e7eaf0" font-size="13" font-weight="600">body B</text>
<text x="418" y="276" fill="#9aa1ad" font-size="10.5" font-family="{_MONO}">pose x_B · modes a_B</text>
<path d="M400,232 Q540,204 680,232" stroke="#34d399" stroke-width="2.2" fill="none"/>
<circle cx="540" cy="218" r="4" fill="#34d399"/>
<text x="552" y="230" fill="#34d399" font-size="11.5" font-family="{_MONO}">p_B</text>
<line x1="540" y1="167" x2="540" y2="213" stroke="#e7eaf0" stroke-width="1.6" marker-start="url(#mBi)" marker-end="url(#mBi)"/>
<text x="558" y="194" fill="#e7eaf0" font-size="12" font-family="{_MONO}">gap C ≥ 0</text>
<circle cx="340" cy="190" r="13" fill="#0c0f15" stroke="#f5c451" stroke-width="2"/>
<text x="340" y="195" text-anchor="middle" fill="#f5c451" font-size="13" font-family="{_MONO}">λ</text>
<path d="M349,181 C380,140 470,112 522,102" fill="none" stroke="#7aa2ff" stroke-width="1.8" marker-end="url(#mBa)"/>
<path d="M349,199 C380,240 470,268 522,276" fill="none" stroke="#7aa2ff" stroke-width="1.8" marker-end="url(#mBa)"/>
<path d="M353,186 C392,178 424,170 450,161" fill="none" stroke="#34d399" stroke-width="1.8" marker-end="url(#mBg)"/>
<path d="M353,194 C392,202 424,210 450,219" fill="none" stroke="#34d399" stroke-width="1.8" marker-end="url(#mBg)"/>
</svg>"""

# ── schematic 3: the network — ring travels through the rows; OFF is dead
SVG_NETWORK = f"""<svg viewBox="0 0 920 336" xmlns="http://www.w3.org/2000/svg" font-family="{_SANS}" role="img" aria-label="contact network on/off">
<defs>
<marker id="mCg" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#34d399"/></marker>
<marker id="mCo" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="#fb923c"/></marker>
</defs>
<text x="48" y="42" fill="#34d399" font-size="12">the ring travels hop-by-hop through the shared rows</text>
<rect x="70" y="272" width="440" height="34" rx="3" fill="rgba(122,162,255,0.05)" stroke="#7aa2ff" stroke-width="1.4" stroke-dasharray="6 4"/>
<path d="M70,272 q27.5,-9 55,0 t55,0 t55,0 t55,0 t55,0 t55,0 t55,0 t55,0" stroke="#34d399" stroke-width="2" fill="none"/>
<text x="90" y="298" fill="#9aa1ad" font-size="10.5">slab — the impact rings it</text>
<path d="M120,218 L120,260" stroke="#fb923c" stroke-width="2.2" marker-end="url(#mCo)"/>
<text x="134" y="232" fill="#fb923c" font-size="11.5">impact</text>
<rect x="300" y="210" width="84" height="62" rx="3" fill="#12151d" stroke="#cdd4e0" stroke-width="1.3"/>
<rect x="352" y="148" width="84" height="62" rx="3" fill="#12151d" stroke="#cdd4e0" stroke-width="1.3"/>
<rect x="300" y="86" width="84" height="62" rx="3" fill="#12151d" stroke="#cdd4e0" stroke-width="1.3"/>
<text x="310" y="228" fill="#9aa1ad" font-size="10.5">base</text>
<text x="362" y="166" fill="#9aa1ad" font-size="10.5">mid</text>
<text x="310" y="104" fill="#9aa1ad" font-size="10.5">upper</text>
<text x="356" y="248" fill="#34d399" font-size="15">∿</text>
<text x="408" y="186" fill="#34d399" font-size="15">∿</text>
<text x="356" y="124" fill="#34d399" font-size="15">∿</text>
<path d="M190,292 C260,292 320,268 336,242 S356,196 366,180 S372,132 366,120" fill="none" stroke="#34d399" stroke-width="2" opacity="0.85" marker-end="url(#mCg)"/>
<circle cx="342" cy="272" r="9" fill="#0c0f15" stroke="#f5c451" stroke-width="1.6"/>
<text x="342" y="275.5" text-anchor="middle" fill="#f5c451" font-size="10" font-family="{_MONO}">λ</text>
<circle cx="368" cy="210" r="9" fill="#0c0f15" stroke="#f5c451" stroke-width="1.6"/>
<text x="368" y="213.5" text-anchor="middle" fill="#f5c451" font-size="10" font-family="{_MONO}">λ</text>
<circle cx="368" cy="148" r="9" fill="#0c0f15" stroke="#f5c451" stroke-width="1.6"/>
<text x="368" y="151.5" text-anchor="middle" fill="#f5c451" font-size="10" font-family="{_MONO}">λ</text>
<line x1="426" y1="249" x2="356" y2="268" stroke="#3d4452" stroke-width="1"/>
<text x="600" y="252" text-anchor="end" fill="#9aa1ad" font-size="11">cube↔slab — same row</text>
<line x1="436" y1="193" x2="381" y2="207" stroke="#3d4452" stroke-width="1"/>
<text x="600" y="196" text-anchor="end" fill="#9aa1ad" font-size="11">cube↔cube — same row</text>
<path d="M320,78 q22,-11 44,0" stroke="#34d399" stroke-width="1.5" fill="none" opacity="0.8"/>
<path d="M328,68 q14,-7 28,0" stroke="#34d399" stroke-width="1.2" fill="none" opacity="0.5"/>
<text x="342" y="58" text-anchor="middle" fill="#34d399" font-size="11.5" font-family="{_MONO}">a_upper ≠ 0</text>
<line x1="612" y1="44" x2="612" y2="312" stroke="#272c38"/>
<text x="766" y="58" text-anchor="middle" fill="#9aa1ad" font-size="12" font-weight="600">network OFF</text>
<text x="766" y="76" text-anchor="middle" fill="#697180" font-size="10.5">rows carry no modal columns</text>
<rect x="646" y="262" width="240" height="30" rx="3" fill="rgba(122,162,255,0.03)" stroke="#3f4654" stroke-width="1.2" stroke-dasharray="6 4"/>
<path d="M646,262 q15,-7 30,0 t30,0 t30,0 t30,0 t30,0 t30,0 t30,0 t30,0" stroke="#7b8496" stroke-width="1.6" fill="none"/>
<text x="656" y="284" fill="#697180" font-size="10">slab still rings…</text>
<rect x="736" y="216" width="60" height="46" rx="3" fill="#10131a" stroke="#566072" stroke-width="1.2"/>
<rect x="766" y="170" width="60" height="46" rx="3" fill="#10131a" stroke="#566072" stroke-width="1.2"/>
<rect x="736" y="124" width="60" height="46" rx="3" fill="#10131a" stroke="#566072" stroke-width="1.2"/>
<circle cx="766" cy="262" r="5" fill="#10131a" stroke="#566072" stroke-width="1.2"/>
<circle cx="781" cy="216" r="5" fill="#10131a" stroke="#566072" stroke-width="1.2"/>
<circle cx="781" cy="170" r="5" fill="#10131a" stroke="#566072" stroke-width="1.2"/>
<text x="766" y="112" text-anchor="middle" fill="#e0635a" font-size="11.5" font-family="{_MONO}">a_upper ≡ 0</text>
<text x="766" y="322" text-anchor="middle" fill="#697180" font-size="10.5">contacts still there — but nothing carries the ring</text>
</svg>"""


def ledger_rows(L):
    order = [("resting_support", "resting cube → slab", "m·g"),
             ("base_support", "base cube → slab", "3 m·g"),
             ("base_mid_box", "base ↔ mid (box-box)", "2 m·g"),
             ("mid_upper_box", "mid ↔ upper (box-box)", "m·g")]
    out = ""
    for key, label, exp in order:
        d = L[key]
        tag = "good" if d["err_pct"] < 3 else "warn"
        out += (f'<tr><td class="k">{label}</td>'
                f'<td class="num">{d["measured"]:.2f} N</td>'
                f'<td class="num">{exp} = {d["expect"]:.2f}</td>'
                f'<td class="num"><span class="tag {tag}">{d["err_pct"]:.1f}%</span></td></tr>')
    return out


def corner_rows(C, ref):
    order = ["-x -z", "-x +z", "+x -z", "+x +z"]
    out = ""
    for k in order:
        out += (f'<tr><td class="k">corner {k}</td>'
                f'<td class="num">{C[k]:.3f} N</td>'
                f'<td class="num">{ref:.3f} N</td></tr>')
    return out


def _read_csv(relpath):
    import csv
    with open(os.path.join(_ROOT, relpath)) as f:
        return list(csv.DictReader(f))


def device_perf():
    """RTX 4090 device-path numbers, straight from the committed X5 CSVs."""
    X5 = "benchmarks/paper_eval/x5_perf/out/"
    perf = _read_csv(X5 + "perf_device.csv")                 # per-scene @16x4
    ladder = _read_csv(X5 + "perf_device_budget.csv")        # dinner budget ladder
    stress = _read_csv(X5 + "stress_device.csv")             # N = 16..512
    psv = _read_csv(X5 + "device_passivity.csv")
    psv_n = _read_csv(X5 + "stress_device_psv.csv")

    rows = ""
    for r in sorted(perf, key=lambda r: float(r["coupling_ms"])):
        rt = float(r["rt_factor_120hz"])
        tag = ('  <span class="tag good">real-time</span>'
               if r["realtime_120hz"] == "True" else "")
        rows += (f'<tr><td class="k">{r["scene"]}</td>'
                 f'<td class="num">{int(r["nb"])}</td>'
                 f'<td class="num">{int(r["modes"])}</td>'
                 f'<td class="num">{float(r["coupling_ms"]):.2f} ms</td>'
                 f'<td class="num">{rt:.2f}×{tag}</td></tr>')

    lad = {r["budget"]: float(r["mean_ms"]) for r in ladder
           if r["scene"] == "dinner"}
    d16x2 = next(r for r in ladder
                 if r["scene"] == "dinner" and r["budget"] == "16x2")
    s8 = [r for r in stress if r["budget"] == "8x1"]
    assert all(r["realtime_120hz"] == "True" for r in s8), "8x1 not RT at some N"
    s8_lo = next(r for r in s8 if r["n_bodies"] == "16")
    s8_hi = next(r for r in s8 if r["n_bodies"] == "512")
    holds = sum(r["holds"] == "True" for r in psv)
    holds_n = sum(r["holds"] == "True" for r in psv_n)
    return {
        "rows": rows, "lad": lad,
        "d16x2_ms": float(d16x2["mean_ms"]), "d16x2_rt": float(d16x2["rt_factor_120hz"]),
        "n512_ms": float(s8_hi["mean_ms"]), "n512_rt": float(s8_hi["rt_factor_120hz"]),
        "n16_ms": float(s8_lo["mean_ms"]),
        "psv": f"{holds}/{len(psv)}", "psv_n": f"{holds_n}/{len(psv_n)}",
    }


def main():
    with open(os.path.join(DIR, "contact_forces.json")) as f:
        S = json.load(f)
    mg = S["mg"]
    fig1 = _b64("contact_forces.png")
    fig2 = _b64("abd_comparison.png")
    fig3 = _b64("payload_ab.png")
    ru = S["ring_upper"]; rip = S["joint_ripple_mid_upper"]
    P = device_perf()

    body = f"""
<div class="wrap">
  <header>
    <h1>Two-Way Modal Contact as a Native Constraint — and the Contact Network It Buys</h1>
    <p class="sub">Follow-up on the two-way coupling raised at the last meeting — it is
    implemented, natively. Every cube now carries its <b>own modal analysis</b>
    (per-cube FEM eigenmodes, not just the slab), and the modal response is a
    <b>native constraint</b>: one unilateral contact row on the deformed surface of
    <b>both</b> bodies, co-solved for rigid poses and modal amplitudes together. A
    stacked cube feels the ring of the cube beneath it. Two formulas, then the
    evidence.</p>
    <p class="by">§N2 modal contact network · AVBD · CPU · h = 1/120, 12 iters × 4
    substeps · scene: reduced_cargo_network (modal slab + resting control cube +
    impactor + 3-high zig-zag stack) · baseline: the previous one-way forced-IIR kick</p>
  </header>

  <div class="grid">

    <div class="card full">
      <h3>0 · Where we left off — the one-way kick <span class="tag">baseline</span></h3>
      <div class="diag">{SVG_ONEWAY}</div>
      <p>The contact solver ran on <b>rigid bodies only</b>; afterwards the impulses
      forced the modal oscillators. The ring is a <em>readout</em> — the modes appear
      in no constraint, so nothing they do can ever change a contact force. The box
      sits on rigid concrete while a movie of a vibrating surface plays underneath it.</p>
    </div>

    <div class="card full">
      <h3>1 · The move — write the contact gap on the <em>deformed</em> surface <span class="tag">two-way by construction</span></h3>
      <p>A contact constraint is a gap that must stay non-negative. The whole change
      is one substitution — measure the gap at the surface point <b>including the
      modal flex</b>:</p>
      <div class="eq">p<sub>X</sub> = x<sub>X</sub> + R<sub>X</sub> ( r<sub>X</sub> <span class="hl">+ Φ<sub>X</sub>(r<sub>X</sub>)·<span class="g">a<sub>X</sub></span></span> )      <span class="m"># contact point = rigid pose + mode shapes × amplitudes</span></div>
      <p>Projected on the contact normal, the row gains one linear term per
      participant:</p>
      <div class="eq">0 ≤ C = C<sub>rigid</sub> <span class="hl">+ Ĝ<sub>A</sub>·<span class="g">a<sub>A</sub></span> − Ĝ<sub>B</sub>·<span class="g">a<sub>B</sub></span></span>  ⊥  λ ≥ 0        <span class="m"># Ĝ<sub>X</sub> = n̂ᵀ R<sub>X</sub> Φ<sub>X</sub> — one number per mode:</span>
<span class="m">                                                  # how far unit amplitude of mode k moves this</span>
<span class="m">                                                  # contact point along the contact normal</span></div>
      <div class="diag">{SVG_ROW}</div>
      <p>One shared multiplier λ now serves rigid poses and modal amplitudes — the
      amplitudes are <b>extra columns of the contact Jacobian</b>, solver unknowns
      now, not a post-solve read:</p>
      <div class="eq">J<sub>row</sub> = [ J<sub>A</sub><sup>rigid</sup> | <span class="g">Ĝ<sub>A</sub></span> | −J<sub>B</sub><sup>rigid</sup> | <span class="g">−Ĝ<sub>B</sub></span> ]   on state ( pose<sub>A</sub>, <span class="g">a<sub>A</sub></span>, pose<sub>B</sub>, <span class="g">a<sub>B</sub></span> )      <span class="m"># one λ, every DOF</span></div>
      <p><b class="pos">Two-way.</b> <code>∂C/∂a = Ĝ ≠ 0</code>: a flexing mode changes
      the gap — hence the force — inside the same solve. The ring modulates the support
      force; a payload mass-loads and detunes the ring.<br>
      <b class="pos">Momentum-consistent.</b> One λ on one row: what drives A's modes is
      exactly the reaction B feels. Newton's third law is in the algebra — no post-solve
      correction, no energy from nowhere.</p>
    </div>

    <div class="card full">
      <h3>2 · Symmetry ⇒ a contact network <span class="tag">one row type · two special cases</span></h3>
      <p>The row is symmetric in A and B — nothing says B must be the ground. A
      <b>rigid</b> body is the zero-modal-column case; the earlier <b>support
      contact</b> is the one-sided case. Cube↔slab and cube↔cube are the <b>same row
      type</b>, so every body can carry a basis — here <b>each cube gets its own modal
      analysis</b>: its own FEM tet mesh, generalized eigensolve of (K,&nbsp;M),
      mass-normalized elastic eigenmodes with modal damping. Vibration then travels
      hop by hop through contacts: slab → base → mid → upper, each hop a physical
      multiplier. The passivity ledger
      <code>ΔE<sub>modal</sub> ≤ η·ΔE<sub>rigid loss</sub></code> is enforced
      <b>globally across the network</b>, not per contact.</p>
      <div class="diag">{SVG_NETWORK}</div>
    </div>

    <div class="card full">
      <h3>Evidence · corner &amp; joint contact forces <span class="tag good">read straight off the multipliers λ</span></h3>
      <div class="fig"><img src="{fig1}" alt="contact forces vs time"/>
        <div class="pin" style="left:22%;top:24%">1</div>
        <div class="pin" style="left:76%;top:68%">2</div>
        <div class="pin" style="left:30%;top:75%">3</div>
      </div>
      <div class="kpi">
        <div class="box"><div class="n pos" style="font-size:14px">① start here — the four flat lines (a)</div>
          <div class="l">each joint's running mean lands on <b>exactly the weight above
          it</b>: m·g, 2·m·g, 3·m·g, within 1.9% — the solver's multipliers <em>are</em>
          the load path, no per-joint tuning.</div></div>
        <div class="box"><div class="n pos" style="font-size:14px">② the two-way shot (d)</div>
          <div class="l">top cube, two hops from the slab: <b>ON it rings, OFF it is
          dead flat at zero</b>. The ring got there only through the shared rows —
          numbers in the card below.</div></div>
        <div class="box"><div class="n pos" style="font-size:14px">③ per-corner load transfer (c)</div>
          <div class="l">stack-foot corners split <b>2.7 → 6.3 N toward the tower's
          lean</b> — the row resolves load corner by corner, ring modulation on top.</div></div>
      </div>
      <p class="cap">Panel <b>(b)</b> is the control: a lone resting cube sharing
      m·g/4 per corner, near-even.</p>
    </div>

    <div class="card">
      <h3>The static ledger is exact</h3>
      <table>
        <tr><th>joint</th><th>measured</th><th>expected</th><th>err</th></tr>
        {ledger_rows(S["ledger"])}
      </table>
      <p class="small">Settled tail mean; m·g = {mg:.3f} N (0.6 kg cube).</p>
      <p>In a settled stack the multipliers <em>are</em> the contact forces: every
      joint carries exactly the weight above it, within 2%, zero per-joint tuning —
      adding modes to the rows did not corrupt statics.</p>
    </div>

    <div class="card">
      <h3>Per-corner: control vs stack foot</h3>
      <table>
        <tr><th>resting control cube</th><th>force</th><th>m·g/4</th></tr>
        {corner_rows(S["resting_corners"], mg/4)}
      </table>
      <table style="margin-top:14px">
        <tr><th>base cube (stack foot)</th><th>force</th><th>3·m·g/4</th></tr>
        {corner_rows(S["base_corners"], 3*mg/4)}
      </table>
      <p class="small">Control: near-even. Stack foot: skewed toward the
      <code>+x −z</code> corner the tower leans on — resolved per corner.</p>
    </div>

    <div class="card full">
      <h3>Evidence · it is genuinely two-way <span class="tag good">falsifiable ON/OFF test</span></h3>
      <div class="kpi">
        <div class="box"><div class="n pos">{ru['fem_rigid']:.1e}</div>
          <div class="l">top-cube ring |a| — network ON</div></div>
        <div class="box"><div class="n" style="color:var(--red)">{ru['off']:.0f}</div>
          <div class="l">top-cube ring |a| — network OFF (identically zero)</div></div>
        <div class="box"><div class="n">±{rip['off']:.2f} → ±{rip['on']:.2f} N</div>
          <div class="l">mid↔upper force ripple OFF → ON (compliance smooths chatter)</div></div>
      </div>
      <p><code>upper</code> touches only <code>mid</code> — two box-box hops from the
      slab. ON it rings; OFF its amplitude is identically zero. There is no other path
      — this is the causality proof for the network: the vibration arrived purely
      through the shared rows. The compliance also halves the box-box chatter
      (±{rip['off']:.2f} → ±{rip['on']:.2f} N) while the mean stays at m·g.</p>
    </div>

    <div class="card full">
      <h3>Live demo · payload mass-loading A/B <span class="tag good">true scale — exaggeration 1</span></h3>
      <p>The same soft plate (~5 Hz fundamental, mm–cm compliance), resting
      payload, and falling impactor — built twice, side by side. On the
      <b>left</b> the payload is in the plate's contact rows (two-way). On the
      <b>right</b> it gets the previous one-way treatment: it <em>rides</em>
      the readout ring (its floor anchors follow y<sub>rest</sub> + U·q, so it
      bounces like the old bystanders did), but its weight and inertia never
      enter q — the plate's response is computed as if it did not exist. No
      render exaggeration anywhere.</p>
      <div class="fig"><img src="{fig3}" alt="payload mass-loading A/B"/></div>
      <p class="cap"><b>(a)</b> plate deflection at the payload point: two-way
      pre-sags −6.2 mm under the payload's weight, then rings <b>mass-loaded —
      detuned 4.9 → 1.6 Hz and damped</b>; one-way stays flat before impact
      and rings free — identical to the empty plate. <b>(b)</b> the payload:
      one-way it is <b>tossed 21 mm by a ring its own mass never damped</b>
      (the free-energy giveaway); two-way it rides the plate it sagged and
      calmed (16 mm, mostly the sag).</p>
      <p>No gain setting on the one-way side can produce the left column: sag,
      detune, and damping are back-reaction, and back-reaction requires the
      shared row. The one-way plate also lifts a 3 kg payload without losing a
      joule — the energy story in one picture.</p>
      <div class="eq">.venv/bin/python scripts/run_native_scenes_viser.py --scene payload      <span class="m"># live side-by-side, GUI reset re-drops</span></div>
    </div>

    <div class="card full">
      <h3>Evidence · real-time on the device path <span class="tag good">measured — RTX 4090 server run</span></h3>
      <p>The same co-solve runs fully device-resident on CUDA (solver, modal blocks,
      and coupler on the GPU). At h&nbsp;=&nbsp;1/120, real-time means
      ≤&nbsp;8.33&nbsp;ms/step. Committed runs from
      <code>benchmarks/paper_eval/x5_perf/</code>, RTX&nbsp;4090:</p>
      <table>
        <tr><th>scene @ 16 iters × 4 substeps</th><th>bodies</th><th>modes</th><th>ms / step</th><th>× real-time (120 Hz)</th></tr>
        {P["rows"]}
      </table>
      <div class="kpi">
        <div class="box"><div class="n pos">{P["d16x2_ms"]:.2f} ms → {P["d16x2_rt"]:.2f}×</div>
          <div class="l">heaviest scene (dinner, 25 bodies) at 16×2 — comfortably
          real-time; ledge &amp; shelf are real-time even at 16×4</div></div>
        <div class="box"><div class="n pos">N = 512 : {P["n512_ms"]:.2f} ms → {P["n512_rt"]:.2f}×</div>
          <div class="l">scale stress at 8×1 — real-time at <b>every</b> N from 16 to 512;
          cost grows ~√N ({P["n16_ms"]:.2f} ms at N = 16)</div></div>
        <div class="box"><div class="n pos">{P["psv"]} + {P["psv_n"]}</div>
          <div class="l">device cells where the ledger ΔE<sub>modal</sub> ≤
          η·ΔE<sub>loss</sub> holds (scenes + N-sweep) — read-only, the clamp never
          needs to fire</div></div>
      </div>
      <p class="small">Budget ladder on dinner: {P["lad"]["8x1"]:.2f} (8×1) →
      {P["lad"]["8x2"]:.2f} (8×2) → {P["lad"]["16x2"]:.2f} (16×2) →
      {P["lad"]["16x4"]:.2f} (16×4) ms/step.</p>
    </div>

    <div class="card full">
      <h3>Would ABD help? <span class="tag">already wired in · interchangeable</span></h3>
      <div class="fig"><img src="{fig2}" alt="ABD comparison"/></div>
      <p class="cap"><b>(a)</b> normalized top-cube ring: the modal cube and the affine
      (ABD) cube both transmit a ring through the network; the pure-rigid cube (0
      modes) cannot ring. <b>(b)</b> the settled ledger is basis-independent — rigid,
      modal, and affine all hit the same m·g multiples at every joint.</p>
      <p>ABD is a co-rotated affine 9-DOF body whose corner Jacobian
      <code>B<sub>c</sub></code> substitutes for the modal <code>Φ<sub>c</sub></code> —
      it drops into the <b>same</b> rows with no special-casing. But the affine
      subspace is uniform stretch/shear only: it <b>cannot</b> represent the
      bending/plate modes that carry the far-field ring, and its flex showed a slow
      secular buildup over the 3&nbsp;s run <span class="tag warn">not yet
      energy-governed</span>.</p>
      <p class="small"><b>Position:</b> modal Φ stays the headline basis; ABD is a
      supported, swappable option and a future-work direction.</p>
    </div>

    <div class="card full">
      <h3>The method in three lines</h3>
      <div class="eq"><span class="m">1)</span>  p = x + R ( r <span class="hl">+ Φ·<span class="g">a</span></span> )                        <span class="m"># deformed contact point</span>
<span class="m">2)</span>  0 ≤ C<sub>rigid</sub> + Ĝ<sub>A</sub>·<span class="g">a<sub>A</sub></span> − Ĝ<sub>B</sub>·<span class="g">a<sub>B</sub></span>  ⊥  λ ≥ 0        <span class="m"># one shared unilateral row</span>
<span class="m">3)</span>  rigid: ±Jᵀλ    modes: +Ĝ<sub>A</sub>ᵀλ , −Ĝ<sub>B</sub>ᵀλ         <span class="m"># same λ routed to every DOF</span></div>
      <p>A rigid body is the zero-column case; the support contact is the one-sided
      case — cube↔slab and cube↔cube are the same row. That is why it is a network.</p>
      <p class="small">On top of this: the §15 passivity ledger is enforced globally
      across the network, and the same co-solve is validated against an all-FEM
      shared-operator ground truth on five scenes. Runtime: the RTX 4090 card above.</p>
    </div>

  </div>

  <footer>Generated from <code>benchmarks/network/report_sheldon_contact_forces.py</code>
  (analysis only — no solver code changed) · figures + JSON in
  <code>docs/07_17_report/</code> · rebuild via
  <code>benchmarks/network/make_sheldon_html.py</code></footer>
</div>
"""

    html = ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\"/>\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>\n"
            "<title>Two-Way Modal Contact as a Native Constraint — 07/17 report</title>\n<style>"
            + CSS + "</style>\n</head>\n<body>" + body + "</body>\n</html>\n")
    out = os.path.join(DIR, "contact_forces.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"wrote {out}  ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
