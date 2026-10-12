"""Build the static GitHub Pages dashboard: python tools/build_dashboard.py -> docs/index.html"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from alerts.evaluate import horizons, scores  # noqa: E402

RES = config.RESULTS
OUT = config.ROOT / "docs"
TEMPLATE = Path(__file__).with_name("dashboard_template.html")
COLS = ["lead", "bss", "bss_lo", "bss_hi", "brier", "logloss", "base_rate", "n"]


def series(tab, model, key, label, slot, dash="solid"):
    t = tab[tab["model"] == model].sort_values("lead")
    return {"key": key, "label": label, "slot": slot, "dash": dash,
            "rows": t[COLS].round(5).to_dict(orient="records")}


def main():
    m = pd.read_csv(RES / "scores_main.csv")
    abl = pd.read_csv(RES / "scores_ablation.csv")
    win = pd.read_csv(RES / "scores_window.csv")
    nai = pd.read_csv(RES / "scores_naive.csv")
    experiments = {
        "models": {
            "short": "Models", "title": "Models vs climatology",
            "note": "Persistence (the 0/1 state at issue time) is far below zero at every lead and is shown in the table only.",
            "series": [series(m, "hgb", "hgb", "Gradient boosting", 0),
                       series(m, "logit", "logit", "Logistic regression", 1)],
            "table_only": [series(m, "pers", "pers", "Persistence", 2)],
        },
        "ablation": {
            "short": "Feature groups", "title": "Feature groups added cumulatively (gradient boosting)",
            "note": "Each line adds one group to the previous set.",
            "series": [series(abl, "hgb_A", "A", "A: calendar + climatology", 0),
                       series(abl, "hgb_AB", "AB", "+ B: own history", 1),
                       series(abl, "hgb_ABC", "ABC", "+ C: national load", 2),
                       series(abl, "hgb_ABCD", "ABCD", "+ D: neighbours", 3),
                       series(m, "hgb", "ABCDE", "+ E: sunset / darkness", 4)],
        },
        "window": {
            "short": "Training window", "title": "Training window: last 12 months vs last 2 months",
            "note": "Colour = model, dashed = 2-month window.",
            "series": [series(m, "hgb", "hgb12", "Gradient boosting, 12 months", 0),
                       series(win, "hgb_last_60d", "hgb2", "Gradient boosting, 2 months", 0, "dash"),
                       series(m, "logit", "logit12", "Logistic regression, 12 months", 1),
                       series(win, "logit_last_60d", "logit2", "Logistic regression, 2 months", 1, "dash")],
        },
        "naive": {
            "short": "Naive records", "title": "Records with an invented end (naive=True)",
            "note": "Dropping them changes the target too, so the two lines are not scored on identical labels.",
            "series": [series(m, "hgb", "all", "All records (main)", 0),
                       series(nai, "hgb_no_naive", "nonaive", "Without naive records", 0, "dash")],
        },
    }

    optional = lambda name: pd.read_csv(RES / name) if (RES / name).exists() else None
    base = optional("diag_baselines.csv")
    if base is not None:
        experiments["baselines"] = {
            "short": "Baselines", "title": "Reference forecasts vs the 28-day climatology",
            "note": "Below zero = worse than the 28-day hour-of-day climatology used as the reference everywhere else.",
            "series": [series(base, "pers_cal", "pers_cal", "Persistence as probability (per oblast)", 0),
                       series(base, "clim7", "clim7", "Climatology, 7 days", 1),
                       series(base, "clim14", "clim14", "Climatology, 14 days", 2),
                       series(base, "clim56", "clim56", "Climatology, 56 days", 3),
                       series(base, "climdow", "climdow", "Same hour and weekday, 4 weeks", 4)]}
    long = optional("scores_longtest.csv")
    if long is not None:
        experiments["longtest"] = {
            "short": "Longer test", "title": "Longer test: issue times from 1 May 2026, 23 weekly refits",
            "note": "Same models and features; about 4x more test days, so intervals are narrower.",
            "series": [series(long, "hgb", "hgb", "Gradient boosting", 0),
                       series(long, "logit", "logit", "Logistic regression", 1)]}
    onset = optional("scores_onset.csv")
    if onset is not None:
        experiments["onset"] = {
            "short": "Onset target", "title": "Alternative target: a new alert starts in the hour [τ+L, τ+L+1h)",
            "note": "Reference = 28-day climatology of alert starts in that hour.",
            "series": [series(onset, "hgb", "hgb", "Gradient boosting", 0),
                       series(onset, "logit", "logit", "Logistic regression", 1)],
            "table_only": [series(onset, "pers_cal", "pers_cal", "Persistence as probability", 2)]}
    murphy = optional("diag_murphy.csv")

    group = pd.read_csv(RES / "scores_main_by_group.csv")
    group = group[group["model"].isin(["hgb", "logit"])]

    pred = pd.read_parquet(config.DATA_PROC / "pred_main.parquet")
    group_of = {r: g for g, rs in config.REGION_GROUPS.items() for r in rs}
    reg = scores(pred, ["hgb", "logit"], by="region", n_boot=500)
    reg = reg[reg["model"].isin(["hgb", "logit"])].assign(group=lambda d: d["region"].map(group_of))

    bins = np.linspace(0, 1, 11)
    calib = []
    for model in ["hgb", "logit"]:
        for L, g in pred.groupby("lead"):
            b = np.clip(np.digitize(g[model], bins) - 1, 0, 9)
            c = g.groupby(b).agg(p=(model, "mean"), y=("y", "mean"), n=("y", "size")).reset_index(drop=True)
            calib += [{"model": model, "lead": int(L), **r} for r in c.round(4).to_dict(orient="records")]

    hz = pd.concat([m, abl, win, nai]).drop_duplicates(["lead", "model"])
    names = {"clim": "Climatology (28 d)", "pers": "Persistence", "hgb": "Gradient boosting (all groups)",
             "logit": "Logistic regression", "hgb_A": "Boosting, A", "hgb_AB": "Boosting, A+B",
             "hgb_ABC": "Boosting, A+B+C", "hgb_ABCD": "Boosting, A+B+C+D",
             "hgb_last_60d": "Boosting, 2-month window", "logit_last_60d": "Logistic, 2-month window",
             "hgb_no_naive": "Boosting, without naive records"}
    hz = horizons(hz).assign(label=lambda d: d["model"].map(names))
    tau = pred["tau"].dt.tz_convert(config.TZ)
    data = {
        "leads": config.LEADS,
        "groups": list(config.REGION_GROUPS),
        "experiments": experiments,
        "group_scores": group[["group", "model"] + COLS].round(5).to_dict(orient="records"),
        "region_scores": reg[["region", "group", "model"] + COLS].round(5).to_dict(orient="records"),
        "calibration": calib,
        "horizons": hz.to_dict(orient="records"),
        "murphy": murphy.round(4).to_dict(orient="records") if murphy is not None else [],
        "meta": {
            "issue_from": tau.min().strftime("%Y-%m-%d %H:%M"),
            "issue_to": tau.max().strftime("%Y-%m-%d %H:%M"),
            "n_days": int(tau.dt.date.nunique()),
            "n_regions": len(config.REGIONS),
            "base_rate": round(float(pred.loc[pred["lead"] == 1, "y"].mean()), 4),
            "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
    }
    # BSS is undefined where climatology is perfect (e.g. an oblast with no alert in the test period).
    clean = lambda o: ({k: clean(v) for k, v in o.items()} if isinstance(o, dict) else
                       [clean(v) for v in o] if isinstance(o, list) else
                       None if isinstance(o, float) and not np.isfinite(o) else o)
    payload = json.dumps(clean(data), ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(TEMPLATE.read_text().replace("__DATA__", payload))
    (OUT / ".nojekyll").touch()
    print(OUT / "index.html", f"{(OUT / 'index.html').stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
