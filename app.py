import os
import sqlite3
import uuid
from io import BytesIO
from datetime import datetime
from urllib.parse import urlparse

import qrcode
from qrcode.image.svg import SvgPathImage
from flask import Flask, request, jsonify, send_from_directory, g, Response

DATA_DIR = "/data"
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
DB_PATH = os.path.join(DATA_DIR, "ecard.db")

os.makedirs(PHOTOS_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")

ALLOWED_PHOTO_EXT = {"png", "jpg", "jpeg", "webp"}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            ra TEXT NOT NULL,
            institute TEXT NOT NULL,
            photo_path TEXT,
            qr_link TEXT,
            qr_expiry TEXT
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "qr_link" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN qr_link TEXT")
    conn.commit()

    # Usuário de exemplo, sempre com dados genéricos.
    existing = conn.execute(
        "SELECT 1 FROM users WHERE username = ?", ("exemplo",)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, full_name, ra, institute, photo_path, qr_expiry) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "exemplo",
                "Nome Sobrenome do Aluno",
                "00000000",
                "Unidade de Ensino Exemplo",
                None,
                None,
            ),
        )
        conn.commit()
    conn.close()


def row_to_dict(row):
    return {
        "username": row["username"],
        "full_name": row["full_name"],
        "ra": row["ra"],
        "institute": row["institute"],
        "photo_url": f"/photos/{row['photo_path']}" if row["photo_path"] else None,
        "qr_link": row["qr_link"],
        "qr_expiry": row["qr_expiry"],
    }


def allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXT


def is_valid_qr_link(value):
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


# ---------- API ----------

@app.get("/api/users")
def api_list_users():
    db = get_db()
    rows = db.execute("SELECT * FROM users ORDER BY username").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.get("/api/users/<username>")
def api_get_user(username):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(row_to_dict(row))


@app.post("/api/users/<username>")
def api_upsert_user(username):
    """Cria ou edita um usuário. Sem senha/autenticação (mock interno)."""
    db = get_db()

    full_name = request.form.get("full_name", "").strip()
    ra = request.form.get("ra", "").strip()
    institute = request.form.get("institute", "").strip()
    qr_link = request.form.get("qr_link", "").strip()

    if not full_name or not ra or not institute or not qr_link:
        return jsonify({"error": "missing_fields"}), 400
    if not is_valid_qr_link(qr_link):
        return jsonify({"error": "invalid_qr_link"}), 400

    photo_filename = None
    photo_file = request.files.get("photo")
    if photo_file and photo_file.filename:
        if not allowed_photo(photo_file.filename):
            return jsonify({"error": "invalid_photo_type"}), 400
        ext = photo_file.filename.rsplit(".", 1)[1].lower()
        photo_filename = f"{username}-{uuid.uuid4().hex[:8]}.{ext}"
        photo_file.save(os.path.join(PHOTOS_DIR, photo_filename))

    existing = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if existing:
        old_photo = existing["photo_path"] if not photo_filename else photo_filename
        db.execute(
            "UPDATE users SET full_name=?, ra=?, institute=?, photo_path=?, qr_link=? WHERE username=?",
            (full_name, ra, institute, old_photo, qr_link, username),
        )
    else:
        db.execute(
            "INSERT INTO users (username, full_name, ra, institute, photo_path, qr_link, qr_expiry) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username, full_name, ra, institute, photo_filename, qr_link, None),
        )
    db.commit()

    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return jsonify(row_to_dict(row))


@app.get("/api/users/<username>/qr.svg")
def api_user_qr(username):
    db = get_db()
    row = db.execute("SELECT qr_link FROM users WHERE username = ?", (username,)).fetchone()
    if not row or not row["qr_link"]:
        return jsonify({"error": "qr_link_not_found"}), 404

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    qr.add_data(row["qr_link"])
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgPathImage)
    output = BytesIO()
    image.save(output)
    return Response(output.getvalue(), mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})


@app.post("/api/users/<username>/renew-qr")
def api_renew_qr(username):
    """Simula a renovação do token/QR: expira no fim do dia atual."""
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    if not row["qr_link"]:
        return jsonify({"error": "qr_link_not_found"}), 400

    new_expiry = datetime.now().strftime("%d/%m/%Y 23:59")
    db.execute(
        "UPDATE users SET qr_expiry=? WHERE username=?", (new_expiry, username)
    )
    db.commit()
    return jsonify({"qr_expiry": new_expiry})


@app.get("/photos/<path:filename>")
def serve_photo(filename):
    return send_from_directory(PHOTOS_DIR, filename)


@app.get("/manifest.webmanifest")
def serve_manifest():
    start_path = request.args.get("start", "/").strip() or "/"
    if not start_path.startswith("/"):
      start_path = "/" + start_path
    manifest = {
        "name": "e-Card",
        "short_name": "e-Card",
        "description": "Carteirinha digital e-Card para visualização de usuário e QR code.",
        "start_url": start_path,
        "scope": "/",
        "display": "standalone",
        "background_color": "#ff9e1b",
        "theme_color": "#038390",
        "icons": [
            {
                "src": "/icon-192.svg",
                "sizes": "192x192",
                "type": "image/svg+xml",
                "purpose": "any",
            },
            {
                "src": "/icon-512.svg",
                "sizes": "512x512",
                "type": "image/svg+xml",
                "purpose": "any",
            },
        ],
    }
    return jsonify(manifest)


# ---------- Front-end (SPA simples) ----------

@app.get("/")
def index_new_user():
    return app.send_static_file("index.html")


@app.get("/<username>")
def index_view_user(username):
    # Se for um arquivo estático de verdade (app.js, style.css, svgs, fotos...),
    # serve o arquivo em si em vez de cair no catch-all do SPA.
    static_path = os.path.join(app.static_folder, username)
    if os.path.isfile(static_path):
        return app.send_static_file(username)

    # Caso contrário, é uma rota de usuário (ex: /exemplo) — deixa o roteamento
    # de "existe ou não" pro JS do front, via /api/users/<username>
    return app.send_static_file("index.html")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
