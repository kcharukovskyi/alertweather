"""Figures and the horizon table from results/scores_*.csv: python report.py"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config
from helpers.chart_style import COLORS, FIGSIZE, FS, setup_style

setup_style()
LEADS = config.LEADS
RES, FIG = config.RESULTS, config.FIGURES
NAMES = {"pers": "Persistence", "logit": "Logistic regression", "hgb": "Gradient boosting",
         "clim": "Climatology (28 d)"}


def load(name):
    path = RES / f"scores_{name}.csv"
    return pd.read_csv(path) if path.exists() else None


def bss_axes(ax, label, ymin=None):
    ax.axhline(0, color=COLORS[6], lw=0.8, ls="--")
    ax.set_xscale("log")
    ax.set_xticks(LEADS, [str(L) for L in LEADS])
    ax.minorticks_off()
    ax.set_xlabel("Lead time, hours")
    ax.set_ylabel("Brier skill score vs climatology")
    if ymin is not None:
        ax.set_ylim(bottom=ymin)
    ax.text(0.5, -0.22, label, transform=ax.transAxes, fontsize=FS, ha="center", va="top")


def skill_line(ax, tab, model, color, label, ls="-"):
    t = tab[tab["model"] == model].sort_values("lead")
    ax.fill_between(t["lead"], t["bss_lo"], t["bss_hi"], color=color, alpha=0.15, lw=0)
    ax.plot(t["lead"], t["bss"], ls, color=color, marker="o", ms=5, label=label)


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    plt.subplots_adjust(bottom=0.18, wspace=0.3)
    fig.savefig(FIG / name, facecolor="white")
    plt.close(fig)


def fig_main(main):
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE["panel_2"])
    for c, m in zip(COLORS, ["hgb", "logit", "pers"]):
        skill_line(axes[0], main, m, c, NAMES[m])
    lo = main[main["model"] != "pers"]["bss_lo"].min()
    bss_axes(axes[0], "A. Skill vs lead (95% day-bootstrap CI)", ymin=min(lo, 0) - 0.1)
    axes[0].legend(loc="upper right")
    ax = axes[1]
    for c, m in zip(COLORS, ["hgb", "logit", "pers", "clim"]):
        t = main[main["model"] == m].sort_values("lead")
        ax.plot(t["lead"], t["brier"], "o-", color=c if m != "clim" else COLORS[6], label=NAMES[m],
                ls="--" if m == "clim" else "-")
    ax.set_xscale("log")
    ax.set_xticks(LEADS, [str(L) for L in LEADS])
    ax.minorticks_off()
    ax.set_ylim(0, min(main["brier"].max() * 1.05, 0.5))
    ax.set_xlabel("Lead time, hours")
    ax.set_ylabel("Brier score (lower is better)")
    ax.text(0.5, -0.22, "B. Brier score", transform=ax.transAxes, fontsize=FS, ha="center", va="top")
    save(fig, "fig1_skill_vs_lead.png")


def fig_ablation(main, abl):
    tab = pd.concat([abl, main[main["model"] == "hgb"].assign(model="hgb_ABCDE")])
    labels = {"hgb_A": "A: calendar + climatology", "hgb_AB": "+ B: own history",
              "hgb_ABC": "+ C: national load", "hgb_ABCD": "+ D: neighbours",
              "hgb_ABCDE": "+ E: sunset / darkness"}
    fig, ax = plt.subplots(figsize=FIGSIZE["wide"])
    for c, (m, lab) in zip(COLORS, labels.items()):
        skill_line(ax, tab, m, c, lab)
    bss_axes(ax, "Cumulative feature groups, gradient boosting",
             ymin=min(tab["bss_lo"].min(), 0) - 0.05)
    ax.legend(loc="upper right")
    save(fig, "fig2_ablation.png")
    return tab


def fig_groups(by_group):
    fig, ax = plt.subplots(figsize=FIGSIZE["wide"])
    for c, g in zip(COLORS, config.REGION_GROUPS):
        t = by_group[by_group["group"] == g]
        rate = t["base_rate"].iloc[0]
        skill_line(ax, t, "hgb", c, f"{g} (alert {rate:.0%} of hours)")
    bss_axes(ax, "Gradient boosting by region group", ymin=min(by_group.query("model=='hgb'")["bss_lo"].min(), 0) - 0.05)
    ax.legend(loc="upper right")
    save(fig, "fig3_region_groups.png")


def fig_calibration(pred):
    fig, ax = plt.subplots(figsize=FIGSIZE["single"])
    ax.plot([0, 1], [0, 1], color=COLORS[6], lw=0.8, ls="--")
    bins = np.linspace(0, 1, 11)
    for c, L in zip(COLORS, [1, 6, 24, 72]):
        g = pred[pred["lead"] == L]
        b = np.clip(np.digitize(g["hgb"], bins) - 1, 0, 9)
        cal = g.groupby(b).agg(p=("hgb", "mean"), y=("y", "mean"), n=("y", "size"))
        cal = cal[cal["n"] >= 50]
        ax.plot(cal["p"], cal["y"], "o-", color=c, label=f"lead {L} h")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Forecast probability")
    ax.set_ylabel("Observed frequency")
    ax.legend(loc="upper left")
    ax.text(0.5, -0.15, "Reliability, gradient boosting (bins with n >= 50)", transform=ax.transAxes,
            fontsize=FS, ha="center", va="top")
    save(fig, "fig4_calibration.png")


def fig_robustness(main, window, naive):
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE["panel_2"])
    panels = [(axes[0], window, "hgb_last_60d", "Last 2 months", "A. Training window"),
              (axes[1], naive, "hgb_no_naive", "Without naive records", "B. Records with invented end")]
    for ax, tab, m, lab, title in panels:
        skill_line(ax, main, "hgb", COLORS[0], "Last 12 months (main)")
        if tab is not None:
            skill_line(ax, tab, m, COLORS[1], lab)
        ymin = min(main.query("model=='hgb'")["bss_lo"].min(),
                   tab.query("model==@m")["bss_lo"].min() if tab is not None else 0, 0) - 0.05
        bss_axes(ax, title, ymin=ymin)
        ax.legend(loc="upper right")
    save(fig, "fig5_robustness.png")


def main():
    main_tab = load("main")
    by_group = pd.read_csv(RES / "scores_main_by_group.csv")
    abl, window, naive = load("ablation"), load("window"), load("naive")
    fig_main(main_tab)
    fig_groups(by_group)
    fig_calibration(pd.read_parquet(config.DATA_PROC / "pred_main.parquet"))
    fig_robustness(main_tab, window, naive)
    tabs = [main_tab, window, naive]
    if abl is not None:
        tabs.append(fig_ablation(main_tab, abl))

    from alerts.evaluate import horizons
    allt = pd.concat([t for t in tabs if t is not None]).drop_duplicates(["lead", "model"])
    h = horizons(allt)
    hg = horizons(by_group, by="group").pivot(index="model", columns="group", values="horizon_h")
    h = h.join(hg, on="model")
    h.to_csv(RES / "horizons.csv", index=False)
    wide = allt.pivot(index="model", columns="lead", values="bss").round(3)
    wide.to_csv(RES / "bss_by_lead.csv")
    print(h.to_string(index=False))
    print(wide.to_string())


if __name__ == "__main__":
    main()
