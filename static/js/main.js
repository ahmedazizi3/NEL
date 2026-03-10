// Chart Instances
const charts = {};

// Chart Configurations
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', sans-serif";

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false }
    },
    scales: {
        x: { display: false },
        y: { 
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            beginAtZero: true
        }
    },
    animation: {
        duration: 800,
        easing: 'easeOutQuart'
    }
};

// Initialize Charts
function initCharts() {
    const defaultData = (color, label) => ({
        labels: ['Run 1', 'Run 2', 'Run 3', 'Run 4', 'Run 5'],
        datasets: [{
            label: label,
            data: [0, 0, 0, 0, 0],
            borderColor: color,
            backgroundColor: color.replace('1)', '0.1)'),
            borderWidth: 2,
            tension: 0.4,
            fill: true,
            pointBackgroundColor: color,
            pointBorderColor: '#0f172a',
            pointRadius: 4
        }]
    });

    const createChart = (id, color, label) => {
        const ctx = document.getElementById(id).getContext('2d');
        return new Chart(ctx, {
            type: 'line',
            data: defaultData(color, label),
            options: commonOptions
        });
    };

    charts['solar'] = createChart('solar-chart', 'rgba(245, 158, 11, 1)', 'Power (W)');
    charts['wind'] = createChart('wind-chart', 'rgba(56, 189, 248, 1)', 'Power (W)');
    charts['fc'] = createChart('fc-chart', 'rgba(168, 85, 247, 1)', 'Power (W)');
    charts['battery'] = createChart('battery-chart', 'rgba(16, 185, 129, 1)', 'SoC (%)');
    
    // EMS uses bar chart
    const emsCtx = document.getElementById('ems-chart').getContext('2d');
    charts['ems'] = new Chart(emsCtx, {
        type: 'bar',
        data: {
            labels: ['Run 1', 'Run 2', 'Run 3', 'Run 4', 'Run 5'],
            datasets: [{
                label: 'Grid Power (W)',
                data: [0,0,0,0,0],
                backgroundColor: 'rgba(239, 68, 68, 0.7)',
                borderRadius: 4
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                x: { display: false },
                y: { grid: { color: 'rgba(255,255,255,0.05)'} }
            }
        }
    });
}

// Update Chart Data Helper
function updateChartData(chartId, newValue) {
    const chart = charts[chartId];
    if(chart.data.datasets[0].data.length >= 5) {
        chart.data.datasets[0].data.shift();
    }
    chart.data.datasets[0].data.push(newValue);
    chart.update();
}

// API Call Wrapper
async function fetchPrediction(endpoint, data) {
    try {
        const response = await fetch(`/api/predict/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if(!response.ok) throw new Error('API Error');
        return await response.json();
    } catch (err) {
        console.error(err);
        return null;
    }
}

// Form Submit Handlers
document.addEventListener('DOMContentLoaded', () => {
    initCharts();

    // 1. Solar Form
    document.getElementById('solar-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        const origText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        
        const data = {
            irradiance: document.getElementById('solar-irradiance').value,
            temperature: document.getElementById('solar-temp').value,
            angle: document.getElementById('solar-angle').value
        };
        const res = await fetchPrediction('solar', data);
        if(res && res.power !== undefined) {
            document.getElementById('solar-result').innerText = res.power.toFixed(2);
            updateChartData('solar', res.power);
        }
        btn.innerHTML = origText;
    });

    // 2. Wind Form
    document.getElementById('wind-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        
        const data = { wind_speed: document.getElementById('wind-speed').value };
        const res = await fetchPrediction('wind', data);
        if(res && res.power !== undefined) {
            document.getElementById('wind-result').innerText = res.power.toFixed(2);
            updateChartData('wind', res.power);
        }
        btn.innerHTML = 'Predict Power';
    });

    // 3. Fuel Cell Form
    document.getElementById('fc-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        
        const data = { h2_flow: document.getElementById('fc-flow').value };
        const res = await fetchPrediction('fc', data);
        if(res && res.power !== undefined) {
            document.getElementById('fc-result').innerText = res.power.toFixed(2);
            updateChartData('fc', res.power);
        }
        btn.innerHTML = 'Predict Power';
    });

    // 4. Battery Form
    document.getElementById('battery-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        
        const data = { 
            initial_soc: document.getElementById('bat-soc').value,
            power_input: document.getElementById('bat-power').value,
            time_min: document.getElementById('bat-time').value
        };
        const res = await fetchPrediction('battery', data);
        if(res && res.final_soc !== undefined) {
            document.getElementById('bat-result').innerText = res.final_soc.toFixed(2);
            updateChartData('battery', res.final_soc);
        }
        btn.innerHTML = 'Predict SoC';
    });

    // 5. EMS Form
    document.getElementById('ems-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button');
        const origText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Loading...';
        
        const data = { 
            solar_p: document.getElementById('ems-solar').value,
            wind_p: document.getElementById('ems-wind').value,
            load_p: document.getElementById('ems-load').value
        };
        const res = await fetchPrediction('ems', data);
        if(res && res.grid_power !== undefined) {
            document.getElementById('ems-result').innerText = res.grid_power.toFixed(2);
            updateChartData('ems', res.grid_power);
            
            // Dynamic color for EMS based on power direction
            const resEl = document.getElementById('ems-result');
            if (res.grid_power > 0) {
                resEl.className = 'text-warning'; // Grid Draw
                charts['ems'].data.datasets[0].backgroundColor = 'rgba(239, 68, 68, 0.7)';
            } else {
                resEl.className = 'text-accent'; // Grid Feed
                charts['ems'].data.datasets[0].backgroundColor = 'rgba(16, 185, 129, 0.7)';
            }
            charts['ems'].update();
        }
        btn.innerHTML = origText;
    });

    // Simulate All Button Functionality
    document.getElementById('simulate-all-btn').addEventListener('click', () => {
        document.getElementById('solar-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        document.getElementById('wind-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        document.getElementById('fc-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        document.getElementById('battery-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        document.getElementById('ems-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    });
});
