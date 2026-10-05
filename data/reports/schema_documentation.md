# Olist Database Schema Documentation

*Auto-generated from live SQLite database catalog at `C:\Users\Avinash\Desktop\NL2SQL-main\data\database\olist.db`*

```text
TABLE: category_translation
ROW_COUNT: 71
PRIMARY_KEY: product_category_name
COLUMNS:
  - product_category_name (TEXT) [PRIMARY KEY]
  - product_category_name_english (TEXT NOT NULL)
```

```text
TABLE: customers
ROW_COUNT: 99,441
PRIMARY_KEY: customer_id
COLUMNS:
  - customer_id (TEXT) [PRIMARY KEY]
  - customer_unique_id (TEXT NOT NULL)
  - customer_zip_code_prefix (TEXT)
  - customer_city (TEXT)
  - customer_state (TEXT)
RELATIONSHIPS:
  - customers.customer_zip_code_prefix -> geolocation_summary.zip_code_prefix
```

```text
TABLE: geolocation
ROW_COUNT: 1,000,163
PRIMARY_KEY: NONE
COLUMNS:
  - geolocation_zip_code_prefix (TEXT)
  - geolocation_lat (REAL)
  - geolocation_lng (REAL)
  - geolocation_city (TEXT)
  - geolocation_state (TEXT)
```

```text
TABLE: geolocation_summary
ROW_COUNT: 19,015
PRIMARY_KEY: zip_code_prefix
COLUMNS:
  - zip_code_prefix (TEXT) [PRIMARY KEY]
  - lat (REAL)
  - lng (REAL)
  - city (TEXT)
  - state (TEXT)
```

```text
TABLE: order_items
ROW_COUNT: 112,650
PRIMARY_KEY: order_id, order_item_id
COLUMNS:
  - order_id (TEXT NOT NULL) [PRIMARY KEY]
  - order_item_id (INTEGER NOT NULL) [PRIMARY KEY]
  - product_id (TEXT NOT NULL)
  - seller_id (TEXT NOT NULL)
  - shipping_limit_date (DATETIME)
  - price (REAL)
  - freight_value (REAL)
RELATIONSHIPS:
  - order_items.seller_id -> sellers.seller_id
  - order_items.product_id -> products.product_id
  - order_items.order_id -> orders.order_id
```

```text
TABLE: order_payments
ROW_COUNT: 103,886
PRIMARY_KEY: order_id, payment_sequential
COLUMNS:
  - order_id (TEXT NOT NULL) [PRIMARY KEY]
  - payment_sequential (INTEGER NOT NULL) [PRIMARY KEY]
  - payment_type (TEXT)
  - payment_installments (INTEGER)
  - payment_value (REAL)
RELATIONSHIPS:
  - order_payments.order_id -> orders.order_id
```

```text
TABLE: order_reviews
ROW_COUNT: 99,224
PRIMARY_KEY: review_id, order_id
COLUMNS:
  - review_id (TEXT NOT NULL) [PRIMARY KEY]
  - order_id (TEXT NOT NULL) [PRIMARY KEY]
  - review_score (INTEGER)
  - review_comment_title (TEXT)
  - review_comment_message (TEXT)
  - review_creation_date (DATETIME)
  - review_answer_timestamp (DATETIME)
RELATIONSHIPS:
  - order_reviews.order_id -> orders.order_id
```

```text
TABLE: orders
ROW_COUNT: 99,441
PRIMARY_KEY: order_id
COLUMNS:
  - order_id (TEXT) [PRIMARY KEY]
  - customer_id (TEXT NOT NULL)
  - order_status (TEXT)
  - order_purchase_timestamp (DATETIME)
  - order_approved_at (DATETIME)
  - order_delivered_carrier_date (DATETIME)
  - order_delivered_customer_date (DATETIME)
  - order_estimated_delivery_date (DATETIME)
RELATIONSHIPS:
  - orders.customer_id -> customers.customer_id
```

```text
TABLE: products
ROW_COUNT: 32,951
PRIMARY_KEY: product_id
COLUMNS:
  - product_id (TEXT) [PRIMARY KEY]
  - product_category_name (TEXT)
  - product_name_length (INTEGER)
  - product_description_length (INTEGER)
  - product_photos_qty (INTEGER)
  - product_weight_g (REAL)
  - product_length_cm (REAL)
  - product_height_cm (REAL)
  - product_width_cm (REAL)
RELATIONSHIPS:
  - products.product_category_name -> category_translation.product_category_name
```

```text
TABLE: sellers
ROW_COUNT: 3,095
PRIMARY_KEY: seller_id
COLUMNS:
  - seller_id (TEXT) [PRIMARY KEY]
  - seller_zip_code_prefix (TEXT)
  - seller_city (TEXT)
  - seller_state (TEXT)
```

