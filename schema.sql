-- StockFlow Database Schema
-- Optimized for B2B SaaS with multi-warehouse and bundle support

-- 1. Tenants
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Warehousing
CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Products
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) NOT NULL UNIQUE, -- SKU unique per company is common, but challenge specified platform-wide uniqueness
    base_price DECIMAL(12, 2) NOT NULL,
    is_bundle BOOLEAN DEFAULT FALSE,
    low_stock_threshold INTEGER DEFAULT 10,
    primary_supplier_id INTEGER -- Optional link to primary supplier
);

-- 4. Junction for Bundles
CREATE TABLE bundle_items (
    parent_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    child_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (parent_id, child_id)
);

-- 5. Inventory Stock levels
CREATE TABLE inventory (
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, warehouse_id)
);

-- 6. Suppliers
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    active BOOLEAN DEFAULT TRUE
);

-- 7. Audit Trail
CREATE TABLE inventory_transactions (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    change_amount INTEGER NOT NULL,
    reason VARCHAR(50), 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_products_company ON products(company_id);
CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX idx_transactions_product ON inventory_transactions(product_id, created_at);
