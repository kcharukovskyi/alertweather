"""Weekly walk-forward and skill scores against climatology with a day-block bootstrap."""
import time

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import config
from alerts.features import MIN_TAU, design

HOUR = pd.Timedelta(hours=1)


def test_weeks(grid):
    """(start, end) hour indices of issue-time blocks; the model is refit at each start."""
    start = pd.Timestamp(config.TEST_START, tz=config.TZ).tz_convert("UTC")
    # Issue times (exclusive end) whose longest-lead target bucket [tau+L, tau+L+1h) ends by TEST_END.
    stop = pd.Timestamp(config.TEST_END, tz=config.TZ).tz_convert("UTC") - max(config.LEADS) * HOUR
    idx = lambda ts: int((ts - grid[0]) / HOUR)
    weeks, ws = [], start
    while ws < stop:
        we = min(ws + pd.Timedelta(days=config.RETRAIN_DAYS), stop)
        weeks.append((idx(ws), idx(we)))
        ws += pd.Timedelta(days=config.RETRAIN_DAYS)
    return weeks


def make_model(kind, names):
    reg = names.index("region")
    if kind == "hgb":
        return HistGradientBoostingClassifier(
            learning_rate=0.08, max_iter=200, max_leaf_nodes=31, min_samples_leaf=200,
            l2_regularization=1.0, categorical_features=[reg], early_stopping=False,
            random_state=config.SEED)
    num = [i for i in range(len(names)) if i != reg]
    pre = ColumnTransformer([("num", StandardScaler(), num),
                             ("reg", OneHotEncoder(handle_unknown="ignore"), [reg])])
    return make_pipeline(pre, LogisticRegression(C=1.0, max_iter=2000))


def walk_forward(P, F, specs, window_days=config.TRAIN_WINDOW_DAYS, leads=config.LEADS):
    """specs: {name: (kind, feature names)}. Returns test predictions, one row per (tau, region, lead)."""
    names = list(dict.fromkeys(["clim", "active_now"] + [f for _, fs in specs.values() for f in fs]))
    R = len(config.REGIONS)
    out = []
    for L in leads:
        t0 = time.time()
        for w, (ws, we) in enumerate(test_weeks(P.grid)):
            lo = MIN_TAU if window_days is None else max(MIN_TAU, ws - window_days * 24)
            tr = np.arange(lo, ws - L)  # label bucket [tau+L, tau+L+1h) ends by the refit time
            te = np.arange(ws, we)
            assert tr[-1] + L + 1 <= ws and we + L <= len(P.grid)
            Xtr, ytr = design(F, P.Y, L, tr, names)
            Xte, yte = design(F, P.Y, L, te, names)
            frame = pd.DataFrame({
                "tau": np.repeat(P.grid[te], R), "region": np.tile(config.REGIONS, len(te)),
                "lead": L, "week": w, "y": yte,
                "clim": Xte[:, names.index("clim")], "pers": Xte[:, names.index("active_now")],
            })
            for name, (kind, feats) in specs.items():
                cols = [names.index(f) for f in feats]
                model = make_model(kind, feats).fit(Xtr[:, cols], ytr)
                frame[name] = model.predict_proba(Xte[:, cols])[:, 1]
            out.append(frame)
        print(f"  lead {L:>2}h: {time.time() - t0:.0f}s (train rows/week ~{len(ytr):,})", flush=True)
    return pd.concat(out, ignore_index=True)


def scores(df, models, by=None, n_boot=config.N_BOOT, seed=config.SEED):
    """Brier, BSS vs climatology with a 95% bootstrap CI over days (Kyiv dates), log-loss."""
    rng = np.random.default_rng(seed)
    df = df.assign(day=df["tau"].dt.tz_convert(config.TZ).dt.date)
    keys = ["lead"] + ([by] if by else [])
    rows = []
    for key, g in df.groupby(keys):
        day, _ = pd.factorize(g["day"])
        D = day.max() + 1
        y = g["y"].to_numpy(float)
        ref = np.bincount(day, (g["clim"].to_numpy(float) - y) ** 2, D)
        idx = rng.integers(0, D, (n_boot, D))
        ref_b = ref[idx].sum(1)
        for m in ["clim"] + models:
            p = g[m].to_numpy(float)
            se = np.bincount(day, (p - y) ** 2, D)
            boot = 1 - se[idx].sum(1) / ref_b
            pc = np.clip(p, 1e-3, 1 - 1e-3)
            rows.append({
                **dict(zip(keys, key if isinstance(key, tuple) else (key,))),
                "model": m, "n": len(y), "base_rate": y.mean(), "brier": se.sum() / len(y),
                "bss": 1 - se.sum() / ref.sum(),
                "bss_lo": np.percentile(boot, 2.5), "bss_hi": np.percentile(boot, 97.5),
                "logloss": -np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)),
            })
    return pd.DataFrame(rows)


def horizons(tab, by=None):
    """horizon_h: largest lead with the BSS 95% CI entirely above zero (0 if none).
    horizon_strict_h: last lead before the CI first touches zero (all shorter leads significant)."""
    keys = ["model"] + ([by] if by else [])
    rows = []
    for key, g in tab.groupby(keys):
        g = g.sort_values("lead")
        sig = (g["bss_lo"] > 0).to_numpy()
        leads = g["lead"].to_numpy()
        first_fail = np.argmin(sig) if not sig.all() else len(sig)
        rows.append({**dict(zip(keys, key)),
                     "horizon_h": leads[sig].max() if sig.any() else 0,
                     "horizon_strict_h": leads[first_fail - 1] if first_fail > 0 else 0})
    return pd.DataFrame(rows)
