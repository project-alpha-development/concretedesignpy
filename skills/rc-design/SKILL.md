---
name: rc-design
description: Design or check reinforced-concrete beams to NSCP 2015 (ACI 318M-14 beam provisions, coefficients page-checked in ACI 318-25M) for APEC projects — flexure (As req'd, As,min, εt, φMn), shear (Vc, Vs, Av/s, s_max), torsion (T_th, At/s, Al, section check), SMF seismic capacity design and NSCP 418.6 detailing (Mpr with A′s, Ve on the clear span, Vc = 0 in the hinge, hoop zone), serviceability (deflection with Branson and Bischoff Ie, Table 24.3.2 crack spacing), and the torsion merge (Al into As, At into Av). Use when the user types /rc-design, asks to design or size beam bars and stirrups, check a beam schedule, get Mpr or Ve, check SMRF beam detailing, or gives beam section + Mu/Vu/Tu from MIDAS/ETABS. Takes JSON in, runs a benchmarked solver, returns one JSON plus a cited report.
---

# rc-design — RC beam design and check (NSCP 2015)

Turns a beam's section, materials and factored demands at I / M / J into a bar and stirrup
schedule with a pass/fail check list. `scripts/design_beam.py` runs everything and writes one JSON.

**Technical basis** is the Structural Mind vault (`~/Desktop/Programs/structural-mind/Structural Mind/vault/`)
and the rectified `concretedesignpy` (`~/Desktop/Projects/concretedesignpy/CLAUSES.md`). Every clause,
printed page and NSCP twin folio is in `references/nscp_clauses.md`. The vault rules apply:
**cite `vault/reference/` only**, mark office defaults **(not vault-cited)**, and where there is no
basis say exactly:
> The reference folder does not contain enough basis to support this answer.

## Workflow

1. **Collect inputs.** Ask only for what is missing and material; default the rest from
   `references/apec_standards.md` and say which defaults you used.
   - Required: `section.b`, `section.h`; `span.L` (m, centreline); `demand` at `I`, `M`, `J` —
     `Mu_neg`, `Mu_pos` (kN·m, magnitudes), `Vu` (kN), and `Tu` (kN·m) / `Nu` (kN, + compression) if any.
   - `frame`: `"SMF"` (default) or `"gravity"`. For SMF also give `columns.hc_i`, `columns.hc_j`
     (mm, column depth along the beam → clear span ln) and `gravity.wD`, `gravity.wL` (kN/m, service
     D incl. SDL, and L) for Ve. Without column depths the script falls back to L and **warns** —
     say so in the report.
   - Serviceability: `service.support` (`simple`, `one_end_continuous`, `both_continuous`,
     `cantilever`), `service.wD`, `service.wL`; `Ma_D`, `Ma_DL` from the model when available.
   - Keep **project facts** (MIDAS forces, drawings, Slack instructions — attribute and date them)
     apart from **technical basis** (vault references).
2. **Choose the mode.** Design mode selects bars and stirrups. Check mode (`"provided"` block with
   `[n, db]` per face per station and `stirrups: {"hinge"|"ends": [legs, db, s], "mid": [...]}`)
   checks an existing schedule and resizes nothing.
3. **Write the input JSON** in the scratchpad (or the project folder the user names). Start from
   `python3 ~/.claude/skills/rc-design/scripts/design_beam.py --template`. Several beams →
   `{"cases": [...]}`.
4. **Run**
   `python3 ~/.claude/skills/rc-design/scripts/design_beam.py input.json --out result.json --summary`
   (exit code 1 = at least one beam FAILs). If you changed any script, run
   `python3 ~/.claude/skills/rc-design/tests/run_benchmarks.py` first and fix anything that is not `ALL PASS`.
5. **Report** in the vault output format:
   1. **Answer** — verdict, the schedule (top/bottom bars at I/M/J, side bars, stirrups per zone),
      and the one or two checks that govern.
   2. **Basis & Citations** — table Point | Reference | Clause | Page | Relevance, taken from the
      `clause`/`page` fields of the checks and from `references/nscp_clauses.md`. ACI 318-25M pages are
      printed pages; NSCP folios only as "twin" unless the page was read this session.
   3. **Verification** — "Partially verified" by default (solver benchmarked; clause pages from the
      vault and a text-layer read of ACI 318-25M). Upgrade only for pages re-read this session.
   4. **Summary** — every `WARN`, every `warnings` line that matters, and the `not_checked` list.
   Point to `result.json`; do not paste it into chat.
6. **If the verdict is FAIL**, name the gate: flexure/εt (bigger section or bar), 22.5.1.2 or 22.7.7.1
   (the **section** is too small — no stirrup fixes it), SMF ratio / ρ / joint depth (detailing),
   stirrup selection (more legs or larger bar), crack spacing or deflection (more smaller bars, depth).

## Non-negotiables — from the vault reviews; do not "simplify" them away

- **No silent zeros.** Zero capacity is D/C = ∞ and FAIL, never 0.0 and OK (Software/12 D1/D2).
- **Mpr includes A′s** — strain compatibility at 1.25 fy, φ = 1.0. The tension-only closed form
  understates Mpr by 8–26 % (Software/12 D3).
- **Ve uses the clear span ln**, both sway directions, plus gravity wu·ln/2 with SDL **and** live load
  (D4, D5). The horizontal analysis shear is not added on top of Vpr.
- **Vc = 0 in the hoop zone** when Vpr ≥ ½ Ve and Pu < Ag f′c/20 (§18.6.5.2).
- **Torsion:** Aoh on the stirrup centreline; Al divisor is **1.7 Aoh**, not 2 Aoh (15 % short);
  s ≤ min(ph/8, **300**); Al,min coefficient **0.42**; Tth coefficient **0.083** with the Nu term.
  Torsion steel is **added** to flexure and shear steel (§9.5.4.3) — `combine.py` does this.
- **Av,min** is 0.062√f′c bw/fyt (not 1/16) and applies on the strength branch too.
- **Edition discipline.** NSCP 2015 governs (CLAUSES.md Option A): φ tension-controlled at 0.005,
  Vc = ⅙√f′c bw d, no λs. Do not "fix" these to ACI 318-19 — that is an edition change. When
  fy > 420 MPa rerun with `"phi_rule": "envelope"` and report the gap.
- **φMn is not monotone in bar count** — the design scan tests every count; never size with a
  closed-form `ceil()`.
- Out of scope (say so, do not improvise): development/hooks/splices, cut-offs, joint shear
  (`concretedesignpy.calculators.joint_shear`), strong-column/weak-beam, IMF, flanged sections,
  hollow torsion, deep beams.

## Files

| Path | Role |
|---|---|
| `scripts/flexure.py` | β1, φ law, As,min, bar layers, strain-compatibility φMn, design scan |
| `scripts/shear.py` | Vc (NSCP), Av/s, section limit, Av,min, s_max |
| `scripts/torsion.py` | Tth/Tcr, At/s, Al, Al,min, section check, compatibility torsion |
| `scripts/seismic.py` | Mpr, Vpr, Ve, Vc = 0 rule, 418.6 detailing, joint depth, hoop limits |
| `scripts/serviceability.py` | min depth, Ie (Branson/Bischoff), long-term deflection, crack spacing |
| `scripts/combine.py` | Al split into As and side bars; (Av + 2At)/s; stirrup selection |
| `scripts/design_beam.py` | runs all; one JSON out; `--template`, `--defaults`, `--summary` |
| `references/nscp_clauses.md` | clause → ACI 318-25M page → NSCP folio; edition positions; vault links |
| `references/apec_standards.md` | bar sizes, cover, rounding, material defaults (office practice) |
| `tests/run_benchmarks.py` + `tests/benchmarks/` | APEC beam id 25 + W&M 4-1M, 4-4, 6-1M, 7-2 + crack-spacing pin + no-silent-zero guards |
