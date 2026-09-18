import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="E-commerce Analytics", layout="wide")

DB_URL = "postgresql+psycopg2://postgres:Keerthi2020@localhost:5432/ecart_clean"


@st.cache_resource
def get_engine():
    return create_engine(DB_URL)


engine = get_engine()


@st.cache_data(ttl=3600)
def run_query(query, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


@st.cache_data(ttl=3600)
def get_filter_options():
    states = run_query("SELECT DISTINCT customer_state FROM customers_clean ORDER BY 1")["customer_state"].tolist()
    cities = run_query("SELECT DISTINCT seller_city FROM sellers_clean ORDER BY 1")["seller_city"].tolist()
    cat_df = run_query("""
        SELECT DISTINCT p.product_category_name,
               COALESCE(t.product_category_name_english, p.product_category_name) AS category_english
        FROM products_clean p
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        ORDER BY category_english
    """)
    categories = cat_df["category_english"].tolist()
    category_map = dict(zip(cat_df["category_english"], cat_df["product_category_name"]))
    return states, cities, categories, category_map


def build_filter(state, city, category):
    clauses, params = [], {}
    if state != "All":
        clauses.append("c.customer_state = :state")
        params["state"] = state
    if city != "All":
        clauses.append("s.seller_city = :city")
        params["city"] = city
    if category != "All":
        clauses.append("p.product_category_name = :category")
        params["category"] = category
    frag = (" AND " + " AND ".join(clauses)) if clauses else ""
    return frag, params


states, cities, categories, category_map = get_filter_options()

st.sidebar.header("Filters")
state_filter = st.sidebar.selectbox("Customer State", ["All"] + states)
city_filter = st.sidebar.selectbox("Seller City", ["All"] + cities)
category_display = st.sidebar.selectbox("Product Category", ["All"] + categories)
category_filter = category_map.get(category_display, category_display)

st.sidebar.header("Navigate")
section = st.sidebar.radio(
    "Go to",
    ["Business Overview", "Sales Analysis", "Customer Analysis",
     "Seller & Product Analysis", "Delivery Analysis", "Customer Experience", "Insights"],
)

frag, params = build_filter(state_filter, city_filter, category_filter)


# ------------------------------
# 1. Business Overview
# ------------------------------
if section == "Business Overview":
    st.header("Business Overview")

    overview_sql = f"""
        WITH filtered_orders AS (
            SELECT DISTINCT o.order_id, o.customer_id
            FROM orders_clean o
            JOIN customers_clean c ON o.customer_id = c.customer_id
            LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
            LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
            LEFT JOIN products_clean p ON oi.product_id = p.product_id
            WHERE 1=1 {frag}
        )
        SELECT
            (SELECT SUM(op.payment_value) FROM order_payments_clean op
             JOIN filtered_orders fo ON op.order_id = fo.order_id) AS total_revenue,
            (SELECT COUNT(*) FROM filtered_orders) AS total_orders,
            (SELECT COUNT(DISTINCT customer_id) FROM filtered_orders) AS total_customers,
            (SELECT COUNT(DISTINCT oi.seller_id) FROM order_items_clean oi
             JOIN filtered_orders fo ON oi.order_id = fo.order_id) AS total_sellers,
            (SELECT AVG(order_value) FROM (
                SELECT oi.order_id, SUM(oi.price + oi.freight_value) AS order_value
                FROM order_items_clean oi
                JOIN filtered_orders fo ON oi.order_id = fo.order_id
                GROUP BY oi.order_id
             ) t) AS avg_order_value,
            (SELECT AVG(r.review_score) FROM order_reviews_clean r
             JOIN filtered_orders fo ON r.order_id = fo.order_id) AS avg_review_score
    """
    overview = run_query(overview_sql, params).iloc[0]

    r1 = st.columns(3)
    r1[0].metric("Total Revenue", f"R$ {overview['total_revenue']:,.0f}" if pd.notna(overview['total_revenue']) else "—")
    r1[1].metric("Total Orders", f"{int(overview['total_orders']):,}")
    r1[2].metric("Total Customers", f"{int(overview['total_customers']):,}")

    r2 = st.columns(3)
    r2[0].metric("Total Sellers", f"{int(overview['total_sellers']):,}")
    r2[1].metric("Avg Order Value", f"R$ {overview['avg_order_value']:,.2f}" if pd.notna(overview['avg_order_value']) else "—")
    r2[2].metric("Avg Review Score", f"{overview['avg_review_score']:.2f}" if pd.notna(overview['avg_review_score']) else "—")


# ------------------------------
# 2. Sales Analysis
# ------------------------------
elif section == "Sales Analysis":
    st.header("Sales Analysis")

    monthly_sql = f"""
        WITH order_totals AS (
            SELECT order_id, SUM(payment_value) AS order_value
            FROM order_payments_clean GROUP BY order_id
        )
        SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
               SUM(ot.order_value) AS revenue
        FROM orders_clean o
        JOIN order_totals ot ON o.order_id = ot.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        WHERE 1=1 {frag}
        GROUP BY month ORDER BY month
    """
    st.subheader("Monthly Revenue Trend")
    st.line_chart(run_query(monthly_sql, params).set_index("month"))

    category_sql = f"""
        SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
               SUM(oi.price) AS revenue
        FROM order_items_clean oi
        JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        JOIN orders_clean o ON oi.order_id = o.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        WHERE 1=1 {frag}
        GROUP BY category ORDER BY revenue DESC LIMIT 15
    """
    st.subheader("Revenue by Category")
    st.bar_chart(run_query(category_sql, params).set_index("category"))

    top_products_sql = f"""
        SELECT p.product_id,
               COALESCE(t.product_category_name_english, p.product_category_name) AS category,
               COUNT(oi.order_item_id) AS units_sold
        FROM order_items_clean oi
        JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        JOIN orders_clean o ON oi.order_id = o.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        WHERE 1=1 {frag}
        GROUP BY p.product_id, category
        ORDER BY units_sold DESC LIMIT 10
    """
    st.subheader("Top-Selling Products")
    st.dataframe(run_query(top_products_sql, params))

    location_sql = f"""
        WITH order_totals AS (
            SELECT order_id, SUM(payment_value) AS order_value
            FROM order_payments_clean GROUP BY order_id
        )
        SELECT c.customer_city, SUM(ot.order_value) AS revenue
        FROM orders_clean o
        JOIN order_totals ot ON o.order_id = ot.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        WHERE 1=1 {frag}
        GROUP BY c.customer_city ORDER BY revenue DESC LIMIT 10
    """
    st.subheader("Sales by Location")
    st.dataframe(run_query(location_sql, params).style.format({"revenue": "R$ {:,.2f}"}))


# ------------------------------
# 3. Customer Analysis
# ------------------------------
elif section == "Customer Analysis":
    st.header("Customer Analysis")

    # Customer-level views only make sense to filter by state (no seller/product context here)
    state_clause = " AND c.customer_state = :state" if state_filter != "All" else ""
    state_params = {"state": state_filter} if state_filter != "All" else {}

    st.subheader("Customer Distribution by State")
    by_state = run_query(f"""
        SELECT customer_state, COUNT(DISTINCT customer_id) AS customers
        FROM customers_clean c
        WHERE 1=1 {state_clause}
        GROUP BY customer_state ORDER BY customers DESC
    """, state_params)
    st.bar_chart(by_state.set_index("customer_state"))

    customer_spend = run_query(f"""
        SELECT o.customer_id, SUM(op.payment_value) AS total_spent, COUNT(DISTINCT o.order_id) AS order_count
        FROM order_payments_clean op
        JOIN orders_clean o ON op.order_id = o.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        WHERE 1=1 {state_clause}
        GROUP BY o.customer_id
    """, state_params)

    st.subheader("Customer Spending")
    bins = pd.cut(customer_spend["total_spent"], bins=[0, 50, 100, 200, 400, 800, float("inf")],
                   labels=["0-50", "50-100", "100-200", "200-400", "400-800", "800+"])
    st.bar_chart(bins.value_counts().sort_index().rename("customers"))

    st.subheader("Repeat vs New Customers")
    customer_spend["customer_type"] = customer_spend["order_count"].apply(lambda x: "Repeat" if x > 1 else "New")
    st.bar_chart(customer_spend["customer_type"].value_counts())

    st.subheader("Top 10 Customers by Spend")
    top_customers = customer_spend.nlargest(10, "total_spent")[["customer_id", "total_spent"]]
    st.dataframe(top_customers.style.format({"total_spent": "R$ {:,.2f}"}))


# ------------------------------
# 4. Seller & Product Analysis
# ------------------------------
elif section == "Seller & Product Analysis":
    st.header("Seller & Product Analysis")

    seller_rev_sql = f"""
        SELECT oi.seller_id, SUM(oi.price + oi.freight_value) AS revenue
        FROM order_items_clean oi
        JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN orders_clean o ON oi.order_id = o.order_id
        LEFT JOIN customers_clean c ON o.customer_id = c.customer_id
        WHERE 1=1 {frag}
        GROUP BY oi.seller_id ORDER BY revenue DESC
    """
    seller_revenue = run_query(seller_rev_sql, params)

    st.subheader("Top 10 Sellers by Revenue")
    st.bar_chart(seller_revenue.head(10).set_index("seller_id"))

    st.subheader("Seller Revenue (All Sellers)")
    st.dataframe(seller_revenue.style.format({"revenue": "R$ {:,.2f}"}))

    category_perf_sql = f"""
        SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
               SUM(oi.price) AS revenue,
               AVG(r.review_score) AS avg_review_score
        FROM order_items_clean oi
        JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        JOIN order_reviews_clean r ON oi.order_id = r.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN orders_clean o ON oi.order_id = o.order_id
        LEFT JOIN customers_clean c ON o.customer_id = c.customer_id
        WHERE 1=1 {frag}
        GROUP BY category ORDER BY revenue DESC
    """
    st.subheader("Product/Category Performance")
    st.dataframe(run_query(category_perf_sql, params).style.format({"revenue": "R$ {:,.2f}", "avg_review_score": "{:.2f}"}))

    seller_ratings_sql = f"""
        SELECT oi.seller_id, AVG(r.review_score) AS avg_review_score
        FROM order_items_clean oi
        JOIN order_reviews_clean r ON oi.order_id = r.order_id
        JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN orders_clean o ON oi.order_id = o.order_id
        LEFT JOIN customers_clean c ON o.customer_id = c.customer_id
        WHERE 1=1 {frag}
        GROUP BY oi.seller_id
        HAVING COUNT(*) >= 10
        ORDER BY avg_review_score DESC LIMIT 15
    """
    st.subheader("Seller Ratings")
    st.bar_chart(run_query(seller_ratings_sql, params).set_index("seller_id"))


# ------------------------------
# 5. Delivery Analysis
# ------------------------------
elif section == "Delivery Analysis":
    st.header("Delivery Analysis")

    delivery_sql = f"""
        SELECT DISTINCT o.order_id, c.customer_city,
               o.order_purchase_timestamp, o.order_delivered_customer_date, o.order_estimated_delivery_date
        FROM orders_clean o
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        WHERE o.order_delivered_customer_date IS NOT NULL {frag}
    """
    delivery = run_query(delivery_sql, params)
    delivery["delivery_days"] = (delivery["order_delivered_customer_date"] - delivery["order_purchase_timestamp"]).dt.days
    delivery["delay_days"] = (delivery["order_delivered_customer_date"] - delivery["order_estimated_delivery_date"]).dt.days
    delivery["status"] = delivery["delay_days"].apply(lambda d: "Delayed" if d > 0 else "On-Time")

    st.metric("Average Delivery Time (days)", f"{delivery['delivery_days'].mean():.1f}")

    st.subheader("On-Time vs Delayed Orders")
    st.bar_chart(delivery["status"].value_counts())

    st.subheader("On-Time % by Customer City")
    by_city = delivery.groupby("customer_city").agg(
        total_orders=("order_id", "count"),
        on_time_orders=("status", lambda s: (s == "On-Time").sum()),
    )
    by_city["on_time_pct"] = (100 * by_city["on_time_orders"] / by_city["total_orders"]).round(1)
    st.dataframe(by_city[by_city["total_orders"] >= 20].sort_values("on_time_pct", ascending=False).head(15))

    st.subheader("Delivery Delay vs Review Score")
    reviews_sql = f"""
        SELECT DISTINCT r.order_id, r.review_score
        FROM order_reviews_clean r
        JOIN orders_clean o ON r.order_id = o.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        WHERE 1=1 {frag}
    """
    reviews = run_query(reviews_sql, params)
    delay_vs_review = delivery.merge(reviews, on="order_id").groupby("review_score")["delay_days"].mean()
    st.bar_chart(delay_vs_review.rename("avg_delay_days"))
    st.caption("Positive = arrived late on average, negative = arrived early on average.")


# ------------------------------
# 6. Customer Experience
# ------------------------------
elif section == "Customer Experience":
    st.header("Customer Experience")

    review_dist_sql = f"""
        SELECT DISTINCT r.review_id, r.review_score
        FROM order_reviews_clean r
        JOIN orders_clean o ON r.order_id = o.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        WHERE 1=1 {frag}
    """
    st.subheader("Review Score Distribution")
    review_dist = run_query(review_dist_sql, params)
    st.bar_chart(review_dist["review_score"].value_counts().sort_index())

    reviews_cat_sql = f"""
        SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
               AVG(r.review_score) AS avg_review_score
        FROM order_reviews_clean r
        JOIN orders_clean o ON r.order_id = o.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        JOIN order_items_clean oi ON o.order_id = oi.order_id
        JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        WHERE 1=1 {frag}
        GROUP BY category ORDER BY avg_review_score DESC LIMIT 15
    """
    st.subheader("Reviews by Category")
    st.dataframe(run_query(reviews_cat_sql, params).style.format({"avg_review_score": "{:.2f}"}))

    delivery_sql = f"""
        SELECT DISTINCT o.order_id, o.order_delivered_customer_date, o.order_estimated_delivery_date
        FROM orders_clean o
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        WHERE o.order_delivered_customer_date IS NOT NULL {frag}
    """
    delivery = run_query(delivery_sql, params)
    delivery["status"] = delivery.apply(
        lambda r: "On-Time" if r["order_delivered_customer_date"] <= r["order_estimated_delivery_date"] else "Delayed",
        axis=1,
    )
    reviews_sql2 = f"""
        SELECT DISTINCT r.order_id, r.review_score
        FROM order_reviews_clean r
        JOIN orders_clean o ON r.order_id = o.order_id
        JOIN customers_clean c ON o.customer_id = c.customer_id
        LEFT JOIN order_items_clean oi ON o.order_id = oi.order_id
        LEFT JOIN sellers_clean s ON oi.seller_id = s.seller_id
        LEFT JOIN products_clean p ON oi.product_id = p.product_id
        WHERE 1=1 {frag}
    """
    reviews2 = run_query(reviews_sql2, params)
    rating_vs_status = delivery.merge(reviews2, on="order_id").groupby("status")["review_score"].mean()
    st.subheader("Rating vs Delivery Performance")
    st.bar_chart(rating_vs_status.rename("avg_review_score"))


# ------------------------------
# 7. Insights
# ------------------------------
elif section == "Insights":
    st.header("Insights")
    st.caption("These run on the full dataset (not the sidebar filters) to keep things simple.")

    delay_sql = """
        SELECT oi.seller_id, COUNT(*) AS delayed_orders
        FROM orders_clean o
        JOIN order_items_clean oi ON o.order_id = oi.order_id
        WHERE o.order_delivered_customer_date > o.order_estimated_delivery_date
        GROUP BY oi.seller_id
        HAVING COUNT(*) >= 5
        ORDER BY delayed_orders DESC
        LIMIT 1
    """
    delay = run_query(delay_sql)
    if not delay.empty:
        st.subheader("Seller with Most Delivery Delays")
        st.write(f"Seller `{delay.iloc[0]['seller_id']}` has the most delayed orders: "
                 f"{int(delay.iloc[0]['delayed_orders'])}.")

    top_product_sql = """
        SELECT product_id, COUNT(*) AS units_sold
        FROM order_items_clean
        GROUP BY product_id
        ORDER BY units_sold DESC
        LIMIT 1
    """
    top_product = run_query(top_product_sql)
    if not top_product.empty:
        st.subheader("Top-Selling Product")
        st.write(f"Product `{top_product.iloc[0]['product_id']}` sold the most units: "
                 f"{int(top_product.iloc[0]['units_sold'])}.")

    top_cat_sql = """
        SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
               COUNT(*) AS units_sold
        FROM order_items_clean oi
        JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        GROUP BY category
        ORDER BY units_sold DESC
        LIMIT 1
    """
    least_cat_sql = top_cat_sql.replace("DESC", "ASC")

    top_cat = run_query(top_cat_sql)
    least_cat = run_query(least_cat_sql)

    if not top_cat.empty:
        st.subheader("Top-Selling Category")
        st.write(f"`{top_cat.iloc[0]['category']}` sold the most units: {int(top_cat.iloc[0]['units_sold'])}.")

    if not least_cat.empty:
        st.subheader("Least-Selling Category")
        st.write(f"`{least_cat.iloc[0]['category']}` sold the fewest units: {int(least_cat.iloc[0]['units_sold'])}.")

    pay_delivered_sql = """
        SELECT op.payment_type, COUNT(*) AS delivered_orders
        FROM order_payments_clean op
        JOIN orders_clean o ON op.order_id = o.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY op.payment_type
        ORDER BY delivered_orders DESC
        LIMIT 1
    """
    pay_delivered = run_query(pay_delivered_sql)
    if not pay_delivered.empty:
        st.subheader("Payment Method with Most Deliveries")
        st.write(f"`{pay_delivered.iloc[0]['payment_type']}` was used in the most delivered orders: "
                 f"{int(pay_delivered.iloc[0]['delivered_orders'])}.")

    pay_cancel_sql = """
        SELECT op.payment_type, COUNT(*) AS cancelled_orders
        FROM order_payments_clean op
        JOIN orders_clean o ON op.order_id = o.order_id
        WHERE o.order_status = 'canceled'
        GROUP BY op.payment_type
        ORDER BY cancelled_orders DESC
        LIMIT 1
    """
    pay_cancel = run_query(pay_cancel_sql)
    if not pay_cancel.empty:
        st.subheader("Payment Method with Most Cancellations")
        st.write(f"`{pay_cancel.iloc[0]['payment_type']}` had the most cancelled orders: "
                 f"{int(pay_cancel.iloc[0]['cancelled_orders'])}.")

    cancel_rate_sql = """
        SELECT ROUND(100.0 * SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancellation_rate
        FROM orders_clean
    """
    cancel_rate = run_query(cancel_rate_sql).iloc[0]["cancellation_rate"]
    st.subheader("Overall Cancellation Rate")
    st.write(f"{cancel_rate}% of all orders were cancelled.")

    st.divider()

    fastest_route_sql = """
        SELECT s.seller_city, c.customer_state,
               AVG(o.order_delivered_customer_date - o.order_purchase_timestamp) AS avg_delivery_time,
               COUNT(*) AS orders
        FROM orders_clean o
        JOIN customers_clean c ON o.customer_id = c.customer_id
        JOIN order_items_clean oi ON o.order_id = oi.order_id
        JOIN sellers_clean s ON oi.seller_id = s.seller_id
        WHERE o.order_delivered_customer_date IS NOT NULL
        GROUP BY s.seller_city, c.customer_state
        HAVING COUNT(*) >= 10
        ORDER BY avg_delivery_time ASC
        LIMIT 1
    """
    fastest_route = run_query(fastest_route_sql)
    if not fastest_route.empty:
        r = fastest_route.iloc[0]
        st.subheader("Fastest Shipping Route")
        st.write(f"`{r['seller_city']}` → `{r['customer_state']}` averages the fastest delivery: "
                 f"{r['avg_delivery_time'].days} days ({int(r['orders'])} orders).")

    slowest_state_sql = """
        SELECT c.customer_state,
               AVG(o.order_delivered_customer_date - o.order_purchase_timestamp) AS avg_delivery_time
        FROM orders_clean o
        JOIN customers_clean c ON o.customer_id = c.customer_id
        WHERE o.order_delivered_customer_date IS NOT NULL
        GROUP BY c.customer_state
        HAVING COUNT(*) >= 20
        ORDER BY avg_delivery_time DESC
        LIMIT 1
    """
    slowest_state = run_query(slowest_state_sql)
    if not slowest_state.empty:
        r = slowest_state.iloc[0]
        st.subheader("Slowest State for Delivery")
        st.write(f"Customers in `{r['customer_state']}` wait the longest on average: "
                 f"{r['avg_delivery_time'].days} days.")

    on_time_split_sql = """
        SELECT
            ROUND(100.0 * SUM(CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date THEN 1 ELSE 0 END) / COUNT(*), 1) AS on_time_pct
        FROM orders_clean
        WHERE order_delivered_customer_date IS NOT NULL
    """
    on_time_pct = run_query(on_time_split_sql).iloc[0]["on_time_pct"]
    st.subheader("On-Time Delivery Rate")
    st.write(f"{on_time_pct}% of delivered orders arrived on or before the estimated date.")

    priciest_item_sql = """
        SELECT oi.product_id, oi.price
        FROM order_items_clean oi
        ORDER BY oi.price DESC
        LIMIT 1
    """
    priciest_item = run_query(priciest_item_sql)
    if not priciest_item.empty:
        st.subheader("Most Expensive Item Ever Sold")
        st.write(f"Product `{priciest_item.iloc[0]['product_id']}` sold for R$ {priciest_item.iloc[0]['price']:,.2f}.")

    best_day_sql = """
        SELECT DATE(o.order_purchase_timestamp) AS order_date, SUM(op.payment_value) AS revenue
        FROM order_payments_clean op
        JOIN orders_clean o ON op.order_id = o.order_id
        GROUP BY order_date
        ORDER BY revenue DESC
        LIMIT 1
    """
    best_day = run_query(best_day_sql)
    if not best_day.empty:
        st.subheader("Best Revenue Day")
        st.write(f"`{best_day.iloc[0]['order_date']}` had the highest single-day revenue: "
                 f"R$ {best_day.iloc[0]['revenue']:,.2f}.")

    top_spender_sql = """
        SELECT o.customer_id, SUM(op.payment_value) AS total_spent
        FROM order_payments_clean op
        JOIN orders_clean o ON op.order_id = o.order_id
        GROUP BY o.customer_id
        ORDER BY total_spent DESC
        LIMIT 1
    """
    top_spender = run_query(top_spender_sql)
    if not top_spender.empty:
        st.subheader("Highest-Spending Customer")
        st.write(f"Customer `{top_spender.iloc[0]['customer_id']}` has spent the most overall: "
                 f"R$ {top_spender.iloc[0]['total_spent']:,.2f}.")

    top_avg_spend_state_sql = """
        WITH customer_totals AS (
            SELECT o.customer_id, c.customer_state, SUM(op.payment_value) AS total_spent
            FROM order_payments_clean op
            JOIN orders_clean o ON op.order_id = o.order_id
            JOIN customers_clean c ON o.customer_id = c.customer_id
            GROUP BY o.customer_id, c.customer_state
        )
        SELECT customer_state, AVG(total_spent) AS avg_spend
        FROM customer_totals
        GROUP BY customer_state
        HAVING COUNT(*) >= 20
        ORDER BY avg_spend DESC
        LIMIT 1
    """
    top_avg_spend_state = run_query(top_avg_spend_state_sql)
    if not top_avg_spend_state.empty:
        r = top_avg_spend_state.iloc[0]
        st.subheader("State with Highest Average Spend per Customer")
        st.write(f"Customers in `{r['customer_state']}` spend the most on average: R$ {r['avg_spend']:,.2f}.")

    most_orders_seller_sql = """
        SELECT seller_id, COUNT(DISTINCT order_id) AS orders
        FROM order_items_clean
        GROUP BY seller_id
        ORDER BY orders DESC
        LIMIT 1
    """
    most_orders_seller = run_query(most_orders_seller_sql)
    if not most_orders_seller.empty:
        st.subheader("Seller with Most Orders")
        st.write(f"Seller `{most_orders_seller.iloc[0]['seller_id']}` has handled the most orders: "
                 f"{int(most_orders_seller.iloc[0]['orders'])}.")

    best_seller_sql = """
        SELECT oi.seller_id, AVG(r.review_score) AS avg_review_score, COUNT(*) AS n
        FROM order_items_clean oi
        JOIN order_reviews_clean r ON oi.order_id = r.order_id
        GROUP BY oi.seller_id
        HAVING COUNT(*) >= 10
        ORDER BY avg_review_score DESC
        LIMIT 1
    """
    best_seller = run_query(best_seller_sql)
    if not best_seller.empty:
        r = best_seller.iloc[0]
        st.subheader("Best-Rated Seller")
        st.write(f"Seller `{r['seller_id']}` has the highest average rating: {r['avg_review_score']:.2f}★ "
                 f"({int(r['n'])} reviews).")

    common_installments_sql = """
        SELECT payment_installments, COUNT(*) AS n
        FROM order_payments_clean
        GROUP BY payment_installments
        ORDER BY n DESC
        LIMIT 1
    """
    common_installments = run_query(common_installments_sql)
    if not common_installments.empty:
        st.subheader("Most Common Installment Count")
        st.write(f"Most orders are paid in {int(common_installments.iloc[0]['payment_installments'])} "
                 f"installment(s) ({int(common_installments.iloc[0]['n'])} orders).")

    pay_highest_aov_sql = """
        SELECT payment_type, AVG(payment_value) AS avg_order_value
        FROM order_payments_clean
        GROUP BY payment_type
        ORDER BY avg_order_value DESC
        LIMIT 1
    """
    pay_highest_aov = run_query(pay_highest_aov_sql)
    if not pay_highest_aov.empty:
        st.subheader("Payment Method with Highest Average Order Value")
        st.write(f"`{pay_highest_aov.iloc[0]['payment_type']}` has the highest average order value: "
                 f"R$ {pay_highest_aov.iloc[0]['avg_order_value']:,.2f}.")

    common_score_sql = """
        SELECT review_score, COUNT(*) AS n
        FROM order_reviews_clean
        GROUP BY review_score
        ORDER BY n DESC
        LIMIT 1
    """
    common_score = run_query(common_score_sql)
    if not common_score.empty:
        st.subheader("Most Common Review Score")
        st.write(f"Most customers give {int(common_score.iloc[0]['review_score'])} stars "
                 f"({int(common_score.iloc[0]['n'])} reviews).")

    worst_cat_1star_sql = """
        SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
               COUNT(*) AS one_star_reviews
        FROM order_reviews_clean r
        JOIN order_items_clean oi ON r.order_id = oi.order_id
        JOIN products_clean p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        WHERE r.review_score = 1
        GROUP BY category
        ORDER BY one_star_reviews DESC
        LIMIT 1
    """
    worst_cat_1star = run_query(worst_cat_1star_sql)
    if not worst_cat_1star.empty:
        st.subheader("Category with Most 1-Star Reviews")
        st.write(f"`{worst_cat_1star.iloc[0]['category']}` has the most 1-star reviews: "
                 f"{int(worst_cat_1star.iloc[0]['one_star_reviews'])}.")