"""Diagnostics on saved test predictions (no refitting): python diagnose.py
  - skill of the fitted models against each reference forecast, not only the 28-day climatology
  - Murphy decomposition of the Brier score (reliability, resolution, uncertainty), ROC-AUC, PR-AUC
  - BSS week by week (stability over the 6 refits)
"""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

import config
from alerts.evaluate import BASELINES, scores

KEYS = ["tau", "region", "lead"]
MODELS = ["hgb", "logit"]
REFS = BASELINES + ["pers_cal"]


def load():
    main = pd.read_parquet(config.DATA_PROC / "pred_main.parquet")
    base = pd.read_parquet(config.DATA_PROC / "pred_baselines.parquet")
    extra = [c for c in base.columns if c not in main.columns]
    df = main.merge(base[KEYS + extra], on=KEYS, validate="one_to_one")
    assert len(df) == len(main) and (df["clim"].notna()).all()
    return df


def murphy(df, models, n_bins=10):
    """Brier = reliability - resolution + uncertainty (binned; exact up to within-bin spread)."""
    rows = []
    for L, g in df.groupby("lead"):
        y = g["y"].to_numpy(float)
        ob = y.mean()
        for m in models:
            p = g[m].to_numpy(float)
            b = np.clip((p * n_bins).astype(int), 0, n_bins - 1)
            n = np.bincount(b, minlength=n_bins)
            k = n > 0
            pk = np.bincount(b, p, n_bins)[k] / n[k]
            ok = np.bincount(b, y, n_bins)[k] / n[k]
            rows.append({"lead": L, "model": m, "brier": np.mean((p - y) ** 2),
                         "reliability": (n[k] * (pk - ok) ** 2).sum() / len(y),
                         "resolution": (n[k] * (ok - ob) ** 2).sum() / len(y),
                         "uncertainty": ob * (1 - ob),
                         "roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p)})
    return pd.DataFrame(rows)


def main():
    df = load()
    vs = pd.concat([scores(df, MODELS, ref=r, n_boot=1000).assign(ref=r) for r in REFS])
    vs = vs[vs["model"].isin(MODELS)]
    vs.to_csv(config.RESULTS / "diag_vs_baselines.csv", index=False)
    base = scores(df, ["pers_cal", "clim7", "clim14", "clim56", "climdow"], n_boot=1000)
    base.to_csv(config.RESULTS / "diag_baselines.csv", index=False)
    mur = murphy(df, ["clim", "pers_cal", "climdow"] + MODELS)
    mur.to_csv(config.RESULTS / "diag_murphy.csv", index=False)
    weekly = scores(df, MODELS, by="week", n_boot=1000)
    weekly.to_csv(config.RESULTS / "diag_weekly.csv", index=False)

    pd.set_option("display.width", 200)
    print("Baselines: BSS vs 28-day climatology\n", base.pivot(index="model", columns="lead", values="bss").round(3))
    for col in ["bss", "bss_lo"]:
        print(f"\nModels vs each reference: {col}\n",
              vs.pivot_table(index=["model", "ref"], columns="lead", values=col).round(3))
    print("\nMurphy (lead 1, 24, 72)\n", mur[mur["lead"].isin([1, 24, 72])].round(4).to_string(index=False))
    print("\nWeekly BSS (hgb)\n", weekly[weekly["model"] == "hgb"].pivot(index="week", columns="lead", values="bss").round(3))


if __name__ == "__main__":
    main()
