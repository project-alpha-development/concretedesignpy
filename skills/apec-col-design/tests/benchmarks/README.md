# Benchmarks

Run: `python3 ~/.claude/skills/apec-col-design/tests/run_benchmarks.py` — must print `ALL PASS`
(79 checks, < 5 s).

| File | Kind | What it pins |
|---|---|---|
| `wm_11_1_interaction.json` | textbook | W&M 7th Ex 11-1: Po, φPn,max, Pnt and the Z = −1, −2, −4 and εt = 0.005 points (Pn, Mn, φ) |
| `wm_11_5_biaxial.json` | textbook | W&M 7th Ex 11-5: Pn, Mnx, Mny, εt for a prescribed inclined neutral axis |
| `wm_11_7_bresler.json` | textbook | W&M 7th Ex 11-7: the exact P-M-M check passes; Bresler φPn; chart-read φPnx/φPny (±5 %) |
| `wm_19_2_smf_column.json` | textbook | W&M 7th Ex 19-2: NSCP combos reproduce Table 19-5; ℓo, hx, nl, kn, Ash/s (a)(b)(c), Mpr, Ve, d, Av/s, Vc |
| `wm_19_3_joint.json` | textbook | W&M 7th Ex 19-3: Vj, φVn, γ |
| `vault_c05_joint.json` | vault worked value | Concrete/05 §5: T, Vj, φVn at γ 1.7 — **and the finding that γ is 1.0 by §418.8.4.2** |
| `nscp_combos.json` | code | NSCP §203.3.1/§203.4 factors incl. Ev = 0.5CaI (Ca 0.523): counts and key rows |
| `footing_no_tension.json` | statics | rigid-base pressure inside and outside the kern vs the closed form |

Plus guards (zero steel, Pu > φPn,max, pure axial), physics (DC = 1 on the surface both ways; the
biaxial penalty larger above n = 0.05; circle direction-independence; circle Po) and smoke runs
(circular spiral SMF column, gravity column, footing, the example project → zip).

**Units.** W&M examples are in US units and are converted exactly (1 in = 25.4 mm,
1 ksi = 6.894757 MPa, 1 kip = 4.448222 kN). Ex 11-1 overrides β1 = 0.80 (the SI expression gives
0.804 at 34.47 MPa). SI coefficients differ from the in-lb ones by up to 2.4 % (Vc 0.17 vs 2√psi;
joint 1.7 vs 20√psi) — those pins carry 3 %.

**What is deliberately not pinned:** W&M Fig. 19-27 φMn chart reads (they match neither φMn(Pn = Pu)
nor φMn(φPn = Pu)); W&M's 6-in hoop pitch (152.4 mm > the SI 150 mm cap — the SI run uses 150).

## ⚠ Open — past APEC columns needed

The rc-design pattern pins at least one issued APEC member. No issued APEC column calculation with
published capacities was reachable (the only column file found in the project folders is a
pushover performance summary without P-M numbers). To add one: copy `wm_19_2_smf_column.json`, put the
section, bars, hoops, load cases and the issued calc-sheet values under `expected`, and add a runner.
Good candidates: an interior SMF column with beams on four sides, a corner column (orthogonal 100/30),
and a footing with partial contact under E/1.4.
