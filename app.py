"""
ETL Control — Flask backend.

Serves the dashboard UI and the small set of internal JSON endpoints the
dashboard's JavaScript polls to show live pipeline status. This is not a
public API product — it's the backend for the one bundled dashboard page.

Run with -  python run.py
"""
import os
import sqlite3

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

import config
import database
from etl.pipeline import run_pipeline_async, is_running

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload cap


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

@app.route("/")
def dashboard():
    return render_template("index.html", sources=config.SOURCES,
                            auto_interval=config.AUTO_RUN_INTERVAL_SECONDS)


# --------------------------------------------------------------------------
# Status & control
# --------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    return jsonify({
        "running": is_running(),
        "stats": database.get_stats(),
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    result = run_pipeline_async(trigger="manual")
    return jsonify(result)


@app.route("/api/runs")
def api_runs():
    limit = int(request.args.get("limit", 25))
    return jsonify(database.get_recent_runs(limit=limit))


@app.route("/api/runs/<int:run_id>")
def api_run_detail(run_id):
    run = database.get_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    run["stages"] = database.get_stages_for_run(run_id)
    return jsonify(run)


@app.route("/api/history")
def api_history():
    limit = int(request.args.get("limit", 20))
    return jsonify(database.get_run_history_series(limit=limit))


@app.route("/api/logs")
def api_logs():
    limit = int(request.args.get("limit", 150))
    run_id = request.args.get("run_id", type=int)
    return jsonify(database.get_recent_logs(limit=limit, run_id=run_id))


# --------------------------------------------------------------------------
# Data preview
# --------------------------------------------------------------------------

@app.route("/api/tables")
def api_tables():
    tables = []
    for source in config.SOURCES:
        tables.append({"source": source["name"], "table": source["table"],
                        "rejects_table": f"{source['table']}_rejects"})
    return jsonify(tables)


@app.route("/api/preview/<table_name>")
def api_preview(table_name):
    limit = int(request.args.get("limit", 50))
    valid_tables = set()
    for s in config.SOURCES:
        valid_tables.add(s["table"])
        valid_tables.add(f"{s['table']}_rejects")
    if table_name not in valid_tables:
        return jsonify({"error": "unknown table"}), 404

    if not os.path.exists(config.WAREHOUSE_DB):
        return jsonify({"columns": [], "rows": [], "row_count": 0})

    conn = database.get_warehouse_conn()
    try:
        cur = conn.execute(f'SELECT * FROM "{table_name}" LIMIT ?', (limit,))
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        count_row = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
        row_count = count_row[0]
    except sqlite3.OperationalError:
        cols, rows, row_count = [], [], 0
    finally:
        conn.close()
    return jsonify({"columns": cols, "rows": rows, "row_count": row_count})


# --------------------------------------------------------------------------
# Upload a replacement source file
# --------------------------------------------------------------------------

@app.route("/api/upload/<source_name>", methods=["POST"])
def api_upload(source_name):
    source = next((s for s in config.SOURCES if s["name"] == source_name), None)
    if not source:
        return jsonify({"error": "unknown source"}), 404

    if "file" not in request.files:
        return jsonify({"error": "no file provided"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"error": "only .csv files are accepted"}), 400

    filename = secure_filename(f.filename)
    dest = source["file"]
    f.save(dest)
    database.log(None, "info", f"New raw file uploaded for source '{source_name}' ({filename})")
    return jsonify({"ok": True, "message": f"Replaced source file for {source_name}"})


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
