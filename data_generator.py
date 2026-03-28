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
Sample rate: 5 minutes during lab hours (08:00–18:00), weekdays only
             (Wind: 1 minute for long-term turbine experiments)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORRECT PHYSICAL ARCHITECTURE (verified from Heliocentris NEL documentation):

  Solar PV  ──► DC bus ──► Buffer Battery (24V, 100Ah)
  Wind      ──► DC bus ──►      │
                                ├──► Load (direct discharge)
                                └──► Electrolyser (when SoC > 40%)
                                          │
                                          ▼
                                     H2 stored (metal hydride canister)
                                          │
                                          ▼
                                     Fuel Cell ──► DC-DC ──► Load / Battery bus

  Key rule: Solar and Wind do NOT drive the electrolyser directly.
            They charge the battery first. The battery then decides
            whether to power the load or the electrolyser.
            SoC_BB is the gate that enables H2 production.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MODEL PIPELINE (training order):

  1. solar_model.pkl        — Solar inputs → P_SOL_total_W
  2. wind_model.pkl         — Wind inputs  → P_Wind_W
  3. battery_model.pkl      — P_SOL_total + P_Wind + load → SoC_BB, V_BB, I_BB
  4. h2_production_model.pkl— SoC_BB, V_BB, I_BB_to_HG → H2_Flow_HG, H2_Pres_HG
  5. fc_model.pkl           — H2_Flow_HG, H2_Pres_HG, T_FC, I_FC → P_FC, V_FC, Eff_FC
  6. ems_model.pkl          — all above outputs + grid_status + load → dispatch decision

  5 dataset files → 6 trained models
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# ── Reproducibility ───────────────────────────────────────────────────────────
rng = np.random.default_rng(42)

# ── Output folder ─────────────────────────────────────────────────────────────
OUT = "nel_datasets"
os.makedirs(OUT, exist_ok=True)

# ── Date range ────────────────────────────────────────────────────────────────
START = datetime(2020, 1, 1)
END   = datetime(2026, 3, 10)

# ── Helpers ───────────────────────────────────────────────────────────────────

def lab_timestamps(sample_minutes=5):
    """
    Weekdays (Mon–Fri), 08:00–18:00, every `sample_minutes` minutes.
    5-min: ~120 samples/day × ~260 days/year × 6.2 years ≈ ~193 000 rows
    1-min: ~600 samples/day → ~965 000 rows (wind only)
    """
    stamps = []
    current = START.replace(hour=8, minute=0, second=0)
    while current <= END:
        if current.weekday() < 5 and current.hour < 18:
            stamps.append(current)
        current += timedelta(minutes=sample_minutes)
    return pd.DatetimeIndex(stamps)

def clip(arr, lo, hi):
    return np.clip(arr, lo, hi)

def noise(size, scale=1.0):
    return rng.normal(0, scale, size)

# ── Shared wind power curve (used in multiple datasets) ───────────────────────
def wind_power_curve(v):
    """Small lab wind turbine: rated ~150W at 8 m/s, cut-in 1.5 m/s"""
    p = np.zeros_like(v, dtype=float)
    mask_ramp  = (v >= 1.5) & (v < 8.0)
    mask_rated = (v >= 8.0) & (v < 12.0)
    p[mask_ramp]  = 150 * ((v[mask_ramp] - 1.5) / 6.5) ** 3
    p[mask_rated] = 150.0
    return p

# ── Climate helpers ───────────────────────────────────────────────────────────

def batna_temperature(ts):
    monthly_mean = np.array([5.1, 6.1, 8.95, 12.5, 17.5, 22.5,
                             27.5, 27.2, 21.35, 16.0, 9.75, 6.35])
    base         = monthly_mean[ts.month - 1]
    diurnal      = np.sin(np.pi * (ts.hour - 8) / 10) * 6
    return base + diurnal + noise(len(ts), 1.2)

def batna_solar_rad(ts):
    seasonal_peak = clip(500 + 450 * np.sin(np.pi * (ts.dayofyear - 80) / 365), 300, 950)
    solar_angle   = clip(np.sin(np.pi * (ts.hour + ts.minute/60 - 8) / 10), 0, 1)
    rad = seasonal_peak * solar_angle
    cloud = rng.choice([1.0, 0.6, 0.2], size=len(ts), p=[0.80, 0.15, 0.05])
    return clip(rad * cloud + noise(len(ts), 15), 0, 1000)

def batna_wind_speed(ts):
    seasonal_mean = np.where((ts.month >= 3) & (ts.month <= 9), 4.8, 3.2).astype(float)
    speed = rng.lognormal(np.log(seasonal_mean) - 0.2, 0.4, len(ts))
    hour_boost = 0.5 * np.sin(np.pi * (ts.hour - 8) / 10)
    return clip(speed + hour_boost, 0.0, 12.0)

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 1 — SOLAR PV
# Experiments S01–S06
# Model: solar_model.pkl
# Inputs:  Solar_Rad, T_SOL1, T_SOL2, T_outdoor, tilt_angle, azimuth_angle, shading_factor
# Outputs: P_SOL_total_W  ← fed into Battery dataset as charging input
# ─────────────────────────────────────────────────────────────────────────────
print("Generating solar dataset...")
ts = lab_timestamps(sample_minutes=5)
n  = len(ts)

T_outdoor = batna_temperature(ts)
Solar_Rad = batna_solar_rad(ts)

T_SOL1 = T_outdoor + Solar_Rad * 0.025 + noise(n, 1.5)
T_SOL2 = T_outdoor + Solar_Rad * 0.023 + noise(n, 1.5)

tilt_options    = np.array([15, 30, 45])
azimuth_options = np.array([-30, 0, 30])
days          = (ts - ts[0]).days
tilt_angle    = tilt_options[days % 3]
azimuth_angle = azimuth_options[days % 3]

V_OC     = 21.0
k_T      = 0.08
k_G      = 2.0
rad_safe = np.where(Solar_Rad > 1, Solar_Rad, 1)

V_SOL1 = V_OC - k_T*(T_SOL1-25) + k_G*np.log10(rad_safe/100+1)
V_SOL1 = V_SOL1 * np.cos(np.radians(azimuth_angle)) * (1 - 0.002*(tilt_angle-45)**2/45)
V_SOL1 = clip(V_SOL1 + noise(n, 0.4), 0, 22)

V_SOL2 = V_OC - k_T*(T_SOL2-25) + k_G*np.log10(rad_safe/100+1)
V_SOL2 = V_SOL2 * np.cos(np.radians(azimuth_angle)) * (1 - 0.002*(tilt_angle-45)**2/45)
V_SOL2 = clip(V_SOL2 + noise(n, 0.4), 0, 22)

I_SOL       = clip(5.5 * (Solar_Rad/1000) + noise(n, 0.1), 0, 6.0)
P_SOL1      = V_SOL1 * I_SOL
P_SOL2      = V_SOL2 * I_SOL
P_SOL_total = P_SOL1 + P_SOL2

V_SOL3         = clip((V_SOL1+V_SOL2)/2 + noise(n, 0.3), 0, 22)
I_SOL3         = clip(I_SOL*2.0 + noise(n, 0.2), 0, 12)
shading_factor = rng.choice([0.0, 0.2, 0.5, 1.0], size=n, p=[0.78, 0.12, 0.07, 0.03])
V_Load         = clip(V_SOL1+V_SOL2 + noise(n, 0.5), 0, 44)
I_Load         = clip(I_SOL * rng.uniform(0.6, 0.95, n) + noise(n, 0.05), 0, 6.0)

df_solar = pd.DataFrame({
    "timestamp":         ts,
    "Solar_Rad_Wm2":     np.round(Solar_Rad, 1),
    "T_SOL1_C":          np.round(T_SOL1, 2),
    "T_SOL2_C":          np.round(T_SOL2, 2),
    "T_outdoor_C":       np.round(T_outdoor, 2),
    "tilt_angle_deg":    tilt_angle,
    "azimuth_angle_deg": azimuth_angle,
    "shading_factor":    shading_factor,
    "V_SOL1_V":          np.round(V_SOL1, 3),
    "V_SOL2_V":          np.round(V_SOL2, 3),
    "I_SOL_A":           np.round(I_SOL, 3),
    "P_SOL1_W":          np.round(P_SOL1, 3),
    "P_SOL2_W":          np.round(P_SOL2, 3),
    "P_SOL_total_W":     np.round(P_SOL_total, 3),   # ← PRIMARY OUTPUT → Battery
    "V_SOL3_V":          np.round(V_SOL3, 3),
    "I_SOL3_A":          np.round(I_SOL3, 3),
    "V_Load_V":          np.round(V_Load, 3),
    "I_Load_A":          np.round(I_Load, 3),
})
df_solar.to_csv(f"{OUT}/dataset_solar.csv", index=False)
print(f"  ✓ dataset_solar.csv — {len(df_solar):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 2 — WIND ENERGY
# Experiments W01–W03
# Model: wind_model.pkl
# Inputs:  Windspeed_ms, T_outdoor_C
# Outputs: P_Wind_W  ← fed into Battery dataset as charging input
# ─────────────────────────────────────────────────────────────────────────────
print("Generating wind dataset...")
ts_w = lab_timestamps(sample_minutes=1)
n_w  = len(ts_w)

Windspeed = batna_wind_speed(ts_w)
T_out_w   = batna_temperature(ts_w)

P_Wind_ideal = wind_power_curve(Windspeed)
V_Wind       = clip(12 + 1.5*Windspeed + noise(n_w, 0.5), 0, 32)
I_Wind       = clip(P_Wind_ideal / np.where(V_Wind>1, V_Wind, 1) + noise(n_w, 0.05), 0, 6.5)
P_Wind       = V_Wind * I_Wind

# Wind battery SoC (12V, 50Ah = 600Wh) — charged by turbine
SoC_WB    = np.zeros(n_w);  SoC_WB[0] = 70.0
for i in range(1, n_w):
    net      = P_Wind[i] - rng.uniform(20, 80)
    dSoC     = (net * (1/60) / 600) * 100
    SoC_WB[i] = clip(np.array([SoC_WB[i-1] + dSoC + noise(1, 0.05)[0]]), 20, 100)[0]

V_WB    = clip(10.8 + (SoC_WB/100)*2.4 + noise(n_w, 0.08), 10.5, 14.5)
I_WB    = clip((P_Wind - rng.uniform(20, 80, n_w)) / np.where(V_WB>1, V_WB, 1)
               + noise(n_w, 0.1), -5, 5)
P_WB    = V_WB * I_WB
V_Load_w = clip(V_WB + noise(n_w, 0.2), 10, 14)
I_Load_w = clip(rng.uniform(1, 6, n_w) + noise(n_w, 0.1), 0, 7)
P_Load_w = V_Load_w * I_Load_w

df_wind = pd.DataFrame({
    "timestamp":    ts_w,
    "Windspeed_ms": np.round(Windspeed, 3),     # ← PRIMARY INPUT
    "T_outdoor_C":  np.round(T_out_w, 2),
    "V_Wind_V":     np.round(V_Wind, 3),
    "I_Wind_A":     np.round(I_Wind, 3),
    "P_Wind_W":     np.round(P_Wind, 3),         # ← PRIMARY OUTPUT → Battery
    "SoC_WB_pct":   np.round(SoC_WB, 2),
    "V_WB_V":       np.round(V_WB, 3),
    "I_WB_A":       np.round(I_WB, 3),
    "P_WB_W":       np.round(P_WB, 3),
    "V_Load_V":     np.round(V_Load_w, 3),
    "I_Load_A":     np.round(I_Load_w, 3),
    "P_Load_W":     np.round(P_Load_w, 3),
})
df_wind.to_csv(f"{OUT}/dataset_wind.csv", index=False)
print(f"  ✓ dataset_wind.csv — {len(df_wind):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 3 — FUEL CELL & HYDROGEN GENERATOR
# Experiments F01–F04
# Models: h2_production_model.pkl  +  fc_model.pkl
#
# CORRECTED ARCHITECTURE (Heliocentris NEL documentation):
#   Solar + Wind → charge Buffer Battery
#   Buffer Battery → powers Electrolyser (when SoC_BB > 40%)
#   Electrolyser → produces H2 → stored in metal hydride canister
#   H2 canister → feeds Fuel Cell → generates electricity
#
# GROUP A — H2 Production model
#   Inputs:  SoC_BB_pct, V_BB_V, I_BB_to_HG_A, P_BB_to_HG_W  (battery state)
#            load_profile_set_W  (current demand)
#   Outputs: H2_Flow_HG_NLmin, H2_Pres_HG_bar
#
# GROUP B — Fuel Cell model
#   Inputs:  H2_Flow_HG_NLmin, H2_Pres_HG_bar  (← Group A outputs)
#            T_FC_C, I_FC_A
#   Outputs: V_FC_V, P_FC_W, Efficiency_FC_pct
# ─────────────────────────────────────────────────────────────────────────────
print("Generating fuel cell dataset...")
ts_f    = lab_timestamps(sample_minutes=5)
n_f     = len(ts_f)
T_out_f = batna_temperature(ts_f)

# ── Simulate solar + wind for this combined session (they drive battery charging) ──
Solar_Rad_f = batna_solar_rad(ts_f)
Windspeed_f = batna_wind_speed(ts_f)
P_SOL_f     = clip(Solar_Rad_f * 0.18 + noise(n_f, 3), 0, 200)         # W  solar output
P_Wind_f    = clip(wind_power_curve(Windspeed_f) + noise(n_f, 2), 0, 150)  # W  wind output
P_renewable_f = P_SOL_f + P_Wind_f                                      # W  total renewable

# ── Load demand during the combined session ───────────────────────────────────
load_profile_set_f = clip(100 + 80*np.sin(np.pi*(ts_f.hour-8)/10)
                          + noise(n_f, 15), 50, 400)                    # W

# ── Buffer battery SoC (24V, 100Ah = 2400Wh) ─────────────────────────────────
# Charged by solar + wind. Discharged by load AND electrolyser.
SoC_BB_f  = np.zeros(n_f);  SoC_BB_f[0] = 65.0
for i in range(1, n_f):
    dt_h       = 5/60
    charge_in  = P_renewable_f[i] * 0.9            # 90% charging efficiency
    load_out   = load_profile_set_f[i]
    # Electrolyser runs only when SoC > 40% (enough to spare after load)
    hg_demand  = 80.0 if SoC_BB_f[i-1] > 40 else 0.0
    net        = charge_in - load_out - hg_demand
    dSoC       = (net * dt_h / 2400) * 100
    SoC_BB_f[i] = clip(np.array([SoC_BB_f[i-1] + dSoC + noise(1, 0.08)[0]]), 15, 100)[0]

V_BB_in_f = clip(21.6 + (SoC_BB_f/100)*4.8 + noise(n_f, 0.1), 21, 29)  # V  battery voltage

# ── GROUP A — H2 Production model ────────────────────────────────────────────
# The electrolyser draws power from the buffer battery when SoC_BB > 40%
# P_BB_to_HG scales with how much excess SoC there is above 40%

hg_active   = (SoC_BB_f > 40.0).astype(float)
# More excess SoC → more power available to electrolyser (up to 200W)
P_BB_to_HG  = clip(
    hg_active * ((SoC_BB_f - 40) / 60) * 180 + noise(n_f, 5),
    0, 200)                                                             # W
I_BB_to_HG  = clip(
    np.where(V_BB_in_f > 1, P_BB_to_HG / V_BB_in_f, 0) + noise(n_f, 0.05),
    0, 8.0)                                                             # A  (positive = discharge to HG)

# H2 flow proportional to power delivered to electrolyser
# ~0.42 Nl/min per 100W input (65% electrolyser efficiency)
H2_Flow_HG  = clip(P_BB_to_HG * 0.0042 + noise(n_f, 0.001), 0, 2.0)  # Nl/min
H2_Pres_HG  = clip(H2_Flow_HG * 1.8 + 2.0 + noise(n_f, 0.1), 0, 5.0) # bar

# Electrolyser electrical measurements
P_HG        = clip(P_BB_to_HG * 0.65 + noise(n_f, 2), 0, None)        # W consumed by HG
V_HG        = clip(2.0 + 0.4*np.sqrt(np.where(P_HG>0, P_HG, 0))
                   + noise(n_f, 0.15), 2.0, 8.0)                       # V
I_HG        = clip(np.where(V_HG>0.5, P_HG/V_HG, 0) + noise(n_f, 0.1), 0, 9.0)  # A
Efficiency_HG = clip(
    np.where(P_HG > 0, (H2_Flow_HG*60*3.5 / (P_HG+0.01))*100, 0),
    0, 75)                                                              # %

# ── GROUP B — Fuel Cell model ─────────────────────────────────────────────────
# FC activates when stored H2 pressure > 1 bar
fc_active   = (H2_Pres_HG > 1.0).astype(float)
I_FC        = clip(rng.uniform(0.5, 5.5, n_f) + noise(n_f, 0.15), 0.1, 6.0) * fc_active  # A

V_FC        = clip((28.0 - 0.8*I_FC - 1.2*np.log(I_FC/0.1+1)) + noise(n_f, 0.2), 0, 28)
P_FC        = clip(V_FC * I_FC, 0, 100)                                # W
I_FC_int    = clip(I_FC * 1.05 + noise(n_f, 0.05), 0, 6.5)
T_FC        = clip(T_out_f + 15 + P_FC*0.1 + noise(n_f, 1.5), 20, 75) # °C

H2_Flow_FC  = clip(P_FC*0.009 + noise(n_f, 0.002), 0.0, 0.6)          # Nl/min consumed
H2_Pres_FC  = clip(H2_Pres_HG - H2_Flow_FC*0.5 + noise(n_f, 0.05), 0, 5.0)  # bar at FC inlet

Efficiency_FC = clip(
    np.where(H2_Flow_FC > 0, (P_FC/(H2_Flow_FC*60*3.5+0.01))*100, 0),
    0, 60)                                                              # %

# DC-DC converter output (fuel cell → load/battery bus)
V_BB_fc_out = clip(rng.uniform(24, 28, n_f) + noise(n_f, 0.3), 22, 30)
I_FC_DCDC   = clip(I_FC*0.92 + noise(n_f, 0.05), 0, 6.0)
P_FC_DCDC   = V_BB_fc_out * I_FC_DCDC

V_Load_f    = clip(V_BB_fc_out + noise(n_f, 0.2), 20, 30)
I_Load_f    = clip(P_FC / np.where(V_Load_f>1, V_Load_f, 1) * rng.uniform(0.7, 0.95, n_f), 0, 5)

df_fc = pd.DataFrame({
    "timestamp":           ts_f,

    # ── Context: what was happening on the renewable + load side ──────────────
    "P_SOL_total_W":       np.round(P_SOL_f, 3),        # solar charging battery
    "P_Wind_W":            np.round(P_Wind_f, 3),        # wind charging battery
    "load_profile_set_W":  np.round(load_profile_set_f, 2),

    # ── GROUP A INPUTS — H2 Production model (battery state) ─────────────────
    "SoC_BB_pct":          np.round(SoC_BB_f, 2),        # ← from Battery model
    "V_BB_V":              np.round(V_BB_in_f, 3),        # ← from Battery model
    "I_BB_to_HG_A":        np.round(I_BB_to_HG, 3),      # ← from Battery model (discharge to HG)
    "P_BB_to_HG_W":        np.round(P_BB_to_HG, 3),      # ← power battery delivers to electrolyser

    # ── GROUP A OUTPUTS — H2 Production model ────────────────────────────────
    "H2_Flow_HG_NLmin":    np.round(H2_Flow_HG, 4),      # → fed into Group B
    "H2_Pres_HG_bar":      np.round(H2_Pres_HG, 3),      # → fed into Group B
    "V_HG_V":              np.round(V_HG, 3),
    "I_HG_A":              np.round(I_HG, 3),
    "P_HG_W":              np.round(P_HG, 3),
    "Efficiency_HG_pct":   np.round(Efficiency_HG, 2),

    # ── GROUP B INPUTS — Fuel Cell model ─────────────────────────────────────
    # H2_Flow_HG_NLmin and H2_Pres_HG_bar come from Group A above
    "T_FC_C":              np.round(T_FC, 2),
    "I_FC_A":              np.round(I_FC, 3),

    # ── GROUP B OUTPUTS — Fuel Cell model ────────────────────────────────────
    "V_FC_V":              np.round(V_FC, 3),
    "I_FC_int_A":          np.round(I_FC_int, 3),
    "P_FC_W":              np.round(P_FC, 3),             # → fed into EMS model
    "H2_Flow_FC_NLmin":    np.round(H2_Flow_FC, 4),
    "H2_Pres_FC_bar":      np.round(H2_Pres_FC, 3),
    "Efficiency_FC_pct":   np.round(Efficiency_FC, 2),
    "V_BB_out_V":          np.round(V_BB_fc_out, 3),
    "I_FC_DCDC_A":         np.round(I_FC_DCDC, 3),
    "P_FC_DCDC_W":         np.round(P_FC_DCDC, 3),
    "V_Load_V":            np.round(V_Load_f, 3),
    "I_Load_A":            np.round(I_Load_f, 3),
    "T_outdoor_C":         np.round(T_out_f, 2),
})
df_fc.to_csv(f"{OUT}/dataset_fuelcell.csv", index=False)
print(f"  ✓ dataset_fuelcell.csv — {len(df_fc):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 4 — BATTERY MANAGEMENT
# Experiments B01–B03
# Model: battery_model.pkl
#
# CORRECTED: Solar and Wind are now INPUTS (charging sources).
# The battery receives power from both and dispatches to load + electrolyser.
#
# Inputs:  P_SOL_total_W  (← Solar model output)
#          P_Wind_W        (← Wind model output)
#          load_current_set_A
# Outputs: SoC_BB_pct, V_BB_V, I_BB_to_HG_A  ← fed into H2 Production model
#          SoC_WB_pct                          ← additional storage state
# ─────────────────────────────────────────────────────────────────────────────
print("Generating battery dataset...")
ts_b = lab_timestamps(sample_minutes=5)
n_b  = len(ts_b)

# ── Simulate solar + wind inputs that charge the battery ─────────────────────
Solar_Rad_b  = batna_solar_rad(ts_b)
Windspeed_b  = batna_wind_speed(ts_b)
P_SOL_b      = clip(Solar_Rad_b * 0.18 + noise(n_b, 3), 0, 200)           # W
P_Wind_b     = clip(wind_power_curve(Windspeed_b) + noise(n_b, 2), 0, 150) # W
P_renewable_b = P_SOL_b + P_Wind_b                                          # W total charging

# ── Load setpoint ─────────────────────────────────────────────────────────────
load_current_set_b = rng.uniform(0.5, 8.0, n_b)    # A  (electronic load setpoint)

# ── Wind battery (12V, 50Ah = 600Wh) — charged by wind turbine ───────────────
SoC_WB_b = np.zeros(n_b);  SoC_WB_b[0] = 60.0
for i in range(1, n_b):
    dt_h      = 5/60
    P_chg_w   = rng.uniform(0, 80) if rng.random() > 0.3 else 0.0
    P_dis_w   = load_current_set_b[i] * 12
    dSoC_w    = ((P_chg_w - P_dis_w) * dt_h / 600) * 100
    SoC_WB_b[i] = clip(np.array([SoC_WB_b[i-1] + dSoC_w + noise(1, 0.1)[0]]), 10, 100)[0]

V_WB_b = clip(10.8 + (SoC_WB_b/100)*2.4 + noise(n_b, 0.06), 10.5, 14.5)
I_WB_b = clip(load_current_set_b + noise(n_b, 0.1), -10, 10)
P_WB_b = V_WB_b * I_WB_b

# ── Buffer battery (24V, 100Ah = 2400Wh) — charged by solar + wind ───────────
SoC_BB_b = np.zeros(n_b);  SoC_BB_b[0] = 75.0
for i in range(1, n_b):
    dt_h        = 5/60
    P_charge_bb = P_renewable_b[i] * 0.9           # 90% charging efficiency from solar+wind
    P_load_bb   = load_current_set_b[i] * 24        # load discharge
    # Electrolyser gets power when SoC > 40%
    P_to_hg     = 80.0 if SoC_BB_b[i-1] > 40 else 0.0
    net_bb      = P_charge_bb - P_load_bb - P_to_hg
    dSoC_bb     = (net_bb * dt_h / 2400) * 100
    SoC_BB_b[i] = clip(np.array([SoC_BB_b[i-1] + dSoC_bb + noise(1, 0.08)[0]]), 15, 100)[0]

V_BB_b = clip(21.6 + (SoC_BB_b/100)*4.8 + noise(n_b, 0.1), 21, 29)
I_BB_b = clip(rng.uniform(-8, 8, n_b) + noise(n_b, 0.15), -10, 10)
P_BB_b = V_BB_b * I_BB_b

# I_BB_to_HG: the portion of battery current going to the electrolyser
hg_active_b   = (SoC_BB_b > 40).astype(float)
I_BB_to_HG_b  = clip(hg_active_b * ((SoC_BB_b-40)/60)*7.0 + noise(n_b, 0.1), 0, 8.0)  # A
P_BB_to_HG_b  = V_BB_b * I_BB_to_HG_b                                    # W

# Internal resistance — aging model
year_frac = (ts_b - pd.Timestamp(START)) / pd.Timedelta(days=365)
Ri_WB = clip(0.05 + 0.003*year_frac.values + noise(n_b, 0.002), 0.04, 0.12)
Ri_BB = clip(0.03 + 0.002*year_frac.values + noise(n_b, 0.001), 0.025, 0.08)

# Energy metrics per 5-min interval
energy_charged    = clip( I_BB_b.clip(min=0) * V_BB_b * 5/60,  0, 50)
energy_discharged = clip(-I_BB_b.clip(max=0) * V_BB_b * 5/60,  0, 50)
conversion_loss   = energy_charged * rng.uniform(0.03, 0.08, n_b)

V_Load_b = clip(V_BB_b + noise(n_b, 0.15), 20, 29)
I_Load_b = clip(load_current_set_b * rng.uniform(0.8, 1.0, n_b), 0, 9)

df_bat = pd.DataFrame({
    "timestamp":              ts_b,

    # ── INPUTS — charging sources (from Solar and Wind models) ───────────────
    "P_SOL_total_W":          np.round(P_SOL_b, 3),       # ← from Solar model
    "P_Wind_W":               np.round(P_Wind_b, 3),       # ← from Wind model
    "load_current_set_A":     np.round(load_current_set_b, 3),

    # ── OUTPUTS — battery state (fed into H2 Production model) ───────────────
    "SoC_WB_pct":             np.round(SoC_WB_b, 2),
    "V_WB_V":                 np.round(V_WB_b, 3),
    "I_WB_A":                 np.round(I_WB_b, 3),
    "P_WB_W":                 np.round(P_WB_b, 3),
    "internal_resist_WB_ohm": np.round(Ri_WB, 4),
    "SoC_BB_pct":             np.round(SoC_BB_b, 2),       # → fed into H2 Production model
    "V_BB_V":                 np.round(V_BB_b, 3),          # → fed into H2 Production model
    "I_BB_A":                 np.round(I_BB_b, 3),
    "P_BB_W":                 np.round(P_BB_b, 3),
    "I_BB_to_HG_A":           np.round(I_BB_to_HG_b, 3),   # → fed into H2 Production model
    "P_BB_to_HG_W":           np.round(P_BB_to_HG_b, 3),   # → fed into H2 Production model
    "internal_resist_BB_ohm": np.round(Ri_BB, 4),
    "V_Load_V":               np.round(V_Load_b, 3),
    "I_Load_A":               np.round(I_Load_b, 3),
    "energy_charged_Wh":      np.round(energy_charged, 4),
    "energy_discharged_Wh":   np.round(energy_discharged, 4),
    "conversion_loss_Wh":     np.round(conversion_loss, 4),
})
df_bat.to_csv(f"{OUT}/dataset_battery.csv", index=False)
print(f"  ✓ dataset_battery.csv — {len(df_bat):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET 5 — ENERGY MANAGEMENT
# Experiments E01–E04
# Model: ems_model.pkl  (meta-learner — takes outputs of all 5 upstream models)
#
# CORRECTED: H2 availability derived from battery SoC, not direct renewable surplus.
# Priority dispatch: Solar → Wind → FuelCell (H2 available) → Grid → Battery
# ─────────────────────────────────────────────────────────────────────────────
print("Generating energy management dataset...")
ts_e = lab_timestamps(sample_minutes=5)
n_e  = len(ts_e)

Solar_Rad_e = batna_solar_rad(ts_e)
Windspeed_e = batna_wind_speed(ts_e)
T_out_e     = batna_temperature(ts_e)

grid_status        = rng.choice([1, 0], size=n_e, p=[0.85, 0.15])
island_grid_status = 1 - grid_status
V_Grid = np.where(grid_status==1, 230 + noise(n_e, 3), 0)
I_Grid = np.where(grid_status==1, clip(rng.uniform(0, 8, n_e) + noise(n_e, 0.3), 0, 10), 0)

# Load profile
hour_frac    = ts_e.hour + ts_e.minute/60
load_profile = clip(200 + 150*np.sin(np.pi*(hour_frac-8)/10) + noise(n_e, 20), 50, 500)
V_Load_e     = clip(230 + noise(n_e, 5), 210, 250)
I_Load_e     = clip(load_profile / V_Load_e + noise(n_e, 0.05), 0, 3)
P_Load_e     = V_Load_e * I_Load_e

# ── Buffer battery SoC (driven by solar + wind charging, load discharging) ────
P_SOL_e      = clip(Solar_Rad_e * 0.18 + noise(n_e, 3), 0, 200)
P_Wind_e     = clip(wind_power_curve(Windspeed_e) + noise(n_e, 2), 0, 150)
P_renewable_e = P_SOL_e + P_Wind_e

SoC_BB_e = np.zeros(n_e);  SoC_BB_e[0] = 65.0
for i in range(1, n_e):
    dt_h       = 5/60
    charge_in  = P_renewable_e[i] * 0.9
    load_out   = load_profile[i]
    hg_demand  = 80.0 if SoC_BB_e[i-1] > 40 else 0.0
    net        = charge_in - load_out - hg_demand
    dSoC       = (net * dt_h / 2400) * 100
    SoC_BB_e[i] = clip(np.array([SoC_BB_e[i-1] + dSoC + noise(1, 0.05)[0]]), 15, 100)[0]

V_BB_e = clip(21.6 + (SoC_BB_e/100)*4.8 + noise(n_e, 0.1), 21, 29)
I_BB_e = clip(rng.uniform(-6, 6, n_e) + noise(n_e, 0.2), -8, 8)

# ── H2 availability — derived from battery SoC (CORRECT architecture) ─────────
# Battery discharges to electrolyser only when SoC_BB > 40%
hg_active_e  = (SoC_BB_e > 40.0).astype(float)
P_BB_to_HG_e = clip(hg_active_e * ((SoC_BB_e-40)/60)*180 + noise(n_e, 5), 0, 200)
H2_Flow_HG_e = clip(P_BB_to_HG_e * 0.0042 + noise(n_e, 0.001), 0, 2.0)
H2_Pres_HG_e = clip(H2_Flow_HG_e * 1.8 + 2.0 + noise(n_e, 0.1), 0, 5.0)

# ── FC power (only when H2 pressure > 1 bar and renewables insufficient) ──────
fc_needed = (Solar_Rad_e < 200) & (Windspeed_e < 3.0)
fc_active_e = (H2_Pres_HG_e > 1.0) & fc_needed
P_FC_e = clip(
    np.where(fc_active_e, rng.uniform(10, 80, n_e) + noise(n_e, 2), 0),
    0, 100)

# ── Active source dispatch ────────────────────────────────────────────────────
active_source = []
for i in range(n_e):
    if   Solar_Rad_e[i] > 300:                              active_source.append("Solar")
    elif Windspeed_e[i] > 3.0:                              active_source.append("Wind")
    elif H2_Pres_HG_e[i] > 1.0 and fc_needed[i]:           active_source.append("FuelCell")
    elif grid_status[i] == 1:                               active_source.append("Grid")
    else:                                                    active_source.append("Battery")

net_power_balance = (P_SOL_e + P_Wind_e + P_FC_e) - P_Load_e + noise(n_e, 10)
dc12V_load_power  = clip(rng.uniform(5, 50, n_e) + noise(n_e, 2), 0, 60)

df_em = pd.DataFrame({
    "timestamp":           ts_e,

    # ── INPUTS FROM SENSORS ───────────────────────────────────────────────────
    "Solar_Rad_Wm2":       np.round(Solar_Rad_e, 1),
    "Windspeed_ms":        np.round(Windspeed_e, 3),
    "T_outdoor_C":         np.round(T_out_e, 2),
    "grid_status":         grid_status,
    "island_grid_status":  island_grid_status,
    "load_profile_W":      np.round(load_profile, 2),

    # ── INPUTS FROM BATTERY MODEL ─────────────────────────────────────────────
    "SoC_BB_pct":          np.round(SoC_BB_e, 2),       # ← Battery model output
    "V_BB_V":              np.round(V_BB_e, 3),           # ← Battery model output
    "I_BB_A":              np.round(I_BB_e, 3),

    # ── INPUTS FROM H2 PRODUCTION MODEL ──────────────────────────────────────
    "H2_Flow_HG_NLmin":    np.round(H2_Flow_HG_e, 4),   # ← H2 Production model output
    "H2_Pres_HG_bar":      np.round(H2_Pres_HG_e, 3),   # ← H2 Production model output

    # ── INPUTS FROM FUEL CELL MODEL ───────────────────────────────────────────
    "P_FC_W":              np.round(P_FC_e, 3),           # ← FC model output

    # ── EMS OUTPUTS ───────────────────────────────────────────────────────────
    "active_source":       active_source,                  # classification target
    "net_power_balance_W": np.round(net_power_balance, 2), # regression target

    # ── MEASURED / AUXILIARY ─────────────────────────────────────────────────
    "V_Grid_V":            np.round(V_Grid, 2),
    "I_Grid_A":            np.round(I_Grid, 3),
    "V_Load_V":            np.round(V_Load_e, 2),
    "I_Load_A":            np.round(I_Load_e, 3),
    "P_Load_W":            np.round(P_Load_e, 2),
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
print(f"Output dir: {OUT}/")
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
print("ARCHITECTURE SUMMARY:")
print("  Solar  → P_SOL_total_W         → Battery (charging input)")
print("  Wind   → P_Wind_W              → Battery (charging input)")
print("  Battery → SoC_BB, V_BB, I_BB_to_HG → H2 Production model")
print("  H2 Prod → H2_Flow_HG, H2_Pres_HG  → Fuel Cell model")
print("  FC     → P_FC_W               → EMS model")
print("  EMS    → active_source, net_power_balance")
print("="*60)