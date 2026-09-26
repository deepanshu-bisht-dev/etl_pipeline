# ETL Control — Automated Data Pipeline & ETL System

A small but complete ETL platform: three messy raw CSV sources get
**extracted → transformed → validated → loaded** into a SQLite warehouse,
on a schedule or on demand, with a live control-room style dashboard to
watch it happen.

Built for the internship brief *"Automated Data Pipeline & ETL System"* —
no Airflow/Celery, no Postgres server, no Docker. It runs anywhere Python
runs, which matters for a short internship where the last thing you want
to debug is your own infrastructure.

---

## What it actually does

- **Extract** — reads `customers.csv`, `products.csv` and `transactions.csv`
  (generated automatically on first run, so there's real data immediately).
- **Transform** — deduplicates, trims whitespace, fixes casing, fills
  missing emails, corrects negative amounts, engineers a couple of derived
  columns (`full_name`, `unit_amount`).
- **Validate** — rule-based data-quality checks per source (missing keys,
  bad prices, unknown foreign keys). Rows that fail are **quarantined**,
  not silently dropped — you can see exactly what got rejected and why.
- **Load** — writes clean rows into a SQLite warehouse (`fact_customers`,
  `fact_products`, `fact_transactions`), and rejected rows into matching
  `_rejects` tables.
- **Schedule** — a lightweight background thread re-runs the whole
  pipeline automatically every N minutes (configurable), or you can
  trigger a run on demand from the dashboard.
- **Observe** — every run, every stage, every log line is recorded and
  shown live: a pipeline schematic, run history with per-stage timing,
  a data explorer for the warehouse, and a scrolling activity log.

## Why it's built this way (for your internship write-up)

| Concept asked for | Where it lives |
|---|---|
| ETL pipelines | `etl/extract.py`, `etl/transform.py`, `etl/validate.py`, `etl/load.py`, orchestrated in `etl/pipeline.py` |
| Scheduling | `scheduler.py` — a daemon thread, no external scheduler service |
| Data validation | `etl/validate.py` — rule-based checks with a quarantine table per source |
| Data engineering | Warehouse tables in `warehouse.db`, separate from the `control.db` run-history database |
| System automation | `run.py` bootstraps sample data → DB → seed run → scheduler → server in one command |

Deliberately **no Airflow**: Airflow's own dependency chain lags behind new
Python releases by months, which is a real risk if you're asked to run
this on Python 3.14 on demo day. A plain `threading` loop gives you the
same "runs automatically on a schedule" story without that risk, and it's
easy to explain and defend in a viva — you wrote every line of it.

---

## Requirements

- Python **3.10–3.14**
- `pip install -r requirements.txt` (just Flask and pandas — both ship
  Python 3.14 wheels)

## Run it

```bash
pip install -r requirements.txt
python run.py
```

Then open **http://localhost:5000**.

The first run will:
1. Generate the three sample source CSVs (deliberately a little messy —
   duplicates, missing emails, a few bad rows — so the dashboard has real
   validation failures to show, not a suspiciously perfect dataset).
2. Create `warehouse/control.db` and `warehouse/warehouse.db`.
3. Run the pipeline once so you land on a dashboard with real history.
4. Start the background scheduler (default: every 10 minutes).

## Project structure

```
etl_pipeline/
├── run.py                  entry point — start here
├── app.py                  Flask app: page + JSON endpoints for the dashboard
├── config.py                sources, schedule, ports — edit this to reconfigure
├── database.py               control-plane SQLite (run history, stage timings, logs)
├── scheduler.py              background thread that re-runs the pipeline on a timer
├── etl/
│   ├── extract.py            reads raw source files into DataFrames
│   ├── transform.py          per-source cleaning + feature engineering
│   ├── validate.py           per-source data-quality rules
│   ├── load.py                writes clean/rejected rows to the warehouse
│   └── pipeline.py            orchestrates the four stages, records everything
├── sample_data/
│   └── generate_sample_data.py   creates the demo CSVs on first run
├── warehouse/                 SQLite files live here (created at runtime)
├── templates/index.html       dashboard markup
└── static/css, static/js      dashboard styling + polling/rendering logic
```

## Using the dashboard

- **Overview** — the pipeline schematic animates while a run is in
  progress; the tiles below show lifetime stats.
- **Run history** — click any row to expand per-source, per-stage timing
  and detail (rows in/out, what was cleaned, why rows were rejected).
- **Data explorer** — pick a source and toggle between the clean rows
  that were loaded and the rows that were rejected, with the reason.
- **Sources** — drop in a replacement CSV for any source; the *next*
  pipeline run (manual or scheduled) will pick it up.
- **Activity log** — a live, color-coded trace of what each stage did,
  polling every 3 seconds.

## Extending it

- **New source**: add an entry to `SOURCES` in `config.py`, then add a
  `transform_<name>` function in `etl/transform.py` and a
  `validate_<name>` function in `etl/validate.py`. `extract.py` and
  `load.py` are already format-agnostic.
- **Real database instead of SQLite**: swap the `sqlite3.connect(...)`
  calls in `database.py` for a driver of your choice (e.g. `psycopg2` for
  Postgres) — the rest of the code only talks to the connection object.
- **A message queue instead of polling**: the dashboard currently polls
  `/api/status` and `/api/logs` every 3 seconds. That's intentional —
  it keeps the whole project dependency-free — but swapping in
  Server-Sent Events or WebSockets would be a good "v2" if you want to
  show that off separately.

## Notes on Python 3.14

Everything here uses only the standard library plus Flask and pandas —
both projects ship prebuilt wheels for 3.14, so `pip install` will not
try to compile anything from source. If you're on a machine where pip
still resolves an older pandas, upgrade pip first (`pip install -U pip`)
so it can see the newer wheels.
