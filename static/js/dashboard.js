let simulationData = [];
let currentVisualization = 'tank_levels';
let updateInterval = null;
let missionStartTime = null;
let isSimulationRunning = false;
let lastReportedSol = -1;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    startDataPolling();
    initializeStatusCards();
    setupPlotlyTheme();
    addTitleEffects();
});

function setupEventListeners() {
    const runButton = document.getElementById('run-simulation');
    const stopButton = document.getElementById('stop-simulation');
    const resetButton = document.getElementById('reset-simulation');
    
    if (runButton) {
        runButton.addEventListener('click', runSimulation);
        console.log('Launch Mission button event listener attached');
    } else {
        console.error('Launch Mission button not found!');
    }
    
    if (stopButton) {
        stopButton.addEventListener('click', function(event) {
            console.log('Stop button clicked!', event);
            stopSimulation();
        });
        console.log('Stop Mission button event listener attached');
    } else {
        console.error('Stop Mission button not found!');
    }
    
    if (resetButton) {
        resetButton.addEventListener('click', function(event) {
            console.log('Reset button clicked!', event);
            resetSimulation();
        });
        console.log('Reset System button event listener attached');
    } else {
        console.error('Reset System button not found!');
    }
    
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
    
    // Enhanced initial logs with sol-based reporting mention
    updateLogs('🌌 Mars ISRU Control System v2.1.0 - Initialized', 'success');
    updateLogs('🔧 Subsystem diagnostics complete', 'info');
    updateLogs('⚡ Power management system online', 'info');
    updateLogs('🏭 Production modules ready for configuration', 'info');
    updateLogs('📅 Sol-based reporting system ready', 'info');
    updateLogs('🎯 Awaiting mission parameters and launch authorization...', 'info');
    updateLogs('📊 Configure system parameters and press Launch Mission', 'info');
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
    
    // Reset sol tracking for new simulation
    lastReportedSol = -1;
    
    // Collect system configuration parameters
    const config = {
        speed: speed,
        duration: duration,
        solar_array_area: parseFloat(document.getElementById('solar-array-area').value),
        battery_capacity: parseFloat(document.getElementById('battery-capacity').value),
        co2_intake_rate: parseFloat(document.getElementById('co2-intake-rate').value),
        h2_production_rate: parseFloat(document.getElementById('h2-production-rate').value),
        ch4_production_rate: parseFloat(document.getElementById('ch4-production-rate').value),
        ignore_temp_overage: document.getElementById('ignore-temp-overage').checked
    };
    
    try {
        const response = await fetch('/api/run_simulation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
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
            updateLogs(`Configuration: Solar=${config.solar_array_area}m², Battery=${config.battery_capacity}kWh`, 'info');
            updateLogs(`Production rates: CO₂=${config.co2_intake_rate}, H₂=${config.h2_production_rate}, CH₄=${config.ch4_production_rate} kg/hr`, 'info');
            updateStatusCard('system-status', 'ACTIVE', '', 'var(--success-green)');
            
            document.getElementById('run-simulation').disabled = true;
            document.getElementById('stop-simulation').disabled = false;
            
            // Add launch sequence effect
            launchSequence();
        }
    } catch (error) {
        updateLogs(`Connection error: ${error.message}`, 'error');
        showAlert('Failed to connect to mission control', 'error');
    }
}

async function stopSimulation() {
    console.log('Stop button clicked - attempting to stop simulation');
    
    try {
        console.log('Sending POST request to /api/pause_simulation');
        const response = await fetch('/api/pause_simulation', {
            method: 'POST'
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('Stop response:', result);
        
        isSimulationRunning = false;
        updateLogs('🛑 Mission stopped by flight director', 'warning');
        updateLogs('📊 Preserving collected telemetry data for analysis', 'info');
        updateStatusCard('system-status', 'STOPPED', '', 'var(--warning-yellow)');
        
        document.getElementById('run-simulation').disabled = false;
        document.getElementById('stop-simulation').disabled = true;
        
        console.log('Button states updated after stop');
        
        // Log comprehensive stop summary if we have data
        if (simulationData.length > 0) {
            const finalData = simulationData[simulationData.length - 1];
            const totalSols = Math.floor((finalData.time || 0) / 88775);
            
            updateLogs(``, 'info');
            updateLogs(`📈 ============= MISSION STOP SUMMARY =============`, 'warning');
            updateLogs(`📅 Mission Duration: ${totalSols + 1} Sols (${formatMissionTime(finalData.time)})`, 'warning');
            updateLogs(`🏭 Production at Stop:`, 'warning');
            updateLogs(`   CH₄ Fuel: ${finalData.ch4_stored?.toFixed(1)} kg`, 'warning');
            updateLogs(`   O₂ Oxidizer: ${finalData.o2_stored?.toFixed(1)} kg`, 'warning');
            updateLogs(`   H₂ Feedstock: ${finalData.h2_stored?.toFixed(1)} kg`, 'warning');
            updateLogs(`📊 Data Points Collected: ${simulationData.length}`, 'warning');
            if (totalSols >= 0) {
                updateLogs(`📊 Partial Sol ${totalSols} Performance:`, 'warning');
                updateLogs(`   Average Daily Rates (est):`, 'warning');
                updateLogs(`     CH₄: ${(finalData.ch4_stored / Math.max(1, totalSols + 1)).toFixed(1)} kg/sol`, 'warning');
                updateLogs(`     O₂: ${(finalData.o2_stored / Math.max(1, totalSols + 1)).toFixed(1)} kg/sol`, 'warning');
            }
            updateLogs(`🛑 Mission Status: STOPPED - Data preserved for analysis`, 'warning');
            updateLogs(`🔄 Use Reset System to clear data and restart`, 'info');
            updateLogs(`===============================================`, 'warning');
            updateLogs(``, 'info');
        }
        
    } catch (error) {
        console.error('Error in stopSimulation:', error);
        updateLogs(`🚨 Error stopping mission: ${error.message}`, 'error');
        updateLogs('   Manual intervention may be required', 'error');
        
        // Still try to update button states even if there was an error
        document.getElementById('run-simulation').disabled = false;
        document.getElementById('stop-simulation').disabled = true;
        isSimulationRunning = false;
    }
}

async function resetSimulation() {
    console.log('Reset button clicked - resetting backend and frontend');
    
    try {
        // Call backend reset API
        const response = await fetch('/api/reset_simulation', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('Reset response:', result);
        
        // Reset frontend state
        simulationData = [];
        isSimulationRunning = false;
        missionStartTime = null;
        lastReportedSol = -1;
        
        // Reset status cards
        updateStatusCard('power-status', '0', 'kW', 'var(--terminal-green)');
        updateStatusCard('fuel-status', '0', 'kg', 'var(--mars-orange)');
        updateStatusCard('oxygen-status', '0', 'kg', 'var(--info-blue)');
        updateStatusCard('mission-time', '00:00:00', '', 'var(--terminal-green)');
        updateStatusCard('system-status', 'STANDBY', '', 'var(--warning-yellow)');
        
        // Reset button states
        document.getElementById('run-simulation').disabled = false;
        document.getElementById('stop-simulation').disabled = true;
        
        // Clear logs
        const logsContainer = document.getElementById('logs-container');
        logsContainer.textContent = '';
        
        // Reinitialize logs
        updateLogs('🔄 System reset completed', 'success');
        updateLogs('🌌 Mars ISRU Control System v2.1.0 - Reinitialized', 'success');
        updateLogs('🔧 Subsystem diagnostics complete', 'info');
        updateLogs('⚡ Power management system online', 'info');
        updateLogs('🏭 Production modules ready for configuration', 'info');
        updateLogs('📅 Sol-based reporting system ready', 'info');
        updateLogs('🎯 Awaiting mission parameters and launch authorization...', 'info');
        updateLogs('📊 Configure system parameters and press Launch Mission', 'info');
        
        // Clear visualization
        updateVisualization();
        
        console.log('System reset complete');
        
    } catch (error) {
        console.error('Error in resetSimulation:', error);
        updateLogs(`🚨 Error resetting system: ${error.message}`, 'error');
        updateLogs('   Some state may not have been cleared properly', 'error');
        
        // Still try to reset frontend state even if backend fails
        simulationData = [];
        isSimulationRunning = false;
        missionStartTime = null;
        lastReportedSol = -1;
        
        document.getElementById('run-simulation').disabled = false;
        document.getElementById('stop-simulation').disabled = true;
    }
}

function launchSequence() {
    const messages = [
        'T-5: Final systems check initiated',
        'T-4: Power systems nominal', 
        'T-3: Atmosphere processors online',
        'T-2: Sabatier reactor warming up',
        'T-1: Electrolysis system ready',
        'T-0: 🚀 MISSION START - All systems operational'
    ];
    
    messages.forEach((message, index) => {
        setTimeout(() => {
            updateLogs(message, index === messages.length - 1 ? 'success' : 'info');
            if (index === messages.length - 1) {
                updateLogs('📊 Beginning telemetry data collection...', 'info');
                updateLogs('🔬 Monitoring system performance and production rates', 'info');
                updateLogs('📈 Real-time analytics and milestone tracking active', 'info');
            }
        }, index * 1000);
    });
}

function startDataPolling() {
    updateInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/simulation_data');
            const result = await response.json();
            
            const previousRunning = isSimulationRunning;
            const previousDataLength = simulationData.length;
            
            simulationData = result.data;
            
            if (result.running !== isSimulationRunning) {
                isSimulationRunning = result.running;
                if (!result.running && document.getElementById('run-simulation').disabled) {
                    updateLogs('🎉 Mission completed successfully', 'success');
                    updateLogs('📈 Final statistics and data analysis available', 'info');
                    updateStatusCard('system-status', 'COMPLETE', '', 'var(--success-green)');
                    document.getElementById('run-simulation').disabled = false;
                    document.getElementById('stop-simulation').disabled = true;
                    
                    // Log comprehensive final mission summary
                    if (simulationData.length > 0) {
                        const finalData = simulationData[simulationData.length - 1];
                        const totalSols = Math.floor((finalData.time || 0) / 88775);
                        
                        updateLogs(``, 'info');
                        updateLogs(`🎊 ============= FINAL MISSION SUMMARY =============`, 'success');
                        updateLogs(`📅 Total Mission Duration: ${totalSols + 1} Sols (${formatMissionTime(finalData.time)})`, 'success');
                        updateLogs(`🏭 Final Production Totals:`, 'success');
                        updateLogs(`   CH₄ Fuel: ${finalData.ch4_stored?.toFixed(1)} kg`, 'success');
                        updateLogs(`   O₂ Oxidizer: ${finalData.o2_stored?.toFixed(1)} kg`, 'success');
                        updateLogs(`   H₂ Feedstock: ${finalData.h2_stored?.toFixed(1)} kg`, 'success');
                        updateLogs(`📊 Mission Statistics:`, 'success');
                        updateLogs(`   Data Points Collected: ${simulationData.length}`, 'success');
                        updateLogs(`   Average Daily Production:`, 'success');
                        if (totalSols > 0) {
                            updateLogs(`     CH₄: ${(finalData.ch4_stored / (totalSols + 1)).toFixed(1)} kg/sol`, 'success');
                            updateLogs(`     O₂: ${(finalData.o2_stored / (totalSols + 1)).toFixed(1)} kg/sol`, 'success');
                        }
                        updateLogs(`🎯 Mission Status: SUCCESSFULLY COMPLETED`, 'success');
                        updateLogs(`🚀 Ready for next mission configuration`, 'success');
                        updateLogs(`===============================================`, 'success');
                        updateLogs(``, 'info');
                    }
                }
            }
            
            // Log when simulation starts producing data
            if (simulationData.length > 0 && previousDataLength === 0) {
                updateLogs('📡 Telemetry data stream established', 'success');
                updateLogs('🔄 Real-time monitoring active', 'info');
                updateLogs('📅 Sol-based reporting system online', 'info');
            }
            
            // Detect data flow issues
            if (isSimulationRunning && simulationData.length === previousDataLength && simulationData.length > 0) {
                updateLogs('⚠️ Data flow anomaly detected - investigating...', 'warning');
            }
            
            updateStatusCards();
            updateMissionTime();
            updateVisualization();
            
            // Log connection quality every 5 sols worth of data instead of time-based
            if (simulationData.length > 0 && simulationData.length % (88775 / 60 * 5) === 0) { // Every 5 sols
                const currentSol = Math.floor((simulationData[simulationData.length - 1].time || 0) / 88775);
                updateLogs(`📶 Telemetry link stable - Sol ${currentSol} monitoring active`, 'info');
            }
            
        } catch (error) {
            console.error('Telemetry link lost:', error);
            updateLogs('🚨 ALERT: Telemetry link unstable - attempting reconnection...', 'error');
            updateLogs(`   Error details: ${error.message}`, 'error');
            
            // Log connection restoration
            setTimeout(() => {
                updateLogs('🔄 Attempting to restore telemetry connection...', 'warning');
            }, 2000);
        }
    }, 1000);
}

function updateStatusCards() {
    if (simulationData.length === 0) return;
    
    const latest = simulationData[simulationData.length - 1];
    const previous = simulationData.length > 1 ? simulationData[simulationData.length - 2] : latest;
    
    updateStatusCard('power-status', latest.power_available?.toFixed(1) || '0', 'kW', 
        latest.power_available > 10 ? 'var(--success-green)' : 'var(--error-red)');
    
    updateStatusCard('fuel-status', latest.ch4_stored?.toFixed(1) || '0', 'kg', 'var(--mars-orange)');
    updateStatusCard('oxygen-status', latest.o2_stored?.toFixed(1) || '0', 'kg', 'var(--info-blue)');
    
    // Track sol changes and log detailed sol reports
    checkSolTransition(latest, previous);
    
    // Log warnings and critical events
    if (latest.power_available < 5) {
        updateLogs(`🚨 CRITICAL: Power brownout detected (${latest.power_available.toFixed(1)} kW available)`, 'error');
        updateStatusCard('system-status', 'BROWNOUT', '', 'var(--error-red)');
    } else if (latest.power_available < 10) {
        if (Math.random() < 0.1) { // Occasional warning to avoid spam
            updateLogs(`⚠️ WARNING: Low power condition (${latest.power_available.toFixed(1)} kW available)`, 'warning');
        }
        updateStatusCard('system-status', 'CAUTION', '', 'var(--warning-yellow)');
    } else if (isSimulationRunning) {
        updateStatusCard('system-status', 'NOMINAL', '', 'var(--success-green)');
    }
    
    // Log production milestones
    checkProductionMilestones(latest, previous);
}

function checkSolTransition(latest, previous) {
    const currentSol = Math.floor((latest.time || 0) / 88775); // Mars sol = ~88,775 seconds
    const previousSol = Math.floor((previous.time || 0) / 88775);
    
    // Debug logging
    console.log(`Sol check: current=${currentSol}, previous=${previousSol}, lastReported=${lastReportedSol}, time=${latest.time}`);
    
    // Log first sol when simulation starts
    if (currentSol === 0 && lastReportedSol === -1 && simulationData.length > 5) {
        lastReportedSol = 0;
        updateLogs(`🌅 SOL 0 - Mission Day 1 begins`, 'success');
        logSolReport(0, latest, previous);
        return;
    }
    
    // Check if we've entered a new sol (more reliable detection)
    if (currentSol > lastReportedSol) {
        console.log(`New sol detected: ${currentSol}, previous reported: ${lastReportedSol}`);
        lastReportedSol = currentSol;
        updateLogs(`🌅 SOL ${currentSol} - Mission Day ${currentSol + 1} begins`, 'success');
        logSolReport(currentSol, latest, previous);
    }
}

function logSolReport(sol, latest, previous) {
    const solStartTime = sol * 88775;
    const timeOfSol = ((latest.time || 0) - solStartTime) / 88775;
    const powerEfficiency = latest.power_available > 0 ? ((latest.power_allocated / latest.power_available) * 100).toFixed(1) : '0.0';
    
    updateLogs(``, 'info'); // Empty line for spacing
    updateLogs(`🌅 =============== SOL ${sol} REPORT ===============`, 'success');
    updateLogs(`📅 Mission Day: ${sol + 1} | Local Time: ${(timeOfSol * 24).toFixed(1)}h`, 'info');
    
    // Power Systems Report
    updateLogs(`🔋 POWER SYSTEMS:`, 'info');
    updateLogs(`   Generation: ${latest.power_available?.toFixed(1)} kW`, 'info');
    updateLogs(`   Consumption: ${latest.power_allocated?.toFixed(1)} kW (${powerEfficiency}% utilization)`, 'info');
    updateLogs(`   Battery: ${latest.battery_level?.toFixed(0)} kWh`, 'info');
    updateLogs(`   Solar Conditions: ${latest.solar_irradiance?.toFixed(0)} W/m²`, 'info');
    
    // Production Systems Report
    updateLogs(`🏭 PRODUCTION STATUS:`, 'info');
    updateLogs(`   CH₄ Fuel: ${latest.ch4_stored?.toFixed(1)} kg`, 'info');
    updateLogs(`   O₂ Oxidizer: ${latest.o2_stored?.toFixed(1)} kg`, 'info');
    updateLogs(`   H₂ Feedstock: ${latest.h2_stored?.toFixed(1)} kg`, 'info');
    updateLogs(`   CO₂ Intake: ${latest.co2_stored?.toFixed(1)} kg`, 'info');
    updateLogs(`   H₂O Reserves: ${latest.h2o_stored?.toFixed(1)} kg`, 'info');
    
    // Calculate sol-to-sol production if we have previous data
    if (previous && sol > 0) {
        const solDuration = 24.65; // Mars sol in hours
        const ch4Produced = (latest.ch4_stored - previous.ch4_stored);
        const o2Produced = (latest.o2_stored - previous.o2_stored);
        const co2Consumed = (previous.co2_stored - latest.co2_stored);
        
        updateLogs(`📈 SOL ${sol} PRODUCTION:`, 'info');
        updateLogs(`   CH₄ Produced: ${ch4Produced.toFixed(2)} kg (${(ch4Produced/solDuration).toFixed(2)} kg/hr avg)`, 'info');
        updateLogs(`   O₂ Produced: ${o2Produced.toFixed(2)} kg (${(o2Produced/solDuration).toFixed(2)} kg/hr avg)`, 'info');
        updateLogs(`   CO₂ Processed: ${Math.abs(co2Consumed).toFixed(2)} kg`, 'info');
    }
    
    // Environmental Report
    updateLogs(`🌡️ ENVIRONMENT:`, 'info');
    updateLogs(`   Temperature: ${latest.temperature?.toFixed(1)} K (${(latest.temperature - 273.15).toFixed(1)}°C)`, 'info');
    updateLogs(`   Atmospheric Conditions: Nominal`, 'info');
    
    // Storage Utilization
    const ch4Utilization = ((latest.ch4_stored / 1000000) * 100).toFixed(1);
    const o2Utilization = ((latest.o2_stored / 2000000) * 100).toFixed(1);
    const co2Utilization = ((latest.co2_stored / 200000) * 100).toFixed(1);
    
    updateLogs(`📦 STORAGE UTILIZATION:`, 'info');
    updateLogs(`   CH₄ Tanks: ${ch4Utilization}% full`, 'info');
    updateLogs(`   O₂ Tanks: ${o2Utilization}% full`, 'info');
    updateLogs(`   CO₂ Buffer: ${co2Utilization}% full`, 'info');
    
    updateLogs(`🔚 ============= END SOL ${sol} REPORT =============`, 'success');
    updateLogs(``, 'info'); // Empty line for spacing
}

function checkProductionMilestones(latest, previous) {
    // Check for significant production milestones
    const milestones = [100, 500, 1000, 5000, 10000, 50000, 100000];
    
    milestones.forEach(milestone => {
        if (latest.ch4_stored >= milestone && previous.ch4_stored < milestone) {
            const currentSol = Math.floor((latest.time || 0) / 88775);
            updateLogs(`🎯 MILESTONE ACHIEVED: ${milestone} kg CH₄ fuel produced on Sol ${currentSol}!`, 'success');
        }
        if (latest.o2_stored >= milestone && previous.o2_stored < milestone) {
            const currentSol = Math.floor((latest.time || 0) / 88775);
            updateLogs(`🎯 MILESTONE ACHIEVED: ${milestone} kg O₂ oxidizer produced on Sol ${currentSol}!`, 'success');
        }
    });
    
    // Check for storage capacity warnings
    const storageWarningThreshold = 0.8; // 80% capacity
    const storageCriticalThreshold = 0.95; // 95% capacity
    
    checkStorageWarnings('CH₄', latest.ch4_stored, 1000000, storageWarningThreshold, storageCriticalThreshold);
    checkStorageWarnings('O₂', latest.o2_stored, 2000000, storageWarningThreshold, storageCriticalThreshold);
    checkStorageWarnings('CO₂', latest.co2_stored, 200000, storageWarningThreshold, storageCriticalThreshold);
}

function checkStorageWarnings(material, currentAmount, capacity, warningThreshold, criticalThreshold) {
    const utilization = currentAmount / capacity;
    
    if (utilization >= criticalThreshold) {
        updateLogs(`🚨 CRITICAL: ${material} storage ${(utilization * 100).toFixed(1)}% full (${currentAmount.toFixed(0)}/${capacity} kg)`, 'error');
    } else if (utilization >= warningThreshold) {
        if (Math.random() < 0.05) { // Occasional warning to avoid spam
            updateLogs(`⚠️ WARNING: ${material} storage ${(utilization * 100).toFixed(1)}% full`, 'warning');
        }
    }
}

function formatMissionTime(timeSeconds) {
    const sol = Math.floor(timeSeconds / 88775);
    const timeOfSol = (timeSeconds % 88775) / 88775;
    const hours = Math.floor(timeOfSol * 24.65);
    const minutes = Math.floor((timeOfSol * 24.65 * 60) % 60);
    return `Sol ${sol} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
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
    const rates = { ch4: [], o2: [] };
    
    for (let i = 1; i < simulationData.length; i++) {
        const dt = (simulationData[i].time - simulationData[i-1].time) / 3600; // hours
        
        rates.ch4.push(Math.max(0, (simulationData[i].ch4_stored - simulationData[i-1].ch4_stored) / dt));
        rates.o2.push(Math.max(0, (simulationData[i].o2_stored - simulationData[i-1].o2_stored) / dt));
    }
    
    return rates;
}

function updateLogs(message, type = 'info') {
    const logsContainer = document.getElementById('logs-container');
    const timestamp = new Date().toLocaleTimeString();
    
    // Check if user has scrolled up before adding new content
    const wasScrolledToBottom = logsContainer.scrollTop >= logsContainer.scrollHeight - logsContainer.clientHeight - 5;
    
    let prefix = '';
    let icon = '';
    switch (type) {
        case 'error': 
            prefix = '[ERROR]'; 
            icon = '🚨';
            break;
        case 'warning': 
            prefix = '[WARN]'; 
            icon = '⚠️';
            break;
        case 'success': 
            prefix = '[OK]'; 
            icon = '✅';
            break;
        case 'info': 
        default: 
            prefix = '[INFO]'; 
            icon = 'ℹ️';
            break;
    }
    
    // Add some visual formatting for better readability
    const logLine = `${timestamp} ${prefix} ${message}`;
    logsContainer.textContent += logLine + '\n';
    
    // Only auto-scroll to bottom if user was already at the bottom
    if (wasScrolledToBottom) {
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
    
    // Keep log size manageable (keep last 1000 lines)
    const lines = logsContainer.textContent.split('\n');
    if (lines.length > 1000) {
        logsContainer.textContent = lines.slice(-1000).join('\n');
    }
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