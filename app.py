from flask import Flask, request, jsonify
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from datetime import datetime, timedelta
from models import db, Product, Inventory, Warehouse, Supplier, InventoryTransaction

app = Flask(__name__)
# Configuration for DB would go here: app.config['SQLALCHEMY_DATABASE_URI'] = '...'
db.init_app(app)

@app.route('/api/products', methods=['POST'])
def create_product():
    """Part 1: Fix - Atomic creation of product and initial inventory"""
    data = request.json or {}
    
    required_fields = ['name', 'sku', 'price', 'warehouse_id', 'initial_quantity']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        price = Decimal(str(data['price']))
        initial_qty = int(data['initial_quantity'])
        if price < 0 or initial_qty < 0:
            return jsonify({"error": "Values must be non-negative"}), 400
    except (InvalidOperation, ValueError):
        return jsonify({"error": "Invalid format for price or quantity"}), 400

    try:
        # Business Rule: Unique SKUs across the platform
        if Product.query.filter_by(sku=data['sku']).first():
            return jsonify({"error": f"SKU {data['sku']} already exists"}), 409

        new_product = Product(
            name=data['name'],
            sku=data['sku'],
            price=price,
            company_id=data.get('company_id', 1) # Default for demo
        )
        db.session.add(new_product)
        db.session.flush() # Get product.id

        new_inventory = Inventory(
            product_id=new_product.id,
            warehouse_id=data['warehouse_id'],
            quantity=initial_qty
        )
        db.session.add(new_inventory)
        db.session.commit()
        
        return jsonify({"message": "Product created", "product_id": new_product.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def get_low_stock_alerts(company_id):
    """Part 3: Proactive Low Stock Alerts based on burn rate"""
    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Products with sales in the last 30 days
        recent_sales_ids = db.session.query(InventoryTransaction.product_id)\
            .filter(
                InventoryTransaction.reason == 'sale',
                InventoryTransaction.created_at >= thirty_days_ago
            ).distinct().subquery()

        # Query items below threshold + active recently
        alerts = db.session.query(
            Inventory, Product, Warehouse, Supplier
        ).join(Product, Inventory.product_id == Product.id)\
         .join(Warehouse, Inventory.warehouse_id == Warehouse.id)\
         .outerjoin(Supplier, Product.primary_supplier_id == Supplier.id)\
         .filter(
             Product.company_id == company_id,
             Inventory.quantity <= Product.low_stock_threshold,
             Product.id.in_(recent_sales_ids)
         ).all()

        results = []
        for inv, prod, wh, supp in alerts:
            # Burn rate calculation
            sales_sum = db.session.query(func.abs(func.sum(InventoryTransaction.change_amount)))\
                .filter(
                    InventoryTransaction.product_id == prod.id,
                    InventoryTransaction.warehouse_id == wh.id,
                    InventoryTransaction.reason == 'sale',
                    InventoryTransaction.created_at >= thirty_days_ago
                ).scalar() or 0
            
            daily_burn = sales_sum / 30
            days_out = int(inv.quantity / daily_burn) if daily_burn > 0 else 999

            results.append({
                "product_id": prod.id,
                "product_name": prod.name,
                "sku": prod.sku,
                "warehouse_id": wh.id,
                "warehouse_name": wh.name,
                "current_stock": inv.quantity,
                "threshold": prod.low_stock_threshold,
                "days_until_stockout": days_out,
                "supplier": {
                    "id": getattr(supp, 'id', None),
                    "name": getattr(supp, 'name', 'N/A'),
                    "contact_email": getattr(supp, 'contact_email', 'N/A')
                }
            })

        return jsonify({"alerts": results, "total_alerts": len(results)}), 200

    except Exception as e:
        return jsonify({"error": "Unexpected error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
