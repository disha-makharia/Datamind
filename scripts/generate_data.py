"""
Generate the NovaMart dummy dataset for DataMind.

NovaMart is a fictional Indian omnichannel retailer. The data is random but
has deliberate "stories" baked in, and the PDFs in docs/ explain them. That
lets you test both agents together:
  SQL agent finds WHAT happened, RAG agent finds WHY.

  1. West-region Electronics sales drop (Jul 8 - Sep 20, 2025)
     -> Bhiwandi warehouse flood (Q3 2025 Business Review)
  2. Big Electronics + Fashion spike Oct 15 - Nov 15, 2025
     -> "Festive Dhamaka 2025" campaign (Campaign Report)
  3. NovaSound X2 Earbuds return spike Apr-Jun 2025
     -> battery defect, batch B-0325 (Quality & Returns Memo)
  4. South region growth from Feb 2025
     -> 2 new stores in Bengaluru and Chennai (Expansion Update)
  5. Home & Kitchen bump every Apr-May (summer: fans, RO purifiers)

Run:  python scripts/generate_data.py
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
random.seed(SEED)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SAMPLE_DIR = ROOT / "sample_files"
DATA_DIR.mkdir(exist_ok=True)
SAMPLE_DIR.mkdir(exist_ok=True)

START, END = date(2024, 1, 1), date(2025, 12, 31)

# ---------------------------------------------------------------- products
# (name, category, brand, unit_price, cost_price, launch_date)
PRODUCTS_RAW = [
    ("Nova Smart TV 43 inch", "Electronics", "Nova", 29999, 23500, "2023-06-01"),
    ("Nova Smart TV 55 inch", "Electronics", "Nova", 45999, 36800, "2023-06-01"),
    ("NovaSound X2 Earbuds", "Electronics", "NovaSound", 2499, 1350, "2025-03-01"),
    ("NovaSound Pro Headphones", "Electronics", "NovaSound", 5999, 3900, "2023-01-15"),
    ("Nova Phone A15", "Electronics", "Nova", 14999, 12200, "2023-09-01"),
    ("Nova Phone A25 Pro", "Electronics", "Nova", 24999, 19800, "2024-02-01"),
    ("Nova Tab 10", "Electronics", "Nova", 17999, 14100, "2023-11-01"),
    ("PowerMax 20000mAh Power Bank", "Electronics", "PowerMax", 1799, 950, "2022-05-01"),
    ("Nova Smartwatch Fit", "Electronics", "Nova", 3999, 2400, "2023-08-01"),
    ("Nova Laptop Air 14", "Electronics", "Nova", 54999, 45500, "2024-01-10"),
    ("AquaPure RO Water Purifier", "Home & Kitchen", "AquaPure", 12999, 8900, "2022-03-01"),
    ("ChefPro Mixer Grinder 750W", "Home & Kitchen", "ChefPro", 3499, 2200, "2022-01-01"),
    ("ChefPro Air Fryer 4L", "Home & Kitchen", "ChefPro", 5499, 3600, "2023-04-01"),
    ("SteelCraft Cookware Set", "Home & Kitchen", "SteelCraft", 2999, 1750, "2022-01-01"),
    ("BreezeMax BLDC Ceiling Fan", "Home & Kitchen", "BreezeMax", 3799, 2500, "2023-02-01"),
    ("CozyHome Cotton Bedsheet Set", "Home & Kitchen", "CozyHome", 1299, 650, "2022-01-01"),
    ("Men's Cotton Kurta", "Fashion", "Rangrez", 899, 380, "2022-01-01"),
    ("Women's Banarasi Silk Saree", "Fashion", "Rangrez", 3499, 1900, "2022-01-01"),
    ("Slim Fit Denim Jeans", "Fashion", "UrbanThread", 1499, 700, "2022-01-01"),
    ("Stride Running Shoes", "Fashion", "Stride", 2799, 1500, "2023-01-01"),
    ("Classic Leather Wallet", "Fashion", "UrbanThread", 699, 280, "2022-01-01"),
    ("Festive Lehenga Choli", "Fashion", "Rangrez", 6999, 3900, "2023-08-01"),
    ("Royal Basmati Rice 5kg", "Grocery", "Annapurna", 649, 520, "2022-01-01"),
    ("Cold Pressed Groundnut Oil 1L", "Grocery", "Annapurna", 289, 225, "2022-01-01"),
    ("Premium Dry Fruits Box 500g", "Grocery", "Annapurna", 899, 610, "2022-01-01"),
    ("Assam Masala Chai 250g", "Grocery", "ChaiGhar", 199, 120, "2022-01-01"),
    ("Organic Whole Wheat Atta 10kg", "Grocery", "Annapurna", 549, 430, "2022-01-01"),
    ("Neem Herbal Face Wash", "Beauty", "Vedika", 249, 110, "2022-01-01"),
    ("Vitamin C Face Serum", "Beauty", "Vedika", 699, 290, "2023-03-01"),
    ("Onion Hair Oil 200ml", "Beauty", "Vedika", 349, 150, "2022-01-01"),
    ("SunShield Sunscreen SPF50", "Beauty", "Vedika", 449, 200, "2022-06-01"),
    ("Oud Royale Perfume 100ml", "Beauty", "Attar House", 1999, 900, "2023-10-01"),
]
products = []
for i, (name, cat, brand, price, cost, launch) in enumerate(PRODUCTS_RAW, 1):
    products.append(dict(product_id=f"P{i:03d}", product_name=name, category=cat,
                         brand=brand, unit_price=price, cost_price=cost, launch_date=launch))
products_df = pd.DataFrame(products)
EARBUDS_ID = products_df.loc[products_df.product_name == "NovaSound X2 Earbuds", "product_id"].item()

# ------------------------------------------------------------------ stores
STORES_RAW = [
    ("S00", "NovaMart Online", "Mumbai", "National", "Online", "2019-01-01"),
    ("S01", "NovaMart Andheri", "Mumbai", "West", "Mall", "2019-04-12"),
    ("S02", "NovaMart Thane", "Thane", "West", "High Street", "2020-01-20"),
    ("S03", "NovaMart Kothrud", "Pune", "West", "High Street", "2020-08-15"),
    ("S04", "NovaMart SG Highway", "Ahmedabad", "West", "Mall", "2021-03-05"),
    ("S05", "NovaMart Connaught Place", "Delhi", "North", "High Street", "2019-06-01"),
    ("S06", "NovaMart Cyber Hub", "Gurugram", "North", "Mall", "2020-11-11"),
    ("S07", "NovaMart Hazratganj", "Lucknow", "North", "High Street", "2021-07-01"),
    ("S08", "NovaMart Koramangala", "Bengaluru", "South", "Mall", "2021-01-26"),
    ("S09", "NovaMart Whitefield", "Bengaluru", "South", "Mall", "2025-02-10"),
    ("S10", "NovaMart T Nagar", "Chennai", "South", "High Street", "2025-02-24"),
    ("S11", "NovaMart Banjara Hills", "Hyderabad", "South", "Mall", "2020-02-14"),
    ("S12", "NovaMart Salt Lake", "Kolkata", "East", "Mall", "2020-10-02"),
    ("S13", "NovaMart Saheed Nagar", "Bhubaneswar", "East", "High Street", "2022-04-14"),
]
stores_df = pd.DataFrame(STORES_RAW, columns=["store_id", "store_name", "city", "region",
                                              "store_type", "opened_date"])
CITY_REGION = {r[2]: r[3] for r in STORES_RAW if r[3] != "National"}
CITY_REGION["Chennai"] = "South"

# --------------------------------------------------------------- customers
FIRST = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Ishaan", "Kabir", "Siddharth", "Rahul",
         "Karan", "Priya", "Ananya", "Diya", "Isha", "Kavya", "Meera", "Neha", "Pooja", "Riya",
         "Sneha", "Tanvi", "Aditi", "Farhan", "Imran", "Zoya", "Sana", "Joseph", "Maria",
         "Harpreet", "Gurpreet", "Lakshmi", "Venkat", "Suresh", "Divya", "Arnav", "Nikhil"]
LAST = ["Sharma", "Patel", "Deshmukh", "Kulkarni", "Iyer", "Nair", "Reddy", "Gupta", "Singh",
        "Khan", "Mehta", "Joshi", "Shah", "Rao", "Das", "Banerjee", "Menon", "Pillai",
        "Chatterjee", "Verma", "Kapoor", "Fernandes", "D'Souza", "Gill", "Mishra", "Jain"]
REGION_CITIES = {}
for city, reg in CITY_REGION.items():
    REGION_CITIES.setdefault(reg, []).append(city)

customers = []
for i in range(1, 1501):
    region = random.choices(["West", "North", "South", "East"], [0.34, 0.28, 0.26, 0.12])[0]
    city = random.choice(REGION_CITIES[region])
    signup = START - timedelta(days=random.randint(0, 900)) + timedelta(days=random.randint(0, 600))
    customers.append(dict(
        customer_id=f"C{i:04d}",
        customer_name=f"{random.choice(FIRST)} {random.choice(LAST)}",
        gender=random.choice(["Male", "Female"]),
        age=random.randint(18, 65),
        city=city, region=region,
        segment=random.choices(["New", "Regular", "Premium"], [0.3, 0.5, 0.2])[0],
        signup_date=signup.isoformat(),
    ))
customers_df = pd.DataFrame(customers)
CUST_BY_REGION = {r: customers_df[customers_df.region == r].to_dict("records")
                  for r in ["West", "North", "South", "East"]}

# ----------------------------------------------------- marketing campaigns
campaigns = [
    dict(campaign_id="CMP01", campaign_name="New Year Bonanza 2024", start_date="2024-01-01",
         end_date="2024-01-10", channel="Social Media", target_category="All",
         target_region="All", budget_inr=1500000),
    dict(campaign_id="CMP02", campaign_name="Summer Cool Deals 2024", start_date="2024-04-01",
         end_date="2024-05-31", channel="TV + Online", target_category="Home & Kitchen",
         target_region="All", budget_inr=2500000),
    dict(campaign_id="CMP03", campaign_name="Diwali Utsav 2024", start_date="2024-10-20",
         end_date="2024-11-10", channel="TV + Online + In-Store", target_category="Electronics",
         target_region="All", budget_inr=5500000),
    dict(campaign_id="CMP04", campaign_name="Republic Day Sale 2025", start_date="2025-01-20",
         end_date="2025-01-27", channel="Online", target_category="All",
         target_region="All", budget_inr=1200000),
    dict(campaign_id="CMP05", campaign_name="NovaSound X2 Launch", start_date="2025-03-01",
         end_date="2025-03-31", channel="Social Media + Influencers",
         target_category="Electronics", target_region="All", budget_inr=1800000),
    dict(campaign_id="CMP06", campaign_name="Summer Cool Deals 2025", start_date="2025-04-01",
         end_date="2025-05-31", channel="TV + Online", target_category="Home & Kitchen",
         target_region="All", budget_inr=2800000),
    dict(campaign_id="CMP07", campaign_name="South Store Opening Offers", start_date="2025-02-10",
         end_date="2025-03-15", channel="In-Store + Local Print", target_category="All",
         target_region="South", budget_inr=900000),
    dict(campaign_id="CMP08", campaign_name="Festive Dhamaka 2025", start_date="2025-10-15",
         end_date="2025-11-15", channel="TV + Online + In-Store",
         target_category="Electronics, Fashion", target_region="All", budget_inr=8500000),
    dict(campaign_id="CMP09", campaign_name="Year End Clearance 2025", start_date="2025-12-20",
         end_date="2025-12-31", channel="Online", target_category="All",
         target_region="All", budget_inr=1000000),
]


# ------------------------------------------------------------------ orders
def between(d, a, b):
    return date.fromisoformat(a) <= d <= date.fromisoformat(b)


CAT_WEIGHTS = {"Electronics": 0.30, "Home & Kitchen": 0.18, "Fashion": 0.22,
               "Grocery": 0.18, "Beauty": 0.12}
PAYMENTS = (["UPI", "Credit Card", "Debit Card", "Cash on Delivery", "Net Banking", "Wallet"],
            [0.42, 0.16, 0.12, 0.14, 0.08, 0.08])


def category_weights(d):
    w = dict(CAT_WEIGHTS)
    if d.month in (4, 5):                                   # story 5: summer
        w["Home & Kitchen"] *= 1.5
    if between(d, "2024-10-20", "2024-11-10"):              # Diwali 2024
        w["Electronics"] *= 1.5; w["Fashion"] *= 1.4
    if between(d, "2025-10-15", "2025-11-15"):              # story 2: Festive Dhamaka
        w["Electronics"] *= 2.2; w["Fashion"] *= 1.8
    return w


def orders_for_day(d):
    base = 13 if d.year == 2024 else 15                     # ~12% YoY growth
    if d.weekday() >= 5:
        base += 3
    if between(d, "2024-10-20", "2024-11-10"):
        base = int(base * 1.4)
    if between(d, "2025-10-15", "2025-11-15"):
        base = int(base * 1.9)
    if between(d, "2025-12-20", "2025-12-31") or between(d, "2025-01-20", "2025-01-27"):
        base = int(base * 1.2)
    return max(1, int(random.gauss(base, 2.5)))


def region_weights(d):
    if d >= date(2025, 2, 10):                              # story 4: new South stores
        return [0.29, 0.26, 0.36, 0.09]
    return [0.34, 0.28, 0.26, 0.12]


def discount_for(d, category):
    if between(d, "2025-10-15", "2025-11-15") and category in ("Electronics", "Fashion"):
        return random.choice([15, 20, 20, 25])
    if between(d, "2024-10-20", "2024-11-10") and category == "Electronics":
        return random.choice([10, 15, 15, 20])
    if d.month in (4, 5) and category == "Home & Kitchen":
        return random.choice([5, 10, 10, 15])
    return random.choices([0, 5, 10], [0.6, 0.25, 0.15])[0]


orders, returns = [], []
oid = rid = 0
d = START
while d <= END:
    live_products = products_df[pd.to_datetime(products_df.launch_date).dt.date <= d]
    cw = category_weights(d)
    for _ in range(orders_for_day(d)):
        region = random.choices(["West", "North", "South", "East"], region_weights(d))[0]
        cust = random.choice(CUST_BY_REGION[region])
        channel = "Online" if random.random() < (0.32 if d.year == 2024 else 0.38) else "In-Store"
        if channel == "Online":
            store_id = "S00"
        else:
            open_stores = stores_df[(stores_df.region == region) &
                                    (pd.to_datetime(stores_df.opened_date).dt.date <= d)]
            same_city = open_stores[open_stores.city == cust["city"]]
            store_id = random.choice((same_city if len(same_city) else open_stores).store_id.tolist())

        cats = list(cw.keys())
        category = random.choices(cats, [cw[c] for c in cats])[0]

        # story 1: Bhiwandi flood -> West electronics stock-outs
        if (category == "Electronics" and region == "West"
                and between(d, "2025-07-08", "2025-09-20") and random.random() < 0.6):
            category = random.choice(["Grocery", "Beauty", "Fashion"])

        pool = live_products[live_products.category == category]
        # NovaSound X2 is a cheap, heavily promoted launch -> sells ~4x a normal SKU
        weights = [4.0 if pid == EARBUDS_ID else 1.0 for pid in pool.product_id]
        prod = pool.iloc[random.choices(range(len(pool)), weights)[0]]
        qty = random.choices([1, 2, 3, 4], [0.55, 0.28, 0.12, 0.05])[0] \
            if category in ("Grocery", "Beauty") else random.choices([1, 2], [0.85, 0.15])[0]
        disc = discount_for(d, category)
        price = int(prod.unit_price)
        total = round(qty * price * (1 - disc / 100), 2)
        oid += 1
        order_id = f"ORD{oid:06d}"
        orders.append(dict(order_id=order_id, order_date=d.isoformat(), customer_id=cust["customer_id"],
                           product_id=prod.product_id, store_id=store_id, channel=channel,
                           quantity=qty, unit_price=price, discount_pct=disc, total_amount=total,
                           payment_method=random.choices(*PAYMENTS)[0]))

        # returns (story 3: earbuds battery defect Apr-Jun 2025)
        if prod.product_id == EARBUDS_ID:
            rate = 0.30 if between(d, "2025-03-20", "2025-06-30") else 0.04
            reasons = (["Battery drains quickly", "Not charging", "Damaged in transit"], [0.6, 0.3, 0.1]) \
                if rate > 0.1 else (["Changed mind", "Damaged in transit", "Battery drains quickly"], [0.5, 0.3, 0.2])
        elif category == "Fashion":
            rate, reasons = 0.07, (["Size issue", "Colour different from image", "Changed mind"], [0.55, 0.25, 0.2])
        elif category == "Grocery":
            rate, reasons = 0.01, (["Damaged packaging", "Expired product"], [0.7, 0.3])
        else:
            rate, reasons = 0.03, (["Defective product", "Damaged in transit", "Changed mind"], [0.4, 0.35, 0.25])
        if random.random() < rate:
            rid += 1
            rdate = d + timedelta(days=random.randint(2, 9))
            if rdate <= END + timedelta(days=10):
                returns.append(dict(return_id=f"RET{rid:05d}", order_id=order_id,
                                    return_date=rdate.isoformat(),
                                    reason=random.choices(*reasons)[0],
                                    refund_amount=total,
                                    status=random.choices(["Refunded", "Replaced"], [0.8, 0.2])[0]))
    d += timedelta(days=1)

sales_df = pd.DataFrame(orders)
returns_df = pd.DataFrame(returns)

# ------------------------------------------------------------------ write
sales_df.to_csv(DATA_DIR / "sales.csv", index=False)
products_df.to_csv(DATA_DIR / "products.csv", index=False)
customers_df.to_csv(DATA_DIR / "customers.csv", index=False)
stores_df.to_csv(DATA_DIR / "stores.csv", index=False)
returns_df.to_csv(DATA_DIR / "returns.csv", index=False)
with open(DATA_DIR / "marketing_campaigns.json", "w") as f:
    json.dump(campaigns, f, indent=2)

# Excel workbook: same data, one sheet per table, plus a data dictionary.
dictionary = pd.DataFrame([
    ("sales", "One row per order line. total_amount = quantity * unit_price * (1 - discount_pct/100). Revenue in INR."),
    ("products", "Product master: category, brand, list price and cost price (INR)."),
    ("customers", "Customer master with home city / region and segment."),
    ("stores", "Store master. store_id S00 is the online channel (region = National)."),
    ("returns", "Returned orders; join to sales on order_id."),
    ("marketing_campaigns", "Campaign calendar with budgets (INR)."),
], columns=["table", "description"])
with pd.ExcelWriter(SAMPLE_DIR / "NovaMart_Retail_Data.xlsx", engine="openpyxl") as xw:
    dictionary.to_excel(xw, sheet_name="data_dictionary", index=False)
    sales_df.to_excel(xw, sheet_name="sales", index=False)
    products_df.to_excel(xw, sheet_name="products", index=False)
    customers_df.to_excel(xw, sheet_name="customers", index=False)
    stores_df.to_excel(xw, sheet_name="stores", index=False)
    returns_df.to_excel(xw, sheet_name="returns", index=False)
    pd.DataFrame(campaigns).to_excel(xw, sheet_name="marketing_campaigns", index=False)
    # light formatting: Arial, bold header, frozen header row, sensible widths
    from openpyxl.styles import Font
    for ws in xw.book.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                cell.font = Font(name="Arial", bold=(cell.row == 1), size=10)
        ws.freeze_panes = "A2"
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col[:200])
            ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 90)

print(f"sales: {len(sales_df):,} rows | returns: {len(returns_df):,} | "
      f"customers: {len(customers_df):,} | products: {len(products_df)} | stores: {len(stores_df)}")
