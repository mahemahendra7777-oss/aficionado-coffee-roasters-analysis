import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Aficionado Coffee Roasters | Sales & Temporal Analytics",
    page_icon="☕",
    layout="wide",
)

DAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]
BUCKET_ORDER = [
    "Morning (6-11)",
    "Afternoon (12-16)",
    "Evening (17-21)",
    "Late Hours (22-5)",
]


def assign_time_bucket(hour: int) -> str:
    if 6 <= hour <= 11:
        return "Morning (6-11)"
    elif 12 <= hour <= 16:
        return "Afternoon (12-16)"
    elif 17 <= hour <= 21:
        return "Evening (17-21)"
    else:
        return "Late Hours (22-5)"


def generate_sample_data(n_rows: int = 6000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    stores = [
        ("ST01", "Lower Manhattan"),
        ("ST02", "Midtown Roastery"),
        ("ST03", "Uptown Express"),
    ]
    products = [
        ("P101", "Coffee", "Gourmet brewed coffee", "Ethiopia Rg", 3.00),
        ("P102", "Tea", "Brewed Chai tea", "Spicy Eye Opener Chai Lg", 3.10),
        ("P103", "Drinking Chocolate", "Hot chocolate", "Dark chocolate Lg", 4.50),
        ("P104", "Coffee", "Drip coffee", "Our Old Time Diner Blend Sm", 2.00),
        ("P105", "Coffee", "Latte", "Oat Milk", 4.75),
        ("P106", "Bakery", "Croissant", "Butter", 3.75),
    ]

    hours = np.arange(24)
    weights = np.array([
        0.005, 0.002, 0.001, 0.001, 0.005, 0.02,
        0.07, 0.12, 0.15, 0.12, 0.09, 0.07,
        0.08, 0.07, 0.05, 0.045, 0.04, 0.03,
        0.02, 0.012, 0.008, 0.004, 0.002, 0.002
    ])
    weights = weights / weights.sum()
    chosen_hours = rng.choice(hours, size=n_rows, p=weights)
    chosen_mins = rng.integers(0, 60, size=n_rows)
    chosen_secs = rng.integers(0, 60, size=n_rows)

    store_idx = rng.integers(0, len(stores), size=n_rows)
    prod_idx = rng.integers(0, len(products), size=n_rows)

    return pd.DataFrame({
        "transaction_id": np.arange(1, n_rows + 1),
        "year": 2025,
        "transaction_time": [
            f"{h:02d}:{m:02d}:{s:02d}"
            for h, m, s in zip(chosen_hours, chosen_mins, chosen_secs)
        ],
        "transaction_qty": rng.choice([1, 1, 2, 2, 3], size=n_rows),
        "store_id": [stores[i][0] for i in store_idx],
        "store_location": [stores[i][1] for i in store_idx],
        "product_id": [products[i][0] for i in prod_idx],
        "unit_price": [products[i][4] for i in prod_idx],
        "product_category": [products[i][1] for i in prod_idx],
        "product_type": [products[i][2] for i in prod_idx],
        "product_detail": [products[i][3] for i in prod_idx],
    })


@st.cache_data
def load_and_clean_data():
    candidates = [
        "Afficionado Coffee Roasters.xlsx",
        "data/Afficionado Coffee Roasters.xlsx",
        "cleaned_coffee_sales.csv",
        "data/cleaned_coffee_sales.csv",
    ]
    found_path = next((p for p in candidates if os.path.exists(p)), None)

    if found_path:
        if found_path.endswith((".xlsx", ".xls")):
            raw_df = pd.read_excel(found_path)
        else:
            raw_df = pd.read_csv(found_path)
        is_sample = False
    else:
        raw_df = generate_sample_data()
        is_sample = True

    df = raw_df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    initial_rows = len(df)

    if "transaction_id" in df.columns:
        df = df.dropna(subset=["transaction_id"]).drop_duplicates(subset=["transaction_id"])
    else:
        df["transaction_id"] = np.arange(1, len(df) + 1)

    df["transaction_qty"] = pd.to_numeric(df["transaction_qty"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df = df.dropna(subset=["transaction_qty", "unit_price"])
    df = df[(df["transaction_qty"] > 0) & (df["unit_price"] > 0)]

    parsed_time = pd.to_datetime(df["transaction_time"].astype(str), format="mixed", errors="coerce")
    df = df[parsed_time.notna()].copy()
    parsed_time = parsed_time[parsed_time.notna()]
    df["hour"] = parsed_time.dt.hour.astype(int)

    date_col = next((c for c in ["transaction_date", "date", "order_date"] if c in df.columns), None)
    if date_col:
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=["date"])
    else:
        yr = pd.to_numeric(df.get("year", 2025), errors="coerce").fillna(2025).astype(int)
        day_offset = np.arange(len(df)) % 365
        df["date"] = pd.to_datetime(yr.astype(str) + "-01-01") + pd.to_timedelta(day_offset, unit="D")

    df["revenue"] = df["transaction_qty"] * df["unit_price"]
    df["day_of_week"] = pd.Categorical(df["date"].dt.day_name(), categories=DAY_ORDER, ordered=True)
    df["is_weekend"] = df["day_of_week"].isin(["Saturday", "Sunday"]).map(
        {True: "Weekend", False: "Weekday"}
    )
    df["time_bucket"] = pd.Categorical(
        df["hour"].apply(assign_time_bucket), categories=BUCKET_ORDER, ordered=True
    )
    df["week_start"] = df["date"].dt.to_period("W").apply(lambda r: r.start_time)

    if "store_location" not in df.columns:
        df["store_location"] = df.get("store_id", "Default Store").astype(str)

    report = {
        "is_sample": is_sample,
        "source_name": found_path if found_path else "Built-in Sample Dataset",
        "initial_rows": initial_rows,
        "clean_rows": len(df),
    }
    return df, report


df, report = load_and_clean_data()

st.title("☕ Aficionado Coffee Roasters — Sales & Temporal Performance")
st.caption(f"Data source: `{report['source_name']}` | Clean records: `{report['clean_rows']:,}`")

if report["is_sample"]:
    st.info(
        "No dataset file found in the repository root, so the app is displaying sample data. "
        "Upload `Afficionado Coffee Roasters.xlsx` or `cleaned_coffee_sales.csv` to the repo to use the full dataset."
    )

# Sidebar Filters
st.sidebar.header("Filters & Controls")
metric_choice = st.sidebar.radio("Metric", ["Revenue", "Quantity"], index=0)
metric_col = "revenue" if metric_choice == "Revenue" else "transaction_qty"
metric_label = "Revenue" if metric_col == "revenue" else "Quantity"

stores = sorted(df["store_location"].dropna().unique().tolist())
selected_stores = st.sidebar.multiselect("Store Location", options=stores, default=stores)

selected_days = st.sidebar.multiselect("Day of Week", options=DAY_ORDER, default=DAY_ORDER)

hour_range = st.sidebar.slider("Hour Range", min_value=0, max_value=23, value=(0, 23))

filtered = df[
    (df["store_location"].isin(selected_stores))
    & (df["day_of_week"].isin(selected_days))
    & (df["hour"].between(hour_range[0], hour_range[1]))
].copy()

if filtered.empty:
    st.warning("No records match your current filter selection.")
    st.stop()

# KPIs
peak_hour = int(filtered.groupby("hour", observed=False)[metric_col].sum().idxmax())
busiest_day = str(filtered.groupby("day_of_week", observed=False)[metric_col].sum().idxmax())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"{filtered['revenue'].sum():,.2f}")
c2.metric("Total Quantity", f"{int(filtered['transaction_qty'].sum()):,}")
c3.metric("Peak Hour", f"{peak_hour:02d}:00")
c4.metric("Busiest Day", busiest_day)

st.divider()

# 1. Overall Sales Trend
st.subheader("1. Overall Sales Trend")
granularity = st.selectbox("Granularity", ["Weekly", "Daily"], index=0)
time_col = "week_start" if granularity == "Weekly" else "date"
trend_data = (
    filtered.groupby([time_col, "store_location"], as_index=False)[metric_col]
    .sum()
    .sort_values(time_col)
)
fig_trend = px.line(
    trend_data,
    x=time_col,
    y=metric_col,
    color="store_location",
    markers=True,
    title=f"{granularity} {metric_label} Trend Across Stores",
)
st.plotly_chart(fig_trend, use_container_width=True)

# 2. Day-of-Week Performance
st.subheader("2. Day-of-Week Performance")
col_d1, col_d2 = st.columns([2, 1])

dow_data = (
    filtered.groupby(["day_of_week", "is_weekend"], observed=False, as_index=False)[metric_col]
    .sum()
)
with col_d1:
    fig_dow = px.bar(
        dow_data,
        x="day_of_week",
        y=metric_col,
        color="is_weekend",
        category_orders={"day_of_week": DAY_ORDER},
        title=f"{metric_label} by Day of Week (Weekday vs. Weekend)",
    )
    st.plotly_chart(fig_dow, use_container_width=True)

bucket_data = (
    filtered.groupby("time_bucket", observed=False, as_index=False)[metric_col].sum()
)
with col_d2:
    fig_bucket = px.pie(
        bucket_data,
        names="time_bucket",
        values=metric_col,
        category_orders={"time_bucket": BUCKET_ORDER},
        hole=0.4,
        title=f"{metric_label} Share by Time Bucket",
    )
    st.plotly_chart(fig_bucket, use_container_width=True)

# 3. Hourly Demand Heatmap
st.subheader("3. Hourly Demand Heatmap (Day of Week × Hour)")
hm_pivot = (
    filtered.pivot_table(
        index="day_of_week",
        columns="hour",
        values=metric_col,
        aggfunc="sum",
        fill_value=0,
        observed=False,
    )
    .reindex(DAY_ORDER)
)
fig_hm = px.imshow(
    hm_pivot,
    x=hm_pivot.columns,
    y=hm_pivot.index,
    aspect="auto",
    color_continuous_scale="YlOrBr",
    labels=dict(x="Hour (0–23)", y="Day of Week", color=metric_label),
    title=f"Hourly {metric_label} Heatmap",
)
st.plotly_chart(fig_hm, use_container_width=True)

# 4. Cross-Location Comparison
st.subheader("4. Cross-Location Temporal Comparison")
loc_hourly = (
    filtered.groupby(["store_location", "hour"], as_index=False)[metric_col].sum()
)
fig_loc = px.line(
    loc_hourly,
    x="hour",
    y=metric_col,
    color="store_location",
    markers=True,
    labels=dict(hour="Hour of Day (0–23)", color="Store Location"),
    title=f"Hourly {metric_label} Profile by Store Location",
)
st.plotly_chart(fig_loc, use_container_width=True)
