let simulationData = [];
let currentVisualization = 'tank_levels';
let updateInterval = null;
let missionStartTime = null;
let isSimulationRunning = false;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    startDataPolling();
    initializeStatusCards();
    setupPlotlyTheme();
    addTitleEffects();
});

function setupEventListeners() {
    document.getElementById('run-simulation').addEventListener('click', runSimulation);
    document.getElementById('pause-simulation').addEventListener('click', pauseSimulation);
    document.getElementById('visualization-select').addEventListener('change', function(e) {
        currentVisualization = e.target.value;
        updateVisualization();
        addGlitchEffect();
    });
    
    // Add new event listeners for additional features
    document.getElementById('fullscreen-viz')?.addEventListener('click', toggleFullscreen);
    document.getElementById('export-data')?.addEventListener('click', exportData);
}

function initializeStatusCards() {
    updateStatusCard('power-status', '0', 'kW', 'var(--terminal-green)');
    updateStatusCard('fuel-status', '0', 'kg', 'var(--mars-orange)');
    updateStatusCard('oxygen-status', '0', 'kg', 'var(--info-blue)');
    updateStatusCard('system-status', 'STANDBY', '', 'var(--warning-yellow)');
}

function updateStatusCard(id, value, unit, color) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = `${value} ${unit}`.trim();
        element.style.color = color;
        
        // Add pulse animation for updates
        element.classList.add('status-update');
        setTimeout(() => element.classList.remove('status-update'), 500);
    }
}

function setupPlotlyTheme() {
    // Custom Mars-themed Plotly template
    window.marsTheme = {
        layout: {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0.2)',
            font: {
                family: 'Inter, sans-serif',
                color: '#ffffff',
                size: 12
            },
            colorway: ['#FF4500', '#CD5C5C', '#00ff41', '#74c0fc', '#ffd700', '#ff6b6b', '#51cf66'],
            title: {
                font: { size: 18, color: '#FF4500' },
                x: 0.5,
                xanchor: 'center'
            },
            xaxis: {
                gridcolor: 'rgba(255, 69, 0, 0.2)',
                linecolor: 'rgba(255, 69, 0, 0.4)',
                tickcolor: 'rgba(255, 69, 0, 0.4)',
                zerolinecolor: 'rgba(255, 69, 0, 0.3)'
            },
            yaxis: {
                gridcolor: 'rgba(255, 69, 0, 0.2)',
                linecolor: 'rgba(255, 69, 0, 0.4)',
                tickcolor: 'rgba(255, 69, 0, 0.4)',
                zerolinecolor: 'rgba(255, 69, 0, 0.3)'
            },
            legend: {
                bgcolor: 'rgba(0,0,0,0.3)',
                bordercolor: 'rgba(255, 69, 0, 0.3)',
                borderwidth: 1
            }
        },
        config: {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
            modeBarButtonsToAdd: ['drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape'],
            displaylogo: false
        }
    };
}

function addTitleEffects() {
    const title = document.querySelector('.dashboard-title');
    if (title) {
        // Random glitch effect
        setInterval(() => {
            if (Math.random() < 0.05) { // 5% chance every interval
                title.classList.add('glitch');
                setTimeout(() => title.classList.remove('glitch'), 300);
            }
        }, 2000);
    }
}

function addGlitchEffect() {
    const vizTitle = document.querySelector('.viz-title');
    if (vizTitle) {
        vizTitle.classList.add('glitch');
        setTimeout(() => vizTitle.classList.remove('glitch'), 300);
    }
}

async function runSimulation() {
    const speed = parseFloat(document.getElementById('sim-speed').value);
    const duration = parseFloat(document.getElementById('sim-duration').value);
    
    try {
        const response = await fetch('/api/run_simulation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                speed: speed,
                duration: duration
            })
        });
        
        const result = await response.json();
        if (result.error) {
            updateLogs(`ERROR: ${result.error}`, 'error');
            showAlert(result.error, 'error');
        } else {
            missionStartTime = Date.now();
            isSimulationRunning = true;
            updateLogs('Mission initialized. All systems go for launch.', 'success');
            updateLogs(`Mission duration: ${duration} Mars years at ${speed}x speed`, 'info');
            updateStatusCard('system-status', 'ACTIVE', '', 'var(--success-green)');
            
            document.getElementById('run-simulation').disabled = true;
            document.getElementById('pause-simulation').disabled = false;
            
            // Add launch sequence effect
            launchSequence();
        }
    } catch (error) {
        updateLogs(`Connection error: ${error.message}`, 'error');
        showAlert('Failed to connect to mission control', 'error');
    }
}

async function pauseSimulation() {
    try {
        const response = await fetch('/api/pause_simulation', {
            method: 'POST'
        });
        
        const result = await response.json();
        isSimulationRunning = false;
        updateLogs('Mission aborted by flight director', 'warning');
        updateStatusCard('system-status', 'STANDBY', '', 'var(--warning-yellow)');
        
        document.getElementById('run-simulation').disabled = false;
        document.getElementById('pause-simulation').disabled = true;
    } catch (error) {
        updateLogs(`Error aborting mission: ${error.message}`, 'error');
    }
}

function launchSequence() {
    const messages = [
        'T-5: Final systems check initiated',
        'T-4: Power systems nominal', 
        'T-3: Atmosphere processors online',
        'T-2: Sabatier reactor warming up',
        'T-1: Electrolysis system ready',
        'T-0: MISSION START - All systems operational'
    ];
    
    messages.forEach((message, index) => {
        setTimeout(() => {
            updateLogs(message, index === messages.length - 1 ? 'success' : 'info');
        }, index * 1000);
    });
}

function startDataPolling() {
    updateInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/simulation_data');
            const result = await response.json();
            
            simulationData = result.data;
            
            if (result.running !== isSimulationRunning) {
                isSimulationRunning = result.running;
                if (!result.running && document.getElementById('run-simulation').disabled) {
                    updateLogs('Mission completed successfully', 'success');
                    updateStatusCard('system-status', 'COMPLETE', '', 'var(--success-green)');
                    document.getElementById('run-simulation').disabled = false;
                    document.getElementById('pause-simulation').disabled = true;
                }
            }
            
            updateStatusCards();
            updateMissionTime();
            updateVisualization();
            
        } catch (error) {
            console.error('Telemetry link lost:', error);
            updateLogs('WARNING: Telemetry link unstable', 'warning');
        }
    }, 1000);
}

function updateStatusCards() {
    if (simulationData.length === 0) return;
    
    const latest = simulationData[simulationData.length - 1];
    
    updateStatusCard('power-status', latest.power_available?.toFixed(1) || '0', 'kW', 
        latest.power_available > 10 ? 'var(--success-green)' : 'var(--error-red)');
    
    updateStatusCard('fuel-status', latest.ch4_stored?.toFixed(1) || '0', 'kg', 'var(--mars-orange)');
    updateStatusCard('oxygen-status', latest.o2_stored?.toFixed(1) || '0', 'kg', 'var(--info-blue)');
    
    // Update system status based on conditions
    if (isSimulationRunning) {
        if (latest.power_available < 5) {
            updateStatusCard('system-status', 'BROWNOUT', '', 'var(--error-red)');
        } else if (latest.power_available < 10) {
            updateStatusCard('system-status', 'CAUTION', '', 'var(--warning-yellow)');
        } else {
            updateStatusCard('system-status', 'NOMINAL', '', 'var(--success-green)');
        }
    }
}

function updateMissionTime() {
    if (!missionStartTime) return;
    
    const elapsed = Date.now() - missionStartTime;
    const hours = Math.floor(elapsed / 3600000);
    const minutes = Math.floor((elapsed % 3600000) / 60000);
    const seconds = Math.floor((elapsed % 60000) / 1000);
    
    const timeString = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    updateStatusCard('mission-time', timeString, '', 'var(--terminal-green)');
}

function updateVisualization() {
    if (simulationData.length === 0) {
        // Show empty state with loading animation
        Plotly.newPlot('visualization', 
            [{x: [], y: [], type: 'scatter', name: 'Awaiting Data...'}], 
            {
                ...window.marsTheme.layout,
                title: 'Telemetry Feed - Waiting for Mission Data',
                annotations: [{
                    text: 'Initializing data stream...',
                    x: 0.5,
                    y: 0.5,
                    xref: 'paper',
                    yref: 'paper',
                    showarrow: false,
                    font: { size: 16, color: '#888888' }
                }]
            }, 
            window.marsTheme.config
        );
        return;
    }
    
    const times = simulationData.map(d => new Date(d.time * 1000));
    let plotData = [];
    let layout = {
        ...window.marsTheme.layout,
        title: 'Mission Telemetry',
        xaxis: { 
            ...window.marsTheme.layout.xaxis,
            title: 'Mission Time' 
        },
        yaxis: { 
            ...window.marsTheme.layout.yaxis,
            title: 'Value' 
        }
    };
    
    switch (currentVisualization) {
        case 'tank_levels':
            plotData = [
                {
                    x: times,
                    y: simulationData.map(d => d.ch4_stored),
                    name: 'CH₄ Fuel',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 3, color: '#FF4500' },
                    fill: 'tonexty'
                },
                {
                    x: times,
                    y: simulationData.map(d => d.o2_stored),
                    name: 'O₂ Oxidizer',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 3, color: '#74c0fc' },
                    fill: 'tonexty'
                },
                {
                    x: times,
                    y: simulationData.map(d => d.h2_stored),
                    name: 'H₂ Storage',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 2, color: '#00ff41' }
                },
                {
                    x: times,
                    y: simulationData.map(d => d.h2o_stored),
                    name: 'H₂O Reserves',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 2, color: '#51cf66' }
                }
            ];
            layout.title = 'Propellant Storage Levels';
            layout.yaxis.title = 'Mass (kg)';
            break;
            
        case 'power_demand':
            plotData = [
                {
                    x: times,
                    y: simulationData.map(d => d.power_available),
                    name: 'Available Power',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 3, color: '#00ff41' },
                    fill: 'tonexty'
                },
                {
                    x: times,
                    y: simulationData.map(d => d.power_allocated),
                    name: 'Power Demand',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 3, color: '#ff6b6b' }
                }
            ];
            layout.title = 'Power System Analysis';
            layout.yaxis.title = 'Power (kW)';
            break;
            
        case 'battery_level':
            plotData = [
                {
                    x: times,
                    y: simulationData.map(d => d.battery_level),
                    name: 'Battery Charge',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 4, color: '#ffd700' },
                    fill: 'tozeroy',
                    fillcolor: 'rgba(255, 215, 0, 0.1)'
                }
            ];
            layout.title = 'Energy Storage Status';
            layout.yaxis.title = 'Energy (kWh)';
            break;
            
        case 'environmental_conditions':
            plotData = [
                {
                    x: times,
                    y: simulationData.map(d => d.solar_irradiance),
                    name: 'Solar Irradiance',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 3, color: '#ffd700' },
                    yaxis: 'y'
                },
                {
                    x: times,
                    y: simulationData.map(d => d.temperature),
                    name: 'Temperature',
                    type: 'scatter',
                    mode: 'lines',
                    line: { width: 3, color: '#74c0fc' },
                    yaxis: 'y2'
                }
            ];
            layout.title = 'Mars Environmental Monitoring';
            layout.yaxis = { 
                ...window.marsTheme.layout.yaxis,
                title: 'Solar Irradiance (W/m²)', 
                side: 'left' 
            };
            layout.yaxis2 = { 
                ...window.marsTheme.layout.yaxis,
                title: 'Temperature (K)', 
                side: 'right', 
                overlaying: 'y' 
            };
            break;
            
        case 'production_metrics':
            const productionRates = calculateProductionRates();
            plotData = [
                {
                    x: times.slice(1),
                    y: productionRates.ch4,
                    name: 'CH₄ Production Rate',
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: { width: 3, color: '#FF4500' },
                    marker: { size: 4 }
                },
                {
                    x: times.slice(1),
                    y: productionRates.o2,
                    name: 'O₂ Production Rate',
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: { width: 3, color: '#74c0fc' },
                    marker: { size: 4 }
                }
            ];
            layout.title = 'Production Rate Metrics';
            layout.yaxis.title = 'Production Rate (kg/h)';
            break;
            
        default:
            plotData = [{ x: [], y: [], type: 'scatter' }];
    }
    
    Plotly.newPlot('visualization', plotData, layout, window.marsTheme.config);
}

function calculateProductionRates() {
    const rates = { ch4: [], o2: [], h2: [] };
    
    for (let i = 1; i < simulationData.length; i++) {
        const dt = (simulationData[i].time - simulationData[i-1].time) / 3600; // hours
        
        rates.ch4.push(Math.max(0, (simulationData[i].ch4_stored - simulationData[i-1].ch4_stored) / dt));
        rates.o2.push(Math.max(0, (simulationData[i].o2_stored - simulationData[i-1].o2_stored) / dt));
        rates.h2.push(Math.max(0, (simulationData[i].h2_stored - simulationData[i-1].h2_stored) / dt));
    }
    
    return rates;
}

function updateLogs(message, type = 'info') {
    const logsContainer = document.getElementById('logs-container');
    const timestamp = new Date().toLocaleTimeString();
    
    let prefix = '';
    switch (type) {
        case 'error': prefix = '[ERROR]'; break;
        case 'warning': prefix = '[WARN]'; break;
        case 'success': prefix = '[OK]'; break;
        case 'info': default: prefix = '[INFO]'; break;
    }
    
    logsContainer.textContent += `${timestamp} ${prefix} ${message}\n`;
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

function showAlert(message, type) {
    // Create custom alert overlay
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <div class="alert-content">
            <strong>${type.toUpperCase()}</strong>
            <p>${message}</p>
            <button onclick="this.parentElement.parentElement.remove()">ACKNOWLEDGE</button>
        </div>
    `;
    alert.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 1000;
        background: rgba(0,0,0,0.9); border: 2px solid var(--error-red);
        border-radius: 8px; padding: 1rem; color: white; max-width: 300px;
    `;
    
    document.body.appendChild(alert);
    setTimeout(() => alert.remove(), 5000);
}

function toggleFullscreen() {
    const viz = document.getElementById('visualization');
    if (viz.requestFullscreen) {
        viz.requestFullscreen();
    }
}

function exportData() {
    if (simulationData.length === 0) {
        showAlert('No data to export', 'warning');
        return;
    }
    
    const csv = [
        'timestamp,power_available,power_allocated,ch4_stored,o2_stored,h2_stored,h2o_stored,solar_irradiance,temperature',
        ...simulationData.map(d => 
            `${d.time},${d.power_available},${d.power_allocated},${d.ch4_stored},${d.o2_stored},${d.h2_stored},${d.h2o_stored},${d.solar_irradiance},${d.temperature}`
        )
    ].join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mars_isru_data_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    
    updateLogs('Mission data exported successfully', 'success');
}

// Add CSS for status update animation
const style = document.createElement('style');
style.textContent = `
    .status-update {
        animation: statusPulse 0.5s ease-in-out;
    }
    
    @keyframes statusPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.1); filter: brightness(1.3); }
    }
    
    .alert {
        animation: slideIn 0.3s ease-out;
    }
    
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;
document.head.appendChild(style); 