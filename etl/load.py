"""Load stage — writes clean data into the warehouse and quarantines rejects."""
import pandas as pd


def load(conn, table_name, clean_df, rejected_df=None):
    """Replace `table_name` in the warehouse with the clean rows for this run,
    and write any rejected rows to `<table_name>_rejects` so they're visible
    in the dashboard rather than silently dropped.
    """
    clean_df.to_sql(table_name, conn, if_exists="replace", index=False)

    if rejected_df is not None and len(rejected_df):
        rejected_df.to_sql(f"{table_name}_rejects", conn, if_exists="replace", index=False)
    else:
        # keep an (empty) rejects table so the dashboard can always query it
        cols = list(clean_df.columns) + ["_rejection_reason"]
        pd.DataFrame(columns=cols).to_sql(f"{table_name}_rejects", conn, if_exists="replace", index=False)

    conn.commit()
    return len(clean_df), len(rejected_df) if rejected_df is not None else 0
