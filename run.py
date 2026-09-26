"""
Entry point. Run with:

    python run.py

This will:
  1. Generate sample raw CSVs if they don't exist yet (so there's real
     data to process immediately).
  2. Initialize the control-plane SQLite database.
  3. Run the pipeline once so the dashboard opens with real history.
  4. Start the background scheduler for automatic runs.
  5. Start the Flask web server.

Then open http://localhost:5000 in a browser.
"""
import sys

import config
import database
import scheduler
from sample_data.generate_sample_data import ensure_sample_data
from etl.pipeline import run_pipeline


def bootstrap():
    print("ETL Control — starting up")

    created = ensure_sample_data()
    if created:
        print(f"  generated {len(created)} sample source file(s)")
    else:
        print("  sample source files already present")

    database.init_db()
    print("  control database ready")

    print("  running pipeline once to seed the warehouse...")
    result = run_pipeline(trigger="startup")
    print(f"  seed run finished: status={result.get('status')} "
          f"loaded={result.get('rows_loaded')} rejected={result.get('rows_rejected')}")

    scheduler.start()
    if config.AUTO_RUN_INTERVAL_SECONDS:
        print(f"  scheduler started — auto-run every {config.AUTO_RUN_INTERVAL_SECONDS}s")
    else:
        print("  scheduler disabled (AUTO_RUN_INTERVAL_SECONDS=0)")


if __name__ == "__main__":
    bootstrap()

    from app import app
    print(f"\n  Dashboard: http://localhost:{config.PORT}\n")
    try:
        app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
    except KeyboardInterrupt:
        sys.exit(0)
