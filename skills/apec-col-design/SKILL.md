---
name: apec-col-design
description: Design or check reinforced-concrete columns for APEC projects to NSCP 2015 (ACI 318M-14 provisions, coefficients page-checked in ACI 318-25M) — P-M interaction (uniaxial), P-M-M biaxial strain compatibility (load contour and radial D/C, Bresler cross-check), and special moment frame (SMRF) columns per NSCP 418.7 (strong column–weak beam, ℓo, hx, Ash/ρs confinement, capacity-design shear Ve from Mpr with the beam cap, Vc = 0 in ℓo, φ 0.60 rule), plus SMF beam-column joints (418.8), isolated spread footings, and a project runner that designs beam (via rc-design) + column + joint + footing and compiles every calc sheet, JSON and P-M plot into one zip. Every member is designed for the NSCP 2015 §203.3.1 load combinations generated from its unfactored load cases (E = ρEh + Ev, Ev = 0.5CaID, 100/30 orthogonal; §203.4 service set for footings). Use when the user types /apec-col-design, asks to design or size column bars and ties/hoops, check a column schedule, draw a P-M or P-M-M interaction diagram, check biaxial bending, get column Mpr/Ve, check strong-column/weak-beam or SMRF column/joint detailing, design a footing under a column, or compile beam/column/joint/footing results for a building.
---

# apec-col-design — RC columns, joints and footings (NSCP 2015)

Turns a column's section, materials and **unfactored load cases** into a bar and hoop schedule
with a pass/fail check list, P-M and P-M-M figures and a cited calc sheet. `scripts/project.py`
does the same for a set of beams, columns, joints and footings and zips everything.

**Technical basis** is the Structural Mind vault (`~/Desktop/Programs/structural-mind/Structural Mind/vault/`)
and the rectified `concretedesignpy` (`CLAUSES.md` Option A: NSCP 2015 governs). Every clause, printed
page and NSCP folio is in `references/nscp_clauses.md` (✅ = NSCP page read visually 2026-09-28).
The vault rules apply: **cite `vault/reference/` only**, mark office defaults and project inputs
**(not vault-cited)**, and where there is no basis say exactly:
> The reference folder does not contain enough basis to support this answer.

## Workflow

1. **Collect inputs.** Ask only for what is missing and material; default the rest from
   `references/apec_standards.md` and say which defaults you used. Schema: `references/inputs.md`.
   - Column: `section` (b, h or D, cover), `materials`, `geometry.lu` (clear height, required for SMF),
     and **`cases`** — per unfactored load case `P, Mx_top, Mx_bot, My_top, My_bot, Vx, Vy`.
   - **Seismic parameters are required when E cases exist:** `loads.Ca`, `loads.I`, `loads.rho`;
     set `loads.orthogonal: true` for columns in two intersecting frames (§208.7.1).
   - SMF strong column / Ve cap: `joints.top/bottom.Mx|My` with `Mnb` (both sways) and `Mpr_b`, or
     let `project.py` take them from the designed beams (`beam_ends`). Without them strong-column is
     NOT checked and Ve uses the column Mpr (conservative) — say so.
   - Keep **project facts** (MIDAS forces, drawings, Slack instructions — attribute and date them)
     apart from **technical basis** (vault references).
2. **Choose the scope.** One column → `design_column.py`. One joint → `joint.py`. One footing →
   `footing.py`. A building or a column line, or the user wants **everything compiled** → `project.py`
   (beams via rc-design, then columns, joints, footings; one zip).
   Design mode = no `bars` / `hoops`; check mode = give them (either may be checked alone).
3. **Write the input JSON** in the scratchpad (or the project folder the user names). Start from
   `--template` (`design_column.py`, `joint.py`, `footing.py`, `project.py`; the project template is
   `examples/project_two_storey.json`).
4. **Run**
   - `python3 ~/.claude/skills/apec-col-design/scripts/design_column.py in.json --out res.json --report calc.md --plots figs --summary`
   - `python3 ~/.claude/skills/apec-col-design/scripts/project.py project.json --out DIR` → `DIR/<project>_results.zip`
   (exit code 1 = at least one FAIL). If you changed any script, run
   `python3 ~/.claude/skills/apec-col-design/tests/run_benchmarks.py` first — it must print `ALL PASS`.
5. **Report** in the vault output format:
   1. **Answer** — verdict, the schedule (bars, hoops in ℓo and beyond, ℓo, splice zone), the governing
      combination with its D/C, and the one or two checks that govern.
   2. **Basis & Citations** — table Point | Reference | Clause | Page | Relevance from the `clause`/`page`
      fields and `references/nscp_clauses.md`. Quote an NSCP folio as read only where it carries ✅.
   3. **Verification** — "Partially verified" by default (solver benchmarked on W&M 11-1/11-5/11-7/19-2/19-3;
      NSCP §203, §208.6.1, §208.7.1, §418.7, §418.8, §421.2, §422.4–422.5 read visually 2026-09-28).
   4. **Summary** — every WARN, the `warnings` that matter, and the `not_checked` list.
   Point to the calc sheet / zip; do not paste the JSON. Send the zip with `SendUserFile` when asked for it.
6. **If the verdict is FAIL**, name the gate: P-M-M (section or f′c), ρ > 0.06 (SMF), strong column
   (column Mn vs beam Mn — bigger column or lighter beams), 422.5.1.2 section limit (no hoop fixes it),
   Ash / hx (more legs, larger hoop, more bars), joint γ (beams < ¾ of the joint width do not confine),
   bearing / punching (plan size, thickness).

## Non-negotiables — do not "simplify" them away

- **Load combinations are generated, never assumed.** NSCP 2015 §203.3.1 from the unfactored cases,
  E = ρEh + Ev with **±Ev paired with ±Eh** (the literal "+E" misses (0.9 − 0.5CaI)D + ρEh uplift);
  footings add §203.4.1 service combinations and the 0.6D stability rows. List them in the report.
- **Biaxial is strain compatibility, not Bresler.** The neutral axis is rotated until the moment vector
  matches the demand direction (W&M Ex 11-5); Bresler is printed as a cross-check only.
- **No silent zeros.** Pu > φPn,max, tension beyond φPnt, or zero steel give D/C = ∞ and FAIL.
- **Mpr is evaluated over the whole E axial range** (max), Mnc for strong column at Pn = Pu (min over
  the E range, both senses), Mn for the §421.2.4.1 φ rule at its max.
- **Ve** = max(analysis Vu, min(column-Mpr shear, beam-Mpr joint shear)); report the column-Mpr bound
  when beams govern (Moehle printed 566).
- **Vc = 0 in ℓo** only by §418.7.6.2.1 unless `vc_zero_in_lo: "always"` is chosen; beyond ℓo Vc uses
  the least axial load.
- **φ shear = 0.60 unless Vn ≥ the shear at nominal moment strength** (§421.2.4.1, literal).
- **Joint γ** from NSCP Table 418.8.4.1 with §418.8.4.2's ¾-width confinement test — a 300 mm beam on
  a 500 mm column does not confine the face.
- **Edition discipline** (CLAUSES.md Option A): φ tension-controlled at 0.005, NSCP 3-row joint γ,
  6db hoop spacing, no roof exemption — ACI 318-19/-25 differences are reported as WARN, never adopted.
- **Office defaults are placeholders** (⚠ in `apec_standards.md`) — q_allow, FS, unit weights and k are
  project inputs; never present them as code values.
- Out of scope (say so, do not improvise): development/splice lengths (except 418.8.5.1 hooks), moment
  magnification of slender columns, IMF/OMF, walls, composite/prestressed/hollow sections,
  combined/mat/pile foundations, settlement.

## Files

| Path | Role |
|---|---|
| `scripts/combos.py` | NSCP 2015 §203.3.1 / §203.4 combinations from load cases; Ev, ρ, 100/30, f1 |
| `scripts/section.py` | geometry, bar layouts, Whitney block (polygon clip / circular segment), lateral support, hx |
| `scripts/pm.py` | strain compatibility: φ laws, P-M curves, P-M-M capacity at Pu, radial D/C, Mpr/Mn at P, Bresler |
| `scripts/shear.py` | Vc with axial load, section limit, Av,min, s max, biaxial-shear WARN |
| `scripts/smf.py` | NSCP 418.7: ℓo, hx rule, spacing, Ash/ρs, capacity-design Ve, strong column |
| `scripts/design_column.py` | column driver: combinations → P-M-M → SMF → hoops; `--report`, `--plots`, `--summary` |
| `scripts/joint.py` | NSCP 418.8 joints (rectified concretedesignpy joint_shear + 418.8.2–418.8.5) |
| `scripts/footing.py` + `scripts/vendor/dp_foundation.py` | spread footing on the vault's calculator (vendored unchanged) |
| `scripts/beam.py` | rc-design bridge (subprocess) with the same combinations |
| `scripts/project.py` | beams → columns → joints → footings → sheets + JSON + PNG + summary → **zip** |
| `scripts/report.py`, `scripts/plots.py` | Markdown calc sheets; P-M and P-M-M figures (matplotlib optional) |
| `references/nscp_clauses.md` | clause → ACI 318-25M page → NSCP folio (✅ read); edition positions; findings |
| `references/apec_standards.md` | office defaults (not vault-cited) |
| `references/inputs.md` | JSON schema, axes and sign conventions, MIDAS mapping notes |
| `tests/run_benchmarks.py` + `tests/benchmarks/` | W&M 11-1, 11-5, 11-7, 19-2, 19-3; vault Concrete/05 joint; NSCP combination factors; footing statics; guards; smoke incl. the example zip |
| `examples/project_two_storey.json` | illustrative project (4 beams, 1 SMF column, 2 joints, 1 footing) |
