# E-Commerce Analytics Dashboard

A Streamlit dashboard for exploring e-commerce data (orders, customers, sellers, deliveries, reviews) stored in PostgreSQL.

## Sections

- **Business Overview** – revenue, orders, customers, sellers, average order value, review score
- **Sales Analysis** – revenue trends, top categories, top products, sales by location
- **Customer Analysis** – customer distribution, spending, repeat vs new customers
- **Seller & Product Analysis** – top sellers, category performance, seller ratings
- **Delivery Analysis** – delivery times, on-time vs delayed orders
- **Customer Experience** – review scores and how they relate to delivery
- **Insights** – quick standalone findings (top product, slowest state, etc.)

Filters for state, city, and category are available in the sidebar (except on the Insights page).

## Setup

```bash
pip install streamlit pandas sqlalchemy psycopg2-binary
```

Update the database connection in `ecommerce_dashboard.py`:

```python
DB_URL = "postgresql+psycopg2://<user>:<password>@<host>:<port>/<database>"
```

## Run

```bash
streamlit run ecommerce_dashboard.py
```

## Notes

- `customer_id` is unique per order, not per customer, so repeat-customer numbers are approximate.
- The Insights page uses the full dataset and isn't affected by the sidebar filters.
