-- =============================================
-- SUPERAPP COMMERCE + DIAGNOSTICS SCHEMA
-- =============================================

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    items JSON,
    total_amount DECIMAL(10,2),
    status VARCHAR(50),
    tracking_id VARCHAR(100),
    delivery_partner VARCHAR(100),
    estimated_delivery DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_tracking (
    id INT PRIMARY KEY,
    order_id INT,
    status VARCHAR(50),
    location VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE superapp_lab_tests (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    category VARCHAR(100),
    price DECIMAL(10,2),
    preparation_instructions TEXT,
    report_time VARCHAR(50)
);

CREATE TABLE lab_bookings (
    id INT PRIMARY KEY,
    user_id INT,
    test_ids JSON,
    collection_address TEXT,
    collection_time DATETIME,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE loyalty_points (
    user_id INT PRIMARY KEY,
    points INT DEFAULT 0,
    tier VARCHAR(20) DEFAULT 'bronze',
    total_spent DECIMAL(10,2) DEFAULT 0
);

CREATE TABLE rewards (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    points_required INT,
    description TEXT,
    type VARCHAR(50)
);

CREATE TABLE campaign_logs (
    id INT PRIMARY KEY,
    user_id INT,
    campaign_type VARCHAR(100),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    opened BOOLEAN DEFAULT FALSE,
    converted BOOLEAN DEFAULT FALSE
);
