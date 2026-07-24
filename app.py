import os
import sqlite3
import uuid
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory, g

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
            qr_expiry TEXT
        )
        """
    )
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
        "qr_expiry": row["qr_expiry"],
    }


def allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXT


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

    if not full_name or not ra or not institute:
        return jsonify({"error": "missing_fields"}), 400

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
            "UPDATE users SET full_name=?, ra=?, institute=?, photo_path=? WHERE username=?",
            (full_name, ra, institute, old_photo, username),
        )
    else:
        db.execute(
            "INSERT INTO users (username, full_name, ra, institute, photo_path, qr_expiry) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, full_name, ra, institute, photo_filename, None),
        )
    db.commit()

    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return jsonify(row_to_dict(row))


@app.post("/api/users/<username>/renew-qr")
def api_renew_qr(username):
    """Simula a renovação do token/QR: define nova data de expiração (+3 dias)."""
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404

    new_expiry = (datetime.now() + timedelta(days=3)).strftime("%d/%m/%Y 23:59")
    db.execute(
        "UPDATE users SET qr_expiry=? WHERE username=?", (new_expiry, username)
    )
    db.commit()
    return jsonify({"qr_expiry": new_expiry})


@app.get("/photos/<path:filename>")
def serve_photo(filename):
    return send_from_directory(PHOTOS_DIR, filename)


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