"""Extract stage — pulls raw data from each configured source file."""
import pandas as pd


def extract(source):
    """Read a source's raw file into a DataFrame.

    Currently supports CSV files. Adding a new format (JSON, an API, a
    database table) means adding a branch here — the rest of the pipeline
    (transform/validate/load) is format-agnostic once it has a DataFrame.
    """
    path = source["file"]
    if path.endswith(".csv"):
        df = pd.read_csv(path)
    elif path.endswith(".json"):
        df = pd.read_json(path)
    else:
        raise ValueError(f"Unsupported source file type: {path}")
    return df
