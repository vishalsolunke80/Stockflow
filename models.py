from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    warehouses = db.relationship('Warehouse', backref='company', lazy=True)

class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.Text)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    low_stock_threshold = db.Column(db.Integer, default=10)
    primary_supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    
    inventory_levels = db.relationship('Inventory', backref='product', lazy=True)

class Inventory(db.Model):
    __tablename__ = 'inventory'
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), primary_key=True)
    quantity = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    contact_email = db.Column(db.String(255))

class InventoryTransaction(db.Model):
    __tablename__ = 'inventory_transactions'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False)
    warehouse_id = db.Column(db.Integer, nullable=False)
    change_amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(50)) # 'sale', 'restock', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
