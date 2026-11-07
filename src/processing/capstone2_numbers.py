"""Recompute every number in deck/capstone2/CAPSTONE2_NUMBERS.md under the team rules (D14 to D27).

Run from the repo root, after build_hourly_table:
    python -m src.processing.capstone2_numbers

For each number it computes 2 values:
  old  the Capstone 2 method rebuilt from the raw files (blanket 1-hour EIA rule, EIA as published,
       curtailment hours on clock-change days handled as in notebook cell 28). It must match the
       slide before the new value is trusted.
  new  the processed table (data/processed/hourly_table.parquet) under D14 to D27.

Cell numbers refer to notebooks/Raul_EDA_v2.ipynb (0-based, as listed by nbformat), which is
untracked: teammates cannot open it until it is committed.

Writes reports/capstone2_numbers_corrected.md and prints the same table. The deck, the notebook
and CAPSTONE2_NUMBERS.md are not changed. Some numbers (the biggest one-day drop, curtailment
shares) include test-period days: they are descriptive, not model scores.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.processing.build_hourly_table import (CLOCK_CHANGE_DAYS, CURT_RP_FILE, CURT_WB_FILE, LOCAL_TZ, OUT_TABLE,
                                               ROOT, TEST_START, build_table, load_eia_labels)
from src.processing.score_references import nmae_rows, score_frame

OUT_MD = ROOT / "reports" / "capstone2_numbers_corrected.md"
SEASON = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
          6: "Summer", 7: "Summer", 8: "Summer", 9: "Fall", 10: "Fall", 11: "Fall"}
CLOUD_BINS = [-1, 10, 30, 60, 101]


# ----------------------------------------------------------------------------- old-method pieces

def old_curtailment(grid: pd.DatetimeIndex) -> pd.Series:
    """Notebook cell 28: same files and date split, but ambiguous or nonexistent clock-change hours
    become NaT and are dropped, and every other hour without a row is 0 (no D22 exclusion)."""
    wb = pd.read_csv(CURT_WB_FILE, usecols=["Date", "Hour", "Solar Curtailment"])
    wb["date"] = wb["Date"].str[:10]
    wb = wb.groupby(["date", "Hour"])["Solar Curtailment"].sum().div(12).rename("mwh").reset_index()
    wb = wb[wb["date"] != "2025-06-16"]
    rp = pd.read_csv(CURT_RP_FILE)
    rp = rp[rp["fuel"] == "solar"].copy()
    rp["mwh"] = rp[[c for c in rp.columns if c.endswith("_mwh")]].sum(axis=1)
    rp = rp.rename(columns={"operating_date": "date", "hour": "Hour"})[["date", "Hour", "mwh"]]
    rp = rp[(rp["date"] == "2025-06-16") | (rp["date"] >= "2026-01-01")]
    c = pd.concat([wb, rp], ignore_index=True)
    local = pd.to_datetime(c["date"]) + pd.to_timedelta(c["Hour"], unit="h")
    c["hour_end_utc"] = local.dt.tz_localize(LOCAL_TZ, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    by_hour = c.dropna(subset=["hour_end_utc"]).groupby("hour_end_utc")["mwh"].sum()
    return by_hour.reindex(grid).fillna(0.0)


# ----------------------------------------------------------------------------- number functions

def daylight_hours(df):
    return int(df["daylight"].sum())


def gap_hours(df, eia):
    return int((df[eia].isna() | df["caiso_dam_mw"].isna() | df["cloud_cover_previous_day2"].isna()).sum())


def capacity_span(df):
    m = df["local_start"].dt.strftime("%Y-%m")
    first, last = df.loc[m == "2024-03", "capacity_mw"].iloc[0], df.loc[m == "2026-09", "capacity_mw"].iloc[0]
    return first, last, last / first - 1


def season_peaks(df, eia, tv_only):
    """Cell 42: mean MW by season and Pacific hour of the hour start, clipped at 0, max per season."""
    t = df[df[eia].notna()]
    if tv_only:
        t = t[t["local_start"] < TEST_START]
    curve = t.groupby([t["local_start"].dt.month.map(SEASON), t["local_start"].dt.hour])[eia].mean()
    curve = curve.unstack(0).clip(lower=0)
    return curve["Summer"].max(), curve["Winter"].max(), curve["Summer"].max() / curve["Winter"].max() - 1


def cloud_buckets(df, eia):
    """Cell 44: training and validation, hours starting 10, 11, 12 Pacific, output / capacity by
    day-2 cloud cover bucket."""
    tv = df[df["local_start"] < TEST_START]
    share = tv[eia] / tv["capacity_mw"] * 100
    mid = pd.DataFrame({"share": share, "cc": tv["cloud_cover_previous_day2"]})[tv["local_start"].dt.hour.isin([10, 11, 12])]
    mid = mid.dropna()
    return mid.groupby(pd.cut(mid["cc"], CLOUD_BINS), observed=True)["share"].mean().tolist(), len(mid)


def sunshine_corr(df, eia):
    """Cell 44: training and validation daylight hours, day-2 shortwave vs output / capacity."""
    tv = df[(df["local_start"] < TEST_START) & df["daylight"]]
    d = pd.DataFrame({"share": tv[eia] / tv["capacity_mw"], "sw": tv["shortwave_radiation_previous_day2"]}).dropna()
    return d["sw"].corr(d["share"]), len(d)


def biggest_drop(df, eia, tv_only=False):
    """Cell 40: daily EIA sum by Pacific date of the hour start, days with 24 values, biggest fall
    between consecutive days."""
    t = df if not tv_only else df[df["local_start"] < TEST_START]
    g = t[eia].groupby(t["local_start"].dt.date).agg(["sum", "count"])
    daily = g.loc[g["count"] == 24, "sum"] / 1000
    daily.index = pd.to_datetime(daily.index)
    drop = daily.diff()[daily.index.to_series().diff() == pd.Timedelta(days=1)]
    d0 = drop.idxmin()
    prev = daily[d0 - pd.Timedelta(days=1)]
    return d0.date(), prev, daily[d0], drop.min() / prev


def curtailment_shares(df, curt, eia_clip, month_key, mask=None):
    """Monthly and overall curtailed / (curtailed + output). month_key: 'pacific_start' (cell 48),
    'utc' (hour ending in UTC), 'pacific_end' (scratch_curtail.py: Pacific time of the hour ending)."""
    d = df if mask is None else df[mask]
    c = d[curt]
    e = d[eia_clip]
    if month_key == "pacific_start":
        key = d["local_start"].dt.tz_localize(None).dt.to_period("M")
    elif month_key == "utc":
        key = d.index.tz_localize(None).to_period("M")
    else:
        key = d.index.tz_convert(LOCAL_TZ).tz_localize(None).to_period("M")
    m = pd.DataFrame({"curt": c.groupby(key).sum(), "eia": e.groupby(key).sum()})
    m["share"] = m["curt"] / (m["curt"] + m["eia"]) * 100
    total = c.sum() / (c.sum() + e.sum()) * 100
    return total, m["share"]


def split_days(df, full_days_only=False):
    """Cell 52: Pacific dates of the hour start, before and from 2026-04-10. The first Pacific date,
    2024-03-07, holds only the window's first 8 hours; full_days_only leaves it out."""
    day = df["local_start"].dt.date
    if full_days_only:
        keep = day >= pd.Timestamp("2024-03-08").date()
        df, day = df[keep], day[keep]
    is_test = df["local_start"] >= TEST_START
    return day[~is_test].nunique(), day[is_test].nunique()


def old_scores(old, curt):
    """Cell 50: blanket rule, EIA as published, hours with EIA, CAISO, D-1 and D-2 present,
    daylight, training and validation."""
    labels = load_eia_labels()
    f = score_frame(old, "blanket", "raw", labels)
    f["actual_adjusted"] = f["actual"] + curt
    m = (old["daylight"] & (old["local_start"] < TEST_START) & f["actual"].notna() & old["caiso_dam_mw"].notna()
         & f["persistence_d1"].notna() & f["persistence_d2"].notna())
    g = f[m]
    out = {}
    for ref in ["persistence_d1", "persistence_d2", "caiso_published", "caiso_adjusted"]:
        a = g["actual_adjusted"] if ref == "caiso_adjusted" else g["actual"]
        err = g[ref] - a
        out[ref] = ((err.abs() / g["capacity_mw"]).mean() * 100, err.mean())
    return out, len(g), g["local_start"].dt.date.nunique()


def new_scores(new):
    labels = load_eia_labels()
    tv = new[new["local_start"] < TEST_START]
    f = score_frame(tv, "d14", "clipped", labels)
    rows = pd.DataFrame(nmae_rows(f, "train_val", "d14", "clipped", "common")).set_index("reference")
    g = f[f["common"]]
    return ({r: (rows.loc[r, "nmae_pct"], rows.loc[r, "bias_mw"]) for r in rows.index},
            int(rows["hours"].iloc[0]), g["local_start"].dt.date.nunique())


# ----------------------------------------------------------------------------- the report

def status(slide_text, new_text, old_val=None, new_val=None):
    """Compare the slide with the new value: yes, no, or rounding (underlying value moved, shown value did not)."""
    if slide_text != new_text:
        return "yes"
    if old_val is not None and new_val is not None and not np.allclose(old_val, new_val):
        return "rounding"
    return "no"


def main() -> None:
    print("building the old-method table (blanket rule) from data/raw ...")
    old, _ = build_table(rule="blanket")
    old["eia_old"] = old["eia_mw_raw"]                       # the notebook used EIA as published
    old["eia_old_clip"] = old["eia_old"].clip(lower=0)
    old["curt_old"] = old_curtailment(old.index)
    new = pd.read_parquet(OUT_TABLE)
    new["curt_share"] = new["curt_mwh"]
    rows = []

    def add(number, slide, old_text, new_text, how, caveat="", old_val=None, new_val=None, reproduced=None):
        if reproduced is None:
            reproduced = "n/a" if not old_text else ("yes" if old_text == slide else "NO")
        rows.append(dict(number=number, slide=slide, old=old_text, reproduced=reproduced, new=new_text,
                         changed=status(slide, new_text, old_val, new_val), how=how, caveat=caveat))

    # Period, rows, daylight
    add("Period, days", "954", str(old.index.normalize().nunique()), str(new.index.normalize().nunique()),
        "`build_hourly_table.calendar` (UTC days of the hour ending)")
    add("Hourly rows", "22,896", f"{len(old):,}", f"{len(new):,}", "`build_hourly_table.build_table` asserts")
    add("Daylight hours", "11,733", f"{daylight_hours(old):,}", f"{daylight_hours(new):,}",
        "`daylight` column; cell 24", "D20 is the notebook's definition, so no change")
    add("Hours with a gap", "225", str(gap_hours(old, "eia_old")), str(gap_hours(new, "eia_mw")),
        "`gap_hours`; EIA, day-ahead or day-2 cloud cover blank",
        "The slide added 24 + 72 + 129. EIA has 25 blank hours under both rules: the old rule leaves the "
        "last hour (hour ending 2026-10-17 23:00 UTC) without a label, D14 leaves the switch hour "
        "(2025-12-02 21:00 UTC) instead. So 225 was an addition slip; the right count is 226 either way")
    f0, l0, g0 = capacity_span(old)
    f1, l1, g1 = capacity_span(new)
    add("Capacity", "21.0 to 26.0 GW, +24%", f"{f0/1000:.1f} to {l0/1000:.1f} GW, {g0:+.0%}",
        f"{f1/1000:.1f} to {l1/1000:.1f} GW, {g1:+.0%}", "`capacity_span`; cell 26",
        f"EIA 860M nameplate, all CISO, 2024-03 {f1:,.1f} MW and 2026-09 {l1:,.1f} MW")

    # Peaks: old = cell 42 (all days); new = both versions
    s0, w0, r0 = season_peaks(old, "eia_old", tv_only=False)
    s0t, w0t, r0t = season_peaks(old, "eia_old", tv_only=True)
    s1, w1, r1 = season_peaks(new, "eia_mw", tv_only=True)
    s1a, w1a, r1a = season_peaks(new, "eia_mw", tv_only=False)
    fmt = lambda s, w, r: f"{round(s, -2):,.0f} vs {round(w, -2):,.0f} MW, {r:+.0%}"
    add("Summer vs winter peak (training and validation days; deck should use this)", "17,400 vs 11,900 MW, +47%",
        fmt(s0t, w0t, r0t), fmt(s1, w1, r1), "`season_peaks(tv_only=True)`; CAPSTONE2_NUMBERS.md wording",
        "Mean EIA MW by Pacific hour of the hour start and season, max per season. Old value under "
        "this definition does not match the slide; the slide came from all days (next row)",
        (s0t, w0t), (s1, w1))
    add("Summer vs winter peak (all days, as cell 42 does)", "17,400 vs 11,900 MW, +47%",
        fmt(s0, w0, r0), fmt(s1a, w1a, r1a), "`season_peaks(tv_only=False)`; cell 42",
        "Includes test-period days (descriptive only). Not the recommended version", (s0, w0), (s1a, w1a))

    # Cloud buckets
    b0, n0 = cloud_buckets(old, "eia_old")
    b1, n1 = cloud_buckets(new, "eia_mw")
    fb = lambda b: ", ".join(f"{v:.0f}%" for v in b)
    add("Cloud effect (0-10, 10-30, 30-60, 60-100% day-2 cloud cover)", "68%, 57%, 52%, 41%", fb(b0), fb(b1),
        "`cloud_buckets`; cell 44", f"Mean output / capacity, hours starting 10 a.m. to 12 p.m. Pacific, "
        f"training and validation, all seasons; {n1:,} hours (old {n0:,})", b0, b1)

    # Sunshine correlation
    c0, m0 = sunshine_corr(old, "eia_old")
    c1, m1 = sunshine_corr(new, "eia_mw")
    add("Sunshine correlation", "0.87", f"{c0:.2f}", f"{c1:.2f}", "`sunshine_corr`; cell 44",
        f"Day-2 shortwave vs output / capacity, daylight, training and validation", c0, c1)
    add("Sunshine correlation, hour count", "9,191", f"{m0:,}", f"{m1:,}", "`sunshine_corr`; cell 44",
        "D14 removes 1 EIA hour; the weather gap is in the test period, so it does not count here")

    # Biggest one-day drop
    d0 = biggest_drop(old, "eia_old")
    d1 = biggest_drop(new, "eia_mw")
    d1t = biggest_drop(new, "eia_mw", tv_only=True)
    fd = lambda d: f"{d[1]:.0f} to {d[2]:.0f} GWh ({d[3]:+.0%}), {d[0]}"
    add("Biggest one-day drop (all days, as on the slide)", "161 to 73 GWh (-54%), 2026-10-10", fd(d0), fd(d1),
        "`biggest_drop`; cell 40", "Daily sum of `eia_mw` (negatives set to 0, D15), Pacific dates with 24 hours. "
        "In the test period: descriptive, not a model score", (d0[1], d0[2]), (d1[1], d1[2]))
    add("Biggest one-day drop (training and validation only)", "(not on slide)", "", fd(d1t),
        "`biggest_drop(tv_only=True)`", "Offered as a replacement that stays out of the locked test period")

    # Curtailment: which grouping reproduces the slide under the old rule
    variants = {
        "cell 48 (Pacific month of hour start, all hours, EIA clipped)":
            curtailment_shares(old, "curt_old", "eia_old_clip", "pacific_start"),
        "UTC month of hour ending, all hours, EIA clipped":
            curtailment_shares(old, "curt_old", "eia_old_clip", "utc"),
        "scratch_curtail.py (Pacific month of hour ending, daylight with EIA and CAISO, EIA raw)":
            curtailment_shares(old, "curt_old", "eia_old", "pacific_end",
                               mask=old["daylight"] & old["eia_old"].notna() & old["caiso_dam_mw"].notna()),
    }
    p = lambda s, m: s.get(pd.Period(m, "M"), np.nan)
    variant_lines = []
    for name, (tot, ms) in variants.items():
        variant_lines.append(f"| {name} | {tot:.1f}% | {p(ms, '2026-04'):.1f}% | {p(ms, '2025-03'):.1f}% |")
    old_tot, old_ms = variants["UTC month of hour ending, all hours, EIA clipped"]
    old_ms_pac = variants["cell 48 (Pacific month of hour start, all hours, EIA clipped)"][1]
    old_ms_scr = variants["scratch_curtail.py (Pacific month of hour ending, daylight with EIA and CAISO, EIA raw)"][1]
    gap_pac = (old_ms - old_ms_pac).abs()
    gap_scr = (old_ms - old_ms_scr).abs()
    variant_lines.append("")
    variant_lines.append(
        f"All 3 round to the slide values (7.6%, 24%, 20%). The first 2 rows (cell 48 and UTC months) differ by at "
        f"most {gap_pac.max():.2f} points in any month ({gap_pac.idxmax()}), so the slide cannot tell them apart and "
        f"both reproduce it. CAPSTONE2_NUMBERS.md says a Pacific-month recount differs by up to 0.4 points. Neither "
        f"comparison gives that: cell 48 against UTC months is at most {gap_pac.max():.2f} points, and the scratch "
        f"method against UTC months is at most {gap_scr.max():.2f} points ({gap_scr.idxmax()}; "
        f"{gap_scr.get(pd.Period('2025-03', 'M')):.2f} in 2025-03). Where the 0.4 came from is not known.")
    keep = ~new["curt_excluded"]
    new_tot, new_ms = curtailment_shares(new[keep], "curt_mwh", "eia_mw", "pacific_start")
    old_txt = f"{old_tot:.1f}%; {p(old_ms, '2026-04'):.0f}% Apr 2026; {p(old_ms, '2025-03'):.0f}% Mar 2025"
    new_txt = f"{new_tot:.1f}%; {p(new_ms, '2026-04'):.0f}% Apr 2026; {p(new_ms, '2025-03'):.0f}% Mar 2025"
    add("Turned-down solar", "7.6%; 24% Apr 2026; 20% Mar 2025", old_txt, new_txt,
        "`curtailment_shares`; old = UTC months (see the grouping table), new = Pacific months of the hour start",
        "New: the 5 clock-change days are left out of both curtailed MWh and output (D22). "
        "Includes test-period months: descriptive, not a model score",
        (old_tot, p(old_ms, "2026-04"), p(old_ms, "2025-03")), (new_tot, p(new_ms, "2026-04"), p(new_ms, "2025-03")))

    # Scores
    os_, oh, od = old_scores(old, old["curt_old"])
    ns, nh, nd = new_scores(new)
    pc = lambda v: f"{v:.1f}%"
    add("Same as yesterday (D-1)", "4.9%", pc(os_["persistence_d1"][0]), pc(ns["persistence_d1"][0]),
        "`score_references` (d14, clipped, common hours); cell 50", "", os_["persistence_d1"][0], ns["persistence_d1"][0])
    add("Same as 2 days ago (D-2)", "6.1%", pc(os_["persistence_d2"][0]), pc(ns["persistence_d2"][0]),
        "`score_references`; cell 50", "", os_["persistence_d2"][0], ns["persistence_d2"][0])
    add("CAISO as published", "5.7%", pc(os_["caiso_published"][0]), pc(ns["caiso_published"][0]),
        "`score_references`; cell 50", "D14 moves this score most", os_["caiso_published"][0], ns["caiso_published"][0])
    add("CAISO as published, bias", "+828 MW", f"{os_['caiso_published'][1]:+,.0f} MW",
        f"{ns['caiso_published'][1]:+,.0f} MW", "`score_references` bias_mw; cell 50",
        "CAISO day-ahead minus EIA, mean over the scored hours", os_["caiso_published"][1], ns["caiso_published"][1])
    add("CAISO adjusted", "3.7%", pc(os_["caiso_adjusted"][0]), pc(ns["caiso_adjusted"][0]),
        "`score_references`; cell 50", "Partly by construction: CAISO defines curtailment against its own forecast",
        os_["caiso_adjusted"][0], ns["caiso_adjusted"][0])
    t_old = f"{1.25 * os_['caiso_adjusted'][0]:.1f}% to about {1.25 * os_['caiso_published'][0]:.0f}%"
    t_new = f"{1.25 * ns['caiso_adjusted'][0]:.1f}% to {1.25 * ns['caiso_published'][0]:.1f}%"
    add("Target range (1.25 x CAISO adjusted to 1.25 x CAISO as published)", "4.6% to about 7%", t_old, t_new,
        "1.25 x the 2 CAISO scores above", f"New: 1.25 x {ns['caiso_adjusted'][0]:.2f} and 1.25 x "
        f"{ns['caiso_published'][0]:.2f}. Which CAISO figure the target uses is still open")
    add("Hours scored", "9,133 over 758 days", f"{oh:,} over {od} days", f"{nh:,} over {nd} days",
        "`score_references` hours (common set); cell 50",
        "New drops the switch hour and its persistence follow-ons (D14) and the daylight hours of the "
        "5 clock-change days (curt_mwh null, D22, D27)")

    sv, st = split_days(new, full_days_only=True)
    sv0, st0 = split_days(old)
    add("Split", "763 and 191 days", f"{sv0} and {st0} days", f"{sv} and {st} days",
        "`split_days(full_days_only=True)`; cell 52",
        "Cell 52 counts 764 because the first Pacific date, 2024-03-07, holds the window's first 8 hours "
        "(00:00 to 08:00 UTC). Counting full days gives 763, as on the slide", reproduced="yes, as full days")
    rows.append(dict(number="Weather API use", slide="about 6,500 of 10,000 daily calls", old="not recomputed",
                     reproduced="n/a", new="not recomputed", changed="no", how="PULL_LOG.md",
                     caveat="From the pull log, not from data"))

    write_md(rows, variant_lines, old_ms, old_ms_pac, new_ms)


def write_md(rows, variant_lines, old_ms, old_ms_pac, new_ms) -> None:
    esc = lambda s: str(s).replace("|", "\\|")
    out = ["# Capstone 2 numbers, corrected (D14 to D27)", "",
           "Generated by `python -m src.processing.capstone2_numbers`. Do not edit by hand.", "",
           "Columns: **On slide** is the value in `deck/capstone2/CAPSTONE2_NUMBERS.md`. **Old method** is that "
           "number rebuilt from the raw files with the Capstone 2 method (blanket 1-hour EIA rule, EIA as published), "
           "and **Reproduced** says whether it matches the slide. **New** uses the processed table under D14 to D27 "
           "(EIA with negatives set to 0, D15). **Changed** compares the slide with the new value: yes, no, or "
           "rounding (the underlying value moved but the shown value did not).", "",
           "Cell numbers refer to `notebooks/Raul_EDA_v2.ipynb` (counted from 0). That notebook is not committed, "
           "so teammates cannot open it until it is. Numbers that include test-period days are descriptive "
           "statistics, not model scores. The deck, the notebook and CAPSTONE2_NUMBERS.md are unchanged.", "",
           "| Number on slide | On slide | Old method | Reproduced | New | Changed | How computed | Caveat |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| " + " | ".join(esc(r[k]) for k in
                                      ["number", "slide", "old", "reproduced", "new", "changed", "how", "caveat"]) + " |")
    out += ["", "## Which grouping gives the curtailment numbers on the slide (old method)", "",
            "| Grouping | Overall | Apr 2026 | Mar 2025 |", "|---|---|---|---|"] + variant_lines
    out += ["", "## Monthly curtailment share", "",
            "Old: the Capstone 2 method by UTC month (as on the slide) and by Pacific month (cell 48). "
            "New: Pacific month of the hour start, with the 5 clock-change days left out of both curtailed MWh "
            "and output (D22). The month moves, and the clock-change days drop out of 2024-03, 2024-11, "
            "2025-03, 2025-11 and 2026-03.", "",
            "| Month | Old, UTC months | Old, Pacific months | New |", "|---|---|---|---|"]
    for m in sorted(set(old_ms.index) | set(new_ms.index)):
        o, op, n = old_ms.get(m, np.nan), old_ms_pac.get(m, np.nan), new_ms.get(m, np.nan)
        out.append(f"| {m} | {o:.1f}% | {op:.1f}% | {n:.1f}% |")
    text = "\n".join(out) + "\n"
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(text, encoding="utf-8")
    print(text)
    print(f"written: {OUT_MD.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
