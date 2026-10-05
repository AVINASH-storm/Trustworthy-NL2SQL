# Dataset Profiling Summary

Generated at: 2026-10-05T13:32:21.759122

| Table | Rows | Cols | Candidate Primary Key | Composite? |
|---|---:|---:|---|---|
| `customers` | 99,441 | 5 | `customer_id` | No |
| `geolocation` | 1,000,163 | 5 | `None` | No |
| `order_items` | 112,650 | 7 | `order_id, order_item_id` | Yes |
| `order_payments` | 103,886 | 5 | `order_id, payment_sequential` | Yes |
| `order_reviews` | 99,224 | 7 | `review_id, order_id` | Yes |
| `orders` | 99,441 | 8 | `order_id, customer_id` | No |
| `products` | 32,951 | 9 | `product_id` | No |
| `sellers` | 3,095 | 4 | `seller_id` | No |
| `product_category_name_translation` | 71 | 2 | `product_category_name, product_category_name_english` | No |


## Detailed Column Profiles

### Table: `customers` (99,441 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `customer_id` | TEXT | 0 | 0.0% | 99,441 | "06b8999e2fba1a1fbc88172c00ba8bc7", "18955e83d337fd6b2def6b18a428ac77" |
| `customer_unique_id` | TEXT | 0 | 0.0% | 96,096 | "861eff4711a542e4b93843c6dd7febb0", "290c77bc529b7ac935b93aa66c333dc3" |
| `customer_zip_code_prefix` | INTEGER | 0 | 0.0% | 14,994 | "14409", "09790" |
| `customer_city` | TEXT | 0 | 0.0% | 4,119 | "franca", "sao bernardo do campo" |
| `customer_state` | TEXT | 0 | 0.0% | 27 | "SP", "SC" |

### Table: `geolocation` (1,000,163 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `geolocation_zip_code_prefix` | INTEGER | 0 | 0.0% | 19,015 | "01037", "01046" |
| `geolocation_lat` | REAL | 0 | 0.0% | 717,372 | "-23.54562128115268", "-23.546081127035535" |
| `geolocation_lng` | REAL | 0 | 0.0% | 717,615 | "-46.63929204800168", "-46.64482029837157" |
| `geolocation_city` | TEXT | 0 | 0.0% | 8,010 | "sao paulo", "são paulo" |
| `geolocation_state` | TEXT | 0 | 0.0% | 27 | "SP", "RN" |

### Table: `order_items` (112,650 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `order_id` | TEXT | 0 | 0.0% | 98,666 | "00010242fe8c5a6d1ba2dd792cb16214", "00018f77f2f0320c557190d7a144bdd3" |
| `order_item_id` | INTEGER | 0 | 0.0% | 21 | "1", "2" |
| `product_id` | TEXT | 0 | 0.0% | 32,951 | "4244733e06e7ecb4970a6e2683c13e61", "e5f2d52b802189ee658865ca93d83a8f" |
| `seller_id` | TEXT | 0 | 0.0% | 3,095 | "48436dade18ac8b2bce089ec2a041202", "dd7ddc04e1b6c2c614352b383efe2d36" |
| `shipping_limit_date` | DATETIME | 0 | 0.0% | 93,318 | "2017-09-19 09:45:35", "2017-05-03 11:05:13" |
| `price` | REAL | 0 | 0.0% | 5,968 | "58.90", "239.90" |
| `freight_value` | REAL | 0 | 0.0% | 6,999 | "13.29", "19.93" |

### Table: `order_payments` (103,886 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `order_id` | TEXT | 0 | 0.0% | 99,440 | "b81ef226f3fe1789b1e8b2acac839d17", "a9810da82917af2d9aefd1278f1dcfa0" |
| `payment_sequential` | INTEGER | 0 | 0.0% | 29 | "1", "2" |
| `payment_type` | TEXT | 0 | 0.0% | 5 | "credit_card", "boleto" |
| `payment_installments` | INTEGER | 0 | 0.0% | 24 | "8", "1" |
| `payment_value` | REAL | 0 | 0.0% | 29,077 | "99.33", "24.39" |

### Table: `order_reviews` (99,224 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `review_id` | TEXT | 0 | 0.0% | 98,410 | "7bc2406110b926393aa56f80a40eba40", "80e641a11e56f04c1ad469d5645fdfde" |
| `order_id` | TEXT | 0 | 0.0% | 98,673 | "73fc7af87114b39712e6da79b0a377eb", "a548910a1c6147796b98fdf73dbeba33" |
| `review_score` | INTEGER | 0 | 0.0% | 5 | "4", "5" |
| `review_comment_title` | TEXT | 87,658 | 88.34% | 4,178 | "recomendo", "Super recomendo" |
| `review_comment_message` | TEXT | 58,274 | 58.73% | 35,616 | "Recebi bem antes do prazo estipulado.", "Parabéns lojas lannister adorei comprar pela Internet seguro e prático Parabéns a todos feliz Páscoa" |
| `review_creation_date` | DATETIME | 0 | 0.0% | 636 | "2018-01-18 00:00:00", "2018-03-10 00:00:00" |
| `review_answer_timestamp` | DATETIME | 0 | 0.0% | 98,248 | "2018-01-18 21:46:59", "2018-03-11 03:05:13" |

### Table: `orders` (99,441 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `order_id` | TEXT | 0 | 0.0% | 99,441 | "e481f51cbdc54678b7cc49136f2d6af7", "53cdb2fc8bc7dce0b6741e2150273451" |
| `customer_id` | TEXT | 0 | 0.0% | 99,441 | "9ef432eb6251297304e76186b10a928d", "b0830fb4747a6c6d20dea0b8c802d7ef" |
| `order_status` | TEXT | 0 | 0.0% | 8 | "delivered", "invoiced" |
| `order_purchase_timestamp` | DATETIME | 0 | 0.0% | 98,875 | "2017-10-02 10:56:33", "2018-07-24 20:41:37" |
| `order_approved_at` | DATETIME | 160 | 0.16% | 90,733 | "2017-10-02 11:07:15", "2018-07-26 03:24:27" |
| `order_delivered_carrier_date` | DATETIME | 1,783 | 1.79% | 81,018 | "2017-10-04 19:55:00", "2018-07-26 14:31:00" |
| `order_delivered_customer_date` | DATETIME | 2,965 | 2.98% | 95,664 | "2017-10-10 21:25:13", "2018-08-07 15:27:45" |
| `order_estimated_delivery_date` | DATETIME | 0 | 0.0% | 459 | "2017-10-18 00:00:00", "2018-08-13 00:00:00" |

### Table: `products` (32,951 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `product_id` | TEXT | 0 | 0.0% | 32,951 | "1e9e8ef04dbcff4541ed26657ea517e5", "3aa071139cb16b67ca9e5dea641aaa2f" |
| `product_category_name` | TEXT | 610 | 1.85% | 73 | "perfumaria", "artes" |
| `product_name_lenght` | INTEGER | 610 | 1.85% | 66 | "40", "44" |
| `product_description_lenght` | INTEGER | 610 | 1.85% | 2,960 | "287", "276" |
| `product_photos_qty` | INTEGER | 610 | 1.85% | 19 | "1", "4" |
| `product_weight_g` | INTEGER | 2 | 0.01% | 2,204 | "225", "1000" |
| `product_length_cm` | INTEGER | 2 | 0.01% | 99 | "16", "30" |
| `product_height_cm` | INTEGER | 2 | 0.01% | 102 | "10", "18" |
| `product_width_cm` | INTEGER | 2 | 0.01% | 95 | "14", "20" |

### Table: `sellers` (3,095 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `seller_id` | TEXT | 0 | 0.0% | 3,095 | "3442f8959a84dea7ee197c632cb2df15", "d1b65fc7debc3361ea86b5f14c68d2e2" |
| `seller_zip_code_prefix` | INTEGER | 0 | 0.0% | 2,246 | "13023", "13844" |
| `seller_city` | TEXT | 0 | 0.0% | 611 | "campinas", "mogi guacu" |
| `seller_state` | TEXT | 0 | 0.0% | 23 | "SP", "RJ" |

### Table: `product_category_name_translation` (71 rows)

| Column | Inferred Type | Nulls | Null % | Unique | Sample Values |
|---|---|---:|---:|---:|---|
| `product_category_name` | TEXT | 0 | 0.0% | 71 | "beleza_saude", "informatica_acessorios" |
| `product_category_name_english` | TEXT | 0 | 0.0% | 71 | "health_beauty", "computers_accessories" |

