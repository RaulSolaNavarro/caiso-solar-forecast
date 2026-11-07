"""The 5 Capstone 3 charts (Brief 4, Task C step 4), from saved results only: no model is refitted and
no forecast is rescored.

Run from the repo root, after final_test --final-test and reserve:
    python -m src.modeling.capstone3_figures

Inputs: data/processed/test_predictions.parquet, reports/final_results_test.csv,
reports/model_results_validation.csv, reports/reserve_test.csv.
Writes deck/capstone3/figures/*.png (16:9, 1920 x 1080) and the data behind each chart to
reports/capstone3_<chart>.csv.

Colors follow the dataviz skill's reference palette, first 3 categorical slots (validated for every
pair in light and dark mode): HGB blue, CAISO as published orange, persistence D-2 aqua; other
forecasts gray. Every mark carries a text label, so no meaning rests on color alone.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.processing.build_hourly_table import PROCESSED, ROOT  # noqa: E402

FIG_DIR = ROOT / "deck" / "capstone3" / "figures"
REPORTS = ROOT / "reports"
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
COLOR = {"hgb": "#2a78d6", "caiso_published": "#eb6834", "persistence_d2": "#1baf7a"}
OTHER = "#b9b8b0"
VAL_SHADE, TEST_SHADE = "#86b6ef", "#1c5cab"           # blue ramp steps 250 and 550
LABEL = {"hgb": "Our model (HGB)", "ridge": "Ridge (dropped)", "climatology": "Climatology (floor)",
         "persistence_d2": "Same as 2 days ago", "persistence_d1": "Same as yesterday*",
         "caiso_published": "CAISO as published", "caiso_adjusted": "CAISO adjusted**"}
CLOUD = ["0-10", "10-30", "30-60", "60-100"]

plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 20, "axes.titlesize": 30,
                     "axes.labelsize": 22, "xtick.labelsize": 20, "ytick.labelsize": 20, "legend.fontsize": 20,
                     "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def new_fig(title: str, caption: str):
    fig = plt.figure(figsize=(16, 9), dpi=120)
    fig.suptitle(title, x=0.04, y=0.96, ha="left", fontsize=30, fontweight="bold", color=INK)
    fig.text(0.04, 0.025, caption, ha="left", va="bottom", fontsize=16, color=INK2, wrap=True)
    return fig


def style(ax, ygrid=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, linewidth=1)
        ax.set_axisbelow(True)


def save(fig, name: str, data: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.png", facecolor=SURFACE)
    plt.close(fig)
    data.to_csv(REPORTS / f"capstone3_{name}.csv", index=False)
    print(f"  {name}.png  (data: reports/capstone3_{name}.csv, {len(data)} rows)")


def nmae(res: pd.DataFrame, model: str, group: str = "all") -> float:
    return float(res[(res["model"] == model) & (res["metric"] == "nmae_pct") & (res["group"] == group)]["value"].iloc[0])


# ----------------------------------------------------------------------------- 1. sample days

def sample_days(pred: pd.DataFrame) -> None:
    s = pred[pred["common"]].copy()
    s["date"] = s["local_start"].dt.date
    s["abs_err_share"] = (s["hgb"] - s["actual"]).abs() / s["capacity_mw"]
    day = s.groupby("date").agg(hours=("hgb", "size"), cloud=("cloud_cover_previous_day2", "mean"),
                                nmae=("abs_err_share", "mean"))
    day = day[day["hours"] >= 8]
    kinds = [("Clear", 0, 10), ("Partly cloudy", 10, 60), ("Cloudy", 60, 101)]
    picks = []
    for name, lo, hi in kinds:
        d = day[(day["cloud"] > lo if lo else day["cloud"] >= 0) & (day["cloud"] <= hi)].sort_values("nmae")
        if d.empty:
            raise ValueError(f"no test day in the {name} bucket")
        picks.append((name, d.index[(len(d) - 1) // 2], len(d), d.iloc[(len(d) - 1) // 2]))
    fig = new_fig("Three ordinary test days: our forecast against what the sun delivered",
                  "Each day is the median-error day (our model, daily nMAE) among test days whose average day-2 "
                  "cloud forecast was 0-10% (clear), 10-60% (partly cloudy) or above 60% (cloudy); days with at "
                  "least 8 scored daylight hours. Pacific time. Actual: EIA hourly solar, CISO. Not hand-picked.")
    axes = fig.subplots(1, 3, sharey=True, gridspec_kw=dict(left=0.07, right=0.98, top=0.74, bottom=0.2, wspace=0.08))
    rows = []
    ymax = 0
    for ax, (name, date, n, info) in zip(axes, picks):
        d = pred[pred["local_start"].dt.date == date].sort_values("local_start")
        h = d["local_start"].dt.hour
        ax.plot(h, d["actual"] / 1000, color=INK, linewidth=3, label="Actual (EIA)")
        ax.plot(h, d["hgb"] / 1000, color=COLOR["hgb"], linewidth=3, label=LABEL["hgb"])
        ax.plot(h, d["caiso_published"] / 1000, color=COLOR["caiso_published"], linewidth=3, linestyle="--",
                label=LABEL["caiso_published"])
        ymax = max(ymax, d[["actual", "hgb", "caiso_published"]].max().max() / 1000)
        ax.set_title(f"{name}: {date:%b %d, %Y}\n(cloud {info['cloud']:.0f}%, our error {info['nmae'] * 100:.1f}%)",
                     fontsize=20, color=INK, pad=10)
        ax.set_xticks([6, 12, 18], ["6 am", "noon", "6 pm"])
        style(ax)
        for _, r in d.iterrows():
            rows.append(dict(kind=name, date=str(date), days_in_bucket=n, day_cloud_pct=round(info["cloud"], 1),
                             day_hgb_nmae_pct=round(info["nmae"] * 100, 2), hour=r["local_start"].hour,
                             actual_mw=round(r["actual"], 0), hgb_mw=round(r["hgb"], 0),
                             caiso_published_mw=round(r["caiso_published"], 0)))
    axes[0].set_ylabel("Solar output (GW)")
    axes[0].set_ylim(0, ymax * 1.1)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper left", bbox_to_anchor=(0.04, 0.91), ncol=3, frameon=False, fontsize=19)
    save(fig, "sample_days", pd.DataFrame(rows))


# ----------------------------------------------------------------------------- 2. nMAE by model

def by_model(res: pd.DataFrame) -> None:
    order = ["caiso_adjusted", "hgb", "ridge", "persistence_d1", "caiso_published", "climatology", "persistence_d2"]
    vals = {m: nmae(res, m) for m in order}
    t_pub, t_adj = 1.25 * vals["caiso_published"], 1.25 * vals["caiso_adjusted"]
    fig = new_fig(f"Our model's error ({vals['hgb']:.1f}%) is well inside the 1.25 x CAISO target",
                  f"Mean absolute error as % of installed solar (EIA 860M nameplate, all CISO), 2,457 daylight test "
                  f"hours, 2026-04-10 to 2026-10-17. Targets: 1.25 x CAISO as published = {t_pub:.2f}%; "
                  f"1.25 x CAISO adjusted = {t_adj:.2f}% (partly circular: CAISO measures curtailment against its "
                  f"own forecast). *Uses data not available at the 10 a.m. bid close. **Adjusted for curtailment.")
    ax = fig.add_axes([0.27, 0.2, 0.68, 0.62])
    y = np.arange(len(order))
    colors = [COLOR.get(m, OTHER) for m in order]
    ax.barh(y, [vals[m] for m in order], color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    for i, m in enumerate(order):
        ax.text(vals[m] + 0.08, i, f"{vals[m]:.2f}%", va="center", fontsize=20, color=INK,
                fontweight="bold" if m == "hgb" else "normal")
    ax.set_yticks(y, [LABEL[m] for m in order])
    ax.invert_yaxis()
    for t, txt, ls in [(t_pub, f"Target: 1.25 x CAISO as published ({t_pub:.2f}%)", "-"),
                       (t_adj, f"1.25 x CAISO adjusted ({t_adj:.2f}%)", ":")]:
        ax.axvline(t, color=INK2, linewidth=2, linestyle=ls)
        ax.text(t, -0.75, txt, ha="center", va="bottom", fontsize=16, color=INK2)
    ax.set_xlabel("Error (nMAE, % of capacity); lower is better")
    ax.set_xlim(0, max(vals.values()) * 1.18)
    style(ax, ygrid=False)
    ax.xaxis.grid(True, color=GRID)
    data = pd.DataFrame([dict(model=m, label=LABEL[m], nmae_pct=vals[m]) for m in order]
                        + [dict(model="target_1.25x_caiso_published", label="target", nmae_pct=round(t_pub, 4)),
                           dict(model="target_1.25x_caiso_adjusted", label="target (partly circular)",
                                nmae_pct=round(t_adj, 4))])
    save(fig, "nmae_by_model", data)


# ----------------------------------------------------------------------------- 3. nMAE by cloud bucket

def by_cloud(res: pd.DataFrame) -> None:
    models = ["hgb", "caiso_published", "persistence_d2"]
    hours = res[(res["model"] == "hgb") & (res["metric"] == "nmae_pct")].set_index("group")["hours"]
    rows = [dict(model=m, cloud_d2=c, nmae_pct=nmae(res, m, f"cloud_d2={c}"), hours=int(hours[f"cloud_d2={c}"]))
            for m in models for c in CLOUD]
    d = pd.DataFrame(rows)
    rise = {m: d[(d.model == m) & (d.cloud_d2 == "60-100")].nmae_pct.iloc[0]
               - d[(d.model == m) & (d.cloud_d2 == "0-10")].nmae_pct.iloc[0] for m in models}
    least = min(rise, key=rise.get)
    title = ("Clouds raise every forecast's error; ours rises least" if least == "hgb"
             else "Clouds raise every forecast's error")
    fig = new_fig(title, "Error (nMAE, % of installed solar, EIA 860M all CISO) by the day-2 cloud cover forecast for "
                         "each hour, daylight test hours 2026-04-10 to 2026-10-17. Hours per bucket under each label. "
                         "Cloud cover is the forecast known before the bid, not the observed sky.")
    ax = fig.add_axes([0.08, 0.22, 0.88, 0.6])
    x = np.arange(len(CLOUD))
    w = 0.26
    for k, m in enumerate(models):
        v = d[d.model == m].set_index("cloud_d2").loc[CLOUD, "nmae_pct"]
        bars = ax.bar(x + (k - 1) * w, v, width=w - 0.02, color=COLOR[m], label=LABEL[m], edgecolor=SURFACE, linewidth=2)
        for b, val in zip(bars, v):
            ax.text(b.get_x() + b.get_width() / 2, val + 0.2, f"{val:.1f}", ha="center", fontsize=17, color=INK)
    ax.set_xticks(x, [f"{c}% cloud\n({int(hours[f'cloud_d2={c}']):,} hours)" for c in CLOUD])
    ax.set_ylabel("Error (nMAE, %)")
    ax.legend(loc="upper left", frameon=False)
    style(ax)
    save(fig, "nmae_by_cloud", d)


# ----------------------------------------------------------------------------- 4. nMAE by month

def by_month(res: pd.DataFrame, val: pd.DataFrame) -> None:
    v = val[(val["model"] == "hgb") & (val["metric"] == "nmae_pct") & (val["fold"] == "pooled")
            & val["group"].str.startswith("month=")]
    t = res[(res["model"] == "hgb") & (res["metric"] == "nmae_pct") & res["group"].str.startswith("month=")]
    d = pd.concat([v.assign(period="validation"), t.assign(period="test")])
    d["month"] = d["group"].str[6:]
    d = d[["period", "month", "value", "hours"]].rename(columns={"value": "nmae_pct"}).reset_index(drop=True)
    labels = [f"{pd.Period(m):%b %Y}" + (" val" if p == "validation" and m == "2026-04" else
                                          " test" if p == "test" and m == "2026-04" else "")
              for p, m in zip(d["period"], d["month"])]
    fig = new_fig("Our error by month: the test half-year has no winter months",
                  "Our model's error (nMAE, % of installed solar, EIA 860M all CISO), daylight hours. Light bars: "
                  "validation (each month predicted by a model trained only on earlier days). Dark hatched bars: the "
                  "one test run. April 2026 is split at the test start (Apr 10). Winter (Dec to Feb) was checked "
                  "only in validation.")
    ax = fig.add_axes([0.08, 0.22, 0.9, 0.6])
    x = np.arange(len(d))
    is_test = (d["period"] == "test").values
    ax.bar(x[~is_test], d["nmae_pct"][~is_test], color=VAL_SHADE, width=0.8, edgecolor=SURFACE, linewidth=2,
           label="Validation")
    ax.bar(x[is_test], d["nmae_pct"][is_test], color=TEST_SHADE, width=0.8, edgecolor=SURFACE, linewidth=2,
           hatch="//", label="Test (one run)")
    for i, val_ in enumerate(d["nmae_pct"]):
        ax.text(i, val_ + 0.12, f"{val_:.1f}", ha="center", fontsize=15, color=INK)
    winter = [i for i, m in enumerate(d["month"]) if int(m[-2:]) in (12, 1, 2)]
    if winter:
        ax.axvspan(min(winter) - 0.5, max(winter) + 0.5, color=GRID, alpha=0.6, zorder=0)
        ax.text((min(winter) + max(winter)) / 2, d["nmae_pct"].max() * 1.12, "Winter: validation only",
                ha="center", fontsize=17, color=INK2)
    ax.set_xticks(x, labels, rotation=45, ha="right", fontsize=16)
    ax.set_ylabel("Error (nMAE, %)")
    ax.set_ylim(0, d["nmae_pct"].max() * 1.22)
    ax.legend(loc="upper right", frameon=False)
    style(ax)
    save(fig, "nmae_by_month", d)


# ----------------------------------------------------------------------------- 5. reserve

def reserve(rsv: pd.DataFrame) -> None:
    models = ["hgb", "persistence_d2", "caiso_published"]
    d = rsv[(rsv["season"] == "all") & (rsv["quantile"] == "P95") & rsv["model"].isin(models)].set_index("model").loc[models]
    hgb, caiso = d.loc["hgb", "mw_today_fleet"], d.loc["caiso_published", "mw_today_fleet"]
    fig = new_fig(f"Backup needed for 95 of 100 daylight hours: {hgb:,.0f} MW with our forecast",
                  "P95 of hourly over-forecast (forecast minus actual EIA output, when positive) on the 2,457 "
                  "daylight test hours, as a share of that hour's capacity, applied to today's fleet: EIA 860M "
                  "nameplate 2026-09, all CISO, 26,034.5 MW. Curtailed hours count as shortfalls here, which "
                  "overstates the backup for forecasts made before curtailment, such as CAISO's.")
    ax = fig.add_axes([0.08, 0.2, 0.88, 0.62])
    x = np.arange(len(models))
    bars = ax.bar(x, d["mw_today_fleet"], color=[COLOR[m] for m in models], width=0.55, edgecolor=SURFACE, linewidth=2)
    for b, (m, r) in zip(bars, d.iterrows()):
        ax.text(b.get_x() + b.get_width() / 2, r["mw_today_fleet"] + 120,
                f"{r['mw_today_fleet']:,.0f} MW\n({r['share_of_capacity_pct']:.1f}% of capacity)",
                ha="center", fontsize=20, color=INK, fontweight="bold" if m == "hgb" else "normal")
    ax.set_xticks(x, [LABEL[m] for m in models])
    ax.set_ylabel("Backup power (MW, today's fleet)")
    ax.set_ylim(0, d["mw_today_fleet"].max() * 1.25)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    style(ax)
    data = d.reset_index()[["model", "quantile", "hours", "overshoot_mw_test", "share_of_capacity_pct", "mw_today_fleet",
                            "sentence"]]
    save(fig, "reserve_p95", data)


def main() -> None:
    pred = pd.read_parquet(PROCESSED / "test_predictions.parquet")
    res = pd.read_csv(REPORTS / "final_results_test.csv")
    val = pd.read_csv(REPORTS / "model_results_validation.csv")
    rsv = pd.read_csv(REPORTS / "reserve_test.csv")
    print("Capstone 3 charts (from saved test and validation results; nothing refitted or rescored):")
    sample_days(pred)
    by_model(res)
    by_cloud(res)
    by_month(res, val)
    reserve(rsv)


if __name__ == "__main__":
    main()
