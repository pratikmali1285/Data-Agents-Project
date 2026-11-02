"""
build_warehouse.py  -  creates warehouse.duckdb, the fake data for the demo

This is a made-up food delivery company with 6 cities, about 240 restaurants,
16,500 customers and 1.7 lakh orders from April to mid October 2026.
The random seed is fixed, so everyone who runs this gets exactly the same numbers.

You do not need to run it. warehouse.duckdb is already in the folder.
Run it only if you want to rebuild the data from scratch:  python build_warehouse.py

THE TRAPS (planted on purpose, this is what makes the revenue demo fail)
  1. orders.amount includes GST and is BEFORE the promo discount. It is not revenue.
  2. GST is kept in a separate table, order_taxes.
  3. Refunds are kept in a separate table, refunds. A refunded order still says 'delivered'.
  4. Cancelled orders still have an amount.
  The company's real rule for revenue is written only in the dbt project:
      revenue = delivered and not refunded orders, after promo discount, without GST

THE STORY FOR CHUNK 2
  Mumbai, week of 5 Oct 2026: heavy rain, no riders, lots of cancellations.
  Delivered orders drop from 1,208 to 816 (-32%).
"""
import csv
import datetime as dt
import math
import os
import random

import duckdb

FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_PATH = f"{FOLDER}/warehouse.duckdb"

random_gen = random.Random(7)            # the fixed seed: same data every time
refund_gen = random.Random(1007)         # a second one, only for refund details

FIRST_DAY = dt.date(2026, 4, 1)
LAST_DAY = dt.date(2026, 10, 14)         # data stops "yesterday". The agent's today is 15 Oct 2026.
RAIN_DAYS = (dt.date(2026, 10, 5), dt.date(2026, 10, 9))   # Mumbai only

# city_id, city, state, how many orders a normal day gets
CITIES = [
    (1, "Mumbai", "Maharashtra", 171),
    (2, "Bengaluru", "Karnataka", 170),
    (3, "Delhi", "Delhi", 155),
    (4, "Pune", "Maharashtra", 95),
    (5, "Hyderabad", "Telangana", 95),
    (6, "Chennai", "Tamil Nadu", 65),
]

RESTAURANT_WORD_1 = ["Bombay", "Udupi", "Punjabi", "Royal", "Spice", "Masala", "Tandoori", "Coastal", "Chaat",
                     "Biryani", "Desi", "Irani", "Madras", "Kolkata", "Lucknowi", "Hyderabadi", "Goan", "Kerala",
                     "Rajdhani", "Amritsari"]
RESTAURANT_WORD_2 = ["Bites", "Kitchen", "Dhaba", "Cafe", "House", "Express", "Junction", "Corner", "Bhavan",
                     "Tiffins", "Grill", "Point", "Darbar", "Adda", "Rasoi"]
CUISINES = ["North Indian", "South Indian", "Biryani", "Chinese", "Street Food", "Pizza", "Desserts", "Healthy",
            "Seafood"]
FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Arjun", "Riya", "Ananya", "Diya", "Saanvi", "Priya", "Rohan",
               "Kabir", "Neha", "Pooja", "Rahul", "Sneha", "Karan", "Meera", "Tanvi", "Vikram", "Nikhil", "Aisha",
               "Zara", "Siddharth"]
LAST_NAMES = ["Sharma", "Patel", "Iyer", "Reddy", "Nair", "Gupta", "Shah", "Mehta", "Rao", "Khan", "Joshi",
              "Kulkarni", "Das", "Singh", "Menon", "Desai", "Pillai", "Bose"]


# ---------------------------------------------------------------------------
# 1. RESTAURANTS  (about 1 restaurant for every 3 daily orders in that city)
# ---------------------------------------------------------------------------
restaurants = []
restaurants_by_city = {}
for city_id, city, state, daily_orders in CITIES:
    for _ in range(int(daily_orders * 0.32)):
        restaurant_id = len(restaurants) + 1
        name = f"{random_gen.choice(RESTAURANT_WORD_1)} {random_gen.choice(RESTAURANT_WORD_2)}"
        cuisine = random_gen.choice(CUISINES)
        rating = round(random_gen.uniform(3.4, 4.8), 1)
        onboarded = FIRST_DAY - dt.timedelta(days=random_gen.randint(30, 900))
        restaurants.append((restaurant_id, name, city_id, cuisine, rating, onboarded))
        restaurants_by_city.setdefault(city_id, []).append(restaurant_id)

# ---------------------------------------------------------------------------
# 2. CUSTOMERS
# ---------------------------------------------------------------------------
customers = []
customers_by_city = {}
for city_id, city, state, daily_orders in CITIES:
    for _ in range(daily_orders * 22):
        customer_id = len(customers) + 1
        name = f"{random_gen.choice(FIRST_NAMES)} {random_gen.choice(LAST_NAMES)}"
        signed_up = FIRST_DAY - dt.timedelta(days=random_gen.randint(0, 700))
        customers.append((customer_id, name, city_id, signed_up))
        customers_by_city.setdefault(city_id, []).append(customer_id)

# A few restaurants get far more orders than the rest, like in real life
popularity = {r[0]: random_gen.paretovariate(1.6) for r in restaurants}

# ---------------------------------------------------------------------------
# 3. ORDERS, ORDER_TAXES AND REFUNDS  (one pass, day by day, city by city)
# ---------------------------------------------------------------------------
orders, order_taxes, refunds = [], [], []
order_id = 100000
day = FIRST_DAY
while day <= LAST_DAY:
    months_since_start = (day.year - FIRST_DAY.year) * 12 + day.month - FIRST_DAY.month
    weekend_boost = 1.25 if day.weekday() >= 4 else 1.0           # Friday to Sunday are busier
    for city_id, city, state, daily_orders in CITIES:
        is_rain = city == "Mumbai" and RAIN_DAYS[0] <= day <= RAIN_DAYS[1]
        orders_today = int(daily_orders * weekend_boost * (1 + 0.015 * months_since_start)
                           * random_gen.uniform(0.9, 1.1) * (0.9 if is_rain else 1.0))
        city_restaurants = restaurants_by_city[city_id]
        weights = [popularity[r] for r in city_restaurants]

        for _ in range(orders_today):
            order_id += 1
            restaurant_id = random_gen.choices(city_restaurants, weights)[0]
            customer_id = random_gen.choice(customers_by_city[city_id])
            minutes = int(random_gen.triangular(8 * 60, 23 * 60 + 50, 20 * 60))   # busiest around 8 pm
            ordered_at = dt.datetime.combine(day, dt.time(0)) + dt.timedelta(minutes=minutes)

            # Money. TRAP 1: amount = item value + GST, before the promo discount
            item_value = round(math.exp(random_gen.gauss(math.log(330), 0.45)))   # around Rs 330
            gst = round(item_value * 0.05, 2)                                     # 5% GST
            amount = round(item_value + gst, 2)
            promo = 0.0
            if random_gen.random() < 0.38:                                        # 38% use a promo code
                promo = float(min(round(item_value * 0.2), random_gen.choice([50, 75, 100, 120])))

            # What happened to the order. On rain days in Mumbai, many more get cancelled.
            roll = random_gen.random()
            cancel_chance = 0.48 if is_rain else 0.09
            if roll < cancel_chance:
                outcome = "cancelled"
                if is_rain and random_gen.random() < 0.8:
                    cancel_reason = "heavy_rain_no_rider"
                else:
                    cancel_reason = random_gen.choice(["customer_cancelled", "restaurant_closed", "rider_unavailable"])
            elif roll < cancel_chance + 0.05:
                outcome, cancel_reason = "refunded", None
            else:
                outcome, cancel_reason = "delivered", None
            payment = random_gen.choices(["UPI", "Card", "Cash on delivery", "Wallet"], [62, 20, 12, 6])[0]

            # TRAP 3: a refunded order is stored as 'delivered', the refund goes in its own table
            status = "delivered" if outcome == "refunded" else outcome
            orders.append((order_id, customer_id, restaurant_id, ordered_at, status, amount, promo, payment, cancel_reason))
            order_taxes.append((order_id, gst))                                   # TRAP 2: GST lives here
            if outcome == "refunded":
                refunded_at = ordered_at + dt.timedelta(hours=refund_gen.randint(2, 72))
                reason = refund_gen.choice(["food_quality", "missing_items", "late_delivery", "wrong_order"])
                refunds.append((len(refunds) + 1, order_id, round(amount - promo, 2), refunded_at, reason))
    day += dt.timedelta(days=1)


# ---------------------------------------------------------------------------
# 4. SAVE EVERYTHING INTO DUCKDB
# ---------------------------------------------------------------------------
def save_table(con, table, columns, rows):
    """Write the rows to a temporary CSV file, then load it into DuckDB with the right column types."""
    csv_path = f"{FOLDER}/{table}.tmp.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv('{csv_path}', header=true, columns={columns})")
    os.remove(csv_path)


if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
con = duckdb.connect(DB_PATH)
save_table(con, "cities", {"city_id": "INTEGER", "city_name": "VARCHAR", "state": "VARCHAR"},
           [c[:3] for c in CITIES])
save_table(con, "restaurants", {"restaurant_id": "INTEGER", "restaurant_name": "VARCHAR", "city_id": "INTEGER",
                                "cuisine": "VARCHAR", "rating": "DECIMAL(2,1)", "onboarded_at": "DATE"}, restaurants)
save_table(con, "customers", {"customer_id": "INTEGER", "customer_name": "VARCHAR", "city_id": "INTEGER",
                              "signup_date": "DATE"}, customers)
save_table(con, "orders", {"order_id": "BIGINT", "customer_id": "INTEGER", "restaurant_id": "INTEGER",
                           "order_ts": "TIMESTAMP", "status": "VARCHAR", "amount": "DECIMAL(10,2)",
                           "promo_value": "DECIMAL(10,2)", "payment_method": "VARCHAR",
                           "cancel_reason": "VARCHAR"}, orders)
save_table(con, "order_taxes", {"order_id": "BIGINT", "gst": "DECIMAL(10,2)"}, order_taxes)
save_table(con, "refunds", {"refund_id": "INTEGER", "order_id": "BIGINT", "refund_amount": "DECIMAL(10,2)",
                            "refunded_at": "TIMESTAMP", "reason": "VARCHAR"}, refunds)
con.close()

print(f"Built warehouse.duckdb: {len(restaurants)} restaurants, {len(customers):,} customers, "
      f"{len(orders):,} orders, {len(refunds):,} refunds")
