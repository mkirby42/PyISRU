from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from flask_caching import Cache
from markdown2 import markdown
from pathlib import Path
import yaml
import logging
import json
from datetime import datetime
import os
import sqlite3
import time
import secrets
import hashlib
import hmac
import uuid
import bleach
from bleach.linkifier import LinkifyFilter
from functools import partial
from io import BytesIO
from PIL import Image

app = Flask(__name__)

# Configure caching
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
cache = Cache(app)

# Thumbnail configuration
THUMB_ROOT = Path('static') / 'thumbs'
THUMB_ROOT.mkdir(parents=True, exist_ok=True)

def _thumb_path(src_relative: str, width: int) -> Path:
    basename = os.path.basename(src_relative)
    name, _ext = os.path.splitext(basename)
    safe_name = name.replace('/', '_')
    return THUMB_ROOT / f"{safe_name}_{width}.webp"

def _open_image_abs(abs_path: Path) -> Image.Image:
    with Image.open(abs_path) as img:
        img.load()
        return img.convert('RGB')

@app.route('/thumb')
def thumb():
    """Generate/serve a cached WebP thumbnail for an image in static/images.

    Query params:
      src: relative path under static/images, e.g. 'its.png'
      w: target width in px (int)
    """
    src = request.args.get('src', '').strip()
    width_str = request.args.get('w', '400').strip()
    try:
        width = max(64, min(2000, int(width_str)))
    except Exception:
        width = 400

    if not src or '..' in src or src.startswith('/'):
        return 'bad src', 400

    abs_src = Path('static') / 'images' / src
    if not abs_src.exists():
        return 'not found', 404

    out_path = _thumb_path(src, width)
    try:
        if out_path.exists() and out_path.stat().st_mtime >= abs_src.stat().st_mtime:
            return send_from_directory(str(out_path.parent), out_path.name, mimetype='image/webp')

        img = _open_image_abs(abs_src)
        w, h = img.size
        if w > width:
            ratio = width / float(w)
            new_size = (width, int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, 'WEBP', quality=82, method=6)
        return send_from_directory(str(out_path.parent), out_path.name, mimetype='image/webp')
    except Exception as e:
        logging.exception(f"thumb error for {src} w={width}: {e}")
        # Fallback to original
        return send_from_directory('static/images', src)


def _running_in_docker() -> bool:
    return os.path.exists('/.dockerenv') or os.environ.get('IN_DOCKER') == '1'


def _default_db_path() -> str:
    env_path = os.environ.get('COMMENTS_DB_PATH')
    if env_path:
        return env_path
    if _running_in_docker():
        return '/data/comments.sqlite3'
    # Local dev/run fallback
    return str((Path(__file__).parent / 'comments-dev.sqlite3').resolve())


# Comments configuration
app.config['COMMENTS_DB_PATH'] = _default_db_path()
app.config['COMMENTS_SALT'] = os.environ.get('COMMENTS_SALT', 'pyisru-comment-salt')


def _get_db_connection():
    db_path = app.config['COMMENTS_DB_PATH']
    # Ensure parent directory exists if it's a file path
    try:
        parent_dir = os.path.dirname(db_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
    except Exception as e:
        logging.warning(f"Could not ensure DB directory exists for {db_path}: {e}")
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception as e:
        logging.warning(f"Could not set SQLite PRAGMAs: {e}")
    return conn


def _init_comments_db():
    conn = _get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
    except Exception as e:
        logging.warning(f"Could not set SQLite PRAGMAs during init: {e}")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_slug TEXT NOT NULL,
            parent_id INTEGER,
            author_name TEXT NOT NULL,
            author_email TEXT,
            content_md TEXT NOT NULL,
            content_html TEXT NOT NULL,
            like_count INTEGER NOT NULL DEFAULT 0,
            edit_token_hash TEXT NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_slug)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id)")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS likes_seen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL,
            user_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(comment_id, user_hash)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            post_slug TEXT NOT NULL,
            last_comment_ts INTEGER NOT NULL,
            UNIQUE(ip, post_slug)
        )
        """
    )
    conn.commit()
    conn.close()


def _hmac_sha256(value: str) -> str:
    salt = app.config['COMMENTS_SALT'].encode('utf-8')
    return hmac.new(salt, value.encode('utf-8'), hashlib.sha256).hexdigest()


def _sanitize_html(html: str) -> str:
    allowed_tags = [
        'p', 'ul', 'ol', 'li', 'pre', 'code', 'blockquote', 'a',
        'strong', 'em', 'br', 'hr'
    ]
    allowed_attrs = {
        'a': ['href', 'title', 'rel', 'target'],
        'code': ['class']
    }

    def add_rel_target(attrs, new=False):
        # attrs keys are tuples like (namespace, attr)
        href = attrs.get((None, 'href'))
        if href:
            rel_val = attrs.get((None, 'rel'), '')
            rel_parts = set(rel_val.split()) if rel_val else set()
            rel_parts.update(['nofollow', 'noopener'])
            attrs[(None, 'rel')] = ' '.join(sorted(rel_parts))
            attrs[(None, 'target')] = '_blank'
        return attrs

    cleaner = bleach.Cleaner(
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True,
        filters=[partial(LinkifyFilter, callbacks=[add_rel_target])]
    )
    return cleaner.clean(html)


# Preserve MathJax delimiters through markdown conversion
def _protect_math_delimiters(text: str) -> str:
    if not text:
        return text
    return (
        text
        .replace('\\(', '::MJX_INL_L::')
        .replace('\\)', '::MJX_INL_R::')
        .replace('\\[', '::MJX_DISP_L::')
        .replace('\\]', '::MJX_DISP_R::')
    )


def _restore_math_delimiters(text: str) -> str:
    if not text:
        return text
    return (
        text
        .replace('::MJX_INL_L::', '\\(')
        .replace('::MJX_INL_R::', '\\)')
        .replace('::MJX_DISP_L::', '\\[')
        .replace('::MJX_DISP_R::', '\\]')
    )


# Initialize DB at startup
_init_comments_db()


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
    
    methanation_post = load_markdown_post("methanation")
    posts.append(methanation_post)
    
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
        
        _pre_md = _protect_math_delimiters(content)
        html_content = markdown(_pre_md, extras=["fenced-code-blocks", "tables", "code-friendly"])
        html_content = _restore_math_delimiters(html_content)

    response = make_response(
        render_template(
            "post.html",
            content=html_content,
            title=metadata.get("title", "Untitled"),
            image=metadata.get("image", ""),
            filename=filename,
            comments_enabled=metadata.get("comments", True)
        )
    )

    # Ensure a stable, anonymous client id cookie for like de-dupe
    if not request.cookies.get('cid'):
        response.set_cookie('cid', uuid.uuid4().hex, max_age=60*60*24*365*5, samesite='Lax')

    return response


@app.route("/comments/<slug>", methods=["GET"])
def get_comments(slug):
    conn = _get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, post_slug, parent_id, author_name, content_html, content_md, like_count, is_deleted, created_at FROM comments WHERE post_slug=? ORDER BY created_at ASC",
        (slug,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Build 1-level threading
    by_id = {r['id']: {**r, 'replies': []} for r in rows}
    top_level = []
    for r in rows:
        if r['parent_id'] and r['parent_id'] in by_id:
            by_id[r['parent_id']]['replies'].append(by_id[r['id']])
        else:
            top_level.append(by_id[r['id']])

    return jsonify({"comments": top_level})


@app.route("/comments/<slug>", methods=["POST"])
def create_comment(slug):
    # Basic honeypot
    if request.form.get('website'):
        return jsonify({"error": "Invalid submission"}), 400

    author_name = (request.form.get('author_name') or '').strip()
    author_email = (request.form.get('author_email') or '').strip()
    content_md = (request.form.get('content') or '').strip()
    parent_id = request.form.get('parent_id')
    parent_id = int(parent_id) if parent_id else None

    # Coalesce too-short names to Anonymous
    if len(author_name) < 2:
        author_name = 'Anonymous'
    if len(author_name) > 40:
        return jsonify({"error": "Invalid name"}), 400
    # Slightly lenient content minimum for UX
    if len(content_md) < 3 or len(content_md) > 3000:
        return jsonify({"error": "Invalid content length"}), 400

    # Rate limit: 1 comment per IP+post per 10s, persisted
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    now = int(time.time())
    conn = _get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT last_comment_ts FROM rate_limits WHERE ip=? AND post_slug=?", (ip, slug))
    row = cur.fetchone()
    if row and now - row[0] < 10:
        conn.close()
        return jsonify({"error": "Rate limited"}), 429
    # Upsert to minimize lock window
    cur.execute(
        """
        INSERT INTO rate_limits (ip, post_slug, last_comment_ts)
        VALUES (?, ?, ?)
        ON CONFLICT(ip, post_slug) DO UPDATE SET last_comment_ts=excluded.last_comment_ts
        """,
        (ip, slug, now)
    )

    # Validate parent: only 1-level deep
    if parent_id is not None:
        cur.execute("SELECT parent_id FROM comments WHERE id=? AND post_slug=?", (parent_id, slug))
        p = cur.fetchone()
        if not p or p[0] is not None:
            conn.close()
            return jsonify({"error": "Invalid parent"}), 400

    # Render and sanitize
    _pre_md = _protect_math_delimiters(content_md)
    content_html_raw = markdown(_pre_md, extras=["fenced-code-blocks", "tables", "code-friendly"])
    content_html = _sanitize_html(_restore_math_delimiters(content_html_raw))

    # Token for edit/delete
    edit_token = secrets.token_urlsafe(16)
    edit_token_hash = _hmac_sha256(edit_token)

    cur.execute(
        """
        INSERT INTO comments (post_slug, parent_id, author_name, author_email, content_md, content_html, like_count, edit_token_hash, is_deleted, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?)
        """,
        (slug, parent_id, author_name, author_email, content_md, content_html, edit_token_hash, now, now)
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "id": new_id,
        "edit_token": edit_token,
        "content_html": content_html
    }), 201


@app.route("/comments/<slug>/<int:comment_id>/like", methods=["POST"])
def like_comment(slug, comment_id):
    cid = request.cookies.get('cid') or ''
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    user_hash = _hmac_sha256(f"{cid}|{ip}")
    now = int(time.time())

    conn = _get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO likes_seen (comment_id, user_hash, created_at) VALUES (?, ?, ?)",
            (comment_id, user_hash, now)
        )
        cur.execute(
            "UPDATE comments SET like_count = like_count + 1 WHERE id=? AND post_slug=?",
            (comment_id, slug)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Already liked"}), 200
    conn.close()
    return jsonify({"ok": True})


@app.route("/comments/<slug>/<int:comment_id>/edit", methods=["POST"])
def edit_comment(slug, comment_id):
    token = request.form.get('edit_token') or ''
    content_md = (request.form.get('content') or '').strip()
    if len(content_md) < 5 or len(content_md) > 3000:
        return jsonify({"error": "Invalid content length"}), 400
    token_hash = _hmac_sha256(token)
    conn = _get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT edit_token_hash FROM comments WHERE id=? AND post_slug=?", (comment_id, slug))
    row = cur.fetchone()
    if not row or row[0] != token_hash:
        conn.close()
        return jsonify({"error": "Unauthorized"}), 403
    _pre_md = _protect_math_delimiters(content_md)
    content_html_raw = markdown(_pre_md, extras=["fenced-code-blocks", "tables", "code-friendly"])
    content_html = _sanitize_html(_restore_math_delimiters(content_html_raw))
    now = int(time.time())
    cur.execute(
        "UPDATE comments SET content_md=?, content_html=?, updated_at=? WHERE id=?",
        (content_md, content_html, now, comment_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "content_html": content_html})


@app.route("/comments/<slug>/<int:comment_id>/delete", methods=["POST"])
def delete_comment(slug, comment_id):
    token = request.form.get('edit_token') or ''
    token_hash = _hmac_sha256(token)
    conn = _get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT edit_token_hash FROM comments WHERE id=? AND post_slug=?", (comment_id, slug))
    row = cur.fetchone()
    if not row or row[0] != token_hash:
        conn.close()
        return jsonify({"error": "Unauthorized"}), 403
    now = int(time.time())
    cur.execute("UPDATE comments SET is_deleted=1, updated_at=? WHERE id=?", (now, comment_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/static/images/<path:filename>")
def images(filename):
    return send_from_directory("static/images", filename)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=False)
    # app.run(debug=True)
