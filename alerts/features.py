"""Feature groups for a forecast issued at instant tau for the hour bucket t* = tau + L,
i.e. the hour [tau+L, tau+L+1h). (Bucket tau itself would be partly "now": A[tau]=1 implies Y[tau]=1.)

tau-features read only Y[:tau] / A[tau]. Target-time features are deterministic functions of the
calendar and the sun at t*. Climatology for t* uses only same-hour buckets that ended before tau.
"""
import numpy as np

import config

GROUPS = {
    "A": ["region", "clim", "hod_sin", "hod_cos", "dow_sin", "dow_cos"],
    "B": ["active_now", "ongoing_h", "log_since_end", "last_bucket",
          "on_24h", "on_7d", "starts_24h", "starts_7d"],
    "C": ["nat_active_now", "nat_on_24h", "nat_starts_24h"],
    "D": ["nb_active_now", "nb_on_24h"],
    "E": ["sun_elev", "h_since_sunset"],
}
TARGET_TIME = {"hod_sin", "hod_cos", "dow_sin", "dow_cos", "sun_elev", "h_since_sunset"}
MIN_TAU = 24 * 35  # enough history for 28-day climatology and 7-day counts


def _past_sum(X, w):
    """Sum of X over buckets [t-w, t): fully observed at instant t."""
    T = X.shape[0]
    c = np.zeros((T + 1, X.shape[1]))
    np.cumsum(X, axis=0, out=c[1:])
    return c[:T] - c[np.maximum(np.arange(T) - w, 0)]


def _solar(grid, lat, lon):
    """NOAA approximation: solar elevation and hours since sunset at each bucket midpoint."""
    t = grid + np.timedelta64(30, "m")
    doy = t.dayofyear.to_numpy()[:, None]
    hour = (t.hour + t.minute / 60).to_numpy()[:, None]
    g = 2 * np.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                    - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    latr, lon = np.radians(lat)[None, :], lon[None, :]
    ha = np.radians((hour * 60 + eqt + 4 * lon) / 4 - 180)
    cosz = np.sin(latr) * np.sin(decl) + np.cos(latr) * np.cos(decl) * np.cos(ha)
    elev = 90 - np.degrees(np.arccos(np.clip(cosz, -1, 1)))
    cos_hs = np.cos(np.radians(90.833)) / (np.cos(latr) * np.cos(decl)) - np.tan(latr) * np.tan(decl)
    sunset = 720 - 4 * lon - eqt + 4 * np.degrees(np.arccos(np.clip(cos_hs, -1, 1)))  # min UTC
    return elev, ((hour * 60 - sunset) / 60) % 24


def build_features(P, adj, lat, lon):
    T, R = P.Y.shape
    Y, A, S = (x.astype(np.float32) for x in (P.Y, P.A, P.S))
    nat = lambda X: np.repeat(X.mean(1, keepdims=True), R, axis=1)
    W = adj / adj.sum(1, keepdims=True)

    F = {"region": np.broadcast_to(np.arange(R), (T, R))}
    F["active_now"] = A
    F["ongoing_h"] = P.ongoing
    F["log_since_end"] = np.log1p(np.nan_to_num(np.minimum(P.since_end, 720), nan=720))
    F["last_bucket"] = np.vstack([np.zeros((1, R)), Y[:-1]])
    F["on_24h"] = _past_sum(Y, 24) / 24
    F["on_7d"] = _past_sum(Y, 168) / 168
    F["starts_24h"] = _past_sum(S, 24)
    F["starts_7d"] = _past_sum(S, 168)
    F["nat_active_now"] = nat(A)
    F["nat_on_24h"] = nat(F["on_24h"])
    F["nat_starts_24h"] = nat(F["starts_24h"])
    F["nb_active_now"] = A @ W.T
    F["nb_on_24h"] = F["on_24h"] @ W.T

    local = P.grid.tz_convert(config.TZ)
    hod = 2 * np.pi * (local.hour.to_numpy() + 0.5) / 24
    dow = 2 * np.pi * local.dayofweek.to_numpy() / 7
    for name, v in [("hod_sin", np.sin(hod)), ("hod_cos", np.cos(hod)),
                    ("dow_sin", np.sin(dow)), ("dow_cos", np.cos(dow))]:
        F[name] = np.repeat(v[:, None], R, axis=1)
    F["sun_elev"], F["h_since_sunset"] = _solar(P.grid, lat, lon)

    # clim_base[t] = share of alert in the same UTC hour over the 28 days before bucket t.
    n = config.CLIM_DAYS
    acc = np.zeros((T, R))
    for k in range(1, n + 1):
        acc[24 * k:] += Y[:-24 * k]
    F["_clim_base"] = np.where(np.arange(T)[:, None] >= 24 * n, acc / n, np.nan)
    return {k: np.ascontiguousarray(v, dtype=np.float32) for k, v in F.items()}


def design(F, Y, L, tau, names):
    """Rows ordered (tau, region). Returns X (n*R, len(names)) and y for bucket tau+L."""
    t_star = tau + L
    # Shift the climatology anchor back by whole days so its newest bucket (anchor-24) has ended
    # by tau: k0 = ceil((L+1)/24) days, e.g. L=24 cannot use bucket tau, which is still running.
    anchor = t_star - 24 * (-(-(L + 1) // 24) - 1)
    assert (anchor - 24 + 1 <= tau).all(), "climatology would use an unfinished hour"
    cols = []
    for n in names:
        if n == "clim":
            src = F["_clim_base"][anchor]
        elif n in TARGET_TIME:
            src = F[n][t_star]
        else:
            src = F[n][tau]
        cols.append(src.reshape(-1))
    return np.column_stack(cols), Y[t_star].reshape(-1)
