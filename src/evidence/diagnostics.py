"""Brief 9, Task 5: error diagnostics from the saved test predictions (descriptive; post-hoc check, not a
pre-registered test).

Run from the repo root:
    python -m src.evidence.diagnostics

All on the 2,457 scored test hours (D27 common hours), read from data/processed/test_predictions.parquet
the way src/modeling/reserve.py does. No model is refitted and nothing is rescored. Models: HGB, CAISO as
published, persistence D-2, each against EIA.

Charts (PNG, 200 dpi, white background, colors, fonts and axis style of src/modeling/capstone3_figures.py,
no title; the slide supplies it) in deck/capstone3/figures/, data in reports/:
  evidence_actual_vs_forecast   hexbin of actual against forecast, HGB and CAISO, GW, 1-to-1 line
  evidence_error_histogram      forecast minus actual as % of capacity_mw (installed solar of that hour)
  evidence_error_by_hour        nMAE (%) and mean error (MW) by Pacific hour of the hour start
  evidence_backup_curve         MW of backup against coverage 50 to 99%: the overshoot quantile as a share of
                                capacity_mw, times the EIA 860M nameplate of 2026-09, all CISO (as reserve.py);
                                the 90, 95 and 99 points must equal reports/reserve_test.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from src.evidence.common import LABEL as NOTE, load_test, reproduce
from src.modeling.capstone3_figures import (AXIS, COLOR, FIG_DIR, GRID, INK, INK2, LABEL, MUTED, REPORTS,
                                            TEST_SHADE, plt, style)
from src.modeling.reserve import FLEET_MONTH, OUT_CSV as RESERVE_CSV, fleet_mw
from src.modeling.score_models import metrics

MODELS = ["hgb", "caiso_published", "persistence_d2"]
WHITE = "#ffffff"
DPI = 200
COUNTS = LinearSegmentedColormap.from_list("counts", ["#e8f1fc", "#86b6ef", TEST_SHADE, "#0d2f5c"])


def fig_axes(ncols: int = 1, **kw):
    fig, axes = plt.subplots(1, ncols, figsize=(16, 9), dpi=DPI / 2, **kw)
    fig.patch.set_facecolor(WHITE)
    for ax in np.atleast_1d(axes):
        ax.set_facecolor(WHITE)
    return fig, axes


def save(fig, name: str, data: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.png", dpi=DPI, facecolor=WHITE)
    plt.close(fig)
    data = data.copy()
    data["note"] = NOTE
    data.to_csv(REPORTS / f"{name}.csv", index=False)
    print(f"  deck/capstone3/figures/{name}.png  (data: reports/{name}.csv, {len(data):,} rows)")


def actual_vs_forecast(s: pd.DataFrame) -> None:
    fig, axes = fig_axes(2, sharex=True, sharey=True)
    fig.subplots_adjust(top=0.97, bottom=0.12, left=0.07, right=0.87, wspace=0.12)
    top = np.ceil(max(s[["actual", "hgb", "caiso_published"]].max()) / 1000 / 5) * 5
    hb = None
    for ax, m in zip(axes, ["hgb", "caiso_published"]):
        style(ax, ygrid=False)
        hb = ax.hexbin(s[m] / 1000, s["actual"] / 1000, gridsize=34, extent=(0, top, 0, top), cmap=COUNTS,
                       mincnt=1, linewidths=0.2, edgecolors=WHITE)
        ax.plot([0, top], [0, top], color=INK, linewidth=2, linestyle="--")
        ax.text(top * 0.30, top * 0.36, "forecast = actual", ha="center", va="center", fontsize=16, color=INK2,
                rotation=45, rotation_mode="anchor")
        nm = metrics(s, m)
        ax.text(0.03, 0.97, f"{LABEL[m]}\nnMAE {nm['nmae_pct']:.2f}%, bias {nm['bias_mw']:+,.0f} MW",
                transform=ax.transAxes, va="top", fontsize=19, color=INK)
        ax.set_xlabel("Forecast (GW)")
        ax.set_xlim(0, top), ax.set_ylim(0, top), ax.set_aspect("equal")
    axes[0].set_ylabel("Actual output, EIA (GW)")
    cb = fig.colorbar(hb, cax=fig.add_axes([0.905, 0.22, 0.014, 0.6]))
    cb.set_label("Hours in each cell", color=INK2, labelpad=18)
    cb.outline.set_edgecolor(AXIS)
    fig.text(0.02, 0.01, f"{len(s):,} daylight test hours, Pacific dates 2026-04-10 to 2026-10-17. Below the line: "
             "forecast too high.", fontsize=14, color=INK2)
    save(fig, "evidence_actual_vs_forecast",
         s[["local_start", "actual", "capacity_mw", "curt_mwh"] + MODELS].reset_index())


def error_histogram(s: pd.DataFrame) -> None:
    fig, ax = fig_axes()
    style(ax)
    edges = np.arange(-40, 41, 1.0)
    rows = []
    for m in MODELS:
        e = (s[m] - s["actual"]) / s["capacity_mw"] * 100
        clipped = e.clip(edges[0] + 0.01, edges[-1] - 0.01)
        cnt, _ = np.histogram(clipped, edges)
        ax.stairs(cnt, edges, color=COLOR[m], linewidth=3, label=f"{LABEL[m]} (median {e.median():+.1f}%)")
        for lo, hi, c in zip(edges[:-1], edges[1:], cnt):
            rows.append(dict(model=m, bin_low_pct=lo, bin_high_pct=hi, hours=int(c)))
        rows.append(dict(model=m, bin_low_pct=None, bin_high_pct=None, hours=int(((e < edges[0]) | (e > edges[-1])).sum()),
                         ))
    ax.axvline(0, color=INK2, linewidth=1.5)
    ax.set_xlabel("Forecast minus actual, % of installed solar (positive: forecast too high)")
    ax.set_ylabel("Daylight test hours")
    ax.set_xlim(-40, 40)
    ax.legend(frameon=False, loc="upper left")
    fig.subplots_adjust(top=0.95, bottom=0.15)
    fig.text(0.02, 0.01, f"{len(s):,} daylight test hours; 1-point bins; errors beyond ±40% are counted in the end bins. "
             "Installed solar: EIA 860M monthly nameplate, all CISO.", fontsize=14, color=INK2)
    d = pd.DataFrame(rows)
    d.loc[d["bin_low_pct"].isna(), "bin_low_pct"] = np.nan
    save(fig, "evidence_error_histogram", d.assign(
        bin=lambda x: np.where(x["bin_low_pct"].isna(), "beyond ±40 (included in end bins)", "")))


def error_by_hour(s: pd.DataFrame) -> pd.DataFrame:
    hour = s["local_start"].dt.hour
    rows = []
    for h, g in s.groupby(hour):
        for m in MODELS:
            r = metrics(g, m)
            rows.append(dict(hour=h, model=m, hours=len(g), nmae_pct=r["nmae_pct"], mean_error_mw=r["bias_mw"]))
    d = pd.DataFrame(rows)
    fig, axes = fig_axes(2, sharex=True)
    for ax, col, lab in [(axes[0], "nmae_pct", "nMAE (% of installed solar)"),
                         (axes[1], "mean_error_mw", "Mean error, forecast minus actual (MW)")]:
        style(ax)
        for m in MODELS:
            x = d[d["model"] == m]
            ax.plot(x["hour"], x[col], color=COLOR[m], linewidth=3, marker="o", markersize=8,
                    markeredgecolor=WHITE, markeredgewidth=2, label=LABEL[m])
        ax.set_xlabel("Pacific hour of day (hour starting)")
        ax.set_ylabel(lab)
    axes[1].axhline(0, color=INK2, linewidth=1.5)
    axes[0].set_ylim(bottom=0)
    for ax in axes:
        ax.set_xticks(range(6, 20, 2))
        ax.set_xlim(5.5, 19.5)
    h0, l0 = axes[0].get_legend_handles_labels()
    fig.legend(h0, l0, frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.99))
    n = d.groupby("hour")["hours"].first()
    fig.text(0.02, 0.01, f"{len(s):,} daylight test hours; hours with fewer than 50 test hours: "
             + (", ".join(f"{h}:00 ({c})" for h, c in n[n < 50].items()) or "none"), fontsize=14, color=INK2)
    fig.subplots_adjust(wspace=0.3, bottom=0.14, top=0.88)
    save(fig, "evidence_error_by_hour", d.round(4))
    return d


def backup_curve(s: pd.DataFrame) -> pd.DataFrame:
    fleet = fleet_mw()
    rows = []
    for m in MODELS:
        over = (s[m] - s["actual"]).clip(lower=0)
        share = over / s["capacity_mw"]
        for c in range(50, 100):
            q = c / 100
            rows.append(dict(model=m, coverage_pct=c, overshoot_mw_test=round(over.quantile(q), 0),
                             share_of_capacity_pct=round(share.quantile(q) * 100, 2),
                             mw_today_fleet=round(share.quantile(q) * fleet, -1)))
    d = pd.DataFrame(rows)
    saved = pd.read_csv(RESERVE_CSV)
    saved = saved[(saved["season"] == "all") & saved["model"].isin(MODELS)]
    for r in saved.itertuples():
        c = int(r.quantile[1:])
        mine = d[(d["model"] == r.model) & (d["coverage_pct"] == c)].iloc[0]
        if mine["mw_today_fleet"] != r.mw_today_fleet or mine["overshoot_mw_test"] != r.overshoot_mw_test:
            raise SystemExit(f"STOP: {r.model} {r.quantile} differs from reserve_test.csv")
    print(f"  check: the 90, 95 and 99% points equal {RESERVE_CSV.relative_to(REPORTS.parent).as_posix()} "
          f"for all 3 models (MW on test hours and MW for today's fleet)")

    fig, ax = fig_axes()
    style(ax)
    ax.xaxis.grid(True, color=GRID, linewidth=1)
    for m in MODELS:
        x = d[d["model"] == m]
        ax.plot(x["coverage_pct"], x["mw_today_fleet"] / 1000, color=COLOR[m], linewidth=3, label=LABEL[m])
    ax.axvline(95, color=INK2, linewidth=1.5, linestyle="--")
    ax.text(94.7, 8.2, "P95, the point used in the deck", fontsize=15, color=INK2, ha="right", va="center")
    h = d[d["model"] == "hgb"].set_index("coverage_pct")["mw_today_fleet"]
    for c in (90, 95, 99):
        ax.plot(c, h[c] / 1000, "o", color=COLOR["hgb"], markersize=10, markeredgecolor=WHITE, markeredgewidth=2)
    ax.text(98.8, 0.3, "Our model (dots):\n" + "\n".join(f"{c}% covered: {h[c]:,.0f} MW" for c in (90, 95, 99)),
            ha="right", va="bottom", fontsize=17, color=INK, linespacing=1.4,
            bbox=dict(facecolor=WHITE, edgecolor="none", pad=6), zorder=5)
    ax.set_xlabel("Share of daylight hours covered (%)")
    ax.set_ylabel("Backup needed for today's fleet (GW)")
    ax.set_xlim(50, 99.5)
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, loc="upper left")
    fig.subplots_adjust(top=0.95, bottom=0.17)
    fig.text(0.02, 0.01, f"Backup = the overshoot (forecast above actual) not exceeded in that share of the 2,457 daylight "
             f"test hours, as a share of capacity,\ntimes EIA 860M nameplate {FLEET_MONTH}, all CISO ({fleet:,.0f} MW). "
             "Dots: our model at 90, 95 and 99% (reports/reserve_test.csv).", fontsize=14, color=INK2)
    save(fig, "evidence_backup_curve", d)
    return d


def main() -> None:
    reproduce()
    print("\n" + "=" * 100)
    print(f"Task 5: error diagnostics on the saved test predictions ({NOTE})\n")
    s = load_test()
    actual_vs_forecast(s)
    error_histogram(s)
    by_hour = error_by_hour(s)
    curve = backup_curve(s)

    print("\nnMAE (%) and mean error (MW) by Pacific hour of day (hour starting), test hours")
    w = by_hour.pivot(index="hour", columns="model")
    n = by_hour.groupby("hour")["hours"].first()
    print(f"  {'hour':>4}{'hours':>7}  " + "".join(f"{LABEL[m][:18]:>20}" for m in MODELS) + "   mean error MW: "
          + " / ".join(["ours", "CAISO", "pers. D-2"]))
    for h in w.index:
        flag = "  <50 h" if n[h] < 50 else ""
        print(f"  {h:>4}{n[h]:>7}  " + "".join(f"{w.loc[h, ('nmae_pct', m)]:>19.2f}%" for m in MODELS) + "   "
              + " / ".join(f"{w.loc[h, ('mean_error_mw', m)]:+,.0f}" for m in MODELS) + flag)

    print("\nBackup for today's fleet (MW) at selected coverage levels")
    p = curve.pivot(index="coverage_pct", columns="model", values="mw_today_fleet")
    print(f"  {'coverage':>8}" + "".join(f"{LABEL[m][:18]:>20}" for m in MODELS))
    for c in (50, 60, 70, 80, 85, 90, 95, 97, 99):
        print(f"  {c:>7}%" + "".join(f"{p.loc[c, m]:>20,.0f}" for m in MODELS))


if __name__ == "__main__":
    main()
