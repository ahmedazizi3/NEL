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

- 🔐 **User Authentication** — Secure login/signup with Firebase Auth
- 🗺️ **Interactive Map** — Select locations worldwide with Leaflet integration
- 🌤️ **Real-Time Weather** — Live weather data from Open-Meteo API
- 🌞 **Solar PV Simulation** — Predict power output based on irradiance, temperature, and panel angle
- 💨 **Wind Energy Simulation** — Simulate turbine output from wind speed and load conditions
- ⚗️ **Fuel Cell & Hydrogen Simulation** — Model fuel cell characteristics and hydrogen generator behavior
- 🔋 **Battery Management Simulation** — Predict charge/discharge curves and State of Charge with animated visualization
- ⚡ **Energy Management Simulation** — Simulate grid/island switching, load balancing, and power flow
- 📊 **Interactive Charts** — Real-time data visualization with Chart.js
- 🤖 **ML-Powered Predictions** — Separate trained models per subsystem for accurate simulation
- 🎨 **Dark/Light Theme** — Customizable UI themes
- ⚙️ **Settings Panel** — Configure graph visibility, update intervals, and model parameters
- 🔍 **Model Inspector** — Inspect and edit ML model parameters in real-time
- 💾 **Data Persistence** — Session data saved across browser restarts
- 📱 **Responsive Design** — Works on desktop and mobile devices

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Frontend | HTML5, CSS3, JavaScript (ES6+) |
| Authentication | Firebase Auth |
| Maps | Leaflet.js |
| Charts | Chart.js |
| Weather API | Open-Meteo |
| Machine Learning | Scikit-learn, Pandas, NumPy, Joblib |
| Data Visualization | Chart.js, Plotly (notebooks) |
| Model Serialization | Pickle, Joblib |
| Version Control | Git + GitHub |
| Hosting | Local Flask server |

---

## 📁 Project Structure

```
NEL/
├── app.py                          # Flask application entry point with API endpoints
├── data_generator.py               # Data collection and preprocessing utilities
├── requirements.txt                # Python dependencies
├── README.md                       # Project documentation
├── models/                         # Trained ML model files
│   ├── fc_model.pkl                # Fuel cell model
│   ├── h2_production_model.pkl     # Hydrogen production model
│   ├── solar_model.pkl             # Solar PV model
│   ├── solar_model_summary.json    # Solar model metadata
│   └── wind_model.pkl              # Wind turbine model
├── nel_datasets/                   # Raw & processed datasets (not tracked by Git)
│   ├── dataset_battery.csv
│   ├── dataset_energy_management.csv
│   ├── dataset_fuelcell.csv
│   ├── dataset_solar.csv
│   └── dataset_wind.csv
├── notebooks/                      # Jupyter notebooks for model development
│   └── 01_solar_model.ipynb
├── preprocessors/                  # Data preprocessing pipelines
│   └── solar_scaler.pkl
├── static/                         # Static assets
│   ├── css/
│   │   └── style.css               # Application styles with themes
│   └── js/
│       └── main.js                 # Frontend logic, charts, auth, map integration
├── templates/
│   └── index.html                  # Main web interface
└── docs/                           # Documentation (various setup guides)
    ├── AUTH_IMPROVEMENTS_V2.md
    ├── FIREBASE_AUTH_SETUP.md
    ├── GOOGLE_ACCOUNT_AUTOMERGE.md
    └── GOOGLE_AUTH_SETUP.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip
- Git
- Node.js (for development, optional)

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

### Firebase Setup

To enable authentication, configure Firebase:

1. Create a Firebase project at https://console.firebase.google.com/
2. Enable Authentication with Email/Password provider
3. Copy your Firebase config to `main.js`
4. Update security rules as needed

See `FIREBASE_AUTH_SETUP.md` for detailed instructions.

---

## 📊 Datasets

Each energy subsystem has its own dedicated dataset collected from the physical NEL station:

| Dataset | Source Experiments | Key Features |
|---|---|---|
| `dataset_solar.csv` | S01 – S06 | V_SOL, I_SOL, Solar_Rad, T_SOL, tilt/azimuth angle |
| `dataset_wind.csv` | W01 – W03 | Windspeed, V_Wind, I_Wind, V_WB, I_WB |
| `dataset_fuelcell.csv` | F01 – F04 | V_FC, I_FC, T_FC, H2_Flow, H2_Pres |
| `dataset_battery.csv` | B01 – B03 | V_WB, V_BB, SoC, internal_resistance |
| `dataset_energy_management.csv` | E01 – E04 | grid_status, active_source, SoC_BB, load_profile |

> ⚠️ Raw datasets are **not tracked by Git** (`nel_datasets/` is in `.gitignore`). Contact the team for access or collect directly from the NEL station using Procedure P01 (Data Logging).

---

## 🤖 ML Models

Each subsystem uses a separately trained model:

| Model | Key Inputs | Target Variable | Status |
|---|---|---|---|
| `solar_model.pkl` | Irradiance, Temp, Angle | Power (W) | ✅ Integrated |
| `wind_model.pkl` | Wind Speed | Power (W) | ✅ Integrated |
| `fc_model.pkl` | H2 Flow | Power (W) | ✅ Integrated |
| `h2_production_model.pkl` | — | H2 Rate | 🔬 In Dev |
| `battery_model.pkl` | — | SoC (%), V_WB (V) | ⚠️ Physics Fallback |
| `ems_model.pkl` | — | Power Balance | ⚠️ Physics Fallback |

> Models are retrained as more data is collected from the station. See `data_generator.py` for the training pipeline and `notebooks/` for development examples.

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
| Data Collection & EDA | Feb 2025 → Mar 2025 | Clean datasets for all 5 subsystems |
| ML Model Development | Mar 2025 → Apr 2025 | Trained & validated models |
| Web App Development | Mar 2025 → Apr 2025 | Functional Flask application with auth & maps |
| Integration & Testing | Apr 2025 → May 2025 | Fully integrated simulator with animations |
| Documentation & Delivery | May 2025 | Final report + deployment |

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