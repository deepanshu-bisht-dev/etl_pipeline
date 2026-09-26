"""
Creates the three raw source CSVs the pipeline extracts from.

Data is generated once (if the files don't already exist) so the project
works immediately after cloning, with no external dataset to download.
The data is deliberately a little messy — duplicate rows, missing emails,
inconsistent casing, a few bad rows — so the transform/validate stages in
the dashboard have real work to show.
"""
import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

HERE = os.path.dirname(os.path.abspath(__file__))

FIRST_NAMES = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sara", "Imran",
               "Neha", "Kabir", "Zoya", "Arjun", "Diya", "Liam", "Emma", "Noah"]
LAST_NAMES = ["Sharma", "Verma", "Khan", "Patel", "Gupta", "Nair", "Iyer",
              "Reddy", "Singh", "Das", "Mehta", "Chowdhury"]
CITIES = ["Bareilly", "Lucknow", "Delhi", "Mumbai", "Pune", "Bengaluru",
          "Hyderabad", "Kolkata", "Jaipur", "Chandigarh"]
CATEGORIES = ["Electronics", "Home & Kitchen", "Fashion", "Books", "Sports",
              "Beauty", "Toys", "Grocery"]


def generate_customers(n=400, path=None):
    path = path or os.path.join(HERE, "customers.csv")
    rows = []
    for i in range(1, n + 1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@mail.com"
        # sprinkle in messiness for the transform stage to clean up
        if random.random() < 0.04:
            email = ""  # missing email
        city = random.choice(CITIES)
        if random.random() < 0.1:
            city = city.upper()  # inconsistent casing
        signup = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 900))
        rows.append({
            "customer_id": i,
            "first_name": first,
            "last_name": last,
            "email": email,
            "city": city,
            "signup_date": signup.strftime("%Y-%m-%d"),
        })
    # inject a handful of exact duplicate rows
    rows += random.sample(rows, k=max(1, n // 50))

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def generate_products(n=60, path=None):
    path = path or os.path.join(HERE, "products.csv")
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "product_id": i,
            "product_name": f"{random.choice(CATEGORIES)} Item {i}",
            "category": random.choice(CATEGORIES),
            "unit_price": round(random.uniform(99, 15000), 2),
        })
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def generate_transactions(n=1200, path=None, n_customers=400, n_products=60):
    path = path or os.path.join(HERE, "transactions.csv")
    rows = []
    start = datetime(2024, 1, 1)
    for i in range(1, n + 1):
        qty = random.randint(1, 5)
        cust = random.randint(1, n_customers)
        # a few rows reference a customer that doesn't exist, to give the
        # validation stage something real to reject
        if random.random() < 0.015:
            cust = n_customers + random.randint(1, 20)
        amount = round(random.uniform(99, 15000) * qty, 2)
        if random.random() < 0.01:
            amount = -amount  # bad data: negative amount
        ts = start + timedelta(minutes=random.randint(0, 60 * 24 * 300))
        rows.append({
            "transaction_id": i,
            "customer_id": cust,
            "product_id": random.randint(1, n_products),
            "quantity": qty,
            "amount": amount,
            "transaction_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
        })
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def ensure_sample_data():
    """Generate all three source files only if they're missing."""
    created = []
    cust_path = os.path.join(HERE, "customers.csv")
    prod_path = os.path.join(HERE, "products.csv")
    txn_path = os.path.join(HERE, "transactions.csv")

    if not os.path.exists(cust_path):
        generate_customers(path=cust_path)
        created.append(cust_path)
    if not os.path.exists(prod_path):
        generate_products(path=prod_path)
        created.append(prod_path)
    if not os.path.exists(txn_path):
        generate_transactions(path=txn_path)
        created.append(txn_path)
    return created


if __name__ == "__main__":
    made = ensure_sample_data()
    print(f"Generated {len(made)} sample files." if made else "Sample data already present.")
