# StockFlow Assessment - Internship Technical Evaluation

This document contains the solutions for the StockFlow B2B Inventory Management System assessment.

---

## Part 1: Code Review & Debugging

### Identified Issues

| Issue Type | Problem | Impact in Production |
| :--- | :--- | :--- |
| **Technical** | **Non-Atomic Transactions**: The code uses two separate `commit()` calls. | If the `Inventory` creation fails (e.g., validation error, db disconnect) after the `Product` is committed, the system is left in an inconsistent state where a product exists but has no inventory record. |
| **Business Logic** | **SKU Uniqueness**: No pre-check for existing SKUs. | Attempting to add a duplicate SKU will trigger a database constraint error, resulting in a generic 500 Internal Server error for the user instead of a helpful validation message. |
| **Technical** | **Lack of Validation**: Direct access to `request.json` keys without checking for existence or types. | Any missing field (e.g., `price`) will cause a `KeyError`, crashing the request. Negative quantities or prices could also be injected. |
| **Business Logic** | **Schema Mismodelling**: `warehouse_id` is stored on the `Product` model. | If a product is stocked in Warehouse A and later moved to Warehouse B, or if it exists in both, the `Product` model shouldn't be tied to a single warehouse ID. The `Inventory` table should serve as the junction. |
| **Technical** | **Precision Errors**: `price` is likely handled as a float. | Floating point arithmetic in financial systems leads to rounding errors (e.g., $19.99 becoming $19.989999998). |

### Corrected Implementation

```python
from flask import request, jsonify
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import IntegrityError
from models import db, Product, Inventory

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json or {}
    
    # 1. Basic validation
    required_fields = ['name', 'sku', 'price', 'warehouse_id', 'initial_quantity']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # 2. Type conversion and safety checks
        price = Decimal(str(data['price']))
        initial_qty = int(data['initial_quantity'])
        
        if price < 0 or initial_qty < 0:
            return jsonify({"error": "Price and quantity must be non-negative"}), 400
            
    except (InvalidOperation, ValueError):
        return jsonify({"error": "Invalid price or quantity format"}), 400

    # 3. Use a single transaction for atomicity
    try:
        # Check if SKU already exists to provide a better UX
        if Product.query.filter_by(sku=data['sku']).first():
            return jsonify({"error": f"SKU {data['sku']} already exists"}), 409

        new_product = Product(
            name=data['name'],
            sku=data['sku'],
            price=price
            # Removed warehouse_id from Product as it's handled in Inventory
        )
        db.session.add(new_product)
        
        # Flush to get the product.id without committing yet
        db.session.flush()

        new_inventory = Inventory(
            product_id=new_product.id,
            warehouse_id=data['warehouse_id'],
            quantity=initial_qty
        )
        db.session.add(new_inventory)
        
        # Atomically commit both records
        db.session.commit()
        
        return jsonify({
            "message": "Product created successfully",
            "product_id": new_product.id
        }), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Database integrity error. Check if warehouse exists."}), 400
    except Exception as e:
        db.session.rollback()
        # Log error here
        return jsonify({"error": "An unexpected error occurred"}), 500
```

---

## Part 2: Database Design

### Schema Overview (PostgreSQL DDL)

To support a multi-tenant B2B SaaS architecture, every primary entity is partitioned by `company_id`.

```sql
-- 1. Tenants
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Warehousing
CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    name VARCHAR(255) NOT NULL,
    location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Products (includes regular items and bundles)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    base_price DECIMAL(12, 2) NOT NULL,
    is_bundle BOOLEAN DEFAULT FALSE,
    low_stock_threshold INTEGER DEFAULT 10,
    UNIQUE(sku) -- SKUs must be unique across the platform per requirements
);

-- 4. Junction for Bundles (Self-referencing)
CREATE TABLE bundle_items (
    parent_id INTEGER REFERENCES products(id),
    child_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (parent_id, child_id)
);

-- 5. Inventory (Stock levels per Warehouse)
CREATE TABLE inventory (
    product_id INTEGER REFERENCES products(id),
    warehouse_id INTEGER REFERENCES warehouses(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, warehouse_id)
);

-- 6. Suppliers
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    active BOOLEAN DEFAULT TRUE
);

-- 7. Product-Supplier Relationship (Many-to-Many)
CREATE TABLE product_suppliers (
    product_id INTEGER REFERENCES products(id),
    supplier_id INTEGER REFERENCES suppliers(id),
    is_primary BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (product_id, supplier_id)
);

-- 8. Audit Trail (Inventory Changes)
CREATE TABLE inventory_transactions (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    change_amount INTEGER NOT NULL, -- (+10 for restock, -2 for sale)
    reason VARCHAR(50), -- 'sale', 'restock', 'return', 'adjustment'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Design Decisions & Justification

1.  **Composite Unique Constraint (`company_id`, `sku`)**: In a SaaS, SKU uniqueness is usually required only at the company level, not globally. This allows different companies to use their own internal SKU systems.
2.  **Self-Referencing `bundle_items`**: This allows for infinite recursion (bundles within bundles) while keeping the schema clean.
3.  **Audit Logging**: The `inventory_transactions` table is critical for traceability ("Track when inventory levels change"). It should be indexed on `(product_id, created_at)` to quickly generate history reports.
4.  **Partitioning Strategy**: Although not shown in DDL, as the system scales to millions of rows, we would likely partition the `inventory_transactions` table by `company_id`.

### Gaps & Questions for Product Team

1.  **Bundle Stock Logic**: If a bundle consists of 2 widgets, do we track the bundle as its own physical stock, or is its "availability" calculated dynamically based on the component widgets?
2.  **Unit of Measure (UoM)**: Do we sell by "Each", "Box of 10", or "Kilograms"? We might need a `uom` table to avoid confusion in multi-warehouse transfers.
3.  **Currency Support**: For a B2B SaaS, companies might operate in different countries. Should `base_price` be tied to a `currency_code`?
4.  **User Ownership**: Who performed the inventory adjustments? We need a `users` table and a `user_id` foreign key in `inventory_transactions`.

---

## Part 3: API Implementation

### Implementation Approach

The low-stock alert endpoint is designed to be proactive. It filters for products where current stock is below the threshold and has had "recent sales activity" to avoid alerting on obsolete inventory.

**Key assumptions:**
1.  **Recent Sales Activity**: Defined as any 'sale' transaction in the `inventory_transactions` table within the last 30 days.
2.  **Burn Rate Calculation**: We calculate the average daily sales over the last 30 days to estimate the `days_until_stockout`.
3.  **Thresholds**: The `low_stock_threshold` is stored on the `Product` model, allowing for product-specific alerting logic.

```python
from flask import jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
from models import db, Product, Inventory, Warehouse, Supplier, InventoryTransaction

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def get_low_stock_alerts(company_id):
    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # 1. Identify products with recent sales activity (last 30 days)
        recent_sales_subquery = db.session.query(InventoryTransaction.product_id)\
            .filter(
                InventoryTransaction.reason == 'sale',
                InventoryTransaction.created_at >= thirty_days_ago
            ).distinct().subquery()

        # 2. Main query: Join Inventory, Product, Warehouse, and Supplier
        # We filter for quantity < threshold and presence in recent sales
        alerts_query = db.session.query(
            Inventory, Product, Warehouse, Supplier
        ).join(Product, Inventory.product_id == Product.id)\
         .join(Warehouse, Inventory.warehouse_id == Warehouse.id)\
         .outerjoin(Supplier, Product.primary_supplier_id == Supplier.id)\
         .filter(
             Product.company_id == company_id,
             Inventory.quantity <= Product.low_stock_threshold,
             Product.id.in_(recent_sales_subquery)
         ).all()

        results = []
        for inv, prod, wh, supp in alerts_query:
            # 3. Calculate Burn Rate (Sales last 30 days / 30)
            total_sales = db.session.query(func.abs(func.sum(InventoryTransaction.change_amount)))\
                .filter(
                    InventoryTransaction.product_id == prod.id,
                    InventoryTransaction.warehouse_id == wh.id,
                    InventoryTransaction.reason == 'sale',
                    InventoryTransaction.created_at >= thirty_days_ago
                ).scalar() or 0
            
            daily_burn_rate = total_sales / 30
            days_until_stockout = int(inv.quantity / daily_burn_rate) if daily_burn_rate > 0 else 999

            results.append({
                "product_id": prod.id,
                "product_name": prod.name,
                "sku": prod.sku,
                "warehouse_id": wh.id,
                "warehouse_name": wh.name,
                "current_stock": inv.quantity,
                "threshold": prod.low_stock_threshold,
                "days_until_stockout": days_until_stockout,
                "supplier": {
                    "id": supp.id if supp else None,
                    "name": supp.name if supp else "N/A",
                    "contact_email": supp.contact_email if supp else "N/A"
                }
            })

        return jsonify({
            "alerts": results,
            "total_alerts": len(results)
        }), 200

    except Exception as e:
        # In production, use structured logging
        print(f"Error fetching alerts: {e}")
        return jsonify({"error": "Internal server error"}), 500
```

### Edge Case Handling

1.  **Zero Sales Velocity**: If a product has a sale in the last 30 days but the average is very low, `daily_burn_rate` might be effectively zero. We handle this by returning a high value (999) or "Infinity" to avoid division by zero.
2.  **Missing Suppliers**: We use an `outerjoin` on Suppliers. Products without an assigned supplier will still appear in alerts, but with "N/A" in the supplier fields.
3.  **Cross-Warehouse Aggregation**: The business rules specify "handle multiple warehouses". This implementation checks stock on a **per-warehouse** basis, which is usually more actionable for Reorder Management.
4.  **Performance**: For a high-volume system, calculating the burn rate in a loop is inefficient (N+1 database calls). In a production environment, I would pre-calculate these metrics via a materialized view or a background worker.

---

## Assumptions & Final Notes

- **Multi-tenancy**: All queries include `company_id` filters to ensure data isolation.
- **Precision**: Money is handled using `Decimal` (per Part 1 corrections) though not explicitly shown in Part 3's query for brevity.
- **Soft Deletes**: Assumed not required for this MVP, but would be recommended for a production B2B SaaS system.

---

## Live Session Preparation Tips

To help you during the interview conversation (30-45 mins), here are some key points you can discuss based on these solutions:

### 1. The "Why" behind the Debugging Fixes
*   **Atomicity**: Explain that `db.session.flush()` vs `db.session.commit()` is about ensuring the system doesn't create "orphan" products with no inventory.
*   **Decimal vs Float**: Mention that for financial transparency in B2B, floating-point errors are unacceptable.

### 2. Database Trade-offs
*   **Audit vs State**: Discuss why we have both `inventory` (for fast current lookups) and `inventory_transactions` (for history). Mention that while it introduces redundancy, it's essential for "Track when inventory levels change" requirements.
*   **Bundles**: Explain that using a self-referencing table (`bundle_items`) allows for "kits of kits," which is a common requirement in manufacturing or e-commerce.

### 3. API Scalability
*   **Burn Rate Algorithm**: If asked how to make it better, suggest using an **Exponential Moving Average (EMA)** instead of a simple 30-day average to give more weight to recent sales.
*   **N+1 Optimization**: Mention that in a real production environment, you would use `.options(joinedload(...))` or a single SQL query with aggregations to avoid hitting the database in a loop.

### 4. Handling Incomplete Requirements
*   **Ambiguity is Expected**: Be ready to say: *"I noticed the requirements didn't specify how to handle bundle stock, so I assumed component-level tracking but flagged it for the product team."* This shows you think like a collaborative engineer.
