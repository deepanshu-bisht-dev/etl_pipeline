"""
Validate stage — applies data-quality rules per source and splits each
DataFrame into rows that pass ("clean") and rows that fail ("rejected"),
each rejection tagged with the reason it was rejected.

This is intentionally rule-based and dependency-free (no external schema
library) so the project has no extra install beyond pandas.
"""
import pandas as pd


def _split(df, mask_valid, reason):
    """mask_valid is True for rows that pass. Returns (clean, rejected_with_reason)."""
    clean = df[mask_valid].copy()
    bad = df[~mask_valid].copy()
    if len(bad):
        bad["_rejection_reason"] = reason
    return clean, bad


def validate_customers(df):
    reasons = []
    valid = pd.Series(True, index=df.index)

    no_id = df["customer_id"].isna()
    valid &= ~no_id

    bad_signup = df["signup_date"].isna()
    valid &= ~bad_signup

    rejected_parts = []
    if no_id.any():
        rejected_parts.append(df[no_id].assign(_rejection_reason="missing customer_id"))
    if bad_signup.any():
        rejected_parts.append(df[bad_signup & ~no_id].assign(_rejection_reason="unparseable signup_date"))

    clean = df[valid].copy()
    rejected = pd.concat(rejected_parts) if rejected_parts else df.iloc[0:0].copy()
    return clean, rejected


def validate_products(df):
    valid = df["unit_price"].notna() & (df["unit_price"] > 0)
    return _split(df, valid, "missing or non-positive unit_price")


def validate_transactions(df, known_customer_ids=None, known_product_ids=None):
    valid = pd.Series(True, index=df.index)
    rejected_parts = []

    bad_amount = df["amount"].isna() | (df["amount"] <= 0)
    if bad_amount.any():
        rejected_parts.append(df[bad_amount].assign(_rejection_reason="missing or non-positive amount"))
    valid &= ~bad_amount

    bad_qty = df["quantity"] <= 0
    if bad_qty.any():
        rejected_parts.append(df[bad_qty & ~bad_amount].assign(_rejection_reason="non-positive quantity"))
    valid &= ~bad_qty

    if known_customer_ids is not None:
        unknown_cust = ~df["customer_id"].isin(known_customer_ids)
        if unknown_cust.any():
            rejected_parts.append(
                df[unknown_cust & ~bad_amount & ~bad_qty].assign(_rejection_reason="unknown customer_id")
            )
        valid &= ~unknown_cust

    clean = df[valid].copy()
    rejected = pd.concat(rejected_parts) if rejected_parts else df.iloc[0:0].copy()
    return clean, rejected


def validate(source_name, df, context=None):
    context = context or {}
    if source_name == "customers":
        return validate_customers(df)
    if source_name == "products":
        return validate_products(df)
    if source_name == "transactions":
        return validate_transactions(
            df,
            known_customer_ids=context.get("known_customer_ids"),
            known_product_ids=context.get("known_product_ids"),
        )
    # no rules defined for this source: everything passes
    return df, df.iloc[0:0].copy()
