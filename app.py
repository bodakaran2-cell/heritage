# app.py  — All-in-one Flask app (serves frontend + backend API)
# Save this file and run: python app.py
# Requirements (pip): Flask==2.2.5 Werkzeug==2.2.3
# (Optional) pip install -r requirements.txt with the two lines above.

import os
import sqlite3
from datetime import datetime
from flask import (
    Flask, request, jsonify, send_from_directory, abort,
    Response, g, redirect, url_for
)
from werkzeug.utils import secure_filename

#######################
# Configuration
#######################
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "database.db")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "pdf", "mp3", "wav", "mp4", "txt"}
MAX_CONTENT_LENGTH = 300 * 1024 * 1024  # 300 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["DATABASE"] = DB_PATH

#######################
# DB helpers
#######################
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    return db

def init_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT,
            mime TEXT,
            title TEXT,
            description TEXT,
            tags TEXT,
            uploaded_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

init_db()

#######################
# Utility
#######################
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

#######################
# Frontend routes (inline HTML/CSS/JS)
#######################
INDEX_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Manuscripts & Folk Archive — Upload & Search</title>
  <style>
    :root{--bg:#f7f7f9;--card:#fff;--accent:#0b61ff}
    *{box-sizing:border-box}
    body{font-family:system-ui, -apple-system, 'Segoe UI', Roboto, Arial;margin:0;background:var(--bg);color:#111}
    .container{max-width:980px;margin:28px auto;padding:16px}
    h1{margin:0 0 12px}
    .card{background:var(--card);padding:14px;border-radius:12px;box-shadow:0 6px 20px rgba(10,10,10,0.04);margin-bottom:16px}
    label{display:block;margin-bottom:8px}
    input[type=text], input, textarea{width:100%;padding:8px;margin-top:6px;border-radius:6px;border:1px solid #ddd}
    button{padding:10px 14px;border-radius:8px;border:0;background:var(--accent);color:#fff;cursor:pointer}
    #items .item{padding:10px;border-bottom:1px solid #eee}
    .item-title{font-weight:600}
    .item-actions{margin-top:6px}
    .item-actions button{margin-right:8px}
    footer{font-size:13px;color:#666;margin-top:12px}
    .row{display:flex;gap:12px;flex-wrap:wrap}
    .col{flex:1 1 300px}
    input[type=file]{margin-top:6px}
    .small{font-size:13px;color:#666}
  </style>
</head>
<body>
  <main class="container">
    <h1>Manuscripts & Folk Archive</h1>

    <section class="card">
      <h2>Upload new item</h2>
      <form id="uploadForm">
        <div class="row">
          <div class="col">
            <label>Title<br /><input name="title" placeholder="e.g., Ramayana palm-leaf page" /></label>
          </div>
          <div class="col">
            <label>Tags (comma separated)<br /><input name="tags" placeholder="manuscript, telugu, palm-leaf" /></label>
          </div>
        </div>
        <label>Description<br /><textarea name="description" rows="3" placeholder="Short description or location"></textarea></label>
        <label>File<br /><input type="file" name="file" required /></label>
        <div style="margin-top:8px"><button type="submit">Upload</button></div>
      </form>
      <div id="uploadStatus" class="small"></div>
    </section>

    <section class="card">
      <h2>Search / Browse</h2>
      <input id="searchInput" placeholder="Search title, description, tags" style="padding:8px;width:100%;border-radius:6px;border:1px solid #ddd" />
      <div id="items" style="margin-top:12px"></div>
    </section>

    <footer>Hackathon MVP — extend with OCR, transcriptions, auth</footer>
  </main>

  <script>
    const API = '/api';

    async function list(q=''){
      const url = q ? `${API}/items?q=${encodeURIComponent(q)}` : `${API}/items`;
      const res = await fetch(url);
      const items = await res.json();
      renderItems(items);
    }

    function renderItems(items){
      const cont = document.getElementById('items');
      cont.innerHTML = '';
      if(!items.length){ cont.innerHTML = '<div class="small">No items yet</div>'; return }
      items.forEach(it=>{
        const div = document.createElement('div'); div.className='item';
        const title = escapeHtml(it.title || it.original_name || 'Untitled');
        const desc = escapeHtml(it.description || '');
        const tags = escapeHtml(it.tags || '');
        div.innerHTML = `<div class="item-title">${title}</div>
          <div class="small">${desc || ''}<br/>Tags: ${tags}</div>
          <div class="item-actions">
            <button onclick="download(${it.id})">Download</button>
            <button onclick="preview(${it.id})">Preview</button>
            <button onclick="removeItem(${it.id})">Delete</button>
          </div>`;
        cont.appendChild(div);
      })
    }

    function escapeHtml(s){ return (s||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;') }

    async function download(id){ window.open(`/api/download/${id}`, '_blank') }

    async function preview(id){
      const res = await fetch(`${API}/item/${id}`);
      if(!res.ok) return alert('Not found');
      const it = await res.json();
      const parts = [
        `Title: ${it.title || it.original_name || ''}`,
        `Description: ${it.description || ''}`,
        `Tags: ${it.tags || ''}`,
        `Uploaded: ${it.uploaded_at || ''}`
      ];
      alert(parts.join('\\n\\n'));
    }

    async function removeItem(id){
      if(!confirm('Delete this item?')) return;
      const res = await fetch(`${API}/delete/${id}`, { method: 'DELETE' });
      if(res.ok) list(document.getElementById('searchInput').value.trim());
      else alert('Delete failed');
    }

    const uploadForm = document.getElementById('uploadForm');
    uploadForm.addEventListener('submit', async (e)=>{
      e.preventDefault();
      const fd = new FormData(uploadForm);
      document.getElementById('uploadStatus').textContent = 'Uploading...';
      const res = await fetch(`${API}/upload`, { method: 'POST', body: fd });
      const data = await res.json();
      if(res.ok){
        document.getElementById('uploadStatus').textContent = 'Uploaded!';
        uploadForm.reset();
        list();
        setTimeout(()=> document.getElementById('uploadStatus').textContent = '', 2500);
      } else {
        document.getElementById('uploadStatus').textContent = data.error || 'Upload failed';
      }
    });

    const searchInput = document.getElementById('searchInput');
    let searchTimeout = null;
    searchInput.addEventListener('input', ()=>{
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(()=> list(searchInput.value.trim()), 300);
    });

    // init
    list();
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")

#######################
# API routes
#######################
@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(f.filename):
        return jsonify({"error": f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXT))}"}), 400

    orig = secure_filename(f.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    stored_name = f"{timestamp}_{orig}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
    f.save(filepath)

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    tags = (request.form.get("tags") or "").strip()
    mime = f.mimetype or ""

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO items (filename, original_name, mime, title, description, tags, uploaded_at) VALUES (?,?,?,?,?,?,?)",
        (stored_name, orig, mime, title, description, tags, datetime.utcnow().isoformat()),
    )
    conn.commit()
    item_id = cur.lastrowid
    return jsonify({"success": True, "id": item_id}), 201

@app.route("/api/items", methods=["GET"])
def list_items():
    q = (request.args.get("q") or "").strip().lower()
    conn = get_db()
    cur = conn.cursor()
    if q:
        like = f"%{q}%"
        cur.execute(
            "SELECT * FROM items WHERE lower(title) LIKE ? OR lower(description) LIKE ? OR lower(tags) LIKE ? ORDER BY uploaded_at DESC",
            (like, like, like),
        )
    else:
        cur.execute("SELECT * FROM items ORDER BY uploaded_at DESC")
    rows = cur.fetchall()
    items = [dict(r) for r in rows]
    return jsonify(items)

@app.route("/api/item/<int:item_id>", methods=["GET"])
def get_item(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))

@app.route("/api/download/<int:item_id>", methods=["GET"])
def download(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT filename, original_name FROM items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if not row:
        return abort(404)
    filename = row["filename"]
    original = row["original_name"] or filename
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True, download_name=original)

@app.route("/api/delete/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT filename FROM items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    filename = row["filename"]
    try:
        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    except Exception:
        pass
    cur.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    return jsonify({"success": True})

#######################
# Optional simple static listing for uploads (for debug) — disabled by default
#######################
# Use only in trusted environment. To enable, uncomment the route.
# @app.route("/uploads/<path:fname>")
# def uploaded_file(fname):
#     return send_from_directory(app.config["UPLOAD_FOLDER"], fname)

#######################
# Run
#######################
if __name__ == "__main__":
    print("Starting Manuscripts & Folk Archive app — http://127.0.0.1:5000/")
    app.run(host="127.0.0.1", port=5000, debug=True)
