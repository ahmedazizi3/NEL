import joblib
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

# Load Models
models_dir = os.path.join(os.path.dirname(__file__), 'models')
try:
    solar_model = joblib.load(os.path.join(models_dir, 'solar_model.pkl'))
    wind_model = joblib.load(os.path.join(models_dir, 'wind_model.pkl'))
    fc_model = joblib.load(os.path.join(models_dir, 'fc_model.pkl'))
    battery_model = joblib.load(os.path.join(models_dir, 'battery_model.pkl'))
    ems_model = joblib.load(os.path.join(models_dir, 'ems_model.pkl'))
    models_loaded = True
except Exception as e:
    print(f"Error loading models: {e}")
    models_loaded = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/predict/solar', methods=['POST'])
def predict_solar():
    if not models_loaded: return jsonify({'error': 'Models not loaded'}), 500
    try:
        data = request.json
        X = pd.DataFrame([{
            'irradiance': float(data['irradiance']),
            'temperature': float(data['temperature']),
            'angle': float(data['angle'])
        }])
        pred = solar_model.predict(X)[0]
        return jsonify({'power': round(max(0, pred), 2)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/predict/wind', methods=['POST'])
def predict_wind():
    if not models_loaded: return jsonify({'error': 'Models not loaded'}), 500
    try:
        data = request.json
        X = pd.DataFrame([{'wind_speed': float(data['wind_speed'])}])
        pred = wind_model.predict(X)[0]
        return jsonify({'power': round(max(0, pred), 2)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/predict/fc', methods=['POST'])
def predict_fc():
    if not models_loaded: return jsonify({'error': 'Models not loaded'}), 500
    try:
        data = request.json
        X = pd.DataFrame([{'h2_flow': float(data['h2_flow'])}])
        pred = fc_model.predict(X)[0]
        return jsonify({'power': round(max(0, pred), 2)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/predict/battery', methods=['POST'])
def predict_battery():
    if not models_loaded: return jsonify({'error': 'Models not loaded'}), 500
    try:
        data = request.json
        X = pd.DataFrame([{
            'initial_soc': float(data['initial_soc']),
            'power_input': float(data['power_input']),
            'time_min': float(data['time_min'])
        }])
        pred = battery_model.predict(X)[0]
        # clip to 0-100
        pred = max(0, min(100, pred))
        return jsonify({'final_soc': round(pred, 2)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/predict/ems', methods=['POST'])
def predict_ems():
    if not models_loaded: return jsonify({'error': 'Models not loaded'}), 500
    try:
        data = request.json
        X = pd.DataFrame([{
            'solar_p': float(data['solar_p']),
            'wind_p': float(data['wind_p']),
            'load_p': float(data['load_p'])
        }])
        pred = ems_model.predict(X)[0]
        return jsonify({'grid_power': round(pred, 2)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
