"""Run one or more experiments: python run.py main ablation window naive"""
import argparse
import time

import config
from alerts import data, evaluate, features, geo

G = features.GROUPS
ALL = G["A"] + G["B"] + G["C"] + G["D"] + G["E"]
LADDER = {"A": G["A"], "AB": G["A"] + G["B"], "ABC": G["A"] + G["B"] + G["C"],
          "ABCD": G["A"] + G["B"] + G["C"] + G["D"]}  # ABCDE is the main hgb

EXPERIMENTS = {
    "main": dict(specs={"logit": ("logit", ALL), "hgb": ("hgb", ALL)}),
    "ablation": dict(specs={f"hgb_{k}": ("hgb", fs) for k, fs in LADDER.items()}),
    "window": dict(specs={"hgb_last_60d": ("hgb", ALL), "logit_last_60d": ("logit", ALL)},
                   window_days=config.RECENT_WINDOW_DAYS),
    "naive": dict(specs={"hgb_no_naive": ("hgb", ALL)}, drop_naive=True),
    # No fitted models: stronger reference forecasts, scored against the 28-day climatology.
    "baselines": dict(specs={}, models=["pers", "pers_cal", "clim7", "clim14", "clim56", "climdow"]),
}


def prepare(drop_naive=False):
    intervals = data.load_intervals(drop_naive=drop_naive)
    P = data.build_panel(intervals)
    adj, lat, lon = geo.region_geo()
    print(f"  {len(intervals):,} merged intervals, panel {P.grid[0]} .. {P.grid[-1]} ({len(P.grid):,} h)")
    return P, features.build_features(P, adj, lat, lon)


def run(name):
    exp = EXPERIMENTS[name]
    print(f"[{name}]", flush=True)
    t0 = time.time()
    P, F = prepare(exp.get("drop_naive", False))
    pred = evaluate.walk_forward(P, F, exp["specs"], window_days=exp.get("window_days", config.TRAIN_WINDOW_DAYS))
    config.DATA_PROC.mkdir(parents=True, exist_ok=True)
    pred.to_parquet(config.DATA_PROC / f"pred_{name}.parquet")
    models = exp.get("models", (["pers"] if name == "main" else []) + list(exp["specs"]))
    tab = evaluate.scores(pred, models)
    tab.to_csv(config.RESULTS / f"scores_{name}.csv", index=False)
    if name == "main":
        group_of = {r: g for g, rs in config.REGION_GROUPS.items() for r in rs}
        evaluate.scores(pred.assign(group=pred["region"].map(group_of)), models, by="group") \
            .to_csv(config.RESULTS / "scores_main_by_group.csv", index=False)
    print(evaluate.horizons(tab).to_string(index=False))
    print(f"[{name}] done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("experiments", nargs="+", choices=list(EXPERIMENTS))
    for name in ap.parse_args().experiments:
        run(name)
