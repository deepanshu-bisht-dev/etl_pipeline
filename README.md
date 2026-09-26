<div align="center">

# ⚙️ ETL Control — Automated Data Pipeline & ETL System

### Messy CSVs in. Clean warehouse out. Zero infrastructure headaches.

A small but complete ETL platform: three messy raw CSV sources get
**extracted → transformed → validated → loaded** into a SQLite warehouse,
on a schedule or on demand — with a live control-room style dashboard to
watch every stage happen in real time.

![Python](https://img.shields.io/badge/Python-3.10--3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=for-the-badge&logo=flask&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Processing-150458?style=for-the-badge&logo=pandas&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Warehouse-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![No Airflow](https://img.shields.io/badge/Dependencies-Zero%20Infra-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

</div>

---

## ⚡ Why this project?

Most "ETL project" tutorials mean one script that reads a CSV and prints
`df.head()`. **ETL Control** is the real thing: a proper four-stage pipeline
with **rule-based validation**, a **quarantine system** for bad rows (nothing
gets silently dropped), a **background scheduler** that reruns everything
automatically, and a live dashboard to actually watch it work.

And deliberately: **no Airflow, no Celery, no Postgres server, no Docker.**
Airflow's own dependencies lag behind new Python releases by months — a real
risk when you're demoing on the latest Python. A plain `threading` loop gives
you the same "runs on a schedule" story, with none of that risk, and every
line of it is something you can actually explain in a viva.

---

## 🖼️ Screenshots

> _Add your own dashboard screenshots/GIF here — the pipeline schematic
> animating live during a run is the money shot for LinkedIn._

<div align="center">

<!-- ![Dashboard Overview](docs/screenshot-overview.png) -->
<!-- ![Live Pipeline Run](docs/screenshot-run.gif) -->

**📸 Dashboard overview — _add screenshot here_**

**🎥 Live pipeline run — _add GIF here_**

</div>

---

## ✨ What it actually does

| | |
|---|---|
| 📥 | **Extract** — reads `customers.csv`, `products.csv`, `transactions.csv` (auto-generated on first run, so there's real data immediately) |
| 🧹 | **Transform** — deduplicates, trims whitespace, fixes casing, fills missing emails, corrects negative amounts, engineers derived columns |
| ✅ | **Validate** — rule-based data-quality checks per source; failing rows are **quarantined**, never silently dropped |
| 🏗️ | **Load** — writes clean rows into a SQLite warehouse, rejected rows into matching `_rejects` tables |
| ⏱️ | **Schedule** — a background thread reruns the whole pipeline every N minutes, or trigger a run on demand |
| 📊 | **Observe** — live pipeline schematic, run history with per-stage timing, a data explorer, and a scrolling activity log |

---

## 🛠️ Tech Stack

| Layer          | Technology                          |
|----------------|----------------------------------------|
| Backend        | Python, Flask                        |
| Data Processing| Pandas                               |
| Scheduling     | Python `threading` (no external service) |
| Database       | SQLite (separate control-plane + warehouse DBs) |
| Frontend       | HTML, CSS, JavaScript (vanilla)      |

---

## 📂 Project Structure

```
etl_pipeline/
├── run.py                    # Entry point — start here
├── app.py                    # Flask app: dashboard + JSON endpoints
├── config.py                  # Sources, schedule, ports — edit to reconfigure
├── database.py                 # Control-plane SQLite (run history, timings, logs)
├── scheduler.py                # Background thread — reruns pipeline on a timer
├── etl/
│   ├── extract.py              # Reads raw source files into DataFrames
│   ├── transform.py            # Per-source cleaning + feature engineering
│   ├── validate.py              # Per-source data-quality rules
│   ├── load.py                   # Writes clean/rejected rows to the warehouse
│   └── pipeline.py                # Orchestrates all four stages, records everything
├── sample_data/
│   └── generate_sample_data.py     # Creates demo CSVs on first run
├── warehouse/                    # SQLite files (created at runtime)
├── templates/index.html          # Dashboard markup
└── static/css, static/js         # Dashboard styling + polling/rendering logic
```

---

## 🚀 Getting Started

Everything here uses only the standard library plus Flask and Pandas —
both ship prebuilt wheels for **Python 3.14**, so `pip install` won't try
to compile anything from source.

```bash
# 1. Clone the repo
git clone https://github.com/deepanshu-bisht-dev/etl_pipeline.git
cd etl_pipeline

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run it
python run.py
```

Open **`http://localhost:5000`**. The first run will generate sample CSVs,
create the warehouse, run the pipeline once, and start the scheduler.

> If pip resolves an older pandas version on your machine, run
> `pip install -U pip` first so it can see the newer 3.14-compatible wheels.

---

## 🔍 How It Works

```
  extract.py         transform.py         validate.py            load.py
──────────────►   ──────────────►   ──────────────────►   ─────────────────►
 read raw CSVs      clean + engineer     quarantine bad rows   write to warehouse
                       features            (never dropped)      + _rejects tables
```

1. On startup, a background thread runs the pipeline once, then repeats it
   every N minutes (configurable in `config.py`)
2. `extract.py` reads the raw CSVs into Pandas DataFrames
3. `transform.py` cleans each source — dedup, trimming, casing, derived columns
4. `validate.py` runs rule-based checks; failures go to quarantine, not the void
5. `load.py` writes clean rows to the warehouse and rejects to `_rejects` tables
6. The dashboard polls `/api/status` and `/api/logs` every 3 seconds to show
   a live, color-coded trace of everything happening

---

## 🖥️ Using the Dashboard

- **Overview** — pipeline schematic animates during a run; tiles show lifetime stats
- **Run history** — click any row to expand per-source, per-stage timing and detail
- **Data explorer** — toggle between clean (loaded) rows and rejected rows, with reasons
- **Sources** — drop in a replacement CSV for any source; picked up on the next run
- **Activity log** — a live, color-coded trace of what each stage did

---

## 🧩 Extending It

- **New source** — add an entry to `SOURCES` in `config.py`, then add matching
  `transform_<name>` and `validate_<name>` functions
- **Real database instead of SQLite** — swap the `sqlite3.connect(...)` calls
  in `database.py` for a driver like `psycopg2` — the rest of the code only
  talks to the connection object
- **Push instead of poll** — the dashboard currently polls every 3 seconds by
  design (keeps it dependency-free); Server-Sent Events or WebSockets would be
  a good "v2" upgrade

---

## ⚠️ Notes & Honest Limitations

- This is a **local/demo tool**, not hardened for production — there's no
  authentication on any route
- CSV uploads are checked by file extension only; a stricter version would
  validate the actual content before overwriting a source file

---

## 📈 Roadmap

- [ ] Content-level CSV validation on upload, not just extension checking
- [ ] Server-Sent Events instead of polling for live updates
- [ ] Support for a real database backend (Postgres) as a drop-in option

---

<div align="center">

Built with ☕ and a strong opinion about not needing Airflow, by
**[Deepanshu Bisht](https://github.com/deepanshu-bisht-dev)**
as part of the Python Developer Internship at Codec Technologies.

⭐ If this helped you, consider starring the repo!

</div>
