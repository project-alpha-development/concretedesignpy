"""
plots.py -- figures for the column calc sheet (matplotlib, Agg).  Optional: every
function returns [] when matplotlib is missing, and the report says so.

* P-M diagram about x and about y: design curve (phi Pn - phi Mn, capped at phi Pn,max),
  nominal Pn - Mn, probable Pn - Mpr (1.25 fy, phi = 1), and every factored demand point
  (both ends of every NSCP combination).
* Mx-My load contour (phi Mn at constant Pu) for the governing combination, the largest
  and the least Pu, with the demand moment vector.
"""

import os

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception:                                    # pragma: no cover
    HAVE_MPL = False

INK, MUTED, ACC, WARN_C, OK_C = "#1f2937", "#9ca3af", "#2563eb", "#dc2626", "#059669"


def _pm_axes(ax, curves, curves_pr, cap, axis):
    for sgn, key in ((1, "pos"), (-1, "neg")):
        pts = curves[axis][key]
        m = [sgn * abs(p["phiMn"]) for p in pts]
        p = [p["phiPn"] for p in pts]
        ax.plot(m, p, color=ACC, lw=2.0, label="design  phiPn-phiMn" if sgn > 0 else None)
        m = [sgn * abs(q["Mn"]) for q in pts]
        p = [q["Pn"] for q in pts]
        ax.plot(m, p, color=MUTED, lw=1.2, ls="--", label="nominal  Pn-Mn" if sgn > 0 else None)
        pr = curves_pr[axis][key]
        ax.plot([sgn * abs(q["Mn"]) for q in pr], [q["Pn"] for q in pr], color=INK, lw=0.9, ls=":",
                label="probable  Pn-Mpr (1.25fy)" if sgn > 0 else None)
    ax.axhline(cap["phiPn_max"], color=ACC, lw=0.8, ls="-.")
    ax.text(0, cap["phiPn_max"], "  phiPn,max", va="bottom", fontsize=7, color=ACC)
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.axvline(0, color=MUTED, lw=0.6)


def column_figures(res, outdir):
    if not HAVE_MPL:
        return []
    os.makedirs(outdir, exist_ok=True)
    files = []
    cid = str(res.get("id", "column")).replace("/", "-").replace(" ", "_")
    cap = res["capacity"]
    for axis, mkey in (("x", "Mux"), ("y", "Muy")):
        fig, ax = plt.subplots(figsize=(6.2, 6.0), dpi=130)
        _pm_axes(ax, res["pm_curves"], res["pm_curves_probable"], cap, axis)
        ok = [r for r in res["pmm"] if max(r["DC_M"], r["DC_PMM"] or 0) <= 1.0]
        bad = [r for r in res["pmm"] if max(r["DC_M"], r["DC_PMM"] or 0) > 1.0]
        ax.scatter([r[mkey] for r in ok], [r["Pu"] for r in ok], s=14, color=OK_C, zorder=5,
                   label=f"demands ({len(res['pmm'])} = combos x 2 ends)")
        if bad:
            ax.scatter([r[mkey] for r in bad], [r["Pu"] for r in bad], s=22, color=WARN_C, marker="x",
                       zorder=6, label="demand outside")
        g = res["governing"]
        ax.scatter([g[mkey]], [g["Pu"]], s=60, facecolors="none", edgecolors=INK, zorder=7,
                   label=f"governing {g['combo']} ({g['eq']})")
        ax.set_xlabel(f"M{axis} (kN.m)   [+M{axis} compresses the +{'y' if axis == 'x' else 'x'} face]")
        ax.set_ylabel("P (kN, compression +)")
        ax.set_title(f"{res.get('id')} -- P-M about {axis}  ({res['schedule']['longitudinal']})", fontsize=9)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7, loc="lower right")
        f = os.path.join(outdir, f"{cid}_PM_{axis}.png")
        fig.tight_layout()
        fig.savefig(f)
        plt.close(fig)
        files.append(os.path.basename(f))
    if res.get("contours"):
        fig, ax = plt.subplots(figsize=(6.2, 6.0), dpi=130)
        colors = [ACC, OK_C, "#7c3aed", "#d97706"]
        for i, (lab, c) in enumerate(res["contours"].items()):
            pts = c["pts"] + c["pts"][:1]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=colors[i % 4], lw=1.6,
                    label=f"phiMn at Pu = {c['Pu']:.0f} kN ({lab})")
        g = res["governing"]
        ax.annotate("", xy=(g["Mux"], g["Muy"]), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="->", color=WARN_C, lw=1.5))
        ax.scatter([g["Mux"]], [g["Muy"]], color=WARN_C, s=30, zorder=5,
                   label=f"governing demand {g['combo']} {g['end']} (DC_M {g['DC_M']:.2f})")
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.axvline(0, color=MUTED, lw=0.6)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel("Mx (kN.m)")
        ax.set_ylabel("My (kN.m)")
        ax.set_title(f"{res.get('id')} -- P-M-M load contours", fontsize=9)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7, loc="upper right")
        f = os.path.join(outdir, f"{cid}_PMM_contour.png")
        fig.tight_layout()
        fig.savefig(f)
        plt.close(fig)
        files.append(os.path.basename(f))
    return files
