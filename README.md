# How far ahead can air-raid alerts in Ukraine be forecast?

A probabilistic forecast, per oblast, of whether the oblast will be under an air-raid alert at
any moment of the hour **[τ+L, τ+L+1h)**, issued at instant **τ**, for leads
**L = 1, 2, 3, 6, 12, 24, 48, 72 h**.

**Forecast horizon** = the largest lead at which a model is *significantly* better than
climatology: Brier Skill Score (BSS) > 0 and the 95% day-block bootstrap interval excludes zero.

<!-- RESULTS -->

## Data

| Source | Use |
|---|---|
| [Vadimkin/ukrainian-air-raid-sirens-dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset), `volunteer_data_en.csv` (eTryvoga), oblast level, UTC | the only model input and the target |
| same repo, `official_data_en.csv` | not used: it ends on 7 Sep 2026 (covers one test week) and since Dec 2025 is mostly raion-level |
| [geoBoundaries UKR ADM1](https://www.geoboundaries.org/), pinned commit | oblast adjacency (`results/adjacency.json`) and centroids for the sun position |

Cleaning (`alerts/data.py`):

* **24 regions**, not 25: Luhansk oblast (permanent alert since Apr 2022) has 3 records and
  Crimea none, so neither can be modelled. Kyiv City is a separate region.
* **Permanent raion-level alerts near the front are not in the input.** The volunteer data is
  oblast-level only, so single raions cannot be removed from it — and they do not need to be.
  In the official raion-level data (Aug – 6 Sep 2026) every raion of Donetska oblast, Nikopolskyi,
  Synelnykivskyi and Melitopolskyi raions are under alert ~98% of hours; aggregated to "any raion
  of the oblast" this gives 98–100% for front-line oblasts, while the volunteer oblast record gives
  24% (Donetska), 31% (Zaporizka), 74% (Dnipropetrovska). The volunteer record therefore does not
  carry these permanent artillery alerts, and the official data aggregated to oblasts would be useless as a target.
* Records longer than **12 h** are dropped: they are mostly declaration/cancellation errors
  (e.g. 17–22 Apr 2026 in the west) and are not worth forecasting.
* Records with an invented end (`naive=True`, end = start + 30 min, ~5% of records) are kept,
  because their start is real; a sensitivity run drops them.
* Overlapping intervals are merged per region; the result is an hourly panel:
  `Y[t] = 1` if the oblast was under alert at any moment of the hour `[t, t+1h)` (the target),
  `A[t] = 1` if an alert was active at the instant `t` (the "state now").

## No-leakage rules

* The target is the hour **starting** at `τ+L`. (A first version used the hour `[τ+L-1h, τ+L)`;
  for L = 1 that is the hour starting at `τ`, which is under alert by definition whenever an alert
  is active at `τ`, and inflated L = 1 skill from ~0.03 to 0.29. Fixed.)
* A forecast issued at `τ` uses only `Y` for hours that ended by `τ` and the state `A[τ]`.
  "Hours since the last alert ended" uses the end time only if it is before `τ`.
* Climatology for target hour `t*` uses the same UTC hour over 28 days, shifted back by
  `ceil((L+1)/24)` days so that its newest hour ended by `τ` (L = 24 cannot use today's hour,
  which is still running at `τ`). Guarded by an `assert` in `features.design`.
* Calendar and sun-position features are computed for the target hour; they are deterministic.
* **Walk-forward:** the model is refit every 7 days at `s`; training rows have `τ + L ≤ s`, so
  every training label was already observed at the refit time. Forecasts in that week use
  that model only.

## Evaluation

* Issue times **1 Sep 2026 00:00 – 8 Oct 2026 23:00 (Kyiv)**, so that every lead is scored on
  the *same* issue times and every target hour falls in 1 Sep – 11 Oct. 6 weekly refits.
* Training window: **last 12 months** before each refit (base) and **last 2 months** (additional
  run): with jet-powered Shaheds and the two-level alert system the regime changed, and Sep 2026
  had about 2× the records of Sep 2025.
* Horizon is reported two ways: `horizon_h` (largest lead with the CI above zero, the definition
  above) and `horizon_strict_h` (last lead before the CI first touches zero).
* Metrics: Brier score, **BSS vs climatology**, log-loss (probabilities clipped to [0.001, 0.999]),
  reliability diagram. CI: 2000 bootstrap resamples of Kyiv calendar days (keeps within-day
  dependence between hours and regions).

## Models

| Model | Inputs |
|---|---|
| Climatology (baseline) | share of alert hours in the same hour of day over the last 28 days |
| Persistence | the state at `τ` (0/1) |
| Logistic regression | all feature groups, standardised, region one-hot |
| Gradient boosting | all feature groups, `HistGradientBoostingClassifier`, region as categorical |

One pooled model per lead for all 24 regions.

### Feature groups (`alerts/features.py`)

| Group | Features |
|---|---|
| A. Calendar + climatology | region, 28-day climatology of the target hour, hour of day and day of week (Kyiv time, sin/cos) |
| B. Own history | state now, duration of the current alert, hours since the last alert ended, last hour, share of alert hours over 24 h and 7 d, number of alert starts over 24 h and 7 d |
| C. National load | share of regions under alert now, mean alert share and starts over 24 h across regions |
| D. Neighbours | share of adjacent oblasts under alert now and over 24 h (adjacency from GeoJSON) |
| E. Darkness | solar elevation and hours since sunset at the target hour, at the oblast centroid (NOAA formula) |

Ablation adds groups cumulatively (A → AB → ABC → ABCD → ABCDE) with gradient boosting.

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py main ablation window naive   # downloads data, ~15-20 min on 8 cores
.venv/bin/python report.py                           # figures + tables in results/
```

## Layout

```
config.py           every fixed choice: leads, test window, regions and groups, URLs
alerts/data.py      download, cleaning, interval merge, hourly panel
alerts/geo.py       adjacency + centroids from GeoJSON
alerts/features.py  feature groups and the leakage-safe design matrix
alerts/evaluate.py  weekly walk-forward, BSS with day-block bootstrap, horizon
run.py / report.py  experiments / figures and tables
results/            scores_*.csv, horizons.csv, bss_by_lead.csv, figures/
```
