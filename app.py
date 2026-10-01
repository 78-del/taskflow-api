"""TaskFlow API: a small REST service used as the case study."""
import hmac
import os
import sqlite3

from flask import Flask, g, jsonify, request

MAX_TITLE_LENGTH = 100


def create_app(db_path=None):
    app = Flask(__name__)
    default_db = os.environ.get("TASKFLOW_DB", "taskflow.db")
    app.config["DATABASE"] = db_path or default_db
    app.config["API_KEY"] = os.environ.get("TASKFLOW_API_KEY", "")

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, "
            "done INTEGER NOT NULL DEFAULT 0)"
        )

    @app.before_request
    def require_api_key():
        if request.path == "/health":
            return None
        expected = app.config["API_KEY"]
        supplied = request.headers.get("X-API-Key", "")
        # Fail closed: if no key is configured, nothing is authorised.
        if not expected or not hmac.compare_digest(
            supplied.encode("utf-8"), expected.encode("utf-8")
        ):
            return jsonify(error="unauthorised"), 401
        return None

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/tasks")
    def list_tasks():
        term = request.args.get("q", "")
        rows = get_db().execute(
            "SELECT id, title, done FROM tasks WHERE title LIKE ? ORDER BY id",
            (f"%{term}%",),
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.post("/tasks")
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        ok = isinstance(title, str)
        ok = ok and 1 <= len(title.strip()) <= MAX_TITLE_LENGTH
        if not ok:
            return jsonify(error="title must be 1-100 characters"), 400
        db = get_db()
        cur = db.execute(
            "INSERT INTO tasks (title) VALUES (?)", (title.strip(),)
        )
        db.commit()
        return jsonify(id=cur.lastrowid, title=title.strip(), done=0), 201

    @app.patch("/tasks/<int:task_id>")
    def update_task(task_id):
        data = request.get_json(silent=True) or {}
        done = data.get("done")
        if not isinstance(done, bool):
            return jsonify(error="done must be true or false"), 400
        db = get_db()
        cur = db.execute(
            "UPDATE tasks SET done = ? WHERE id = ?", (int(done), task_id)
        )
        db.commit()
        if cur.rowcount == 0:
            return jsonify(error="not found"), 404
        return jsonify(id=task_id, done=int(done))

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        db = get_db()
        cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(error="not found"), 404
        return "", 204

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
