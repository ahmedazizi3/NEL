# 🌱 NEL Simulator

> **Machine Learning-Based Renewable Energy Simulation Web Application**  
> Simulating the [Heliocentris New Energy Lab](http://www.hns-re2sd.dz) station using real experimental data and ML models.

---

## 📌 About the Project

The **NEL Simulator** is a web-based application that digitally replicates the behavior of the **Heliocentris New Energy Lab (NEL)** station — a complete renewable energy laboratory system covering solar, wind, hydrogen, battery, and energy management subsystems.

The simulator collects real experimental data from the physical NEL station, trains machine learning models on that data, and provides an interactive interface where users input operating parameters and receive predicted energy outputs in real time — no physical lab access required.

This project was developed as part of the **Industrial Networking & Artificial Intelligence Engineering** program at **HNS-RE2SD**, Academic Year 2024–2025.

---

## ✨ Features

- 🌞 **Solar PV Simulation** — Predict power output based on irradiance, temperature, and panel angle
- 💨 **Wind Energy Simulation** — Simulate turbine output from wind speed and load conditions
- ⚗️ **Fuel Cell & Hydrogen Simulation** — Model fuel cell characteristics and hydrogen generator behavior
- 🔋 **Battery Management Simulation** — Predict charge/discharge curves and State of Charge
- ⚡ **Energy Management Simulation** — Simulate grid/island switching, load balancing, and power flow
- 📊 **Interactive Web Interface** — Real-time charts and result visualization in the browser
- 🤖 **ML-Powered Predictions** — Separate trained models per subsystem for accurate simulation

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Web Framework | Flask |
| Machine Learning | Scikit-learn |
| Data Processing | Pandas, NumPy |
| Visualization | Chart.js / Plotly |
| Frontend | HTML, CSS, JavaScript |
| Model Serialization | Pickle / Joblib |
| Version Control | Git + GitHub |

---

## 📁 Project Structure

```
NEL/
├── app.py                  # Flask application entry point
├── data_generator.py       # Data collection and preprocessing utilities
├── requirements.txt        # Python dependencies
├── models/                 # Trained ML model files (.pkl)
│   ├── solar_model.pkl
│   ├── wind_model.pkl
│   ├── fc_model.pkl
│   ├── battery_model.pkl
│   └── ems_model.pkl
├── static/
│   ├── css/style.css       # Application styles
│   └── js/main.js          # Frontend logic and chart rendering
├── templates/
│   └── index.html          # Main web interface
└── nel_datasets/           # Raw & processed datasets (not tracked by Git)
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip
- Git

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/ahmedazizi3/NEL.git
cd NEL

# 2. Create a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py
```

Then open your browser and go to: **http://localhost:5000**

---

## 📊 Datasets

Each energy subsystem has its own dedicated dataset collected from the physical NEL station:

| Dataset | Source Experiments | Key Features |
|---|---|---|
| `solar_dataset.csv` | S01 – S06 | V_SOL, I_SOL, Solar_Rad, T_SOL, tilt/azimuth angle |
| `wind_dataset.csv` | W01 – W03 | Windspeed, V_Wind, I_Wind, V_WB, I_WB |
| `fuelcell_dataset.csv` | F01 – F04 | V_FC, I_FC, T_FC, H2_Flow, H2_Pres |
| `battery_dataset.csv` | B01 – B03 | V_WB, V_BB, SoC, internal_resistance |
| `ems_dataset.csv` | E01 – E04 | grid_status, active_source, SoC_BB, load_profile |

> ⚠️ Raw datasets are **not tracked by Git** (`nel_datasets/` is in `.gitignore`). Contact the team for access or collect directly from the NEL station using Procedure P01 (Data Logging).

---

## 🤖 ML Models

Each subsystem uses a separately trained model:

| Model | Algorithm | Target Variable |
|---|---|---|
| `solar_model.pkl` | Random Forest Regressor | P_SOL_total (W) |
| `wind_model.pkl` | Random Forest Regressor | P_Wind (W) |
| `fc_model.pkl` | Gradient Boosting Regressor | P_FC (W), Efficiency_FC (%) |
| `battery_model.pkl` | Random Forest Regressor | SoC (%), V_WB (V) |
| `ems_model.pkl` | Random Forest Classifier/Regressor | net_power_balance (W), active_source |

> Models are retrained as more data is collected from the station. See `data_generator.py` for the training pipeline.

---

## 👥 Team

| Name | Role | GitHub |
|---|---|---|
| Ahmed Azizi | ML & Data Lead | [@ahmedazizi3](https://github.com/ahmedazizi3) |
| Ayoub Chaib Aino | Back-End Lead | — |
| Nesrine Mazari | Front-End Lead | — |
| Ikram Khadidja Bahri | Integration & QA Lead | — |

> 📌 Roles are proposed and will be confirmed at project kick-off.

---

## 🗓️ Project Timeline

| Phase | Period | Deliverable |
|---|---|---|
| Data Collection & EDA | Feb 2026 → Mar 2026 | Clean datasets for all 5 subsystems |
| ML Model Development | Mar 2026 → Apr 2026 | Trained & validated models |
| Web App Development | Mar 2026 → Apr 2026 | Functional Flask application |
| Integration & Testing | Apr 2026 → May 2026 | Fully integrated simulator |
| Documentation & Delivery | May 2026 | Final report + deployment |

---

## 📄 License

This project is currently **private** and intended for academic use at HNS-RE2SD.  
For external use or collaboration inquiries, contact the project team.

---

## 🏫 Institution

**École Nationale Supérieure — HNS-RE2SD**  
Department of Industrial Networking & Artificial Intelligence Engineering  
Academic Year 2024 – 2025  
Supervised by: *[Professor name]*

---

*Built with ❤️ by the NEL Simulator team — turning lab data into digital intelligence.*