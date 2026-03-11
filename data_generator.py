"""
NEL Dataset Generator — Fesdis, Batna, Algeria
Higher National School of Renewable Energies, Environment and Sustainable Development

Generates 5 realistic CSV datasets based on Batna's actual climate:
  - Latitude:  35.55°N
  - Altitude:  1037m ASL
  - Climate:   Semi-arid (BSk), cold winters / hot summers
  - Solar:     ~3300 sunshine hours/year, peak irradiance ~950 W/m²
  - Wind:      Mean 4.36 m/s at 10m AGL, higher in spring (Mar–Sep)

Data range: 2020-01-01 → 2026-03-10  (~6.2 years)
Sample rate: 1 minute during lab hours (08:00–18:00), weekdays only
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# ── Reproducibility ──────────────────────────────────────────────────────────
rng = np.random.default_rng(42)

# ── Output folder ────────────────────────────────────────────────────────────
OUT = "nel_datasets"
os.makedirs(OUT, exist_ok=True)

# ── Date range ───────────────────────────────────────────────────────────────
START = datetime(2020, 1, 1)
END   = datetime(2026, 3, 10)

# ── Helpers ──────────────────────────────────────────────────────────────────

def lab_timestamps(sample_minutes=5):
    """
    Generate timestamps for lab working hours only:
    Weekdays (Mon–Fri), 08:00–18:00, every `sample_minutes` minutes.
    ~120 samples/day × ~260 days/year × 6.2 years ≈ ~193 000 rows per dataset.
    """
    stamps = []
    current = START.replace(hour=8, minute=0, second=0)
    while current <= END:
        # skip weekends (5=Sat, 6=Sun)
        if current.weekday() < 5 and current.hour < 18:
            stamps.append(current)
        current += timedelta(minutes=sample_minutes)
    return pd.DatetimeIndex(stamps)

def clip(arr, lo, hi):
    return np.clip(arr, lo, hi)

def noise(size, scale=1.0):
    return rng.normal(0, scale, size)

# ── Climate helpers ───────────────────────────────────────────────────────────

def batna_temperature(ts):
    """
    Monthly mean temperatures (°C) for Batna, Algeria.
    Returns outdoor ambient temp array matching ts.
    """
    # Monthly mean highs (°C): Jan–Dec
    monthly_mean = np.array([5.1, 6.1, 8.95, 12.5, 17.5, 22.5,
                             27.5, 27.2, 21.35, 16.0, 9.75, 6.35])
    month_idx = ts.month - 1
    base = monthly_mean[month_idx]
    # diurnal swing: cooler morning, hotter midday
    hour_factor = np.sin(np.pi * (ts.hour - 8) / 10)  # 0→1→0 over 08:00–18:00
    diurnal = hour_factor * 6
    return base + diurnal + noise(len(ts), 1.2)

def batna_solar_rad(ts):
    """
    Realistic solar irradiance (W/m²) for Batna, Algeria.
    Peak summer ~950 W/m², winter ~500 W/m² at noon.
    Zero at night (guaranteed by lab hours 08:00–18:00).
    """
    doy = ts.dayofyear
    # Seasonal peak (W/m²): summer high, winter low
    seasonal_peak = 500 + 450 * np.sin(np.pi * (doy - 80) / 365)
    seasonal_peak = clip(seasonal_peak, 300, 950)
    # Solar angle (0 at 08:00 and 18:00, 1 at 13:00)
    solar_angle = np.sin(np.pi * (ts.hour + ts.minute/60 - 8) / 10)
    solar_angle = clip(solar_angle, 0, 1)
    rad = seasonal_peak * solar_angle
    # Cloud cover: random 15% of days partially cloudy, 5% overcast
    cloud = rng.choice([1.0, 0.6, 0.2],
                       size=len(ts),
                       p=[0.80, 0.15, 0.05])
    rad = rad * cloud + noise(len(ts), 15)
    return clip(rad, 0, 1000)

def batna_wind_speed(ts):
    """
    Wind speed (m/s) for Batna. Mean 4.36 m/s.
    Higher in spring (Mar–Sep): 3–8 m/s.
    Calmer in winter (Nov–Feb): 1.5–5 m/s.
    """
    month = ts.month
    # Seasonal mean
    seasonal_mean = np.where(
        (month >= 3) & (month <= 9), 4.8, 3.2
    ).astype(float)
    # Weibull-like: use log-normal to avoid negatives
    log_mean = np.log(seasonal_mean) - 0.2
    speed = rng.lognormal(log_mean, 0.4, len(ts))
    # Daily pattern: windier during midday hours
    hour_boost = 0.5 * np.sin(np.pi * (ts.hour - 8) / 10)
    return clip(speed + hour_boost, 0.0, 12.0)

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 1 — SOLAR PV
# Experiments: S01–S06
# Features extracted from NEL Experiment Guide
# ─────────────────────────────────────────────────────────────────────────────
print("Generating solar dataset...")
ts = lab_timestamps(sample_minutes=5)
n  = len(ts)

T_outdoor  = batna_temperature(ts)
Solar_Rad  = batna_solar_rad(ts)

# Panel temperatures: follow outdoor + self-heating under irradiance
T_SOL1 = T_outdoor + Solar_Rad * 0.025 + noise(n, 1.5)
T_SOL2 = T_outdoor + Solar_Rad * 0.023 + noise(n, 1.5)

# Tilt and azimuth angles — rotate through experimental configurations
tilt_options    = np.array([15, 30, 45])
azimuth_options = np.array([-30, 0, 30])
# Assign a configuration per day (changes daily in experiments)
days = (ts - ts[0]).days
tilt_angle    = tilt_options[days % 3]
azimuth_angle = azimuth_options[days % 3]

# Panel voltage: V_OC ~21V, drops with temperature, rises with irradiance
# V = Voc - k_T*(T-25) + k_G*log(G/1000)
V_OC = 21.0
k_T  = 0.08   # V/°C temperature coefficient
k_G  = 2.0    # voltage boost from irradiance
rad_safe = np.where(Solar_Rad > 1, Solar_Rad, 1)

V_SOL1 = V_OC - k_T * (T_SOL1 - 25) + k_G * np.log10(rad_safe / 100 + 1)
V_SOL1 = V_SOL1 * np.cos(np.radians(azimuth_angle)) * (1 - 0.002 * (tilt_angle - 45)**2 / 45)
V_SOL1 = clip(V_SOL1 + noise(n, 0.4), 0, 22)

V_SOL2 = V_OC - k_T * (T_SOL2 - 25) + k_G * np.log10(rad_safe / 100 + 1)
V_SOL2 = V_SOL2 * np.cos(np.radians(azimuth_angle)) * (1 - 0.002 * (tilt_angle - 45)**2 / 45)
V_SOL2 = clip(V_SOL2 + noise(n, 0.4), 0, 22)

# Current: proportional to irradiance, slight temp dependence
I_SC = 5.5   # short-circuit current at 1000 W/m²
I_SOL = I_SC * (Solar_Rad / 1000) + noise(n, 0.1)
I_SOL = clip(I_SOL, 0, 6.0)

# Powers
P_SOL1      = V_SOL1 * I_SOL
P_SOL2      = V_SOL2 * I_SOL
P_SOL_total = P_SOL1 + P_SOL2

# Fixed solar modules (S05 — slightly different specs)
V_SOL3  = clip((V_SOL1 + V_SOL2) / 2 + noise(n, 0.3), 0, 22)
I_SOL3  = clip(I_SOL * 2.0 + noise(n, 0.2), 0, 12)

# Shading factor (0=no shade, 1=full shade): mostly clear, occasional cloud
shading_factor = rng.choice([0.0, 0.2, 0.5, 1.0],
                            size=n, p=[0.78, 0.12, 0.07, 0.03])

# Load voltage and current
V_Load = clip(V_SOL1 + V_SOL2 + noise(n, 0.5), 0, 44)
I_Load = clip(I_SOL * rng.uniform(0.6, 0.95, n) + noise(n, 0.05), 0, 6.0)

df_solar = pd.DataFrame({
    "timestamp":      ts,
    "V_SOL1_V":       np.round(V_SOL1, 3),
    "V_SOL2_V":       np.round(V_SOL2, 3),
    "I_SOL_A":        np.round(I_SOL, 3),
    "P_SOL1_W":       np.round(P_SOL1, 3),
    "P_SOL2_W":       np.round(P_SOL2, 3),
    "P_SOL_total_W":  np.round(P_SOL_total, 3),
    "Solar_Rad_Wm2":  np.round(Solar_Rad, 1),
    "T_SOL1_C":       np.round(T_SOL1, 2),
    "T_SOL2_C":       np.round(T_SOL2, 2),
    "T_outdoor_C":    np.round(T_outdoor, 2),
    "tilt_angle_deg": tilt_angle,
    "azimuth_angle_deg": azimuth_angle,
    "shading_factor": shading_factor,
    "V_SOL3_V":       np.round(V_SOL3, 3),
    "I_SOL3_A":       np.round(I_SOL3, 3),
    "V_Load_V":       np.round(V_Load, 3),
    "I_Load_A":       np.round(I_Load, 3),
})
df_solar.to_csv(f"{OUT}/dataset_solar.csv", index=False)
print(f"  ✓ dataset_solar.csv — {len(df_solar):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 2 — WIND ENERGY
# Experiments: W01–W03
# ─────────────────────────────────────────────────────────────────────────────
print("Generating wind dataset...")
# Wind uses 60-second logging for long-term experiments
ts_w = lab_timestamps(sample_minutes=1)
n_w  = len(ts_w)

Windspeed = batna_wind_speed(ts_w)
T_out_w   = batna_temperature(ts_w)

# Wind turbine power curve (simplified Betz model for small lab turbine)
# Rated power ~150W at ~8 m/s, cut-in ~1.5 m/s, cut-out ~12 m/s
def wind_power_curve(v):
    """Small lab wind turbine: rated ~150W at 8 m/s"""
    p = np.zeros_like(v)
    # Cut-in to rated (cubic region)
    mask_ramp = (v >= 1.5) & (v < 8.0)
    p[mask_ramp] = 150 * ((v[mask_ramp] - 1.5) / (8.0 - 1.5)) ** 3
    # Rated region
    mask_rated = (v >= 8.0) & (v < 12.0)
    p[mask_rated] = 150.0
    # Cut-out
    p[v >= 12.0] = 0.0
    return p

P_Wind_ideal = wind_power_curve(Windspeed)

# Voltage and current from wind turbine (DC output, ~24V nominal)
V_Wind = clip(12 + 1.5 * Windspeed + noise(n_w, 0.5), 0, 32)
I_Wind = clip(P_Wind_ideal / np.where(V_Wind > 1, V_Wind, 1) + noise(n_w, 0.05), 0, 6.5)
P_Wind = V_Wind * I_Wind

# Wind battery (12V lead-acid, 50Ah)
# SoC drifts realistically over time based on charge/discharge
SoC_WB_init = 70.0
SoC_WB = np.zeros(n_w)
SoC_WB[0] = SoC_WB_init
battery_capacity_Wh = 12 * 50   # 600 Wh

for i in range(1, n_w):
    dt_h = 1 / 60  # 1 minute in hours
    # Net power to battery = wind power - load
    P_load_i = rng.uniform(20, 80)
    net = P_Wind[i] - P_load_i
    delta_SoC = (net * dt_h / battery_capacity_Wh) * 100
    SoC_WB[i] = clip(np.array([SoC_WB[i-1] + delta_SoC + noise(1, 0.05)[0]]), 20, 100)[0]

V_WB = 10.8 + (SoC_WB / 100) * 2.4 + noise(n_w, 0.08)  # 10.8V–13.2V
V_WB = clip(V_WB, 10.5, 14.5)
I_WB = clip((P_Wind - rng.uniform(20, 80, n_w)) / np.where(V_WB > 1, V_WB, 1) + noise(n_w, 0.1), -5, 5)
P_WB = V_WB * I_WB

# Electronic load
V_Load_w = clip(V_WB + noise(n_w, 0.2), 10, 14)
I_Load_w = clip(rng.uniform(1, 6, n_w) + noise(n_w, 0.1), 0, 7)
P_Load_w = V_Load_w * I_Load_w

df_wind = pd.DataFrame({
    "timestamp":    ts_w,
    "Windspeed_ms": np.round(Windspeed, 3),
    "V_Wind_V":     np.round(V_Wind, 3),
    "I_Wind_A":     np.round(I_Wind, 3),
    "P_Wind_W":     np.round(P_Wind, 3),
    "SoC_WB_pct":   np.round(SoC_WB, 2),
    "V_WB_V":       np.round(V_WB, 3),
    "I_WB_A":       np.round(I_WB, 3),
    "P_WB_W":       np.round(P_WB, 3),
    "V_Load_V":     np.round(V_Load_w, 3),
    "I_Load_A":     np.round(I_Load_w, 3),
    "P_Load_W":     np.round(P_Load_w, 3),
    "T_outdoor_C":  np.round(T_out_w, 2),
})
df_wind.to_csv(f"{OUT}/dataset_wind.csv", index=False)
print(f"  ✓ dataset_wind.csv — {len(df_wind):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 3 — FUEL CELL & HYDROGEN GENERATOR
# Experiments: F01–F04
# ─────────────────────────────────────────────────────────────────────────────
print("Generating fuel cell dataset...")
ts_f = lab_timestamps(sample_minutes=5)
n_f  = len(ts_f)
T_out_f = batna_temperature(ts_f)

# ── GROUP A — H2 PRODUCTION (inputs come from renewable sources) ──────────────
# The hydrogen generator is powered by surplus renewable energy
# (solar + wind), NOT by the grid. This reflects the green hydrogen principle:
# when generation > load → excess energy goes to the electrolyser → H2 stored.

# Simulate solar and wind for this combined experiment session
Solar_Rad_f   = batna_solar_rad(ts_f)
Windspeed_f   = batna_wind_speed(ts_f)

# Solar power (simplified from solar model output)
P_SOL_total_f = clip(Solar_Rad_f * 0.18 + noise(n_f, 3), 0, 200)   # W

# Wind power (simplified from wind turbine model)
def _wind_power(v):
    p = np.zeros_like(v)
    mask = (v >= 1.5) & (v < 8.0)
    p[mask] = 150 * ((v[mask] - 1.5) / 6.5) ** 3
    p[v >= 8.0] = 150.0
    return p
P_Wind_f = clip(_wind_power(Windspeed_f) + noise(n_f, 2), 0, 150)  # W

# Battery SoC at the moment of the experiment
SoC_BB_f = clip(rng.uniform(20, 100, n_f) + noise(n_f, 1), 15, 100)  # %

# Load demand during the session
load_profile_set_f = clip(100 + 80 * np.sin(np.pi * (ts_f.hour - 8) / 10)
                          + noise(n_f, 15), 50, 400)                  # W

# Renewable surplus → drives the electrolyser
# If surplus > 0: electrolyser runs and produces H2
# If surplus <= 0 (or battery SoC < 20%): fall back to battery or FC alone
renewable_total_f = P_SOL_total_f + P_Wind_f
surplus_f = clip(renewable_total_f - load_profile_set_f, 0, None)    # W

# H2 flow from electrolyser: proportional to surplus power
# ~0.42 Nl/min per 100W of surplus (real electrolyser efficiency ~65%)
H2_Flow_HG = clip(surplus_f * 0.0042 + noise(n_f, 0.001), 0, 2.0)   # Nl/min

# H2 pressure builds as function of flow rate and session duration
H2_Pres_HG = clip(H2_Flow_HG * 1.8 + 2.0 + noise(n_f, 0.1), 0, 5.0)  # bar

# Electrolyser electrical measurements
# P_HG is the power consumed by the electrolyser (= surplus used)
P_HG  = clip(surplus_f * 0.65 + noise(n_f, 2), 0, None)              # W  (65% efficiency)
V_HG  = clip(2.0 + 0.4 * np.sqrt(np.where(P_HG > 0, P_HG, 0))
             + noise(n_f, 0.15), 2.0, 8.0)                            # V
I_HG  = clip(np.where(V_HG > 0.5, P_HG / V_HG, 0)
             + noise(n_f, 0.1), 0, 9.0)                               # A

# ── GROUP B — FUEL CELL (inputs come from Group A outputs) ───────────────────
# Fuel cell activates when H2 pressure is sufficient (> 1 bar)
# and renewable sources alone cannot meet the load demand.

# Polarisation curve: V = V_OC − R_int×I − B×log(I/I0 + 1)
V_FC_OC  = 28.0    # V  open circuit voltage
R_int_FC = 0.8     # Ω  internal resistance
I_FC     = clip(rng.uniform(0.5, 5.5, n_f) + noise(n_f, 0.15), 0.1, 6.0)  # A

# FC only produces power when H2 pressure is available
fc_active = (H2_Pres_HG > 1.0).astype(float)
I_FC      = I_FC * fc_active

V_FC     = V_FC_OC - R_int_FC * I_FC - 1.2 * np.log(I_FC / 0.1 + 1)
V_FC     = clip(V_FC + noise(n_f, 0.2), 0, 28)
P_FC     = clip(V_FC * I_FC, 0, 100)                                  # W
I_FC_int = clip(I_FC * 1.05 + noise(n_f, 0.05), 0, 6.5)

# Temperature: rises with load, ambient baseline
T_FC = T_out_f + 15 + P_FC * 0.1 + noise(n_f, 1.5)
T_FC = clip(T_FC, 20, 75)

# H2 consumption at FC inlet (drawn from stored H2)
H2_Flow_FC = clip(P_FC * 0.009 + noise(n_f, 0.002), 0.0, 0.6)        # Nl/min
H2_Pres_FC = clip(H2_Pres_HG - H2_Flow_FC * 0.5
                  + noise(n_f, 0.05), 0, 5.0)                          # bar

# DC-DC converter (fuel cell → buffer battery bus)
V_BB_f    = clip(rng.uniform(24, 28, n_f) + noise(n_f, 0.3), 22, 30)  # V
I_FC_DCDC = clip(I_FC * 0.92 + noise(n_f, 0.05), 0, 6.0)
P_FC_DCDC = V_BB_f * I_FC_DCDC

# Efficiencies
Efficiency_FC = clip(
    np.where(H2_Flow_FC > 0,
             (P_FC / (H2_Flow_FC * 60 * 3.5 + 0.01)) * 100,
             0), 0, 60)                                                 # %
Efficiency_HG = clip(
    np.where(P_HG > 0,
             (H2_Flow_HG * 60 * 3.5 / (P_HG + 0.01)) * 100,
             0), 0, 75)                                                 # %

# Load
V_Load_f = clip(V_BB_f + noise(n_f, 0.2), 20, 30)
I_Load_f = clip(P_FC / np.where(V_Load_f > 1, V_Load_f, 1)
                * rng.uniform(0.7, 0.95, n_f), 0, 5)

df_fc = pd.DataFrame({
    "timestamp":            ts_f,

    # ── Group A: H2 Production model inputs (from renewable sources) ──
    "P_SOL_total_W":        np.round(P_SOL_total_f, 3),   # from solar model
    "P_Wind_W":             np.round(P_Wind_f, 3),         # from wind model
    "SoC_BB_pct":           np.round(SoC_BB_f, 2),         # from battery model
    "load_profile_set_W":   np.round(load_profile_set_f, 2),
    # ── Group A: H2 Production model outputs ──────────────────────────
    "H2_Flow_HG_NLmin":     np.round(H2_Flow_HG, 4),
    "H2_Pres_HG_bar":       np.round(H2_Pres_HG, 3),
    "V_HG_V":               np.round(V_HG, 3),
    "I_HG_A":               np.round(I_HG, 3),
    "P_HG_W":               np.round(P_HG, 3),
    "Efficiency_HG_pct":    np.round(Efficiency_HG, 2),

    # ── Group B: Fuel Cell model inputs (from Group A outputs) ────────
    # H2_Flow_HG and H2_Pres_HG flow directly from Group A above
    "T_FC_C":               np.round(T_FC, 2),
    "I_FC_A":               np.round(I_FC, 3),
    # ── Group B: Fuel Cell model outputs ──────────────────────────────
    "V_FC_V":               np.round(V_FC, 3),
    "I_FC_int_A":           np.round(I_FC_int, 3),
    "P_FC_W":               np.round(P_FC, 3),
    "H2_Flow_FC_NLmin":     np.round(H2_Flow_FC, 4),
    "H2_Pres_FC_bar":       np.round(H2_Pres_FC, 3),
    "Efficiency_FC_pct":    np.round(Efficiency_FC, 2),
    "V_BB_V":               np.round(V_BB_f, 3),
    "I_FC_DCDC_A":          np.round(I_FC_DCDC, 3),
    "P_FC_DCDC_W":          np.round(P_FC_DCDC, 3),
    "V_Load_V":             np.round(V_Load_f, 3),
    "I_Load_A":             np.round(I_Load_f, 3),
    "T_outdoor_C":          np.round(T_out_f, 2),
})
df_fc.to_csv(f"{OUT}/dataset_fuelcell.csv", index=False)
print(f"  ✓ dataset_fuelcell.csv — {len(df_fc):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 4 — BATTERY MANAGEMENT
# Experiments: B01–B03 (wind battery + buffer battery)
# ─────────────────────────────────────────────────────────────────────────────
print("Generating battery dataset...")
ts_b = lab_timestamps(sample_minutes=5)
n_b  = len(ts_b)

# Wind battery (12V, 50Ah = 600 Wh)
SoC_WB_b = np.zeros(n_b)
SoC_WB_b[0] = 60.0
V_WB_b   = np.zeros(n_b)
I_WB_b   = np.zeros(n_b)

# Buffer battery (24V, 100Ah = 2400 Wh)
SoC_BB = np.zeros(n_b)
SoC_BB[0] = 75.0
V_BB_b = np.zeros(n_b)
I_BB_b = np.zeros(n_b)

load_current_set_b = rng.uniform(0.5, 8.0, n_b)

for i in range(1, n_b):
    dt_h = 5 / 60
    # Wind battery
    P_charge_w = rng.uniform(0, 80) if rng.random() > 0.3 else 0  # charging from wind
    P_discharge_w = load_current_set_b[i] * 12
    net_w = P_charge_w - P_discharge_w
    dSoC_w = (net_w * dt_h / 600) * 100
    SoC_WB_b[i] = clip(np.array([SoC_WB_b[i-1] + dSoC_w + noise(1, 0.1)[0]]), 10, 100)[0]

    # Buffer battery
    P_charge_bb = rng.uniform(0, 150) if rng.random() > 0.4 else 0
    P_discharge_bb = rng.uniform(10, 100)
    net_bb = P_charge_bb - P_discharge_bb
    dSoC_bb = (net_bb * dt_h / 2400) * 100
    SoC_BB[i] = clip(np.array([SoC_BB[i-1] + dSoC_bb + noise(1, 0.08)[0]]), 15, 100)[0]

V_WB_b = 10.8 + (SoC_WB_b / 100) * 2.4 + noise(n_b, 0.06)
V_WB_b = clip(V_WB_b, 10.5, 14.5)
I_WB_b = clip(load_current_set_b + noise(n_b, 0.1), -10, 10)
P_WB_b = V_WB_b * I_WB_b

V_BB_b = 21.6 + (SoC_BB / 100) * 4.8 + noise(n_b, 0.1)
V_BB_b = clip(V_BB_b, 21, 29)
I_BB_b = clip(rng.uniform(-8, 8, n_b) + noise(n_b, 0.15), -10, 10)
P_BB_b = V_BB_b * I_BB_b

# Internal resistance (for B02 experiment)
# Ri increases slightly as battery ages (simulate multi-year degradation)
year_fraction = (ts_b - pd.Timestamp(START)) / pd.Timedelta(days=365)
Ri_WB = clip(0.05 + 0.003 * year_fraction.values + noise(n_b, 0.002), 0.04, 0.12)
Ri_BB = clip(0.03 + 0.002 * year_fraction.values + noise(n_b, 0.001), 0.025, 0.08)

# Energy metrics (per 5-min interval)
energy_charged    = clip((I_BB_b.clip(min=0) * V_BB_b * 5/60), 0, 50)
energy_discharged = clip((-I_BB_b.clip(max=0) * V_BB_b * 5/60), 0, 50)
conversion_loss   = energy_charged * rng.uniform(0.03, 0.08, n_b)

V_Load_b = clip(V_BB_b + noise(n_b, 0.15), 20, 29)
I_Load_b = clip(load_current_set_b * rng.uniform(0.8, 1.0, n_b), 0, 9)

df_bat = pd.DataFrame({
    "timestamp":          ts_b,
    "SoC_WB_pct":         np.round(SoC_WB_b, 2),
    "V_WB_V":             np.round(V_WB_b, 3),
    "I_WB_A":             np.round(I_WB_b, 3),
    "P_WB_W":             np.round(P_WB_b, 3),
    "internal_resist_WB_ohm": np.round(Ri_WB, 4),
    "SoC_BB_pct":         np.round(SoC_BB, 2),
    "V_BB_V":             np.round(V_BB_b, 3),
    "I_BB_A":             np.round(I_BB_b, 3),
    "P_BB_W":             np.round(P_BB_b, 3),
    "internal_resist_BB_ohm": np.round(Ri_BB, 4),
    "load_current_set_A": np.round(load_current_set_b, 3),
    "V_Load_V":           np.round(V_Load_b, 3),
    "I_Load_A":           np.round(I_Load_b, 3),
    "energy_charged_Wh":  np.round(energy_charged, 4),
    "energy_discharged_Wh": np.round(energy_discharged, 4),
    "conversion_loss_Wh": np.round(conversion_loss, 4),
})
df_bat.to_csv(f"{OUT}/dataset_battery.csv", index=False)
print(f"  ✓ dataset_battery.csv — {len(df_bat):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 5 — ENERGY MANAGEMENT
# Experiments: E01–E04
# ─────────────────────────────────────────────────────────────────────────────
print("Generating energy management dataset...")
ts_e = lab_timestamps(sample_minutes=5)
n_e  = len(ts_e)

Solar_Rad_e   = batna_solar_rad(ts_e)
Windspeed_e   = batna_wind_speed(ts_e)
T_out_e       = batna_temperature(ts_e)

# Grid status: mostly on (85%), off for island-mode experiments (15%)
grid_status = rng.choice([1, 0], size=n_e, p=[0.85, 0.15])
island_grid_status = 1 - grid_status

V_Grid = np.where(grid_status == 1, 230 + noise(n_e, 3), 0)
I_Grid = np.where(grid_status == 1, clip(rng.uniform(0, 8, n_e) + noise(n_e, 0.3), 0, 10), 0)

# Buffer battery SoC (energy management context)
SoC_BB_e = np.zeros(n_e)
SoC_BB_e[0] = 65.0
for i in range(1, n_e):
    solar_input = Solar_Rad_e[i] * 0.001 * 5 / 60 * 100 / 24   # rough SoC contribution
    wind_input  = Windspeed_e[i] * 0.005 * 5 / 60 * 100 / 24
    load_draw   = rng.uniform(0.05, 0.3)
    dSoC = solar_input + wind_input - load_draw + noise(1, 0.05)[0]
    SoC_BB_e[i] = clip(np.array([SoC_BB_e[i-1] + dSoC]), 15, 100)[0]

V_BB_e = 21.6 + (SoC_BB_e / 100) * 4.8 + noise(n_e, 0.1)
V_BB_e = clip(V_BB_e, 21, 29)
I_BB_e = clip(rng.uniform(-6, 6, n_e) + noise(n_e, 0.2), -8, 8)

# Active source decision logic
# Priority: Solar → Wind → FuelCell (if H2 available) → Grid → Battery

# Compute H2 availability in this EMS session
# (derived from renewable surplus, consistent with fuelcell dataset logic)
surplus_e    = clip(Solar_Rad_e * 0.18 + Windspeed_e ** 2 * 0.5
                    - (200 + 150 * np.sin(np.pi * (ts_e.hour + ts_e.minute/60 - 8) / 10)),
                    0, None)                                            # W  renewable surplus
H2_Flow_HG_e = clip(surplus_e * 0.0042 + noise(n_e, 0.001), 0, 2.0)  # Nl/min
H2_Pres_HG_e = clip(H2_Flow_HG_e * 1.8 + 2.0 + noise(n_e, 0.1), 0, 5.0)  # bar

# FC power: only when H2 pressure > 1 bar and solar/wind are insufficient
fc_needed    = (Solar_Rad_e < 200) & (Windspeed_e < 3.0)
fc_possible  = H2_Pres_HG_e > 1.0
P_FC_e       = clip(
    np.where(fc_needed & fc_possible,
             rng.uniform(10, 80, n_e) + noise(n_e, 2), 0), 0, 100)   # W

active_source = []
for i in range(n_e):
    if Solar_Rad_e[i] > 300:
        active_source.append("Solar")
    elif Windspeed_e[i] > 3.0:
        active_source.append("Wind")
    elif H2_Pres_HG_e[i] > 1.0 and fc_needed[i]:
        active_source.append("FuelCell")
    elif grid_status[i] == 1:
        active_source.append("Grid")
    else:
        active_source.append("Battery")

# Load profile: typical school lab load pattern (W)
# Morning ramp-up, midday peak, afternoon ramp-down
hour_frac = ts_e.hour + ts_e.minute / 60
base_load = 200 + 150 * np.sin(np.pi * (hour_frac - 8) / 10)
load_profile = clip(base_load + noise(n_e, 20), 50, 500)

# Actual load
V_Load_e = clip(230 + noise(n_e, 5), 210, 250)
I_Load_e = clip(load_profile / V_Load_e + noise(n_e, 0.05), 0, 3)
P_Load_e = V_Load_e * I_Load_e

net_power_balance = (
                            Solar_Rad_e * 0.04 +       # rough solar contribution W
                            Windspeed_e ** 3 * 0.002 + # rough wind contribution W
                            P_FC_e                     # fuel cell contribution W
                    ) - P_Load_e + noise(n_e, 10)

# 12V DC external loads (E04)
dc12V_load_power = clip(rng.uniform(5, 50, n_e) + noise(n_e, 2), 0, 60)

df_em = pd.DataFrame({
    "timestamp":           ts_e,
    "grid_status":         grid_status,
    "island_grid_status":  island_grid_status,
    "V_Grid_V":            np.round(V_Grid, 2),
    "I_Grid_A":            np.round(I_Grid, 3),
    "SoC_BB_pct":          np.round(SoC_BB_e, 2),
    "V_BB_V":              np.round(V_BB_e, 3),
    "I_BB_A":              np.round(I_BB_e, 3),
    # H2 availability — passed in from H2 Production model output
    "H2_Flow_HG_NLmin":    np.round(H2_Flow_HG_e, 4),
    "H2_Pres_HG_bar":      np.round(H2_Pres_HG_e, 3),
    # FC output — passed in from Fuel Cell model output
    "P_FC_W":              np.round(P_FC_e, 3),
    "active_source":       active_source,
    "load_profile_W":      np.round(load_profile, 2),
    "Solar_Rad_Wm2":       np.round(Solar_Rad_e, 1),
    "Windspeed_ms":        np.round(Windspeed_e, 3),
    "T_outdoor_C":         np.round(T_out_e, 2),
    "V_Load_V":            np.round(V_Load_e, 2),
    "I_Load_A":            np.round(I_Load_e, 3),
    "P_Load_W":            np.round(P_Load_e, 2),
    "net_power_balance_W": np.round(net_power_balance, 2),
    "dc12V_load_power_W":  np.round(dc12V_load_power, 2),
})
df_em.to_csv(f"{OUT}/dataset_energy_management.csv", index=False)
print(f"  ✓ dataset_energy_management.csv — {len(df_em):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY REPORT
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("NEL DATASET GENERATION COMPLETE")
print("="*60)
print(f"Location  : Fesdis, Batna, Algeria (35.55°N, 1037m ASL)")
print(f"Date range: 2020-01-01 → 2026-03-10")
print(f"Output dir: {OUT}")
print()

datasets = {
    "dataset_solar.csv":             df_solar,
    "dataset_wind.csv":              df_wind,
    "dataset_fuelcell.csv":          df_fc,
    "dataset_battery.csv":           df_bat,
    "dataset_energy_management.csv": df_em,
}

total_rows = 0
for name, df in datasets.items():
    size_kb = os.path.getsize(f"{OUT}/{name}") / 1024
    print(f"  {name:<40} {len(df):>8,} rows   {size_kb:>8.1f} KB")
    total_rows += len(df)

print(f"\n  {'TOTAL':<40} {total_rows:>8,} rows")
print()

print("FEATURE RANGES (from Batna climate data):")
print(f"  Solar irradiance   : 0 – 950 W/m²  (peak summer noon)")
print(f"  Outdoor temperature: 1°C – 33°C     (winter–summer)")
print(f"  Wind speed         : 0 – 12 m/s     (mean ~4.4 m/s)")
print(f"  Panel voltage      : 0 – 22 V       (per module)")
print(f"  Panel current      : 0 – 6 A        (at peak irradiance)")
print(f"  FC output voltage  : 10 – 28 V      (load-dependent)")
print(f"  Battery SoC        : 10 – 100 %")
print(f"  Wind battery volt  : 10.5 – 14.5 V  (12V system)")
print(f"  Buffer battery volt: 21 – 29 V       (24V system)")
print(f"  H2 pressure        : 2 – 5 bar")
print(f"  H2 flow (FC)       : 0.01 – 0.6 Nl/min")
print(f"  Grid voltage       : 0 / 230 V AC")
print("="*60)