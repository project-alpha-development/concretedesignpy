"""
report.py -- Markdown calculation sheets for apec-col-design results (column, joint,
footing, beam wrapper, project summary).  Every sheet ends with the vault output format:
Basis & Citations, Verification, Summary (warnings + not checked).
"""

import math

REFUSAL = "The reference folder does not contain enough basis to support this answer."


def _f(x, n=1):
    if x is None:
        return "-"
    if isinstance(x, str):
        return x
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x:,.{n}f}"


def _checks_table(checks):
    rows = ["| Status | Check | Value | Limit | Clause | Page | Note |", "|---|---|---|---|---|---|---|"]
    order = {"FAIL": 0, "WARN": 1, "OK": 2}
    for c in sorted(checks, key=lambda c: order.get(c["status"], 3)):
        v = c["value"]
        v = _f(v, 3) if isinstance(v, float) else str(v if v is not None else "-")
        cell = lambda x: str(x if x is not None else '-').replace('|', '·')
        rows.append(f"| **{c['status']}** | {c['id']} | {cell(v)} | {cell(c['limit'] or '-')} | {cell(c['clause'])} | "
                    f"{cell(c['page'])} | {cell(c.get('note') or '')} |")
    return "\n".join(rows)


def _combos_table(combos):
    if not combos:
        return "_No generated combinations (pre-factored demands were supplied)._"
    rows = ["| ID | NSCP Eq. | Combination | Load factors |", "|---|---|---|---|"]
    for c in combos:
        fac = ", ".join(f"{k} {v:+.4g}" for k, v in c["factors"].items())
        rows.append(f"| {c['id']} | {c['eq']} | {c['name']} | {fac} |")
    return "\n".join(rows)


def _loads_line(ld):
    ev = 0.5 * ld.get("Ca", 0.0) * ld.get("I", 1.0)
    return (f"f1 = {ld['f1']:g} · rho = {ld['rho']:g} · Ca = {ld.get('Ca', 0):g} · I = {ld.get('I', 1):g} → "
            f"Ev = 0.5CaI·D = {ev:.4f}D (applied with both senses) · orthogonal 100/30: "
            f"{'yes' if ld.get('orthogonal') else 'no'}")


VERIFICATION = (
    "**Partially verified.** Solver benchmarked against Wight & MacGregor 7th Ex 11-1, 11-5, 11-7 "
    "and 19-2 (`tests/run_benchmarks.py`). NSCP 2015 folios 2-10/2-11, 2-219, 2-221, 4-115/116/117, "
    "4-140/141, 4-143/144/145 were rendered and **read visually on 2026-09-28**; ACI 318-25M pages "
    "were read from its text layer. Other NSCP folios are carried from the vault notes named in "
    "`references/nscp_clauses.md` and are not re-read.")


COLUMN_BASIS = [
    ("Load combinations", "NSCP 2015 Vol. I", "§203.3.1 Eqs. 203-1..203-7", "2-11", "strength set used for every demand"),
    ("E = ρEh + Ev, Ev = 0.5CaID", "NSCP 2015 Vol. I", "§208.6.1 Eq. 208-18", "2-219", "vertical component in strength combos"),
    ("100 % + 30 % orthogonal", "NSCP 2015 Vol. I", "§208.7.1", "2-221", "columns in two intersecting systems"),
    ("Strain compatibility, εcu 0.003", "ACI 318-25M / NSCP", "§22.2 / §422.2; §422.4.1.1", "437-438 / 4-143", "P-M and P-M-M"),
    ("Po, Pn,max = 0.80/0.85 Po", "NSCP 2015 / ACI 318-25M", "Table 422.4.2.1, Eq. 422.4.2.2", "4-143 / 440-441", "axial cap"),
    ("φ by εt (0.005 limit)", "NSCP 2015", "Table 421.2.2, §421.2.2.1", "4-140", "strength reduction"),
    ("Biaxial: NA ≠ moment direction", "W&M 7th", "§11-7, Ex 11-5", "567-572", "P-M-M method"),
    ("Bresler reciprocal load (info)", "W&M 7th", "Eq. (11-31)", "568", "cross-check only"),
    ("0.01–0.06 Ag (SMF), 0.08 Ag", "NSCP 2015", "§418.7.4.1 / §410.6.1.1", "4-115 / 4-71", "longitudinal limits"),
    ("SMF dimensions", "NSCP 2015", "§418.7.2.1", "4-115", "≥ 300 mm, ≥ 0.4"),
    ("ΣMnc ≥ 1.2ΣMnb", "NSCP 2015", "Eq. 418.7.3.2", "4-115", "strong column"),
    ("ℓo, hx, spacing, so", "NSCP 2015", "§418.7.5.1–418.7.5.3", "4-116", "confinement zone"),
    ("Ash / ρs, kf, kn", "NSCP 2015", "Table 418.7.5.4, Eq. 418.7.5.4a/b", "4-116/117", "confinement amount"),
    ("Beyond ℓo: 6db / 150", "NSCP 2015", "§418.7.5.5", "4-116", "mid-height hoops"),
    ("Ve from Mpr; beam cap; ≥ analysis", "NSCP 2015", "§418.7.6.1.1", "4-117", "design shear"),
    ("Vc = 0 in ℓo", "NSCP 2015", "§418.7.6.2.1", "4-117", "shear in hinge zone"),
    ("φ = 0.60 if Vn < V at Mn", "NSCP 2015", "§421.2.4.1", "4-141", "shear φ in SMF"),
    ("Vc with axial load", "NSCP 2015", "Eqs. 422.5.6.1, 422.5.7.1", "4-145", "concrete shear"),
    ("Section limit 0.66√f'c bw d", "ACI 318-25M (NSCP prints 0.67)", "Eq. 22.5.1.2 / 422.5.1.2", "442 / 4-144", "cross-section"),
    ("Lateral support of bars", "ACI 318-25M / NSCP", "§25.7.2.3 / §425.7.2.3", "551-552 / 4-170", "tie legs"),
    ("Column bar clear spacing", "ACI 318-25M", "§25.2.3", "510", "≥ 40 mm, 1.5db"),
    ("Slenderness screen", "NSCP 2015 / ACI 318-25M", "§406.2.5 / §6.2.5", "4-36 / 76-78", "k ℓu/r ≤ 22 (sway)"),
    ("Capacity-design guidance", "NIST GCR 8-917-1", "§5.2", "15-17", "balanced-point and 3-leg guidance"),
]


def _basis_table(rows):
    out = ["| Point | Reference | Clause/Section | Page | Relevance |", "|---|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows]
    return "\n".join(out)


def column_md(res):
    sec, mat, cap = res["section"], res["materials"], res["capacity"]
    shape = (f"{sec['b']:.0f} × {sec['h']:.0f} mm" if sec["shape"] == "rect" else f"Ø{sec['D']:.0f} mm")
    L = []
    L.append(f"# Column {res['id']} — {res['frame']} column design (NSCP 2015)\n")
    L.append(f"**Verdict: {res['verdict']}** · mode: {res['mode']} · φ rule: `{res['phi_rule']}` · tool: {res['tool']}\n")
    L.append(f"> Basis: {res['basis']}.\n")
    L.append("## 1. Schedule\n")
    for k, v in res["schedule"].items():
        if isinstance(v, (int, float)):
            v = _f(v, 4 if k == "rho" else 0)
        L.append(f"- **{k}**: {v}")
    L.append("\n## 2. Input\n")
    L.append(f"- Section {shape}, clear cover {sec['cover']:.0f} mm to hoops, Ag = {sec['Ag']:,.0f} mm², "
             f"Ach = {sec['Ach']:,.0f} mm², Ast = {sec['Ast']:,.0f} mm² (ρ = {sec['rho']:.4f})")
    L.append(f"- f'c = {mat['fc']:g} MPa, fy = {mat['fy']:g} MPa, fyt = {mat['fyt']:g} MPa, Es = {mat.get('Es', 200000):g} MPa, "
             f"β1 = {cap['beta1']:.3f}")
    if res.get("geometry"):
        g = res["geometry"]
        L.append(f"- Clear height ℓu = {g.get('lu', '-')} mm; k = {g.get('k', 1)}; second-order analysis: {g.get('second_order')}")
    if res.get("loads"):
        L.append(f"- Loads: {_loads_line(res['loads'])}")
    if res.get("cases"):
        keys = ["P", "Mx_top", "Mx_bot", "My_top", "My_bot", "Vx", "Vy"]
        L.append("\n**Unfactored load cases** (kN, kN·m)\n")
        L.append("| Case | " + " | ".join(keys) + " |")
        L.append("|---|" + "---|" * len(keys))
        for c, f in res["cases"].items():
            L.append(f"| {c} | " + " | ".join(_f(f.get(k, 0.0)) for k in keys) + " |")
    L.append("\n## 3. Load combinations — NSCP 2015 §203.3.1 (generated)\n")
    L.append(_combos_table(res.get("combinations")))
    L.append("\n## 4. Factored demands\n")
    L.append("| ID | Eq. | Pu | Mux top | Muy top | Mux bot | Muy bot | Vx | Vy | seismic |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for d in res["demands"]:
        L.append(f"| {d['id']} | {d['eq']} | {_f(d['P'])} | {_f(d['Mx_top'])} | {_f(d['My_top'])} | "
                 f"{_f(d['Mx_bot'])} | {_f(d['My_bot'])} | {_f(d['Vx'])} | {_f(d['Vy'])} | {'E' if d['seismic'] else ''} |")
    L.append("\n## 5. Axial–flexural strength (P-M and P-M-M)\n")
    L.append(f"- Po = {cap['Po']:,.1f} kN; Pn,max = {cap['Pn_max']:,.1f} kN; **φPn,max = {cap['phiPn_max']:,.1f} kN**; "
             f"φPnt = {cap['phiPnt']:,.1f} kN")
    for ax in ("x", "y"):
        b = cap.get(f"balanced_{ax}")
        if b:
            L.append(f"- Balanced point, bending about {ax}: Pb = {b['Pb']:,.1f} kN, Mb = {b['Mb']:,.1f} kN·m")
    for ax in ("x", "y"):
        L.append(f"\n**Uniaxial key points — bending about {ax}** (positive sense)\n")
        L.append("| Point | c (mm) | Pn (kN) | Mn (kN·m) | εt | φ | φPn (kN) | φMn (kN·m) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for p in res["pm_curves"][ax]["pos"]:
            if p.get("tag"):
                c = "∞" if (isinstance(p["c"], float) and math.isinf(p["c"])) else _f(p["c"])
                L.append(f"| {p['tag']} | {c} | {_f(p['Pn'])} | {_f(p['Mn'])} | {_f(p['eps_t'], 5)} | "
                         f"{_f(p.get('phi'), 3)} | {_f(p.get('phiPn'))} | {_f(p.get('phiMn'))} |")
    g = res["governing"]
    L.append(f"\n**Governing demand:** {g['combo']} ({g['eq']}), {g['end']} end — Pu = {g['Pu']:,.1f} kN, "
             f"Mux = {g['Mux']:,.1f}, Muy = {g['Muy']:,.1f} kN·m → φMn(Pu, same direction) = {_f(g['phiMn'])} kN·m, "
             f"**DC_M = {_f(g['DC_M'], 3)}**, DC_PMM (radial) = {_f(g['DC_PMM'], 3)}, φ = {_f(g['phi'], 3)} ({g['cls']}).\n")
    L.append("| Combo | Eq. | End | Pu | Mux | Muy | φMn | DC_M | DC_PMM | φ | status |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(res["pmm"], key=lambda r: -max(r["DC_M"], r["DC_PMM"] or 0))[:30]:
        L.append(f"| {r['combo']} | {r['eq']} | {r['end']} | {_f(r['Pu'])} | {_f(r['Mux'])} | {_f(r['Muy'])} | "
                 f"{_f(r['phiMn'])} | {_f(r['DC_M'], 3)} | {_f(r['DC_PMM'], 3)} | {_f(r['phi'], 3)} | {r['status'][:40]} |")
    if len(res["pmm"]) > 30:
        L.append(f"\n_{len(res['pmm'])} demand points in total; the 30 highest are listed — all are in the JSON._")
    br = res.get("bresler_governing")
    if br and br.get("phiPn"):
        L.append(f"\nBresler cross-check (information only, W&M Eq. 11-31): φPnx = {_f(br['phiPnx'])}, "
                 f"φPny = {_f(br['phiPny'])}, φPno = {_f(br['phiPno'])} → φPn = {_f(br['phiPn'])} kN, "
                 f"Pu/φPn = {_f(br['ratio'], 3)} {'' if br['valid'] else '(' + br['note'] + ')'}")
    for fig in res.get("figures") or []:
        L.append(f"\n![{fig}]({fig})")
    sm = res.get("smf")
    if sm:
        L.append("\n## 6. Special moment frame provisions — NSCP 2015 §418.7\n")
        ls = sm["lateral_support"]
        L.append(f"- Axial range of the E combinations: {sm['P_E'][0]:,.1f} to {sm['P_E'][1]:,.1f} kN; all combinations "
                 f"{sm['P_all'][0]:,.1f} to {sm['P_all'][1]:,.1f} kN")
        L.append(f"- ℓo = {sm['lo']:.0f} mm; hx = {ls['hx']:.0f} mm; legs ∥x = {ls['legs_x']}, legs ∥y = {ls['legs_y']}; "
                 f"nl = {ls['nl']}; s max in ℓo = {sm['s_max_lo']:.0f} mm ("
                 + ", ".join(f"{k} {v:.0f}" for k, v in sm["s_max_lo_parts"].items()) + ")")
        cf = sm["confinement"]
        if "ratio" in cf:
            L.append(f"- Table 418.7.5.4: (a) {cf['a']:.5f}, (b) {cf['b']:.5f}, (c) {cf['c']:.5f} "
                     f"[kf {cf['kf']:.2f}, kn {cf['kn']:.3f}, (c) {'applies' if cf['triggered_c_f'] else 'not triggered'}] "
                     f"→ Ash/(s·bc) ≥ **{cf['ratio']:.5f}** (expr. {cf['governs']})")
        else:
            L.append(f"- Table 418.7.5.4: (d) {cf['d']:.5f}, (e) {cf['e']:.5f}, (f) {cf['f']:.5f} → ρs ≥ **{cf['rho_s']:.5f}**")
        L.append("\n**Design shear (§418.7.6)**\n")
        L.append("| Dir. | Mpr (kN·m) at P | Ve col-Mpr | Ve beam-limited | Vu analysis | **Ve** | V at Mn | Vc in ℓo | Vc beyond | Vn req | Av/s req ℓo (mm²/mm) |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for d, sh in sm["shear"].items():
            L.append(f"| V{d} | {sh['Mpr']:,.1f} at {sh['P_at_Mpr']:,.0f} | {sh['Ve_col']:,.1f} | {sh['Ve_cap']:,.1f} | "
                     f"{sh['Vu_analysis']:,.1f} | **{sh['Ve']:,.1f}** | {sh['V_at_Mn']:,.1f} | {sh['Vc_lo_used']:,.1f} | "
                     f"{sh['Vc_mid']:,.1f} | {sh['Vn_req']:,.1f} | {sh['Av_s_req_lo']:.3f} |")
        if sm.get("scwb"):
            L.append("\n**Strong column – weak beam (Eq. 418.7.3.2)**\n")
            L.append("| Joint | ΣMnc (kN·m) | ΣMnb sway+ / sway− | ratio (≥ 1.2) | other column |")
            L.append("|---|---|---|---|---|")
            for k, v in sm["scwb"].items():
                if isinstance(v, dict) and v.get("rows"):
                    L.append(f"| {k} | {v['rows'][0]['SumMnc']:,.1f} | "
                             + " / ".join(f"{r['SumMnb']:,.1f}" for r in v["rows"])
                             + f" | {min(r['ratio'] for r in v['rows']):.3f} | {v['other_source']} |")
                elif isinstance(v, dict):
                    L.append(f"| {k} | – | – | – | {v.get('note', '')} |")
    h = res.get("hoops")
    if h:
        L.append("\n## 7. Transverse reinforcement\n")
        for k, v in (h.get("schedule") or {}).items():
            L.append(f"- **{k}**: {v}")
        if h.get("limits_lo"):
            L.append("\nSpacing limits in ℓo (mm): " + ", ".join(f"{k} {v:.0f}" for k, v in h["limits_lo"].items()))
        if h.get("limits_mid"):
            L.append("\nSpacing limits beyond ℓo (mm): " + ", ".join(f"{k} {v:.0f}" for k, v in h["limits_mid"].items()))
    L.append("\n## 8. Checks\n")
    L.append(_checks_table(res["checks"]))
    L.append("\n## 9. Basis & Citations\n")
    L.append(_basis_table(COLUMN_BASIS))
    L.append("\n## 10. Verification\n")
    L.append(VERIFICATION)
    L.append("\n## 11. Summary — warnings and what is not checked\n")
    for w in res["warnings"]:
        L.append(f"- ⚠ {w}")
    for n in res["not_checked"]:
        L.append(f"- Not checked: {n}")
    L.append("\n_Office defaults (bar sizes, cover, spacing increments) are APEC practice **(not vault-cited)** — "
             "see `references/apec_standards.md`._")
    return "\n".join(L) + "\n"


# ============================================================================ beam
def beam_md(res):
    L = [f"# Beam {res['id']} — rc-design with NSCP 2015 §203.3.1 combinations\n"]
    L.append(f"**Verdict: {res.get('verdict')}** · engine: rc-design (`~/.claude/skills/rc-design`), run with the "
             "envelope below\n")
    if res.get("error"):
        L.append(f"> ⛔ {res['error']}\n")
    if res.get("loads"):
        L.append(f"- Loads: {_loads_line(res['loads'])}")
    sch = res.get("schedule") or {}
    if sch:
        L.append("\n## 1. Schedule\n")
        for st in ("I", "M", "J"):
            if st in sch:
                s = sch[st]
                L.append(f"- **{st}**: top {s.get('top')}, bottom {s.get('bot')}"
                         + (f", sides {s['side_each_face']}" if s.get("side_each_face") else ""))
        for z, v in (sch.get("stirrups") or {}).items():
            L.append(f"- **stirrups {z}**: {v}")
    L.append("\n## 2. Load combinations — NSCP 2015 §203.3.1 (generated)\n")
    L.append(_combos_table(res.get("combinations")))
    L.append("\n## 3. Envelope handed to rc-design (kN, kN·m)\n")
    L.append("| Station | Mu− | Mu+ | Vu | Tu | governing combos |")
    L.append("|---|---|---|---|---|---|")
    for st, e in (res.get("envelope") or {}).items():
        gv = ", ".join(f"{k}:{v}" for k, v in e.get("gov", {}).items())
        L.append(f"| {st} | {_f(e['Mu_neg'])} | {_f(e['Mu_pos'])} | {_f(e['Vu'])} | {_f(e['Tu'])} | {gv} |")
    rc = res.get("rc_design") or {}
    se = rc.get("seismic")
    if se:
        L.append(f"\n**SMF capacity design:** Mpr− I/J {se['Mpr_neg_I']:.1f}/{se['Mpr_neg_J']:.1f}, "
                 f"Mpr+ I/J {se['Mpr_pos_I']:.1f}/{se['Mpr_pos_J']:.1f} kN·m, ℓn {se['ln']:.3f} m, "
                 f"Vpr {se['Vpr']:.1f}, wu {se['wu']:.2f} kN/m, **Ve {se['Ve']:.1f} kN**, Vc = 0 in hinge: "
                 f"{se['Vc_zero_in_hinge']}")
    if res.get("checks"):
        L.append("\n## 4. Checks (rc-design)\n")
        L.append(_checks_table(res["checks"]))
    L.append("\n## 5. Basis\n")
    L.append("Beam provisions, clause register and benchmarks: rc-design `references/nscp_clauses.md` "
             "(NSCP 2015 = ACI 318M-14; W&M 7th Ex 4-1M, 4-4, 6-1M, 7-2; APEC rc-beam id 25). "
             "Combinations: NSCP 2015 §203.3.1, 2-11; Ev §208.6.1, 2-219 (read visually 2026-09-28).")
    if res.get("warnings"):
        L.append("\n## 6. Summary — warnings\n")
        for w in res["warnings"]:
            L.append(f"- ⚠ {w}")
    for n in res.get("not_checked") or []:
        L.append(f"- Not checked: {n}")
    return "\n".join(L) + "\n"


JOINT_BASIS = [
    ("Beam bars at 1.25 fy", "NSCP 2015", "§418.8.2.1", "4-117", "joint demand"),
    ("Column depth ≥ 20 db", "NSCP 2015", "§418.8.2.3", "4-118", "bar slip"),
    ("Joint depth ≥ ½ beam depth", "NSCP 2015", "§418.8.2.4", "4-118", "geometry"),
    ("Joint hoops, half with 4 beams", "NSCP 2015", "§418.8.3.1–.2", "4-118", "confinement"),
    ("Vn = γλ√f'c Aj (1.7/1.2/1.0)", "NSCP 2015", "Table 418.8.4.1, §418.8.4.2", "4-118", "joint shear strength"),
    ("Aj, bj ≤ b + h, b + 2x, column width", "NSCP 2015 / ACI 318-25M", "§418.8.4.3 / R15.5.2.2", "4-118 / 231-232", "effective area"),
    ("φ = 0.85", "NSCP 2015", "§421.2.4.3", "4-141", "joint φ"),
    ("Vcol from ΣMpr / ℓc", "NIST GCR 8-917-1", "§5.2, Figs. 5-4/5-5", "13-14", "free body"),
    ("ℓdh = fy db/(5.4λ√f'c)", "NSCP 2015", "§418.8.5.1", "4-118", "hooked bars"),
]


def joint_md(res):
    L = [f"# Joint {res['id']} — SMF beam-column joint, direction {res.get('direction', '-')} (NSCP 2015 §418.8)\n"]
    L.append(f"**Verdict: {res['verdict']}** · Vj = {res['Vj']:,.1f} kN · φVn = {res['phiVn']:,.1f} kN · "
             f"D/C = {_f(res['DC'], 3)}\n")
    L.append(f"- Bar forces T (1.25 fy As): top {', '.join(f'{t:,.1f}' for t in res['T_top'])} kN; "
             f"bottom {', '.join(f'{t:,.1f}' for t in res['T_bot'])} kN")
    L.append(f"- Column shear Vcol = {', '.join(f'{v:,.1f}' for v in res['Vcol'])} kN — {res['Vcol_basis']}")
    L.append(f"- Vj for the two sway senses = {', '.join(f'{v:,.1f}' for v in res['Vj_sway'])} kN")
    L.append(f"- bj = {res['bj']:.0f} mm, Aj = {res['Aj']:,.0f} mm², γ = {res['gamma']} ({res['category']} faces "
             "confined; a face counts only if the beam is ≥ ¾ of the effective joint width, §418.8.4.2)")
    L.append(f"- Joint hoops: {res['joint_hoops_note']}")
    for bm in res["beams"]:
        L.append(f"- Beam {bm.get('id', '')} {bm['b']:.0f}×{bm['h']:.0f}: top {bm['top']}, bottom {bm['bot']}, "
                 f"Mpr− {_f(bm.get('Mpr_neg'))}, Mpr+ {_f(bm.get('Mpr_pos'))} kN·m")
    L.append("\n## Checks\n")
    L.append(_checks_table(res["checks"]))
    L.append("\n## Basis & Citations\n")
    L.append(_basis_table(JOINT_BASIS))
    L.append("\n## Verification\n")
    L.append(VERIFICATION)
    L.append("\n## Not checked\n")
    for n in res["not_checked"]:
        L.append(f"- {n}")
    return "\n".join(L) + "\n"


FOOTING_BASIS = [
    ("Base area from unfactored loads", "NSCP 2015", "§413.3.1.1", "4-84", "service sizing (OCR, vault note 01)"),
    ("ASD combinations 203-8..203-12, 0.6D rows", "NSCP 2015", "§203.4.1, §203.4.2", "2-11", "read visually 2026-09-28"),
    ("Strength combinations 203-1..203-7", "NSCP 2015", "§203.3.1", "2-11", "read visually 2026-09-28"),
    ("Kern e ≤ B/6", "W&M 7th", "Eq. (15-5)", "831", "full contact"),
    ("Critical sections", "ACI 318-25M", "§13.2.7.1–.2", "210-211", "face / d / d/2"),
    ("Two-way vc (no λs)", "NSCP 2015", "Table 422.6.5.2", "4-148", "punching (OCR, vault)"),
    ("Moment transfer γv Msc", "ACI 318-25M", "§8.4.2.2.2, §8.4.4.2.2–.3", "116-119", "eccentric shear"),
    ("One-way Vc = 0.17λ√f'c bd", "NSCP 2015", "§422.5.5.1", "4-145", "read visually 2026-09-28"),
    ("As,min two-tier", "NSCP 2015", "Table 407.6.1.1 / 408.6.1.1 via 413.3.3.1", "4-84", "dp_foundation"),
    ("Band γs = 2/(β+1)", "ACI 318-25M", "§13.3.3.3", "212", "rectangular footings"),
    ("Bar spacing (crack control)", "ACI 318-25M / NSCP", "Table 24.3.2 / 424.3.2", "503 / 4-158", "fs = ⅔fy"),
    ("Depth above bottom bars ≥ 150 mm", "ACI 318-25M", "§13.3.1.2", "211", "minimum depth"),
    ("Bearing on concrete", "ACI 318-25M", "§22.8.3", "468", "φ 0.65"),
    ("Cover 75 mm", "NSCP 2015", "Table 420.6.1.3.1", "4-136", "cast against ground"),
    ("Sliding ceilings", "NSCP 2015", "Table 304-1 + footnote", "3-13", "OCR, provisional rows"),
]


def footing_md(res):
    L = [f"# Footing {res['id']} — isolated spread footing (NSCP 2015)\n"]
    L.append(f"**Verdict: {res['verdict']}** · engine: vault `dp_foundation.py` (vendored) + {res['tool']}\n")
    L.append("## 1. Schedule\n")
    for k, v in res["schedule"].items():
        L.append(f"- **{k}**: {v}")
    s = res["soil"]
    L.append(f"\n- Soil (project inputs, **not vault-cited**): q_allow = {s['q_allow']} kPa gross, γs = {s['gamma_soil']} kN/m³, "
             f"Df = {s['Df']} m, μ = {s.get('mu')}, FS overturning {s['FS_overturning']}, FS sliding {s['FS_sliding']}")
    L.append(f"- Loads: {_loads_line(res['loads'])}")
    L.append("\n## 2. Service combinations — NSCP 2015 §203.4.1 (+ 0.6D stability rows)\n")
    L.append(_combos_table(res["combinations_service"]))
    L.append("\n## 3. Strength combinations — NSCP 2015 §203.3.1\n")
    L.append(_combos_table(res["combinations_strength"]))
    st = res["strength"]
    L.append("\n## 4. Factored soil pressure and punching per combination\n")
    L.append("| Combo | Pu (kN) | Mxu | Myu | q_max (kPa) | contact | punching D/C |")
    L.append("|---|---|---|---|---|---|---|")
    for d in st["per_combo"]:
        if "Pu" in d:
            L.append(f"| {d['id']} | {_f(d['Pu'])} | {_f(d['Mxu'])} | {_f(d['Myu'])} | {_f(d['q_max'])} | "
                     f"{d['contact']:.0%} | {_f(d['punch_ratio'], 3)} |")
    L.append("\n## 5. Checks\n")
    L.append(_checks_table(res["checks"]))
    L.append("\n## 6. Basis & Citations\n")
    L.append(_basis_table(FOOTING_BASIS))
    L.append("\n## 7. Verification\n")
    L.append("**Partially verified.** Engine = the vault's `dp_foundation.py` (self-test 86 guards, vendored "
             "unchanged); its NSCP constants are OCR-transcribed (2026-08-25) except the folios re-read visually "
             "on 2026-09-28 (2-11, 4-144, 4-145). The no-tension pressure solver is checked against the closed-form "
             "uniaxial partial-contact solution (`tests/run_benchmarks.py`).")
    L.append("\n## 8. Summary — warnings and not checked\n")
    for w in res["warnings"]:
        L.append(f"- ⚠ {w}")
    for n in res["not_checked"]:
        L.append(f"- Not checked: {n}")
    return "\n".join(L) + "\n"


def project_md(proj, results, combos_md):
    L = [f"# {proj.get('project', 'Project')} — RC design package (NSCP 2015)\n"]
    L.append(f"Generated by apec-col-design (project runner). Every member below was designed for the NSCP 2015 "
             f"§203.3.1 strength combinations generated from its unfactored load cases; footings also use the "
             f"§203.4.1 service combinations.\n")
    ld = proj.get("loads") or {}
    L.append(f"- Load settings: f1 = {ld.get('f1', 0.5)}, ρ = {ld.get('rho', 1.0)}, Ca = {ld.get('Ca', 0)}, "
             f"I = {ld.get('I', 1.0)}, orthogonal 100/30 = {ld.get('orthogonal', False)}\n")
    L.append("| Type | ID | Verdict | Governing / schedule |")
    L.append("|---|---|---|---|")
    for kind, lst in results.items():
        for r in lst:
            if kind == "columns":
                g = r["governing"]
                txt = (f"{r['schedule']['longitudinal']}; DC {max(g['DC_M'], g['DC_PMM'] or 0):.2f} "
                       f"({g['combo']} {g['eq']})")
            elif kind == "beams":
                sch = r.get("schedule") or {}
                txt = "; ".join(f"{st} T {sch[st]['top']} B {sch[st]['bot']}" for st in ("I", "M", "J") if st in sch)
            elif kind == "joints":
                txt = f"Vj {r['Vj']:.0f} kN vs φVn {r['phiVn']:.0f} kN (γ {r['gamma']})"
            else:
                txt = f"{r['schedule']['plan']}; {r['schedule']['bars_x']}"
            L.append(f"| {kind[:-1]} | {r['id']} | **{r.get('verdict')}** | {txt} |")
    L.append("\nEach member has its own JSON (full numbers) and Markdown sheet in its folder; "
             "`combinations.md` lists the generated combinations per member.\n")
    L.append("> Technical basis: the Structural Mind vault (`vault/reference/`). Office defaults and project "
             "inputs (q_allow, FS, unit weights, bar sizes) are marked **(not vault-cited)** in each sheet.")
    return "\n".join(L) + "\n"
