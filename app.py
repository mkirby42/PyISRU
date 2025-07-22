from flask import Flask, render_template, request, jsonify, send_from_directory
from markdown2 import markdown
from pathlib import Path
import yaml
import logging
import json
import threading
import time
from datetime import datetime

# Import our simulation modules
import sys
sys.path.append('src')
from simulation_engine import SimulationEngine
from core.plant_state import PlantState
from modules.environment import EnvironmentModule
from modules.power import PowerModule
from modules.atmosphere_intake import AtmosphereIntakeModule
from modules.electrolysis import ElectrolysisModule
from modules.sabatier_reactor import SabatierReactorModule

app = Flask(__name__)

# Global simulation state
current_simulation = None
simulation_thread = None
simulation_data = []
simulation_running = False

POSTS_DIRECTORY = "posts"


def load_posts():
    posts = []
    # Load local Markdown posts
    for md_file in Path(POSTS_DIRECTORY).glob("*.md"):
        with open(md_file, "r", encoding="utf-8") as file:
            content = file.read()
            if content.startswith("---"):
                _, front_matter, md_content = content.split("---", 2)
                metadata = yaml.safe_load(front_matter)
                metadata["content"] = md_content.strip()
            else:
                metadata = {
                    "title": "Untitled",
                    "description": "",
                    "image": "",
                    "content": content,
                }
            metadata["filename"] = md_file.stem
            posts.append(metadata)
    
    # Load Medium posts from YAML
    medium_posts_file = Path(f"{POSTS_DIRECTORY}/medium_posts.yaml")
    try:
        with open(medium_posts_file, "r", encoding="utf-8") as file:
            medium_posts = yaml.safe_load(file)
            for post in medium_posts:
                post["is_medium"] = True  # Add a flag for Medium posts
                posts.append(post)
    except Exception as e:
        logging.error(f"Error loading Medium posts: {e}")

    # Sort posts by title or add custom sorting
    return posts



@app.route("/")
def index():
    posts = load_posts()
    return render_template("index.html", posts=posts)


@app.route("/post/<filename>")
def post(filename):
    filepath = Path(POSTS_DIRECTORY) / f"{filename}.md"
    if not filepath.exists():
        return "Post not found", 404

    with open(filepath, "r", encoding="utf-8") as file:
        content = file.read()
        if content.startswith("---"):
            _, front_matter, md_content = content.split("---", 2)
            metadata = yaml.safe_load(front_matter)
            content = md_content.strip()
        else:
            metadata = {"title": "Untitled", "image": ""}
        
        html_content = markdown(content, extras=["fenced-code-blocks", "tables"])

    return render_template(
        "post.html",
        content=html_content,
        title=metadata.get("title", "Untitled"),
        image=metadata.get("image", "")
    )


@app.route("/static/images/<path:filename>")
def images(filename):
    return send_from_directory("static/images", filename)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/run_simulation", methods=["POST"])
def run_simulation():
    global current_simulation, simulation_thread, simulation_data, simulation_running
    
    data = request.json
    speed = data.get("speed", 1.0)
    duration_years = data.get("duration", 0.1)
    
    # Get configuration parameters with defaults
    solar_array_area = data.get("solar_array_area", 50000.0)
    battery_capacity = data.get("battery_capacity", 20000.0)
    co2_intake_rate = data.get("co2_intake_rate", 100.0)
    h2_production_rate = data.get("h2_production_rate", 10.0)
    ch4_production_rate = data.get("ch4_production_rate", 46.0)
    ignore_temp_overage = data.get("ignore_temp_overage", False)
    
    if simulation_running:
        return jsonify({"error": "Simulation already running"}), 400
    
    # Reset simulation data
    simulation_data = []
    simulation_running = True
    
    def run_sim():
        global simulation_running, simulation_data
        try:
            # Create new simulation with configurable modules
            engine = SimulationEngine()
            
            # Add all required modules with user-configured parameters
            logging.info(f"Initializing simulation with config: Solar={solar_array_area}m², Battery={battery_capacity}kWh")
            logging.info(f"Production targets: CO₂={co2_intake_rate}, H₂={h2_production_rate}, CH₄={ch4_production_rate} kg/hr")
            
            engine.add_module(EnvironmentModule(ignore_temp_overage=ignore_temp_overage))
            engine.add_module(PowerModule(
                solar_array_area_m2=solar_array_area,
                battery_capacity_kwh=battery_capacity,
                ignore_temp_overage=ignore_temp_overage
            ))
            engine.add_module(AtmosphereIntakeModule(
                target_flow_rate_kg_hr=co2_intake_rate,
                ignore_temp_overage=ignore_temp_overage
            ))
            engine.add_module(ElectrolysisModule(
                target_h2_rate_kg_hr=h2_production_rate,
                ignore_temp_overage=ignore_temp_overage
            )) 
            engine.add_module(SabatierReactorModule(
                target_ch4_rate_kg_hr=ch4_production_rate,
                ignore_temp_overage=ignore_temp_overage
            ))
            
            logging.info(f"All modules initialized. Beginning simulation with {len(engine.modules)} active modules")
            
            # Run simulation and collect data
            timesteps = int(duration_years * 365 * 24 * 60 / engine.timestep_minutes)
            logging.info(f"Simulation will run for {timesteps} timesteps ({duration_years} Mars years)")
            
            step_count = 0
            for i in range(timesteps):
                if not simulation_running:  # Check for pause/stop
                    logging.info(f"Simulation stopped by user after {step_count} steps")
                    break
                    
                step_result = engine.step()
                step_count += 1
                
                # Get modules by name (since modules is a list)
                modules_dict = {m.name: m for m in engine.modules}
                power_module = modules_dict.get('Power')
                environment_module = modules_dict.get('Environment')
                
                # Collect data for visualization with correct property names
                state_data = {
                    'time': engine.plant_state.current_time,
                    'power_available': engine.plant_state.power_budget.generation_kw,
                    'power_allocated': engine.plant_state.power_budget.total_allocated_kw,
                    'battery_level': getattr(power_module, 'battery_soc', 0) * getattr(power_module, 'battery_capacity_kwh', 0) if power_module else 0,
                    'ch4_stored': engine.plant_state.materials['CH4'].mass_kg,
                    'o2_stored': engine.plant_state.materials['O2'].mass_kg,
                    'h2_stored': engine.plant_state.materials['H2'].mass_kg,
                    'co2_stored': engine.plant_state.materials['CO2'].mass_kg,
                    'h2o_stored': engine.plant_state.materials['H2O'].mass_kg,
                    'solar_irradiance': engine.plant_state.environment.solar_irradiance_w_m2,
                    'temperature': engine.plant_state.environment.ambient_temperature_k,
                }
                
                simulation_data.append(state_data)
                
                # Log periodic status for debugging
                if step_count % 3600 == 0:  # Every hour of simulation time
                    logging.info(f"Step {step_count}: CH₄={state_data['ch4_stored']:.1f}kg, Power={state_data['power_available']:.1f}kW")
                
                # Sleep based on speed
                time.sleep(0.01 / speed)
            
            logging.info(f"Simulation completed after {step_count} steps. Final data points: {len(simulation_data)}")
            
        except Exception as e:
            logging.error(f"Simulation error after {len(simulation_data)} steps: {e}")
            logging.error(f"Error type: {type(e).__name__}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
        finally:
            simulation_running = False
            logging.info("Simulation thread terminated")
    
    simulation_thread = threading.Thread(target=run_sim)
    simulation_thread.start()
    
    return jsonify({"status": "started"})

@app.route("/api/pause_simulation", methods=["POST"])
def pause_simulation():
    global simulation_running
    simulation_running = False
    return jsonify({"status": "paused"})

@app.route("/api/reset_simulation", methods=["POST"])
def reset_simulation():
    global current_simulation, simulation_thread, simulation_data, simulation_running
    
    # Stop any running simulation
    simulation_running = False
    
    # Wait for simulation thread to finish if it's running
    if simulation_thread and simulation_thread.is_alive():
        simulation_thread.join(timeout=2.0)  # Wait up to 2 seconds
    
    # Reset all simulation state
    current_simulation = None
    simulation_thread = None
    simulation_data = []
    simulation_running = False
    
    return jsonify({"status": "reset"})

@app.route("/api/simulation_data")
def get_simulation_data():
    return jsonify({
        "data": simulation_data,
        "running": simulation_running
    })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=False)
    # app.run(debug=True)
