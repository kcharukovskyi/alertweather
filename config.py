"""All fixed choices of the study live here, so every result can be traced to one place."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"

# Volunteer (eTryvoga) dataset, oblast level, updated daily. All times are UTC.
VOLUNTEER_URL = (
    "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/"
    "main/datasets/volunteer_data_en.csv"
)
# geoBoundaries ADM1, pinned to a commit so adjacency is reproducible.
GEOJSON_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/UKR/ADM1/"
    "geoBoundaries-UKR-ADM1.geojson"
)

TZ = "Europe/Kyiv"
LEADS = [1, 2, 3, 6, 12, 24, 36, 48, 60, 72]  # hours ahead; target = hour bucket [tau+L, tau+L+1h)

# Test: issue times from TEST_START (Kyiv) on, retrained weekly. Data is cut at TEST_END (Kyiv,
# exclusive) and the last issue time is TEST_END - max(LEADS), so every lead is scored on the
# same issue times and every target hour falls inside 1 Sep - 11 Oct.
TEST_START = "2026-09-01"
TEST_END = "2026-10-12"
RETRAIN_DAYS = 7
LONG_TEST_START = "2026-05-01"  # robustness: same pipeline, ~5 months of issue times

TRAIN_WINDOW_DAYS = 365  # base; the "recent" run uses 60 days (jet Shaheds, two-level alerts)
RECENT_WINDOW_DAYS = 60
MAX_ALERT_HOURS = 12  # longer records are mostly declaration/cancellation errors (e.g. 17 Apr 2026)
CLIM_DAYS = 28
N_BOOT = 2000
SEED = 0

# Luhansk (permanent alert since Apr 2022) and Crimea are not in the dataset as normal records.
# Odeska is put in "center" (rear, not on a land front line) — a judgment call, kept fixed here.
REGION_GROUPS = {
    "front": [
        "Chernihivska oblast", "Dnipropetrovska oblast", "Donetska oblast", "Kharkivska oblast",
        "Khersonska oblast", "Mykolaivska oblast", "Sumska oblast", "Zaporizka oblast",
    ],
    "center": [
        "Cherkaska oblast", "Kirovohradska oblast", "Kyiv City", "Kyivska oblast",
        "Odeska oblast", "Poltavska oblast", "Vinnytska oblast", "Zhytomyrska oblast",
    ],
    "west": [
        "Chernivetska oblast", "Ivano-Frankivska oblast", "Khmelnytska oblast", "Lvivska oblast",
        "Rivnenska oblast", "Ternopilska oblast", "Volynska oblast", "Zakarpatska oblast",
    ],
}
REGIONS = sorted(r for rs in REGION_GROUPS.values() for r in rs)

# geoBoundaries shapeName -> dataset region name (Luhansk, Crimea, Sevastopol are dropped).
GEO_NAMES = {
    "Cherkasy Oblast": "Cherkaska oblast",
    "Chernihiv Oblast": "Chernihivska oblast",
    "Chernivtsi Oblast": "Chernivetska oblast",
    "Dnipropetrovsk Oblast": "Dnipropetrovska oblast",
    "Donetsk Oblast": "Donetska oblast",
    "Ivano-Frankivsk Oblast": "Ivano-Frankivska oblast",
    "Kharkiv Oblast": "Kharkivska oblast",
    "Kherson Oblast": "Khersonska oblast",
    "Khmelnytskyi Oblast": "Khmelnytska oblast",
    "Kirovohrad Oblast": "Kirovohradska oblast",
    "Kyiv": "Kyiv City",
    "Kyiv Oblast": "Kyivska oblast",
    "Lviv Oblast": "Lvivska oblast",
    "Mykolaiv Oblast": "Mykolaivska oblast",
    "Odessa Oblast": "Odeska oblast",
    "Poltava Oblast": "Poltavska oblast",
    "Rivne Oblast": "Rivnenska oblast",
    "Sumy Oblast": "Sumska oblast",
    "Ternopil Oblast": "Ternopilska oblast",
    "Vinnytsia Oblast": "Vinnytska oblast",
    "Volyn Oblast": "Volynska oblast",
    "Zakarpattia Oblast": "Zakarpatska oblast",
    "Zaporizhia Oblast": "Zaporizka oblast",
    "Zhytomyr Oblast": "Zhytomyrska oblast",
}
