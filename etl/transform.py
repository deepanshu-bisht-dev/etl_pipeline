"""
Transform stage — cleans and reshapes each source's DataFrame.

Every transform function takes a raw DataFrame and returns
(clean_df, notes) where `notes` is a short list of human-readable strings
describing what was changed, for the run log.
"""
import pandas as pd


def _generic_clean(df, notes):
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    if removed:
        notes.append(f"dropped {removed} exact duplicate row(s)")

    # trim whitespace on every text column
    text_cols = df.select_dtypes(include="object").columns
    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()
    return df


def transform_customers(df):
    notes = []
    df = _generic_clean(df, notes)

    df["city"] = df["city"].str.title()
    df["first_name"] = df["first_name"].str.title()
    df["last_name"] = df["last_name"].str.title()
    df["full_name"] = df["first_name"] + " " + df["last_name"]

    missing_email = df["email"].isin(["", "nan", "None"]) | df["email"].isna()
    n_missing = int(missing_email.sum())
    if n_missing:
        df.loc[missing_email, "email"] = "unknown@placeholder.local"
        notes.append(f"filled {n_missing} missing email address(es) with a placeholder")

    df["signup_date"] = pd.to_datetime(df["signup_date"], errors="coerce")
    df["customer_id"] = df["customer_id"].astype(int)
    return df, notes


def transform_products(df):
    notes = []
    df = _generic_clean(df, notes)
    df["category"] = df["category"].str.title()
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").round(2)
    df["product_id"] = df["product_id"].astype(int)
    return df, notes


def transform_transactions(df):
    notes = []
    df = _generic_clean(df, notes)

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    negative = df["amount"] < 0
    n_negative = int(negative.sum())
    if n_negative:
        df.loc[negative, "amount"] = df.loc[negative, "amount"].abs()
        notes.append(f"corrected {n_negative} negative amount(s) to their absolute value")

    df["transaction_ts"] = pd.to_datetime(df["transaction_ts"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["unit_amount"] = (df["amount"] / df["quantity"].replace(0, pd.NA)).round(2)
    df["transaction_id"] = df["transaction_id"].astype(int)
    df["customer_id"] = df["customer_id"].astype(int)
    df["product_id"] = df["product_id"].astype(int)
    return df, notes


TRANSFORMS = {
    "customers": transform_customers,
    "products": transform_products,
    "transactions": transform_transactions,
}


def transform(source_name, df):
    fn = TRANSFORMS.get(source_name)
    if fn is None:
        notes = []
        return _generic_clean(df, notes), notes
    return fn(df)
