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
    
    if simulation_running:
        return jsonify({"error": "Simulation already running"}), 400
    
    # Reset simulation data
    simulation_data = []
    simulation_running = True
    
    def run_sim():
        global simulation_running, simulation_data
        try:
            # Create new simulation
            engine = SimulationEngine()
            
            # Run simulation and collect data
            timesteps = int(duration_years * 365 * 24 * 60 / engine.timestep_minutes)
            
            for i in range(timesteps):
                if not simulation_running:  # Check for pause/stop
                    break
                    
                engine.step()
                
                # Collect data for visualization
                state_data = {
                    'time': engine.plant_state.current_time,
                    'power_available': engine.plant_state.power_budget.available_power,
                    'power_allocated': sum(engine.plant_state.power_budget.allocated_power.values()),
                    'battery_level': getattr(engine.modules.get('Power'), 'battery_charge', 0),
                    'ch4_stored': engine.plant_state.material_stores['CH4'].current_mass,
                    'o2_stored': engine.plant_state.material_stores['O2'].current_mass,
                    'h2_stored': engine.plant_state.material_stores['H2'].current_mass,
                    'co2_stored': engine.plant_state.material_stores['CO2'].current_mass,
                    'h2o_stored': engine.plant_state.material_stores['H2O'].current_mass,
                    'solar_irradiance': getattr(engine.modules.get('Environment'), 'current_irradiance', 0),
                    'temperature': getattr(engine.modules.get('Environment'), 'temperature', 220),
                }
                
                simulation_data.append(state_data)
                
                # Sleep based on speed
                time.sleep(0.01 / speed)
            
        except Exception as e:
            logging.error(f"Simulation error: {e}")
        finally:
            simulation_running = False
    
    simulation_thread = threading.Thread(target=run_sim)
    simulation_thread.start()
    
    return jsonify({"status": "started"})

@app.route("/api/pause_simulation", methods=["POST"])
def pause_simulation():
    global simulation_running
    simulation_running = False
    return jsonify({"status": "paused"})

@app.route("/api/simulation_data")
def get_simulation_data():
    return jsonify({
        "data": simulation_data,
        "running": simulation_running
    })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=False)
    # app.run(debug=True)
