// Firebase Modular SDK imports
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-app.js";
import {
    getAuth,
    onAuthStateChanged,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    signOut,
    sendEmailVerification,
    sendPasswordResetEmail
} from "https://www.gstatic.com/firebasejs/12.12.0/firebase-auth.js";

/* ═══════════════════════════════════════════════════════════════
   NEL Simulator — Frontend Application
   Real-time renewable energy simulation with map-based input
   ═══════════════════════════════════════════════════════════════ */

    'use strict';

    /* ── Configuration ─────────────────────────────────────── */
    const CONFIG = {
        DEFAULT_LAT: 35.55,
        DEFAULT_LNG: 6.17,
        DEFAULT_ZOOM: 6,
        SELECTED_ZOOM: 10,
        DEFAULT_PANEL_ANGLE: 30,
        DEFAULT_SOC: 65,
        MAX_DATA_POINTS: 10000,        // long-running history window
        WEATHER_API: 'https://api.open-meteo.com/v1/forecast',
        NOMINATIM_API: 'https://nominatim.openstreetmap.org/search',
        SEARCH_DEBOUNCE_MS: 400,
    };

    // Firebase config and initialization
    const firebaseConfig = {
        apiKey: "AIzaSyAUFm9a657qFueCDddSyy6vm2swHEN19tg",
        authDomain: "se-nel.firebaseapp.com",
        projectId: "se-nel",
        storageBucket: "se-nel.firebasestorage.app",
        messagingSenderId: "252917296517",
        appId: "1:252917296517:web:4c9d07820fd72443dc68ec",
        measurementId: "G-3RCW3MY9D2"
    };
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    console.log('✅ Firebase initialized');
    console.log('🔐 Auth module loaded');

    function cssVar(name) {
        return getComputedStyle(document.body).getPropertyValue(name).trim();
    }

    function hexToRgba(hex, alpha) {
        const clean = hex.replace('#', '');
        const full = clean.length === 3 ? clean.split('').map(c => c + c).join('') : clean;
        const int = Number.parseInt(full, 16);
        const r = (int >> 16) & 255;
        const g = (int >> 8) & 255;
        const b = int & 255;
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    function getSeriesColors() {
        const solar = cssVar('--solar');
        const wind = cssVar('--wind');
        const fc = cssVar('--fc');
        const battery = cssVar('--battery');
        const ems = cssVar('--ems');
        return {
            solar: { border: solar, bg: hexToRgba(solar, 0.12) },
            wind: { border: wind, bg: hexToRgba(wind, 0.12) },
            fc: { border: fc, bg: hexToRgba(fc, 0.12) },
            battery: { border: battery, bg: hexToRgba(battery, 0.12) },
            ems: { border: ems, bg: hexToRgba(ems, 0.12) },
        };
    }

    function getMapTileConfig(theme) {
        return {
            url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        };
    }

    /* ── State ──────────────────────────────────────────────── */
    const state = {
        location: null,          // { lat, lng, name }
        batterySoC: CONFIG.DEFAULT_SOC,
        charts: {},              // Chart.js instances
        chartData: {},           // { solar: {labels:[], data:[]}, ... }
        preferences: {           // graph visibility + interval
            visible: { solar: true, wind: true, fc: true, battery: true, ems: true },
            intervalMinutes: 30,
            theme: 'dark',
            modelParams: {
                solar: { angle: CONFIG.DEFAULT_PANEL_ANGLE },
                wind: { inputScale: 1.0 },
                battery: { loadBias: 0, timeMultiplier: 1.0 },
                fc: { h2Factor: 0.756, h2Noise: 0.05, socThreshold: 40 },
                ems: { loadBias: 0 },
            },
        },
        updateTimer: null,
        countdownTimer: null,
        nextUpdateTime: null,
        isUpdating: false,
        map: null,
        marker: null,
        searchTimeout: null,
        latestWeather: null,
        latestResults: null,     // { solar, wind, fc, battery, ems, load }
        lastUpdatedTimes: {},    // { solar: timestamp, wind: ... }
        isApplyingExternalSync: false,
        mapModalOpen: false,
        theme: 'dark',
        mapTileLayer: null,
        selectedModelKey: null,
        latestModelDetails: {},
        dischargeInterval: null,
        authUser: null,
        appInitialized: false,
    };

    /* ══════════════════════════════════════��═══════════════════
       MODULE 1 — Toast Notifications
       ══════════════════════════════════════════════════════════ */
    function showToast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icons = { success: 'fa-circle-check', error: 'fa-circle-exclamation', info: 'fa-circle-info' };
        toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    /* ══════════════════════════════════════════════════════════
       MODULE 2 — Map Manager
       ══════════════════════════════════════════════════════════ */
    function initMap() {
        state.map = L.map('map', {
            center: [CONFIG.DEFAULT_LAT, CONFIG.DEFAULT_LNG],
            zoom: CONFIG.DEFAULT_ZOOM,
            zoomControl: true,
            attributionControl: false,
        });

        const mapTheme = getMapTileConfig(state.theme);
        state.mapTileLayer = L.tileLayer(mapTheme.url, {
            maxZoom: 19,
            attribution: mapTheme.attribution,
        }).addTo(state.map);

        // Click to select location
        state.map.on('click', async (e) => {
            const { lat, lng } = e.latlng;
            await selectLocation(lat, lng);
        });

        // Search bar
        const searchInput = document.getElementById('map-search-input');
        searchInput.addEventListener('input', (e) => {
            clearTimeout(state.searchTimeout);
            const q = e.target.value.trim();
            if (q.length < 3) { hideSearchResults(); return; }
            state.searchTimeout = setTimeout(() => searchLocation(q), CONFIG.SEARCH_DEBOUNCE_MS);
        });

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') { hideSearchResults(); searchInput.blur(); }
        });

        // Close search on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.map-search')) hideSearchResults();
        });
    }

    function applyMapTheme() {
        if (!state.map) return;
        const mapTheme = getMapTileConfig(state.theme);
        if (state.mapTileLayer) {
            state.map.removeLayer(state.mapTileLayer);
        }
        state.mapTileLayer = L.tileLayer(mapTheme.url, {
            maxZoom: 19,
            attribution: mapTheme.attribution,
        }).addTo(state.map);
    }

    function initMapVisibility() {
        const topbarToggle = document.getElementById('map-toggle-btn');
        const closeBtn = document.getElementById('map-modal-close');
        const backdrop = document.getElementById('map-modal-backdrop');
        const modal = document.getElementById('map-modal');

        function openMapModal() {
            state.mapModalOpen = true;
            modal.classList.add('open');
            backdrop.classList.add('open');
            modal.setAttribute('aria-hidden', 'false');
            topbarToggle.classList.add('active');
            topbarToggle.setAttribute('aria-expanded', 'true');
            setTimeout(() => {
                if (!state.map) return;
                state.map.invalidateSize();
                if (state.location) {
                    state.map.setView([state.location.lat, state.location.lng], CONFIG.SELECTED_ZOOM, { animate: false });
                }
            }, 200);
        }

        function closeMapModal() {
            state.mapModalOpen = false;
            modal.classList.remove('open');
            backdrop.classList.remove('open');
            modal.setAttribute('aria-hidden', 'true');
            topbarToggle.classList.remove('active');
            topbarToggle.setAttribute('aria-expanded', 'false');
        }

        topbarToggle.addEventListener('click', () => {
            if (state.mapModalOpen) closeMapModal();
            else openMapModal();
        });
        closeBtn.addEventListener('click', closeMapModal);
        backdrop.addEventListener('click', closeMapModal);
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && state.mapModalOpen) closeMapModal();
        });

        // expose for selection flow auto-close
        state.closeMapModal = closeMapModal;
    }

    function applyTheme(theme) {
        state.theme = theme === 'light' ? 'light' : 'dark';
        state.preferences.theme = state.theme;
        document.body.setAttribute('data-theme', state.theme);

        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            const icon = toggle.querySelector('i');
            const toLight = state.theme === 'dark';
            toggle.setAttribute('aria-label', toLight ? 'Switch to light mode' : 'Switch to dark mode');
            toggle.title = toLight ? 'Switch to light mode' : 'Switch to dark mode';
            if (icon) {
                icon.className = toLight ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
            }
        }

        applyMapTheme();
        applyChartTheme();
    }

    function initTheme() {
        const systemPrefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        applyTheme(state.preferences.theme || (systemPrefersDark ? 'dark' : 'light'));

        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                applyTheme(state.theme === 'dark' ? 'light' : 'dark');
                PersistenceManager.savePreferences();
            });
        }
    }

    async function searchLocation(query) {
        try {
            const url = `${CONFIG.NOMINATIM_API}?q=${encodeURIComponent(query)}&format=json&limit=5&addressdetails=1`;
            const res = await fetch(url, { headers: { 'Accept-Language': 'en' } });
            const results = await res.json();
            showSearchResults(results);
        } catch (err) {
            console.error('Search error:', err);
        }
    }

    function showSearchResults(results) {
        const container = document.getElementById('search-results');
        container.innerHTML = '';
        if (results.length === 0) {
            container.innerHTML = '<div class="search-result-item">No results found</div>';
        } else {
            results.forEach(r => {
                const item = document.createElement('div');
                item.className = 'search-result-item';
                item.textContent = r.display_name;
                item.addEventListener('click', () => {
                    selectLocation(parseFloat(r.lat), parseFloat(r.lon), r.display_name);
                    hideSearchResults();
                    document.getElementById('map-search-input').value = '';
                });
                container.appendChild(item);
            });
        }
        container.classList.add('show');
    }

    function hideSearchResults() {
        document.getElementById('search-results').classList.remove('show');
    }

    async function selectLocation(lat, lng, name) {
        // Detect a genuine location switch (>0.01° ≈ 1 km tolerance)
        const isLocationChange = state.location &&
            (Math.abs(state.location.lat - lat) > 0.01 || Math.abs(state.location.lng - lng) > 0.01);

        // Place / move marker
        if (state.marker) {
            state.marker.setLatLng([lat, lng]);
        } else {
            state.marker = L.marker([lat, lng]).addTo(state.map);
        }
        state.map.flyTo([lat, lng], CONFIG.SELECTED_ZOOM, { duration: 1 });

        // Reverse geocode if no name provided
        if (!name) {
            try {
                const res = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&zoom=10`, {
                    headers: { 'Accept-Language': 'en' },
                });
                const data = await res.json();
                name = data.display_name || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
            } catch {
                name = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
            }
        }

        // Truncate long names
        const shortName = name.length > 60 ? name.substring(0, 57) + '...' : name;

        // If the user switched to a different location, clear the landmark's graph history
        // so the new container holds only data for the new site
        if (isLocationChange) {
            clearChartsForNewLocation();
            showToast(`Location changed — graph history reset for new site`, 'info', 3500);
        }

        state.location = { lat, lng, name: shortName };

        // Start battery discharge animation
        startBatteryDischarge();

        // Update map overlay badge
        document.getElementById('location-name').textContent = shortName;
        document.getElementById('location-coords').textContent = `${lat.toFixed(4)}°, ${lng.toFixed(4)}°`;

        // Update the landmark panel header
        updateLandmarkHeader(shortName, lat, lng);

        // Save to storage
        PersistenceManager.saveLocation();

        // Run the full pipeline
        await runFullPipeline();

        // Start auto-updates
        startAutoUpdate();

        // Close the map popup after picking a location.
        if (typeof state.closeMapModal === 'function') {
            state.closeMapModal();
        }
    }

    function updateLandmarkHeader(name, lat, lng) {
        const locationIndicator = document.getElementById('main-location-indicator');
        if (locationIndicator) {
            const hasCoords = lat !== undefined && lng !== undefined;
            locationIndicator.textContent = name ? `Location: ${name}` : 'Location: not selected';
            locationIndicator.title = hasCoords ? `${lat.toFixed(4)}°, ${lng.toFixed(4)}°` : '';
        }
    }

    function clearChartsForNewLocation() {
        ['solar', 'wind', 'fc', 'battery', 'ems'].forEach(key => {
            state.chartData[key] = { labels: [], data: [] };
            state.lastUpdatedTimes[key] = null;
        });
        renderMainAnalyticsChart();
        const updatedEl = document.getElementById('main-updated');
        if (updatedEl) updatedEl.textContent = '';
        state.latestResults = null;
        PersistenceManager.saveChartData();
        // Hide dashboard until new data arrives
        document.getElementById('empty-state').style.display = '';
        document.getElementById('dashboard-grid').style.display = 'none';
    }

    /* ══════════════════════════════════════════════════════════
       MODULE 3 — Weather Service
       ══════════════════════════════════════════════════════════ */
    async function fetchWeather(lat, lng) {
        const url = `${CONFIG.WEATHER_API}?latitude=${lat}&longitude=${lng}&current=temperature_2m,wind_speed_10m,shortwave_radiation&timezone=auto`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Weather API error: ${res.status}`);
        const data = await res.json();
        return {
            radiation: data.current.shortwave_radiation || 0,
            temperature: data.current.temperature_2m || 20,
            windSpeed: data.current.wind_speed_10m || 0,
        };
    }

    function updateWeatherUI(weather) {
        animateValue('w-radiation', weather.radiation, 0);
        animateValue('w-temperature', weather.temperature, 1);
        animateValue('w-windspeed', weather.windSpeed, 1);
    }

    function animateValue(elementId, target, decimals) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const start = parseFloat(el.textContent) || 0;
        const duration = 600;
        const startTime = performance.now();

        function step(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            const current = start + (target - start) * eased;
            el.textContent = current.toFixed(decimals);
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    const MODEL_METADATA = {
        solar: {
            title: 'Solar Model',
            inputs: ['irradiance', 'temperature', 'angle'],
            outputs: ['power'],
            editable: [{ key: 'angle', label: 'Panel Angle (deg)', min: 0, max: 90, step: 1 }],
        },
        wind: {
            title: 'Wind Model',
            inputs: ['wind_speed'],
            outputs: ['power'],
            editable: [{ key: 'inputScale', label: 'Wind Input Scale', min: 0.5, max: 1.5, step: 0.01 }],
        },
        fc: {
            title: 'Fuel Cell Model',
            inputs: ['h2_flow'],
            outputs: ['power'],
            editable: [
                { key: 'h2Factor', label: 'H2 Factor', min: 0.1, max: 2.0, step: 0.001 },
                { key: 'h2Noise', label: 'H2 Noise Range', min: 0, max: 0.2, step: 0.005 },
                { key: 'socThreshold', label: 'SOC Threshold (%)', min: 0, max: 100, step: 1 },
            ],
        },
        battery: {
            title: 'Battery Model',
            inputs: ['initial_soc', 'power_input', 'time_min'],
            outputs: ['final_soc'],
            editable: [
                { key: 'loadBias', label: 'Load Bias (W)', min: -200, max: 200, step: 1 },
                { key: 'timeMultiplier', label: 'Time Multiplier', min: 0.5, max: 2.0, step: 0.05 },
            ],
        },
        ems: {
            title: 'EMS Model',
            inputs: ['solar_p', 'wind_p', 'load_p'],
            outputs: ['grid_power'],
            editable: [{ key: 'loadBias', label: 'Load Bias (W)', min: -200, max: 200, step: 1 }],
        },
    };

    function openModelInspector(modelKey) {
        const inspector = document.getElementById('model-inspector');
        const titleEl = document.getElementById('model-inspector-title');
        const subtitleEl = document.getElementById('model-inspector-subtitle');
        const grid = document.getElementById('model-inspector-grid');
        if (!inspector || !titleEl || !subtitleEl || !grid || !MODEL_METADATA[modelKey]) return;

        state.selectedModelKey = modelKey;
        const meta = MODEL_METADATA[modelKey];
        const details = state.latestModelDetails[modelKey] || { inputs: {}, outputs: {} };
        const params = state.preferences.modelParams[modelKey] || {};

        titleEl.textContent = `${meta.title} Details`;
        subtitleEl.textContent = 'Editable fields are non-weather hardcoded parameters. Save to apply for future points.';
        grid.innerHTML = '';

        meta.inputs.forEach((inputKey) => {
            const field = document.createElement('div');
            field.className = 'inspector-field';
            field.innerHTML = `<label>Input · ${inputKey}</label><span class="readonly-value">${details.inputs[inputKey] ?? '—'}</span>`;
            grid.appendChild(field);
        });

        meta.outputs.forEach((outputKey) => {
            const field = document.createElement('div');
            field.className = 'inspector-field';
            field.innerHTML = `<label>Output · ${outputKey}</label><span class="readonly-value">${details.outputs[outputKey] ?? '—'}</span>`;
            grid.appendChild(field);
        });

        meta.editable.forEach((cfg) => {
            const current = params[cfg.key];
            const field = document.createElement('div');
            field.className = 'inspector-field';
            field.innerHTML = `
                <label>Editable · ${cfg.label}</label>
                <input type="number" data-param-key="${cfg.key}" value="${current}" min="${cfg.min}" max="${cfg.max}" step="${cfg.step}">
            `;
            grid.appendChild(field);
        });

        inspector.classList.add('open');
    }

    function initModelInspector() {
        const saveBtn = document.getElementById('model-inspector-save');
        if (!saveBtn) return;
        saveBtn.addEventListener('click', () => {
            const modelKey = state.selectedModelKey;
            if (!modelKey || !MODEL_METADATA[modelKey]) return;
            const wrapper = document.getElementById('model-inspector-grid');
            const next = { ...state.preferences.modelParams[modelKey] };
            wrapper.querySelectorAll('input[data-param-key]').forEach((input) => {
                const key = input.dataset.paramKey;
                const val = Number.parseFloat(input.value);
                if (!Number.isNaN(val)) next[key] = val;
            });
            state.preferences.modelParams[modelKey] = next;
            PersistenceManager.savePreferences();
            showToast(`${MODEL_METADATA[modelKey].title} parameters saved`, 'success', 2200);
        });
    }

    /* ══════════════════════════════════════════════════════════
       MODULE 4 — Simulation Pipeline
       ══════════════════════════════════════════════════════════ */
    async function fetchPrediction(endpoint, data) {
        const user = auth.currentUser;
        if (!user) throw new Error('auth-required');
        const idToken = await user.getIdToken();
        const res = await fetch(`/api/predict/${endpoint}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${idToken}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error(`${res.status}`);
        return await res.json();
    }

    function calculateLoadDemand(biasW = 0) {
        // Sinusoidal load pattern matching data_generator.py
        // Base 100W + 200W sinusoidal based on time of day (peak at midday)
        const hour = new Date().getHours() + new Date().getMinutes() / 60;
        if (hour < 8 || hour > 18) return 50; // low load outside lab hours
        const load = 100 + 200 * Math.sin(Math.PI * (hour - 8) / 10);
        return Math.round(Math.max(50, Math.min(400, load + (Math.random() - 0.5) * 20 + biasW)));
    }

    /* ── Physics-based fallbacks (used when a model endpoint fails) ── */

    function simWeather() {
        // Time-of-day climate approximation (Batna, Algeria reference)
        const hour = new Date().getHours() + new Date().getMinutes() / 60;
        const radiation = (hour >= 6 && hour <= 20)
            ? Math.max(0, 920 * Math.sin(Math.PI * (hour - 6) / 14))
            : 0;
        const temperature = 18 + 12 * Math.sin(Math.PI * (hour - 6) / 14);
        const windSpeed = 12 + (Math.random() - 0.5) * 6; // km/h
        return {
            radiation: Math.round(radiation),
            temperature: Math.round(temperature * 10) / 10,
            windSpeed: Math.round(windSpeed * 10) / 10,
        };
    }

    function simSolar(irradiance, temperature, angle) {
        // Lab PV array: ~1.05 m², 15.5% efficiency, temp coefficient -0.4%/°C
        const cosAngle = Math.cos((angle * Math.PI) / 180);
        const tempCoeff = 1 - 0.004 * Math.max(0, temperature - 25);
        return Math.max(0, Math.round(irradiance * 0.155 * 1.05 * cosAngle * tempCoeff * 10) / 10);
    }

    function simWind(windSpeedMs) {
        // Lab turbine: cut-in 1.5 m/s, rated 150 W at 8 m/s, cut-out 15 m/s
        if (windSpeedMs < 1.5 || windSpeedMs > 15) return 0;
        if (windSpeedMs >= 8) return 150;
        return Math.round(150 * Math.pow((windSpeedMs - 1.5) / 6.5, 3) * 10) / 10;
    }

    function simBattery(initialSoC, powerInput, timeMin) {
        // Simple coulomb counting: 100 Wh lab battery
        const energyDelta = (powerInput * timeMin) / 60;
        const socDelta = (energyDelta / 100) * 100;
        return Math.round(Math.max(0, Math.min(100, initialSoC + socDelta)) * 10) / 10;
    }

    function simFuelCell(h2Flow) {
        // Empirical: ~18.5 W per slm H₂ (from dataset calibration)
        return Math.round(Math.max(0, h2Flow * 18.5) * 10) / 10;
    }

    function simEMS(solarP, windP, loadP) {
        // Net grid balance: positive = grid import, negative = export
        return Math.round((loadP - solarP - windP) * 10) / 10;
    }

    async function runFullPipeline() {
        if (!state.location || state.isUpdating) return;

        state.isUpdating = true;
        showMapLoading(true);
        const simulated = []; // tracks which subsystems fell back to simulation

        try {
            // 1. Fetch weather (external API — fallback to local simulation on failure)
            let weather;
            try {
                weather = await fetchWeather(state.location.lat, state.location.lng);
            } catch (e) {
                console.warn('Weather API unavailable, using time-of-day simulation:', e.message);
                weather = simWeather();
                simulated.push('Weather');
            }
            state.latestWeather = weather;
            updateWeatherUI(weather);

            const solarCfg = state.preferences.modelParams.solar;
            const windCfg = state.preferences.modelParams.wind;
            const batteryCfg = state.preferences.modelParams.battery;
            const fcCfg = state.preferences.modelParams.fc;
            const emsCfg = state.preferences.modelParams.ems;

            // 2. Solar prediction
            const windSpeedMs = weather.windSpeed / 3.6; // Open-Meteo gives km/h
            const solarAngle = solarCfg.angle;
            let solarPower;
            try {
                const r = await fetchPrediction('solar', {
                    irradiance: weather.radiation,
                    temperature: weather.temperature,
                    angle: solarAngle,
                });
                solarPower = r.power || 0;
            } catch {
                solarPower = simSolar(weather.radiation, weather.temperature, solarAngle);
                simulated.push('Solar');
            }
            state.latestModelDetails.solar = {
                inputs: {
                    irradiance: Number(weather.radiation.toFixed(2)),
                    temperature: Number(weather.temperature.toFixed(2)),
                    angle: Number(solarAngle.toFixed(2)),
                },
                outputs: { power: Number(solarPower.toFixed(2)) },
            };

            // 3. Wind prediction
            const adjustedWindInput = windSpeedMs * windCfg.inputScale;
            let windPower;
            try {
                const r = await fetchPrediction('wind', { wind_speed: adjustedWindInput });
                windPower = r.power || 0;
            } catch {
                windPower = simWind(adjustedWindInput);
                simulated.push('Wind');
            }
            state.latestModelDetails.wind = {
                inputs: { wind_speed: Number(adjustedWindInput.toFixed(3)) },
                outputs: { power: Number(windPower.toFixed(2)) },
            };

            // 4. Battery prediction
            const loadDemand = calculateLoadDemand(batteryCfg.loadBias + emsCfg.loadBias);
            const netPower = solarPower + windPower - loadDemand;
            const timeMin = state.preferences.intervalMinutes * batteryCfg.timeMultiplier;
            const initialSoC = state.batterySoC;
            let newSoC;
            try {
                const r = await fetchPrediction('battery', {
                    initial_soc: initialSoC,
                    power_input: netPower,
                    time_min: timeMin,
                });
                newSoC = r.final_soc || initialSoC;
            } catch {
                newSoC = simBattery(initialSoC, netPower, timeMin);
                simulated.push('Battery');
            }
            state.batterySoC = newSoC;
            state.latestModelDetails.battery = {
                inputs: {
                    initial_soc: Number(initialSoC.toFixed(2)),
                    power_input: Number(netPower.toFixed(2)),
                    time_min: Number(timeMin.toFixed(2)),
                },
                outputs: { final_soc: Number(newSoC.toFixed(2)) },
            };

            // 5. Fuel Cell prediction
            let h2Flow = 0;
            if (state.batterySoC > fcCfg.socThreshold) {
                h2Flow = ((state.batterySoC - fcCfg.socThreshold) / Math.max(1, 100 - fcCfg.socThreshold)) * fcCfg.h2Factor;
                h2Flow = Math.max(0, Math.min(2.0, h2Flow + (Math.random() - 0.5) * fcCfg.h2Noise));
            }
            let fcPower;
            try {
                const r = await fetchPrediction('fc', { h2_flow: h2Flow });
                fcPower = r.power || 0;
            } catch {
                fcPower = simFuelCell(h2Flow);
                simulated.push('Fuel Cell');
            }
            state.latestModelDetails.fc = {
                inputs: { h2_flow: Number(h2Flow.toFixed(4)) },
                outputs: { power: Number(fcPower.toFixed(2)) },
            };

            // 6. EMS prediction
            let gridPower;
            try {
                const r = await fetchPrediction('ems', {
                    solar_p: solarPower,
                    wind_p: windPower,
                    load_p: loadDemand,
                });
                gridPower = r.grid_power || 0;
            } catch {
                gridPower = simEMS(solarPower, windPower, loadDemand);
                simulated.push('EMS');
            }
            state.latestModelDetails.ems = {
                inputs: {
                    solar_p: Number(solarPower.toFixed(2)),
                    wind_p: Number(windPower.toFixed(2)),
                    load_p: Number(loadDemand.toFixed(2)),
                },
                outputs: { grid_power: Number(gridPower.toFixed(2)) },
            };

            // Store latest results
            state.latestResults = {
                solar: solarPower,
                wind: windPower,
                fc: fcPower,
                battery: newSoC,
                ems: gridPower,
                load: loadDemand,
                netPower: netPower,
            };

            // Update charts & values
            const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            appendChartData('solar', timestamp, solarPower);
            appendChartData('wind', timestamp, windPower);
            appendChartData('fc', timestamp, fcPower);
            appendChartData('battery', timestamp, newSoC);
            appendChartData('ems', timestamp, gridPower);
            renderMainAnalyticsChart();
            if (state.selectedModelKey) openModelInspector(state.selectedModelKey);

            updateDisplayValues();

            // Show dashboard
            document.getElementById('empty-state').style.display = 'none';
            document.getElementById('dashboard-grid').style.display = 'grid';

            // Persist
            PersistenceManager.saveChartData();
            PersistenceManager.saveBatterySoC();

            if (simulated.length === 0) {
                updateApiStatus(true);
                showToast('Simulation updated — all models active', 'success', 3000);
            } else {
                updateApiStatus(false);
                const label = simulated.length === 6
                    ? 'All subsystems'
                    : simulated.join(', ');
                showToast(`${label} using physics simulation (model unavailable)`, 'info', 5000);
            }

        } catch (err) {
            // Only reached if weather fetch AND simWeather both fail (shouldn't happen)
            console.error('Pipeline error:', err);
            showToast(`Error: ${err.message}`, 'error');
            updateApiStatus(false);
        } finally {
            state.isUpdating = false;
            showMapLoading(false);
        }
    }

    function showMapLoading(show) {
        const el = document.getElementById('map-loading');
        if (show) el.classList.add('active');
        else el.classList.remove('active');
    }

    function updateApiStatus(online) {
        const pill = document.getElementById('api-status');
        const text = document.getElementById('api-status-text');
        if (online) {
            pill.className = 'status-pill online';
            text.textContent = 'API Online';
        } else {
            pill.className = 'status-pill offline';
            text.textContent = 'API Error';
        }
    }

    function updateDisplayValues() {
        if (!state.latestResults) return;
        animateValue('val-solar', state.latestResults.solar, 2);
        animateValue('val-wind', state.latestResults.wind, 2);
        animateValue('val-fc', state.latestResults.fc, 2);
        animateValue('val-battery', state.latestResults.battery, 2);
        animateValue('val-ems', state.latestResults.ems, 2);

        // Update battery animation
        updateBatteryAnimation();
    }

    function updatePowerSummary() {
        if (!state.latestResults || !document.getElementById('ps-renewable')) return;
        const { solar, wind, fc, ems, load } = state.latestResults;
        const renewable = Math.max(0, solar) + Math.max(0, wind) + Math.max(0, fc);
        animateValue('ps-renewable', renewable, 1);
        animateValue('ps-load', load || 0, 0);
        animateValue('ps-soc', state.batterySoC, 1);

        const gridEl = document.getElementById('ps-grid');
        const gridUnitEl = document.getElementById('ps-grid-unit');
        if (ems > 0) {
            gridEl.textContent = ems.toFixed(1);
            gridUnitEl.textContent = ' W ↑';
            gridEl.style.color = 'var(--ems)';
        } else if (ems < 0) {
            gridEl.textContent = Math.abs(ems).toFixed(1);
            gridUnitEl.textContent = ' W ↓';
            gridEl.style.color = 'var(--success)';
        } else {
            gridEl.textContent = '0';
            gridUnitEl.textContent = ' W';
            gridEl.style.color = '';
        }
    }

    function formatTimeAgo(timestamp) {
        if (!timestamp) return '';
        const seconds = Math.floor((Date.now() - timestamp) / 1000);
        if (seconds < 5) return 'just now';
        if (seconds < 60) return `${seconds}s ago`;
        const mins = Math.floor(seconds / 60);
        if (mins < 60) return `${mins}m ago`;
        return `${Math.floor(mins / 60)}h ago`;
    }

    function refreshCardTimestamp(key) {
        const el = document.getElementById('main-updated');
        if (el) el.textContent = formatTimeAgo(state.lastUpdatedTimes[key]);
    }

    function refreshAllCardTimestamps() {
        const timestamps = ['solar', 'wind', 'fc', 'battery', 'ems']
            .map(key => state.lastUpdatedTimes[key])
            .filter(Boolean);
        const latest = timestamps.length ? Math.max(...timestamps) : null;
        const el = document.getElementById('main-updated');
        if (el) el.textContent = formatTimeAgo(latest);
    }

    /* ══════════════════════════════════════════════════════════
       MODULE 5 — Chart Manager
       ══════════════════════════════════════════════════════════ */
    function getChartThemeOptions() {
        return {
            text: cssVar('--chart-text'),
            grid: cssVar('--chart-grid'),
            tooltipBg: cssVar('--tooltip-bg'),
            tooltipBorder: cssVar('--tooltip-border'),
            tooltipTitle: cssVar('--text-primary'),
            tooltipBody: cssVar('--text-secondary'),
            axisTitle: cssVar('--text-muted'),
        };
    }

    function initCharts() {
        const theme = getChartThemeOptions();
        const series = getSeriesColors();

        Chart.defaults.color = theme.text;
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.font.size = 11;

        const mainOpts = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            onClick: (event, elements, chart) => {
                const points = chart.getElementsAtEventForMode(event, 'nearest', { intersect: false }, true);
                if (!points.length) return;
                const datasetIndex = points[0].datasetIndex;
                const map = ['solar', 'wind', 'fc'];
                const key = map[datasetIndex];
                if (key) openModelInspector(key);
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: theme.text,
                        usePointStyle: true,
                        pointStyle: 'line',
                        boxWidth: 20,
                        padding: 14,
                    },
                },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    borderColor: theme.tooltipBorder,
                    borderWidth: 1,
                    titleColor: theme.tooltipTitle,
                    bodyColor: theme.tooltipBody,
                    padding: 10,
                    cornerRadius: 8,
                    displayColors: false,
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 8, maxRotation: 0 },
                    title: {
                        display: true,
                        text: 'Timeline',
                        color: theme.axisTitle,
                        font: { size: 10, weight: '600' },
                    },
                },
                y: {
                    grid: { color: theme.grid },
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Subsystem Output (W / %)',
                        color: theme.axisTitle,
                        font: { size: 10, weight: '600' },
                    },
                }
            },
            animation: { duration: 600, easing: 'easeOutQuart' },
            elements: {
                point: { radius: 2, hoverRadius: 5 },
                line: { tension: 0.35, borderWidth: 2 },
            },
        };

        const ctx = document.getElementById('chart-main-analytics').getContext('2d');
        state.charts.main = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Solar (W)',
                        data: [],
                        borderColor: series.solar.border,
                        backgroundColor: series.solar.bg,
                        fill: false,
                        hidden: state.preferences.visible.solar === false,
                    },
                    {
                        label: 'Wind (W)',
                        data: [],
                        borderColor: series.wind.border,
                        backgroundColor: series.wind.bg,
                        fill: false,
                        hidden: state.preferences.visible.wind === false,
                    },
                    {
                        label: 'Fuel Cell (W)',
                        data: [],
                        borderColor: series.fc.border,
                        backgroundColor: series.fc.bg,
                        fill: false,
                        hidden: state.preferences.visible.fc === false,
                    },
                ],
            },
            options: mainOpts,
        });

        // Initialize chart data storage
        ['solar', 'wind', 'fc', 'battery', 'ems'].forEach(key => {
            state.chartData[key] = { labels: [], data: [] };
        });
    }

    function applyChartTheme() {
        const chart = state.charts.main;
        if (!chart) return;

        const theme = getChartThemeOptions();
        const series = getSeriesColors();

        Chart.defaults.color = theme.text;
        chart.options.plugins.legend.labels.color = theme.text;
        chart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
        chart.options.plugins.tooltip.borderColor = theme.tooltipBorder;
        chart.options.plugins.tooltip.titleColor = theme.tooltipTitle;
        chart.options.plugins.tooltip.bodyColor = theme.tooltipBody;
        chart.options.scales.y.grid.color = theme.grid;
        chart.options.scales.x.title.color = theme.axisTitle;
        chart.options.scales.y.title.color = theme.axisTitle;

        chart.data.datasets[0].borderColor = series.solar.border;
        chart.data.datasets[0].backgroundColor = series.solar.bg;
        chart.data.datasets[1].borderColor = series.wind.border;
        chart.data.datasets[1].backgroundColor = series.wind.bg;
        chart.data.datasets[2].borderColor = series.fc.border;
        chart.data.datasets[2].backgroundColor = series.fc.bg;
        chart.update('none');
    }

    function appendChartData(key, label, value) {
        const cd = state.chartData[key];
        cd.labels.push(label);
        cd.data.push(value);

        // Trim to max points
        while (cd.labels.length > CONFIG.MAX_DATA_POINTS) {
            cd.labels.shift();
            cd.data.shift();
        }

        // Track update time
        state.lastUpdatedTimes[key] = Date.now();
        refreshCardTimestamp(key);
    }

    function renderMainAnalyticsChart() {
        const chart = state.charts.main;
        if (!chart) return;

        const labels = state.chartData.solar?.labels || [];
        chart.data.labels = [...labels];
        chart.data.datasets[0].data = [...(state.chartData.solar?.data || [])];
        chart.data.datasets[1].data = [...(state.chartData.wind?.data || [])];
        chart.data.datasets[2].data = [...(state.chartData.fc?.data || [])];

        chart.data.datasets[0].hidden = state.preferences.visible.solar === false;
        chart.data.datasets[1].hidden = state.preferences.visible.wind === false;
        chart.data.datasets[2].hidden = state.preferences.visible.fc === false;
        chart.update('none');
    }

    function applySyncedSession(payload) {
        if (!payload) return;

        state.isApplyingExternalSync = true;
        try {
            if (payload.location && payload.location.lat && payload.location.lng) {
                state.location = payload.location;
            }
            if (payload.preferences) {
                state.preferences = {
                    ...state.preferences,
                    ...payload.preferences,
                    modelParams: {
                        ...state.preferences.modelParams,
                        ...(payload.preferences.modelParams || {}),
                    },
                };
                applyTheme(state.preferences.theme);
            }
            if (typeof payload.batterySoC === 'number') {
                state.batterySoC = payload.batterySoC;
            }
            if (payload.chartData) {
                state.chartData = payload.chartData;
            }
            if (payload.latestResults) {
                state.latestResults = payload.latestResults;
            }
            if (payload.lastUpdatedTimes) {
                state.lastUpdatedTimes = payload.lastUpdatedTimes;
            }

            // Re-apply restored UI state without calling backend.
            restoreChartFromData();
            if (state.latestResults) {
                updateDisplayValues();
            }

            if (state.location && state.map) {
                const { lat, lng, name } = state.location;
                if (state.marker) {
                    state.marker.setLatLng([lat, lng]);
                } else {
                    state.marker = L.marker([lat, lng]).addTo(state.map);
                }
                document.getElementById('location-name').textContent = name;
                document.getElementById('location-coords').textContent = `${lat.toFixed(4)}°, ${lng.toFixed(4)}°`;
                updateLandmarkHeader(name, lat, lng);
            }

            // Re-apply graph visibility switches in synced tabs.
            document.querySelectorAll('[data-toggle]').forEach(toggle => {
                const key = toggle.dataset.toggle;
                const visible = state.preferences.visible[key] !== false;
                toggle.checked = visible;
                applyCardVisibility(key, visible);
            });
        } finally {
            state.isApplyingExternalSync = false;
        }
    }

    function restoreChartFromData() {
        renderMainAnalyticsChart();

        // Show dashboard if we have data
        if (state.chartData.solar && state.chartData.solar.data.length > 0) {
            document.getElementById('empty-state').style.display = 'none';
            document.getElementById('dashboard-grid').style.display = 'grid';
        }
    }

    /* ══════════════════════════════════════════════════════════
       MODULE 6 — Auto-Update Engine
       ════════════════════════════════════════════���═════════════ */
    function startAutoUpdate() {
        stopAutoUpdate();

        const intervalMs = state.preferences.intervalMinutes * 60 * 1000;
        state.nextUpdateTime = Date.now() + intervalMs;

        state.updateTimer = setInterval(async () => {
            // Skip if hidden (Page Visibility API)
            if (document.hidden) {
                state.nextUpdateTime = Date.now() + intervalMs;
                return;
            }
            await runFullPipeline();
            state.nextUpdateTime = Date.now() + intervalMs;
        }, intervalMs);

        // Countdown display
        state.countdownTimer = setInterval(() => {
            updateCountdown();
        }, 1000);
    }

    function stopAutoUpdate() {
        if (state.updateTimer) { clearInterval(state.updateTimer); state.updateTimer = null; }
        if (state.countdownTimer) { clearInterval(state.countdownTimer); state.countdownTimer = null; }
    }

    function updateCountdown() {
        const el = document.getElementById('update-timer');
        if (!state.nextUpdateTime) { el.textContent = 'Next update in --:--'; return; }

        const remaining = Math.max(0, state.nextUpdateTime - Date.now());
        const mins = Math.floor(remaining / 60000);
        const secs = Math.floor((remaining % 60000) / 1000);
        el.textContent = `Next update in ${mins}:${secs.toString().padStart(2, '0')}`;
    }

    /* ══════════════════════════════════════════════════════════
       MODULE 7 — Persistence Manager
       ══════════════════════════════════════════════════════════ */
    const PersistenceManager = {
        baseKeys: {
            location: 'nel_location',
            charts: 'nel_charts',
            preferences: 'nel_preferences',
            batterySoC: 'nel_battery_soc',
            session: 'nel_unified_session',
        },

        key(name) {
            const uid = state.authUser?.uid || auth.currentUser?.uid;
            if (!uid) return this.baseKeys[name];
            return `${this.baseKeys[name]}_${uid}`;
        },

        allKeys() {
            return Object.keys(this.baseKeys).map(name => this.key(name));
        },

        saveLocation() {
            if (state.location) {
                localStorage.setItem(this.key('location'), JSON.stringify(state.location));
            }
            this.saveUnifiedSession();
        },

        saveChartData() {
            const payload = {
                data: state.chartData,
                timestamp: Date.now(),
                results: state.latestResults,
                lastUpdatedTimes: state.lastUpdatedTimes,
            };
            localStorage.setItem(this.key('charts'), JSON.stringify(payload));
            this.saveUnifiedSession();
        },

        savePreferences() {
            localStorage.setItem(this.key('preferences'), JSON.stringify(state.preferences));
            this.saveUnifiedSession();
        },

        saveBatterySoC() {
            localStorage.setItem(this.key('batterySoC'), JSON.stringify(state.batterySoC));
            this.saveUnifiedSession();
        },

        saveUnifiedSession() {
            const payload = {
                location: state.location,
                chartData: state.chartData,
                latestResults: state.latestResults,
                preferences: state.preferences,
                batterySoC: state.batterySoC,
                lastUpdatedTimes: state.lastUpdatedTimes,
                timestamp: Date.now(),
            };
            localStorage.setItem(this.key('session'), JSON.stringify(payload));
        },

        loadAll() {
            // Prefer unified session to keep all landmark dashboard state together.
            try {
                const unified = JSON.parse(localStorage.getItem(this.key('session')));
                if (unified && typeof unified === 'object') {
                    applySyncedSession(unified);
                }
            } catch { /* ignore */ }

            // Location
            try {
                const loc = JSON.parse(localStorage.getItem(this.key('location')));
                if (loc && loc.lat && loc.lng) {
                    state.location = loc;
                }
            } catch { /* ignore */ }

            // Chart data
            try {
                const saved = JSON.parse(localStorage.getItem(this.key('charts')));
                if (saved && saved.data) {
                    state.chartData = saved.data;
                    state.latestResults = saved.results || null;
                    state.lastUpdatedTimes = saved.lastUpdatedTimes || state.lastUpdatedTimes;
                }
            } catch { /* ignore */ }

            // Preferences
            try {
                const prefs = JSON.parse(localStorage.getItem(this.key('preferences')));
                if (prefs) {
                    state.preferences = {
                        ...state.preferences,
                        ...prefs,
                        modelParams: {
                            ...state.preferences.modelParams,
                            ...(prefs.modelParams || {}),
                        },
                    };
                }
            } catch { /* ignore */ }

            // Battery SoC
            try {
                const soc = JSON.parse(localStorage.getItem(this.key('batterySoC')));
                if (typeof soc === 'number') {
                    state.batterySoC = soc;
                }
            } catch { /* ignore */ }
        },

        clearAll() {
            this.allKeys().forEach(k => localStorage.removeItem(k));
            state.location = null;
            state.batterySoC = CONFIG.DEFAULT_SOC;
            state.latestResults = null;
            state.latestWeather = null;
            ['solar', 'wind', 'fc', 'battery', 'ems'].forEach(key => {
                state.chartData[key] = { labels: [], data: [] };
            });
            renderMainAnalyticsChart();
            if (state.marker) { state.marker.remove(); state.marker = null; }
            stopAutoUpdate();

            document.getElementById('empty-state').style.display = '';
            document.getElementById('dashboard-grid').style.display = 'none';
            updateLandmarkHeader('Select a location on the map');
            document.getElementById('location-name').textContent = 'Click the map to select a location';
            document.getElementById('location-coords').textContent = '';
            document.getElementById('w-radiation').textContent = '—';
            document.getElementById('w-temperature').textContent = '—';
            document.getElementById('w-windspeed').textContent = '—';
            document.getElementById('update-timer').textContent = 'Next update in --:--';
            document.getElementById('val-solar').textContent = '0.00';
            document.getElementById('val-wind').textContent = '0.00';
            document.getElementById('val-fc').textContent = '0.00';
            document.getElementById('val-battery').textContent = '65.00';
            document.getElementById('val-ems').textContent = '0.00';

            // Reset battery animation
            const levelEl = document.getElementById('battery-level');
            if (levelEl) {
                levelEl.style.height = '65%';
                levelEl.style.background = 'linear-gradient(180deg, var(--battery) 0%, color-mix(in srgb, var(--battery) 80%, black) 100%)';
            }
            const socEl = document.getElementById('battery-soc-display');
            if (socEl) socEl.textContent = '65%';
            const statusEl = document.querySelector('.battery-status');
            if (statusEl) {
                statusEl.textContent = 'Idle';
                statusEl.style.color = 'var(--text-secondary)';
            }

            showToast('Session cleared', 'info');
        },
    };

    /* ══════════════════════════════════════════════════════════
       MODULE 8 — Settings Panel
       ══════════════════════════════════════════════════════════ */
    function initSettings() {
        const panel = document.getElementById('settings-panel');
        const backdrop = document.getElementById('settings-backdrop');
        const openBtn = document.getElementById('settings-btn');
        const closeBtn = document.getElementById('settings-close');

        function open() { panel.classList.add('open'); backdrop.classList.add('open'); }
        function close() { panel.classList.remove('open'); backdrop.classList.remove('open'); }

        openBtn.addEventListener('click', open);
        closeBtn.addEventListener('click', close);
        backdrop.addEventListener('click', close);

        // Graph visibility toggles
        document.querySelectorAll('[data-toggle]').forEach(toggle => {
            const key = toggle.dataset.toggle;

            // Restore saved preference
            toggle.checked = state.preferences.visible[key] !== false;
            applyCardVisibility(key, toggle.checked);

            toggle.addEventListener('change', () => {
                state.preferences.visible[key] = toggle.checked;
                applyCardVisibility(key, toggle.checked);
                PersistenceManager.savePreferences();
            });
        });

        // Update interval
        const intervalSelect = document.getElementById('update-interval');
        intervalSelect.value = String(state.preferences.intervalMinutes);
        intervalSelect.addEventListener('change', () => {
            state.preferences.intervalMinutes = parseInt(intervalSelect.value);
            PersistenceManager.savePreferences();
            if (state.location) startAutoUpdate(); // restart with new interval
            showToast(`Update interval set to ${intervalSelect.value} minutes`, 'info', 2500);
        });

        // Clear session
        document.getElementById('clear-session').addEventListener('click', () => {
            if (confirm('Clear all session data and reset the dashboard?')) {
                PersistenceManager.clearAll();
            }
        });
    }

    function applyCardVisibility(key, visible) {
        state.preferences.visible[key] = visible;
        renderMainAnalyticsChart();
    }

    /* ══════════════════════════════════════════════════════════
       MODULE 8 — Firebase Authentication
       ══════════════════════════════════════════════════════════ */
    function initFirebaseAuth() {
        console.log('🚀 Initializing Firebase Auth Module...');
        const authModal = document.getElementById('auth-modal');
        const appShell = document.getElementById('app-shell');
        const loginForm = document.getElementById('auth-form');
        const signupForm = document.getElementById('signup-form');
        const loginToggle = document.getElementById('auth-signup-toggle');
        const signupToggle = document.getElementById('signup-login-toggle');
        const resetPasswordLink = document.getElementById('auth-reset-password');
        const loginError = document.getElementById('auth-error');
        const signupError = document.getElementById('signup-error');
        const userEmailEl = document.getElementById('user-email');
        const logoutBtn = document.getElementById('logout-btn');

        function friendlyAuthError(error) {
            const code = error?.code || '';
            const messages = {
                'auth/email-already-in-use': 'An account already exists for this email.',
                'auth/invalid-email': 'Enter a valid email address.',
                'auth/invalid-credential': 'The email or password is incorrect.',
                'auth/missing-password': 'Enter your password.',
                'auth/network-request-failed': 'Network error. Check your connection and try again.',
                'auth/too-many-requests': 'Too many attempts. Please wait a moment and try again.',
                'auth/user-disabled': 'This account has been disabled.',
                'auth/user-not-found': 'No account exists for this email.',
                'auth/weak-password': 'Use a stronger password.',
                'auth/wrong-password': 'The email or password is incorrect.',
            };
            return messages[code] || 'Authentication failed. Please try again.';
        }

        console.log('✓ Auth DOM elements loaded:', {
            authModal: !!authModal,
            appShell: !!appShell,
            loginForm: !!loginForm,
            signupForm: !!signupForm,
            loginToggle: !!loginToggle,
            signupToggle: !!signupToggle
        });

        // Show/hide modal
        function showModal(show, signup) {
            if (show) {
                authModal.classList.remove('hidden');
                authModal.style.pointerEvents = 'auto';
            } else {
                authModal.classList.add('hidden');
                authModal.style.pointerEvents = 'none';
            }
            appShell.style.display = show ? 'none' : 'flex';
            loginForm.style.display = signup ? 'none' : 'flex';
            signupForm.style.display = signup ? 'flex' : 'none';
            loginError.textContent = '';
            signupError.textContent = '';
        }

        // Update UI based on auth state
        function updateAuthUI(user) {
            if (user) {
                // User is signed in
                state.authUser = user;
                userEmailEl.textContent = user.email;
                logoutBtn.style.display = 'flex';
                showModal(false, false);
                initializeAuthenticatedApp();
            } else {
                // User is signed out
                state.authUser = null;
                userEmailEl.textContent = '';
                logoutBtn.style.display = 'none';
                showModal(true, false);
            }
        }

        // Listen to auth state changes
        onAuthStateChanged(auth, (user) => {
            updateAuthUI(user);
        });

        // Login handler
        loginForm.onsubmit = async function(e) {
            e.preventDefault();
            const email = document.getElementById('auth-email').value.trim();
            const password = document.getElementById('auth-password').value;

            // Clear previous errors
            loginError.textContent = '';

            if (!email || !password) {
                loginError.textContent = 'Please fill in all fields';
                console.warn('Login: Empty email or password');
                return;
            }

            try {
                console.log('Attempting login with:', email);
                await signInWithEmailAndPassword(auth, email, password);
                console.log('Login successful');
                showToast('Signed in successfully', 'success');
                loginForm.reset();
            } catch (error) {
                console.error('Login error:', error);
                loginError.textContent = friendlyAuthError(error);
                loginError.style.display = 'block';
            }
        };

        // Signup handler
        signupForm.onsubmit = async function(e) {
            e.preventDefault();
            const email = document.getElementById('signup-email').value.trim();
            const password = document.getElementById('signup-password').value;
            const confirmPassword = document.getElementById('signup-confirm').value;

            // Clear previous errors
            signupError.textContent = '';

            if (!email || !password || !confirmPassword) {
                signupError.textContent = 'Please fill in all fields';
                console.warn('Signup: Empty fields');
                return;
            }

            // Validation
            if (password !== confirmPassword) {
                signupError.textContent = 'Passwords do not match.';
                signupError.style.display = 'block';
                console.warn('Signup: Passwords do not match');
                return;
            }

            if (password.length < 6) {
                signupError.textContent = 'Password must be at least 6 characters.';
                signupError.style.display = 'block';
                console.warn('Signup: Password too short');
                return;
            }

            try {
                console.log('Attempting signup with:', email);
                const credential = await createUserWithEmailAndPassword(auth, email, password);
                await sendEmailVerification(credential.user);
                console.log('Signup successful');
                showToast('Account created. Verification email sent.', 'success', 4000);
                signupForm.reset();
            } catch (error) {
                console.error('Signup error:', error);
                signupError.textContent = friendlyAuthError(error);
                signupError.style.display = 'block';
            }
        };

        resetPasswordLink.addEventListener('click', async function(e) {
            e.preventDefault();
            const email = document.getElementById('auth-email').value.trim();
            loginError.textContent = '';
            if (!email) {
                loginError.textContent = 'Enter your email, then request a password reset.';
                loginError.style.display = 'block';
                return;
            }

            try {
                await sendPasswordResetEmail(auth, email);
                showToast('Password reset email sent', 'success', 3500);
            } catch (error) {
                console.error('Password reset error:', error);
                loginError.textContent = friendlyAuthError(error);
                loginError.style.display = 'block';
            }
        });

        // Toggle between login/signup
        loginToggle.addEventListener('click', function(e) {
            console.log('🔄 Login toggle clicked!');
            e.preventDefault();
            e.stopPropagation();
            console.log('🔄 Switching to signup form...');
            showModal(true, true);
            console.log('🔄 Form switch complete');
        });
        signupToggle.addEventListener('click', function(e) {
            console.log('🔄 Signup toggle clicked!');
            e.preventDefault();
            e.stopPropagation();
            console.log('🔄 Switching to login form...');
            showModal(true, false);
            console.log('🔄 Form switch complete');
        });

        // Logout handler
        logoutBtn.addEventListener('click', async () => {
            try {
                await signOut(auth);
                showToast('Signed out successfully', 'info');
                window.location.reload();
            } catch (error) {
                showToast(friendlyAuthError(error), 'error');
            }
        });

        // Password visibility toggles
        document.getElementById('auth-password-toggle').addEventListener('click', function() {
            const input = document.getElementById('auth-password');
            const icon = this.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'fa-solid fa-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'fa-solid fa-eye';
            }
        });

        document.getElementById('signup-password-toggle').addEventListener('click', function() {
            const input = document.getElementById('signup-password');
            const icon = this.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'fa-solid fa-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'fa-solid fa-eye';
            }
        });

        document.getElementById('signup-confirm-toggle').addEventListener('click', function() {
            const input = document.getElementById('signup-confirm');
            const icon = this.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'fa-solid fa-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'fa-solid fa-eye';
            }
        });

        console.log('✅ Firebase Auth Module initialized successfully');
    }

    // Debug function for testing
    window.testAuthToggle = function() {
        console.log('🧪 Testing auth toggle...');
        const loginToggle = document.getElementById('auth-signup-toggle');
        const signupToggle = document.getElementById('signup-login-toggle');

        console.log('Login toggle element:', loginToggle);
        console.log('Signup toggle element:', signupToggle);

        if (loginToggle) {
            console.log('Clicking login toggle...');
            loginToggle.click();
        } else {
            console.error('Login toggle not found!');
        }
    };

    /* ══════════════════════════════════════════════════════════
       MODULE 9 — App Initialization
       ══════════════════════════════════════════════════════════ */
    async function initializeAuthenticatedApp() {
        if (state.appInitialized) return;
        state.appInitialized = true;

        // Load persisted state
        const hadSavedData = !!localStorage.getItem(PersistenceManager.key('charts'));
        PersistenceManager.loadAll();

        // Initialize UI modules
        initMap();
        initMapVisibility();
        initCharts();
        initModelInspector();
        initTheme();
        initSettings();

        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', async () => {
            if (!state.location) { showToast('Select a location first', 'info', 2500); return; }
            const btn = document.getElementById('refresh-btn');
            btn.classList.add('spinning');
            await runFullPipeline();
            btn.classList.remove('spinning');
            if (state.location) startAutoUpdate(); // restart countdown
        });

        // Tick card timestamps every 30 s
        setInterval(refreshAllCardTimestamps, 30000);

        // Cross-tab synchronization: keep landmark dashboard state identical in all tabs.
        window.addEventListener('storage', (event) => {
            if (event.key !== PersistenceManager.key('session') || !event.newValue) return;
            if (state.isApplyingExternalSync) return;
            try {
                const payload = JSON.parse(event.newValue);
                applySyncedSession(payload);
                showToast('Dashboard synchronized from another tab', 'info', 2200);
            } catch {
                // Ignore malformed data.
            }
        });

        // Restore chart data from localStorage
        restoreChartFromData();

        // Restore display values
        if (state.latestResults) {
            updateDisplayValues();
            if (hadSavedData) {
                showToast('Previous session restored', 'info', 3000);
            }
        }

        // If we had a saved location, restore it
        if (state.location) {
            const { lat, lng, name } = state.location;

            // Place marker
            state.marker = L.marker([lat, lng]).addTo(state.map);
            state.map.setView([lat, lng], CONFIG.SELECTED_ZOOM);

            // Update location UI (map badge + landmark panel header)
            document.getElementById('location-name').textContent = name;
            document.getElementById('location-coords').textContent = `${lat.toFixed(4)}°, ${lng.toFixed(4)}°`;
            updateLandmarkHeader(name, lat, lng);

            // Show dashboard if data exists
            if (state.chartData.solar && state.chartData.solar.data.length > 0) {
                document.getElementById('empty-state').style.display = 'none';
                document.getElementById('dashboard-grid').style.display = 'grid';
            }

            // Fetch fresh data and start updates
            await runFullPipeline();
            startAutoUpdate();
        }

        // Check API health
        try {
            // Quick test — just check if Flask is responding
            const res = await fetch('/');
            updateApiStatus(res.ok);
        } catch {
            updateApiStatus(false);
        }
    }

    function init() {
        initFirebaseAuth();
    }

    // Boot
    document.addEventListener('DOMContentLoaded', init);

    function updateBatteryAnimation() {
        if (!state.latestResults) return;

        const soc = state.batterySoC; // Use hardcoded SOC for animation
        const netPower = state.latestResults.netPower || 0;

        // Update battery level
        const levelEl = document.getElementById('battery-level');
        if (levelEl) {
            levelEl.style.width = `${soc}%`;
            // Color based on SOC: green to red
            const red = Math.round(239 - (239 - 16) * (soc / 100));
            const green = Math.round(44 + (185 - 44) * (soc / 100));
            const blue = Math.round(44 + (129 - 44) * (soc / 100));
            levelEl.style.background = `linear-gradient(90deg, rgb(${red}, ${green}, ${blue}) 0%, color-mix(in srgb, rgb(${red}, ${green}, ${blue}) 80%, black) 100%)`;
        }

        // Update SOC display
        const socEl = document.getElementById('battery-soc-display');
        if (socEl) {
            socEl.textContent = `${Math.round(soc)}%`;
        }

        // Update status
        const statusEl = document.querySelector('.battery-status');
        if (statusEl) {
            if (netPower > 0) {
                statusEl.textContent = 'Charging';
                statusEl.style.color = 'var(--success)';
            } else if (netPower < 0) {
                statusEl.textContent = 'Discharging';
                statusEl.style.color = 'var(--warning)';
            } else {
                statusEl.textContent = 'Idle';
                statusEl.style.color = 'var(--text-secondary)';
            }
        }
    }

    function startBatteryDischarge() {
        if (state.dischargeInterval) clearInterval(state.dischargeInterval);
        state.batterySoC = 100;
        state.dischargeInterval = setInterval(() => {
            state.batterySoC = Math.max(0, state.batterySoC - 0.1667);
            updateBatteryAnimation();
            PersistenceManager.saveBatterySoC();
        }, 1000);
    }

