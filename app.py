from flask import Flask, render_template, request, jsonify, send_from_directory
from markdown2 import markdown
from pathlib import Path
import yaml
import logging
import json
from datetime import datetime

app = Flask(__name__)

# Import the separate simulation modules
from isru_simulation import isru_manager
from fleet_simulator import create_fleet_dash_app

# Create integrated Dash app for fleet simulator
fleet_dash_app = create_fleet_dash_app(app)

POSTS_DIRECTORY = "posts"


def load_posts():
    def load_markdown_post(filename):
        filepath = Path(POSTS_DIRECTORY) / f"{filename}.md"
        with open(filepath, "r", encoding="utf-8") as file:
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
            metadata["filename"] = filename
            return metadata
        
    posts = []
    mars_base_post = load_markdown_post("how_long_to_mars_base")
    posts.append(mars_base_post)
    
    fleet_simulator_post = {
        "title": "Mars Fleet Simulator",
        "description": "Interactive simulation of Mars transport fleet operations, manufacturing, and logistics planning",
        "image": "its.png",
        "filename": "fleet-simulator",
        "is_app": True,
        "app_url": "/fleet-simulator/",
        "medium_link": None
    }
    posts.append(fleet_simulator_post)
    
    isru_dashboard_post = {
        "title": "ISRU Plant Dashboard",
        "description": "Interactive dashboard for Mars In-Situ Resource Utilization plant operations and monitoring",
        "image": "fuel_production_plant.jpg",  # Using existing image
        "filename": "isru-dashboard",
        "is_app": True,
        "app_url": "/dashboard",  # Existing dashboard route
        "medium_link": None
    }
    posts.append(isru_dashboard_post)
        
    solaris_post = load_markdown_post("a_the_other_the_unknown_and_ourselves")
    posts.append(solaris_post)
    
    server_post = load_markdown_post("personal_server")
    posts.append(server_post)
    
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
    data = request.json
    
    # Prepare parameters for the ISRU simulation
    params = {
        'speed': data.get("speed", 1.0),
        'duration': data.get("duration", 0.1),
        'solar_array_area': data.get("solar_array_area", 50000.0),
        'battery_capacity': data.get("battery_capacity", 20000.0),
        'co2_intake_rate': data.get("co2_intake_rate", 100.0),
        'h2_production_rate': data.get("h2_production_rate", 10.0),
        'ch4_production_rate': data.get("ch4_production_rate", 46.0),
        'ignore_temp_overage': data.get("ignore_temp_overage", False)
    }
    
    # Use the ISRU manager to run the simulation
    result = isru_manager.run_simulation(params)
    
    if "error" in result:
        return jsonify(result), 400
    
    return jsonify(result)

@app.route("/api/pause_simulation", methods=["POST"])
def pause_simulation():
    return jsonify(isru_manager.pause_simulation())

@app.route("/api/reset_simulation", methods=["POST"])
def reset_simulation():
    return jsonify(isru_manager.reset_simulation())

@app.route("/api/simulation_data")
def get_simulation_data():
    return jsonify(isru_manager.get_simulation_data())


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=False)
    # app.run(debug=True)
