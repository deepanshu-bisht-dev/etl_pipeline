"""
Central configuration for the ETL Control system.
Edit these values to point the pipeline at different sources,
change the schedule, or tighten validation rules.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Storage -----------------------------------------------------------
RAW_DATA_DIR = os.path.join(BASE_DIR, "sample_data")
WAREHOUSE_DB = os.path.join(BASE_DIR, "warehouse", "warehouse.db")
CONTROL_DB = os.path.join(BASE_DIR, "warehouse", "control.db")

# --- Sources -------------------------------------------------------------
# Each source is one raw file that gets extracted, cleaned, validated and
# loaded into its own warehouse table on every pipeline run.
SOURCES = [
    {
        "name": "customers",
        "file": os.path.join(RAW_DATA_DIR, "customers.csv"),
        "table": "fact_customers",
        "primary_key": "customer_id",
    },
    {
        "name": "transactions",
        "file": os.path.join(RAW_DATA_DIR, "transactions.csv"),
        "table": "fact_transactions",
        "primary_key": "transaction_id",
    },
    {
        "name": "products",
        "file": os.path.join(RAW_DATA_DIR, "products.csv"),
        "table": "fact_products",
        "primary_key": "product_id",
    },
]

# --- Scheduler -----------------------------------------------------------
# How often the pipeline runs automatically, in seconds. The dashboard can
# also trigger a run on demand at any time. Set to 0 to disable auto-runs.
AUTO_RUN_INTERVAL_SECONDS = 60 * 10  # every 10 minutes

# --- Web server ------------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False
