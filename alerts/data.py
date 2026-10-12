"""Alert intervals -> hourly region panel.

Conventions (all UTC, hour index t = hours since grid start):
  Y[t]  1 if the region was under alert at any moment of the bucket [t, t+1h)  -> the target
  A[t]  1 if an alert was active at the instant t                               -> "state now"
A forecast issued at instant tau may use Y[:tau], A[tau] and anything derived from them.
"""
import urllib.request
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config

H = pd.Timedelta(hours=1)


def fetch(url, path, force=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if force or not path.exists():
        urllib.request.urlretrieve(url, path)
    return path


def load_intervals(drop_naive=False, refresh=False):
    """Clean volunteer records and merge overlapping intervals per region."""
    path = fetch(config.VOLUNTEER_URL, config.DATA_RAW / "volunteer_data_en.csv", force=refresh)
    df = pd.read_csv(path)
    df["start"] = pd.to_datetime(df["started_at"], utc=True)
    df["end"] = pd.to_datetime(df["finished_at"], utc=True)
    df["naive"] = df["naive"].astype(str).eq("True")
    df = df[df["region"].isin(config.REGIONS)]
    dur = df["end"] - df["start"]
    df = df[(dur > pd.Timedelta(0)) & (dur <= pd.Timedelta(hours=config.MAX_ALERT_HOURS))]
    if drop_naive:
        df = df[~df["naive"]]

    merged = []
    for region, g in df.sort_values("start").groupby("region"):
        prev_end = g["end"].cummax().shift()
        block = (g["start"] > prev_end).cumsum()
        m = g.groupby(block).agg(start=("start", "min"), end=("end", "max"))
        m["region"] = region
        merged.append(m)
    return pd.concat(merged, ignore_index=True)[["region", "start", "end"]]


@dataclass
class Panel:
    grid: pd.DatetimeIndex  # UTC hour starts
    Y: np.ndarray  # (T, R) int8, any alert in bucket
    A: np.ndarray  # (T, R) int8, alert active at instant t
    S: np.ndarray  # (T, R) int16, alert starts in bucket
    since_end: np.ndarray  # (T, R) hours since last alert ended at instant t (0 if active, nan if none)
    ongoing: np.ndarray  # (T, R) hours since the current alert started (0 if none)


def _cover(i0, i1, T):
    diff = np.zeros(T + 1, np.int32)
    np.add.at(diff, np.clip(i0, 0, T), 1)
    np.add.at(diff, np.clip(i1, 0, T), -1)
    return (np.cumsum(diff[:T]) > 0).astype(np.int8)


def build_panel(intervals):
    t0 = intervals["start"].min().floor("h")
    end = pd.Timestamp(config.TEST_END, tz=config.TZ).tz_convert("UTC")
    grid = pd.date_range(t0, end, freq="h", inclusive="left")
    T, R = len(grid), len(config.REGIONS)
    Y = np.zeros((T, R), np.int8)
    A = np.zeros((T, R), np.int8)
    S = np.zeros((T, R), np.int16)
    since_end = np.full((T, R), np.nan, np.float32)
    ongoing = np.zeros((T, R), np.float32)
    tt = np.arange(T, dtype=float)

    for j, region in enumerate(config.REGIONS):
        g = intervals[intervals["region"] == region].sort_values("start")
        s = ((g["start"] - t0) / H).to_numpy(float)
        e = ((g["end"] - t0) / H).to_numpy(float)
        Y[:, j] = _cover(np.floor(s).astype(int), np.ceil(e).astype(int), T)
        first = np.floor(s).astype(int)
        np.add.at(S[:, j], first[first < T], 1)
        # Last interval that started at or before t; it is "active" if it has not ended by t.
        i = np.searchsorted(s, tt, side="right") - 1
        seen = i >= 0
        si, ei = s[i.clip(0)], e[i.clip(0)]
        active = seen & (ei > tt)
        A[:, j] = active
        since_end[:, j] = np.where(active, 0.0, np.where(seen, tt - ei, np.nan))
        ongoing[:, j] = np.where(active, tt - si, 0.0)
    return Panel(grid, Y, A, S, since_end, ongoing)
