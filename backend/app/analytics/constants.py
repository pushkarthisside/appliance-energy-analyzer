"""Analytics constants (ARCHITECTURE.md §9). Frozen design parameters; not environment settings."""

WINDOW_DAYS = 21
WEEK_DAYS = 7
MINUTES_PER_DAY = 1440
WINDOW_MINUTES = WINDOW_DAYS * MINUTES_PER_DAY  # 30 240
WEEK_MINUTES = WEEK_DAYS * MINUTES_PER_DAY  # 10 080

WEEK_HOURS = 168
WINDOW_HOURS = 504
DAY_HOURS = 24

MIN_VALID_FRACTION = 0.80  # a week (or window) is valid at >= 80 % valid minutes
MIN_DAY_FRACTION = 0.50  # daily kWh is null below 50 % coverage (§7.4)
MIN_BASELINE_KWH_WEEK = 0.5
FLAG_THRESHOLD_FLOOR = 0.25
FLAG_ERROR_MULTIPLIER = 2
MIN_EXCESS_FLOOR_KWH = 1.0
DRIVER_MIN_RATIO = 1.10
DAYS_PER_MONTH = 30
SYNTHETIC_DEFAULT_UNCERTAINTY_PCT = 15

MAX_VALID_POWER_W = 30_000  # values above this become missing (§7.2)

WEEK_NAMES = ("baseline_1", "baseline_2", "current")
SIGNAL_STEP_MINUTES = 15
OTHER_ID = "other"
