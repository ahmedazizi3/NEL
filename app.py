import joblib
import numpy as np
import pandas as pd
from functools import wraps
from flask import Flask, render_template, request, jsonify, g
import os

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

app = Flask(__name__)


def init_firebase_admin():
    if firebase_admin._apps:
        return True

    service_account_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    try:
        if service_account_path:
            cred = credentials.Certificate(service_account_path)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': os.environ.get('FIREBASE_PROJECT_ID', 'se-nel')
        })
        return True
    except Exception as e:
        print(f"Firebase Admin initialization failed: {e}")
        return False


firebase_admin_ready = init_firebase_admin()


def require_firebase_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not firebase_admin_ready:
            return jsonify({
                'error': 'Firebase Admin is not configured on the server.'
            }), 503

        auth_header = request.headers.get('Authorization', '')
        scheme, _, token = auth_header.partition(' ')
        if scheme.lower() != 'bearer' or not token:
            return jsonify({'error': 'Missing Firebase ID token.'}), 401

        try:
            g.firebase_user = firebase_auth.verify_id_token(token)
        except Exception:
            return jsonify({'error': 'Invalid or expired Firebase ID token.'}), 401

        return view(*args, **kwargs)

    return wrapped

# Load Models
models_dir = os.path.join(os.path.dirname(__file__), 'models')
try:
    solar_model = joblib.load(os.path.join(models_dir, 'solar_model.pkl'))
    wind_model = joblib.load(os.path.join(models_dir, 'wind_model.pkl'))
    fc_model = joblib.load(os.path.join(models_dir, 'fc_model.pkl'))
    models_loaded = True
except Exception as e:
    print(f"Error loading models: {e}")
    models_loaded = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/predict/solar', methods=['POST'])
@require_firebase_auth
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
@require_firebase_auth
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
@require_firebase_auth
def predict_fc():
    if not models_loaded: return jsonify({'error': 'Models not loaded'}), 500
    try:
        data = request.json
        X = pd.DataFrame([{'h2_flow': float(data['h2_flow'])}])
        pred = fc_model.predict(X)[0]
        return jsonify({'power': round(max(0, pred), 2)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
