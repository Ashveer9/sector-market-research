"""
Generates a synthetic Global Superstore-style dataset (1,500 rows).
Run this before executing the pipeline if you don't have a real Kaggle CSV.

Usage:
    python scripts/generate_sample_data.py [--rows 5000]
"""

import argparse
import random
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd


random.seed(42)
np.random.seed(42)

# ── Master data ──────────────────────────────────────────────────────────────

MARKETS = {
    "US": {"regions": ["East", "West", "Central", "South"], "countries": ["United States"]},
    "EU": {"regions": ["North", "South", "Central"], "countries": ["Germany", "France", "UK", "Italy", "Spain"]},
    "APAC": {"regions": ["Oceania", "Southeast Asia", "North Asia"], "countries": ["Australia", "Japan", "China", "India", "Singapore"]},
    "LATAM": {"regions": ["North", "South", "Caribbean"], "countries": ["Brazil", "Mexico", "Argentina", "Colombia"]},
    "Africa": {"regions": ["North Africa", "Sub-Saharan Africa"], "countries": ["Nigeria", "South Africa", "Egypt", "Kenya"]},
    "EMEA": {"regions": ["Middle East", "Eastern Europe"], "countries": ["UAE", "Saudi Arabia", "Poland", "Turkey"]},
    "Canada": {"regions": ["West", "East", "Central"], "countries": ["Canada"]},
}

SEGMENTS = ["Consumer", "Corporate", "Home Office"]

PRODUCTS = {
    "Technology": {
        "Phones": [
            ("TEC-PH-10001798", "Samsung Galaxy S10"),
            ("TEC-PH-10001829", "Apple iPhone 13"),
            ("TEC-PH-10004632", "Motorola Edge 30"),
            ("TEC-PH-10002035", "Cisco IP Phone 7942"),
        ],
        "Accessories": [
            ("TEC-AC-10003070", "Kensington USB Lock"),
            ("TEC-AC-10004633", "Belkin USB Hub"),
            ("TEC-AC-10001722", "Logitech Wireless Mouse"),
        ],
        "Machines": [
            ("TEC-MA-10001047", "Fellowes Laminating Machine"),
            ("TEC-MA-10004002", "Hewlett Packard LaserJet"),
            ("TEC-MA-10002412", "Zebra GK420t Printer"),
        ],
        "Copiers": [
            ("TEC-CO-10000786", "Canon imageCLASS D1420"),
            ("TEC-CO-10001645", "Samsung CLX-3185FW Wireless"),
        ],
    },
    "Furniture": {
        "Chairs": [
            ("FUR-CH-10000454", "Global Ergonomic Chair"),
            ("FUR-CH-10001215", "Hon 4070 Series Chair"),
            ("FUR-CH-10002647", "SAFCO Steel Folding Chair"),
        ],
        "Tables": [
            ("FUR-TA-10000198", "Bretford CR4500 Series Table"),
            ("FUR-TA-10001539", "Bevis Steel Folding Table"),
            ("FUR-TA-10002962", "Barricks Computer Table"),
        ],
        "Bookcases": [
            ("FUR-BO-10001798", "O'Sullivan Plantations Bookcase"),
            ("FUR-BO-10004834", "Bush Buffalo Bookcase"),
        ],
        "Furnishings": [
            ("FUR-FU-10000010", "Eldon Base Accessories Caddy"),
            ("FUR-FU-10001487", "Tennsco Steel Locker"),
        ],
    },
    "Office Supplies": {
        "Labels": [
            ("OFF-LA-10000240", "Avery 5-Tab Dividers"),
            ("OFF-LA-10003656", "Avery Thermal Labels"),
        ],
        "Storage": [
            ("OFF-ST-10000604", "Steelmaster Combination Lock"),
            ("OFF-ST-10002743", "Fellowes Black Plastic Caddies"),
            ("OFF-ST-10001546", "Storex Durable Binder"),
        ],
        "Art": [
            ("OFF-AR-10000058", "Newell 322"),
            ("OFF-AR-10001374", "Fiskars 8 Titanium Designer"),
            ("OFF-AR-10003068", "Acme Value Line Scissors"),
        ],
        "Binders": [
            ("OFF-BI-10001060", "Wilson Jones Active Use Binders"),
            ("OFF-BI-10003656", "GBC Binding Machine"),
            ("OFF-BI-10004098", "Avery Durable Slant Ring Binders"),
        ],
        "Paper": [
            ("OFF-PA-10000174", "Xerox 1894"),
            ("OFF-PA-10002005", "Hammermill Copy Plus Copy Paper"),
            ("OFF-PA-10003569", "Southworth 25% Cotton Paper"),
        ],
        "Fasteners": [
            ("OFF-FA-10000304", "Advantus Ring Panel Binders"),
            ("OFF-FA-10002080", "Acco 4-Hole Punch"),
        ],
        "Supplies": [
            ("OFF-SU-10000618", "Acco Perma 2700 Binder"),
            ("OFF-SU-10001741", "Holmes Replacement Filter Pads"),
        ],
        "Envelopes": [
            ("OFF-EN-10000927", "Jiffy Padded Mailers"),
            ("OFF-EN-10001600", "Wausau Papers Astrobrights Envelopes"),
        ],
    },
}

SHIP_MODES = ["First Class", "Second Class", "Standard Class", "Same Day"]
ORDER_PRIORITIES = ["Critical", "High", "Medium", "Low"]

# Pricing parameters per category
PRICING = {
    "Technology": {"base_sales": (50, 2000), "margin_range": (0.05, 0.35)},
    "Furniture": {"base_sales": (80, 1500), "margin_range": (-0.1, 0.3)},
    "Office Supplies": {"base_sales": (5, 300), "margin_range": (0.1, 0.45)},
}

US_CITIES = [
    ("New York", "New York", "10001"), ("Los Angeles", "California", "90001"),
    ("Chicago", "Illinois", "60601"), ("Houston", "Texas", "77001"),
    ("Phoenix", "Arizona", "85001"), ("Philadelphia", "Pennsylvania", "19101"),
    ("San Antonio", "Texas", "78201"), ("San Diego", "California", "92101"),
    ("Dallas", "Texas", "75201"), ("San Jose", "California", "95101"),
]


def generate_dataset(n_rows: int = 1500) -> pd.DataFrame:
    rows = []
    order_num = 10000
    customer_counter = 1
    customer_pool: dict[str, tuple] = {}

    n_customers = max(100, n_rows // 8)
    for i in range(n_customers):
        cid = f"CG-{random.randint(10000, 99999)}"
        seg = random.choice(SEGMENTS)
        fname = random.choice(["James", "Sarah", "Michael", "Emma", "David", "Olivia", "John", "Sophia"])
        lname = random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"])
        customer_pool[cid] = (f"{fname} {lname}", seg)

    customer_ids = list(customer_pool.keys())

    start_date = date(2011, 1, 1)
    end_date = date(2014, 12, 31)
    date_range = (end_date - start_date).days

    for _ in range(n_rows):
        # Order header
        order_num += random.randint(1, 10)
        order_id = f"CA-{random.randint(2011, 2014)}-{order_num}"
        order_dt = start_date + timedelta(days=random.randint(0, date_range))

        ship_mode = random.choice(SHIP_MODES)
        ship_delta = {"First Class": (2, 3), "Second Class": (3, 5), "Standard Class": (5, 7), "Same Day": (0, 1)}
        lo, hi = ship_delta[ship_mode]
        ship_dt = order_dt + timedelta(days=random.randint(lo, hi))

        # Customer
        cust_id = random.choice(customer_ids)
        cust_name, segment = customer_pool[cust_id]

        # Geography
        market = random.choice(list(MARKETS.keys()))
        market_data = MARKETS[market]
        country = random.choice(market_data["countries"])
        region = random.choice(market_data["regions"])

        if country == "United States":
            city_data = random.choice(US_CITIES)
            city, state, postal_code = city_data
        else:
            city = f"{country} City {random.randint(1, 5)}"
            state = f"Province {random.randint(1, 10)}"
            postal_code = str(random.randint(10000, 99999))

        # Product
        cat = random.choice(list(PRODUCTS.keys()))
        sub_cats = list(PRODUCTS[cat].keys())
        sub_cat = random.choice(sub_cats)
        product_id, product_name = random.choice(PRODUCTS[cat][sub_cat])

        # Financials
        p_params = PRICING[cat]
        base_sales = round(random.uniform(*p_params["base_sales"]), 2)
        quantity = random.choices([1, 2, 3, 5, 7, 10], weights=[40, 25, 15, 10, 7, 3])[0]

        # Discount: Consumer gets more, Corporate less
        discount_prob = {"Consumer": 0.35, "Corporate": 0.20, "Home Office": 0.25}
        if random.random() < discount_prob[segment]:
            discount = round(random.choice([0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]), 2)
        else:
            discount = 0.0

        sales = round(base_sales * quantity * (1 - discount), 2)
        margin = random.uniform(*p_params["margin_range"])
        # Higher discounts hurt margin
        margin -= discount * 0.6
        profit = round(sales * margin, 2)
        shipping_cost = round(random.uniform(2.5, max(3.0, sales * 0.05)), 2)

        priority = random.choices(
            ORDER_PRIORITIES, weights=[5, 15, 45, 35]
        )[0]

        rows.append({
            "Row ID": len(rows) + 1,
            "Order ID": order_id,
            "Order Date": order_dt.strftime("%d/%m/%Y"),
            "Ship Date": ship_dt.strftime("%d/%m/%Y"),
            "Ship Mode": ship_mode,
            "Customer ID": cust_id,
            "Customer Name": cust_name,
            "Segment": segment,
            "City": city,
            "State": state,
            "Country": country,
            "Postal Code": postal_code,
            "Market": market,
            "Region": region,
            "Product ID": product_id,
            "Category": cat,
            "Sub-Category": sub_cat,
            "Product Name": product_name,
            "Sales": sales,
            "Quantity": quantity,
            "Discount": discount,
            "Profit": profit,
            "Shipping Cost": shipping_cost,
            "Order Priority": priority,
        })

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Global Superstore data")
    parser.add_argument("--rows", type=int, default=1500, help="Number of rows to generate")
    parser.add_argument("--output", type=str, default="data/sample/global_superstore.csv")
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.rows} rows of Global Superstore data...")
    df = generate_dataset(args.rows)
    df.to_csv(out_path, index=False)

    print(f"✓ Saved {len(df)} rows to {out_path}")
    print(f"  Markets: {df['Market'].unique().tolist()}")
    print(f"  Date range: {df['Order Date'].min()} → {df['Order Date'].max()}")
    print(f"  Total Sales: ${df['Sales'].sum():,.2f}")
    print(f"  Total Profit: ${df['Profit'].sum():,.2f}")


if __name__ == "__main__":
    main()
