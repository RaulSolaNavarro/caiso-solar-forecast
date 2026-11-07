"""Charts for the Capstone 2 deck, drawn with matplotlib from reports/deck_chart_data.csv.

Run from the repo root, after deck_chart_data:
    python -m src.processing.deck_figures

Writes deck/capstone2/figures/daily_shape.png and cloud_effect.png (training and validation days only,
before 2026-04-10 Pacific). The data behind them comes from the processed hourly table
(src/processing/build_hourly_table.py and src/processing/deck_chart_data.py).
"""
from __future__ import annotations

import argparse
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter

ROOT = pathlib.Path(__file__).resolve().parents[2]
BG, INK, INK2, MUTED, GRID, AXIS = "#0f1830", "#f1f4fb", "#b9c2d6", "#8893ab", "#1d2a4d", "#34436e"
COLORS = {"winter": "#3987e5", "spring": "#199e70", "summer": "#d95926", "fall": "#9085e9"}
BLUE = "#3987e5"

for f in font_manager.findSystemFonts():
    if "/inter/" in f.replace("\\", "/").lower() and "Display" not in f:
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"], "text.color": INK, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": BG, "axes.facecolor": BG,
                     "savefig.facecolor": BG})


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["bottom"].set_linewidth(1.6)
    ax.tick_params(length=0, labelsize=17)


def daily_shape(df: pd.DataFrame, out: pathlib.Path) -> None:
    sp = df[df.chart == "season_profile"].copy()
    sp["x"] = sp["x"].astype(int)
    fig, ax = plt.subplots(figsize=(8.6, 5.3), dpi=200)
    peaks = {}
    for season in ("winter", "fall", "spring", "summer"):
        s = sp[sp.series == f"{season}_tv"].sort_values("x")
        ax.plot(s["x"], s["value"], color=COLORS[season], lw=4, label=season.capitalize(), solid_capstyle="round")
        peaks[season] = s["value"].max()
    ax.set_xlim(4, 21)
    ax.set_ylim(0, 20000)
    ax.set_xticks([6, 9, 12, 15, 18], ["6 AM", "9 AM", "Noon", "3 PM", "6 PM"])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_yticks([0, 5000, 10000, 15000, 20000])
    ax.grid(axis="y", color=GRID, lw=1.4)
    ax.set_axisbelow(True)
    style(ax)
    ax.set_ylabel("Average solar output (MW)", fontsize=17, labelpad=10)
    ax.text(12, peaks["summer"] + 450, f"Summer peak: {round(peaks['summer'], -2):,.0f} MW", fontsize=17, color=INK,
            fontweight="bold", ha="center", va="bottom")
    ax.text(12, 8200, f"Winter peak:\n{round(peaks['winter'], -2):,.0f} MW", fontsize=17, color=INK,
            fontweight="bold", ha="center", va="top")
    leg = ax.legend(loc="upper left", ncol=4, frameon=False, fontsize=17, handlelength=1.4, columnspacing=1.2,
                    bbox_to_anchor=(0.0, 1.13))
    for t in leg.get_texts():
        t.set_color(INK)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def cloud_effect(df: pd.DataFrame, out: pathlib.Path) -> None:
    cb = df[df.chart == "cloud_buckets"].reset_index(drop=True)
    labels = ["Clear\n0 to 10%", "Some cloud\n10 to 30%", "Cloudy\n30 to 60%", "Very cloudy\n60 to 100%"]
    vals = cb["value"].astype(float).tolist()
    fig, ax = plt.subplots(figsize=(8.6, 5.3), dpi=200)
    bars = ax.bar(range(4), vals, width=0.62, color=BLUE)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}%", ha="center", va="bottom", fontsize=24,
                fontweight="bold", color=INK)
    ax.set_xticks(range(4), labels)
    ax.set_ylim(0, 82)
    ax.set_yticks([])
    style(ax)
    ax.tick_params(axis="x", labelsize=17, pad=8)
    ax.set_ylabel("Midday output (% of capacity)", fontsize=16, labelpad=10)
    ax.set_xlabel("Cloud cover in the forecast made 2 days before", fontsize=17, labelpad=12, color=MUTED)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "reports" / "deck_chart_data.csv"))
    ap.add_argument("--out", default=str(ROOT / "deck" / "capstone2" / "figures"))
    a = ap.parse_args()
    df = pd.read_csv(a.csv, dtype={"x": str})
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    daily_shape(df, out / "daily_shape.png")
    cloud_effect(df, out / "cloud_effect.png")
    print("written:", out / "daily_shape.png", out / "cloud_effect.png")


if __name__ == "__main__":
    main()
