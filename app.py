from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_caching import Cache
from markdown2 import markdown
from pathlib import Path
import yaml
import logging
import json
from datetime import datetime

app = Flask(__name__)

# Configure caching
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
cache = Cache(app)


from fleet_simulator import create_fleet_dash_app

# Create integrated Dash app for fleet simulator
fleet_dash_app = create_fleet_dash_app(app)

POSTS_DIRECTORY = "posts"

@cache.memoize(timeout=600)  # Cache for 10 minutes
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
@cache.cached(timeout=300)  # Cache homepage for 5 minutes
def index():
    posts = load_posts()
    response = render_template("index.html", posts=posts)
    return response


@app.route("/post/<filename>")
@cache.cached(timeout=600)  # Cache individual posts for 10 minutes
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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=False)
    # app.run(debug=True)
