-- Geolocation table
CREATE TABLE geolocation_clean (
    geolocation_zip_code_prefix VARCHAR(20) PRIMARY KEY,
    geolocation_lat FLOAT,
    geolocation_lng FLOAT,
    geolocation_city VARCHAR(100),
    geolocation_state VARCHAR(50));

-- Customers table
CREATE TABLE customers_clean (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_unique_id VARCHAR(50),
    customer_zip_code_prefix VARCHAR(20),
    customer_city VARCHAR(100),
    customer_state VARCHAR(50),
    FOREIGN KEY (customer_zip_code_prefix) 
        REFERENCES geolocation_clean(geolocation_zip_code_prefix));

-- Orders table
CREATE TABLE orders_clean (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50),
    order_status VARCHAR(50),
    order_purchase_timestamp TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    FOREIGN KEY (customer_id) 
        REFERENCES customers_clean(customer_id));

-- Product Category Translation table
CREATE TABLE product_category_name_translation (
    product_category_name VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100));

-- Products table
CREATE TABLE products_clean (
    product_id VARCHAR(50) PRIMARY KEY,
    product_category_name VARCHAR(100),
    product_weight_g INT,
    product_length_cm INT,
    product_photos_qty INT,
    FOREIGN KEY (product_category_name) 
        REFERENCES product_category_name_translation(product_category_name));

-- Sellers table
CREATE TABLE sellers_clean (
    seller_id VARCHAR(50) PRIMARY KEY,
    seller_zip_code_prefix VARCHAR(20),
    seller_city VARCHAR(100),
    seller_state VARCHAR(50),
    FOREIGN KEY (seller_zip_code_prefix) 
        REFERENCES geolocation_clean(geolocation_zip_code_prefix));

-- Order Payments table
CREATE TABLE order_payments_clean (
    order_id VARCHAR(50),
    payment_sequential INT,
    payment_type VARCHAR(50),
    payment_installments INT,
    payment_value FLOAT,
    PRIMARY KEY (order_id, payment_sequential),
    FOREIGN KEY (order_id) 
        REFERENCES orders_clean(order_id));

-- Order Reviews table
CREATE TABLE order_reviews_clean (
    review_id VARCHAR(50),
    order_id VARCHAR(50),
    review_score INT,
    review_comment_message VARCHAR(250),
    review_creation_date TIMESTAMP,
    PRIMARY KEY (review_id, order_id),
    FOREIGN KEY (order_id) REFERENCES orders_clean(order_id)
);


-- Order Items table
CREATE TABLE order_items_clean (
    order_id VARCHAR(50),
    order_item_id INT,
    product_id VARCHAR(50),
    seller_id VARCHAR(50),
    shipping_limit_date TIMESTAMP,
    price FLOAT,
    freight_value FLOAT,
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (order_id) REFERENCES orders_clean(order_id),
    FOREIGN KEY (product_id) REFERENCES products_clean(product_id),
    FOREIGN KEY (seller_id) REFERENCES sellers_clean(seller_id));

select * from geolocation_clean limit 10;

select * from customers_clean limit 10;

select * from sellers_clean limit 10;

select * from products_clean limit 10;

select * from product_category_name_translation limit 10;

select * from orders_clean limit 10;

select * from order_items_clean limit 10;

select * from order_payments_clean limit 10;

select * from order_reviews_clean limit 10;

----------------------FEATURE ENGINEERING-----------------------------
-- 1. Total Order Value (sum of item prices + freight per order)
SELECT 
    oi.order_id,
    SUM(oi.price) AS total_order_value,
    SUM(oi.freight_value) AS total_freight
FROM order_items_clean oi
GROUP BY oi.order_id;

-- 2. Delivery Days (difference between purchase and delivery date)
-- Delivery days: difference in days between purchase and delivery
SELECT 
    order_id,
    (order_delivered_customer_date::date - order_purchase_timestamp::date) AS delivery_days
FROM orders_clean;

-- 3. Delivery Delay (actual vs estimated delivery)
SELECT 
    o.order_id,
    (o.order_delivered_customer_date::date - o.order_estimated_delivery_date::date) AS delivery_delay
FROM orders_clean o;

-- 4. Customer Order Count & Spending
SELECT 
    o.customer_id,
    COUNT(o.order_id) AS customer_order_count,
    SUM(oi.price) AS customer_total_spending
FROM orders_clean o
JOIN order_items_clean oi ON o.order_id = oi.order_id
GROUP BY o.customer_id;

-- 5. Average Order Value (AOV)
SELECT 
    customer_id,
    SUM(total_order_value) / COUNT(order_id) AS average_order_value
FROM (
    SELECT o.customer_id, o.order_id, SUM(oi.price) AS total_order_value
    FROM orders_clean o
    JOIN order_items_clean oi ON o.order_id = oi.order_id
    GROUP BY o.customer_id, o.order_id
) sub
GROUP BY customer_id;

-- 6. Repeat Customer Indicator
SELECT 
    customer_id,
    CASE WHEN COUNT(order_id) > 1 THEN 1 ELSE 0 END AS repeat_customer
FROM orders_clean
GROUP BY customer_id;

-- 7. Seller Revenue & Order Count
SELECT 
    oi.seller_id,
    SUM(oi.price) AS seller_revenue,
    COUNT(DISTINCT oi.order_id) AS seller_order_count
FROM order_items_clean oi
GROUP BY oi.seller_id
ORDER BY seller_revenue desc;

----BUSINESS OVERVIEW
-- Total Revenue
SELECT SUM(payment_value) AS total_revenue
FROM order_payments_clean;

-- Total Orders
SELECT COUNT(order_id) AS total_orders FROM orders_clean;

-- Total Customers
SELECT COUNT(DISTINCT customer_id) AS total_customers FROM orders_clean;

-- Total Sellers
SELECT COUNT(DISTINCT seller_id) AS total_sellers FROM order_items_clean;

-- Average Order Value
WITH order_totals AS (
    SELECT order_id,
           SUM(price + freight_value) AS order_value
    FROM order_items_clean
    GROUP BY order_id
)
SELECT AVG(order_value) AS avg_order_value
FROM order_totals;

-- Average Review Score
SELECT AVG(review_score) AS avg_review_score FROM order_reviews_clean;

--SALES ANALYSIS
-- Monthly Revenue Trend
WITH order_totals AS (
    SELECT order_id,
           SUM(payment_value) AS total_order_value
    FROM order_payments_clean
    GROUP BY order_id
)
SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
       SUM(ot.total_order_value) AS monthly_revenue
FROM orders_clean o
JOIN order_totals ot ON o.order_id = ot.order_id
GROUP BY month
ORDER BY month;

-- Revenue by Category
SELECT p.product_category_name,
       SUM(oi.price) AS revenue
FROM order_items_clean oi
JOIN products_clean p ON oi.product_id = p.product_id
GROUP BY p.product_category_name
ORDER BY revenue DESC;

-- Top-Selling Products
SELECT p.product_category_name, p.product_id,
       SUM(oi.order_item_id) AS total_sold
FROM order_items_clean oi
JOIN products_clean p ON oi.product_id = p.product_id
GROUP BY p.product_category_name, p.product_id
ORDER BY total_sold DESC
LIMIT 10;

-- Sales by Location
WITH order_totals AS (
    SELECT order_id,
           SUM(payment_value) AS total_order_value
    FROM order_payments_clean
    GROUP BY order_id
)
SELECT c.customer_city,
       SUM(ot.total_order_value) AS revenue
FROM orders_clean o
JOIN order_totals ot ON o.order_id = ot.order_id
JOIN customers_clean c ON o.customer_id = c.customer_id
GROUP BY c.customer_city
ORDER BY revenue DESC
LIMIT 10;

-- Order totals from items
WITH item_totals AS (
    SELECT order_id, SUM(price + freight_value) AS item_total
    FROM order_items_clean
    GROUP BY order_id
),
payment_totals AS (
    SELECT order_id, SUM(payment_value) AS payment_total
    FROM order_payments_clean
    GROUP BY order_id
)
SELECT o.order_id,
       i.item_total,
       p.payment_total,
       (i.item_total - p.payment_total) AS variation
FROM orders_clean o
LEFT JOIN item_totals i ON o.order_id = i.order_id
LEFT JOIN payment_totals p ON o.order_id = p.order_id;

--CUSTOMER ANALYSIS
-- Customer Distribution by State
SELECT c.customer_state, COUNT(DISTINCT c.customer_id) AS total_customers
FROM customers_clean c
GROUP BY c.customer_state
ORDER BY total_customers DESC;

-- Customer Spending
WITH customer_totals AS (
    SELECT o.customer_id,
           SUM(op.payment_value) AS total_spent
    FROM order_payments_clean op
    JOIN orders_clean o ON op.order_id = o.order_id
    GROUP BY o.customer_id
)
SELECT customer_id, total_spent
FROM customer_totals
ORDER BY total_spent DESC;

-- Repeat vs New Customers
WITH customer_orders AS (
    SELECT customer_id, COUNT(order_id) AS order_count
    FROM orders_clean
    GROUP BY customer_id
)
SELECT CASE WHEN order_count > 1 THEN 'Repeat' ELSE 'New' END AS customer_type,
       COUNT(customer_id) AS num_customers
FROM customer_orders
GROUP BY customer_type;

-- Top Customers
WITH customer_totals AS (
    SELECT o.customer_id,
           SUM(op.payment_value) AS total_spent
    FROM order_payments_clean op
    JOIN orders_clean o ON op.order_id = o.order_id
    GROUP BY o.customer_id
)
SELECT ct.customer_id, ct.total_spent
FROM customer_totals ct
ORDER BY ct.total_spent DESC
LIMIT 10;

---SELLER AND PRODUCT ANALYSIS
-- Top Sellers
SELECT seller_id, SUM(price) AS revenue
FROM order_items_clean
GROUP BY seller_id
ORDER BY revenue DESC
LIMIT 10;

-- Seller Revenue
SELECT seller_id,
       SUM(price + freight_value) AS total_revenue
FROM order_items_clean
GROUP BY seller_id
ORDER BY total_revenue DESC;

-- Product/Category Performance
SELECT p.product_category_name, AVG(r.review_score) AS avg_review_score,
       SUM(oi.price) AS total_revenue
FROM order_items_clean oi
JOIN products_clean p ON oi.product_id = p.product_id
JOIN order_reviews_clean r ON oi.order_id = r.order_id
GROUP BY p.product_category_name
ORDER BY total_revenue DESC;

-- Seller Ratings
SELECT oi.seller_id, AVG(r.review_score) AS avg_review_score
FROM order_items_clean oi
JOIN order_reviews_clean r ON oi.order_id = r.order_id
GROUP BY oi.seller_id
ORDER BY avg_review_score DESC;

---DELIVERY ANALYSIS
-- Average Delivery Time
SELECT AVG(EXTRACT(EPOCH FROM (order_delivered_customer_date - order_purchase_timestamp)) / 86400) AS avg_delivery_days
FROM orders_clean
WHERE order_delivered_customer_date IS NOT NULL;

---Average Delivery Time (Excluding Outliers — Z‑Score Method)
WITH stats AS (
    SELECT AVG(EXTRACT(EPOCH FROM (order_delivered_customer_date - order_purchase_timestamp)) / 86400) AS avg_days,
           STDDEV(EXTRACT(EPOCH FROM (order_delivered_customer_date - order_purchase_timestamp)) / 86400) AS std_days
    FROM orders_clean
    WHERE order_delivered_customer_date IS NOT NULL
)
SELECT AVG(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400) AS avg_delivery_days_no_outliers
FROM orders_clean o, stats s
WHERE o.order_delivered_customer_date IS NOT NULL
  AND (EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400) <= (s.avg_days + 3 * s.std_days);

---Average Delivery Time (Excluding Outliers — IQR Method)
WITH delivery AS (
    SELECT EXTRACT(EPOCH FROM (order_delivered_customer_date - order_purchase_timestamp)) / 86400 AS delivery_days
    FROM orders_clean
    WHERE order_delivered_customer_date IS NOT NULL
),
quartiles AS (
    SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY delivery_days) AS q1,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY delivery_days) AS q3
    FROM delivery
)
SELECT AVG(d.delivery_days) AS avg_delivery_days_no_outliers
FROM delivery d, quartiles q
WHERE d.delivery_days BETWEEN (q.q1 - 1.5 * (q.q3 - q.q1)) AND (q.q3 + 1.5 * (q.q3 - q.q1));


-- On-Time vs Delayed Orders
SELECT CASE 
           WHEN (order_delivered_customer_date - order_estimated_delivery_date) > INTERVAL '0 days' 
                THEN 'Delayed'
           ELSE 'On-Time'
       END AS delivery_status,
       COUNT(order_id) AS num_orders
FROM orders_clean
WHERE order_delivered_customer_date IS NOT NULL
GROUP BY delivery_status;


-- Delivery Performance by Customer Location
SELECT c.customer_city,
       COUNT(o.order_id) AS total_orders,
       SUM(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS on_time_orders,
       SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS delayed_orders,
       ROUND(100.0 * SUM(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 1 ELSE 0 END) / COUNT(o.order_id), 2) AS on_time_percentage
FROM orders_clean o
JOIN customers_clean c ON o.customer_id = c.customer_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_city
ORDER BY on_time_percentage DESC;

----Delivery Performance by Seller Location
SELECT s.seller_city,
       COUNT(o.order_id) AS total_orders,
       SUM(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS on_time_orders,
       SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS delayed_orders,
       ROUND(100.0 * SUM(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 1 ELSE 0 END) / COUNT(o.order_id), 2) AS on_time_percentage
FROM orders_clean o
JOIN order_items_clean oi ON o.order_id = oi.order_id
JOIN sellers_clean s ON oi.seller_id = s.seller_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY s.seller_city
ORDER BY on_time_percentage DESC;

----Delivery Delay vs Review Score
WITH delivery AS (
    SELECT o.order_id,
           EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_estimated_delivery_date)) / 86400 AS delivery_delay
    FROM orders_clean o
    WHERE o.order_delivered_customer_date IS NOT NULL
)
SELECT r.review_score,
       AVG(d.delivery_delay) AS avg_delay_days
FROM delivery d
JOIN order_reviews_clean r ON d.order_id = r.order_id
GROUP BY r.review_score
ORDER BY r.review_score;


---CUSTOMER EXPERIENCE
---Review Score Distribution
SELECT review_score, COUNT(*) AS num_reviews
FROM order_reviews_clean
GROUP BY review_score
ORDER BY review_score;

---Reviews by Category
SELECT p.product_category_name,
       AVG(r.review_score) AS avg_review_score,
       COUNT(r.review_id) AS num_reviews
FROM order_reviews_clean r
JOIN orders_clean o ON r.order_id = o.order_id
JOIN order_items_clean oi ON o.order_id = oi.order_id
JOIN products_clean p ON oi.product_id = p.product_id
GROUP BY p.product_category_name
ORDER BY avg_review_score DESC;

---Rating vs Delivery Performance
WITH delivery AS (
    SELECT o.order_id,
           EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_estimated_delivery_date)) / 86400 AS delivery_delay
    FROM orders_clean o
    WHERE o.order_delivered_customer_date IS NOT NULL
)
SELECT r.review_score,
       AVG(d.delivery_delay) AS avg_delay_days
FROM delivery d
JOIN order_reviews_clean r ON d.order_id = r.order_id
GROUP BY r.review_score
ORDER BY r.review_score;

SELECT MIN(order_estimated_delivery_date - order_purchase_timestamp),
       AVG(order_estimated_delivery_date - order_purchase_timestamp),
       MAX(order_estimated_delivery_date - order_purchase_timestamp)
FROM orders_clean;


























