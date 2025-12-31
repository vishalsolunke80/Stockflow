# StockFlow: B2B Inventory Management System

StockFlow is a multi-tenant B2B SaaS platform designed for small businesses to track products across multiple warehouses and manage supplier relationships efficiently.

## 🚀 Project Overview

This repository contains the technical assessment for the StockFlow platform, covering:
- **Part 1**: Production-ready API debugging and refactoring.
- **Part 2**: Scalable multi-tenant database schema design.
- **Part 3**: Proactive low-stock alerting with stockout forecasting.

---

## 📂 Project Structure

- `app.py`: Flask application containing the core API endpoints.
- `models.py`: SQLAlchemy database models defining the enterprise entities.
- `schema.sql`: Raw SQL DDL for database initialization and indexing.
- `README.md`: This documentation.

---

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.8+
- Flask & Flask-SQLAlchemy
- PostgreSQL (or SQLite for local testing)

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install flask flask-sqlalchemy
   ```
3. Initialize the database using `schema.sql` or let `models.py` handle it via `db.create_all()`.
4. Run the application:
   ```bash
   python app.py
   ```

---

## 📋 Technical Decisions & Solutions

### 1. Code Review & Debugging (Part 1)
The initial implementation suffered from transaction atomicity issues and weak validation. The refactored code in `app.py` ensures:
- **Atomicity**: Single `commit()` calls prevent partial data states.
- **Precision**: Uses `Decimal` for financial values to avoid floating-point errors.
- **Validation**: Robust SKU uniqueness checks and input sanitization.

### 2. Database Design (Part 2)
The schema is designed for a multi-tenant environment:
- **Global SKU Uniqueness**: Enforced at the platform level.
- **Bundle Support**: Self-referencing `bundle_items` table allows for unlimited kit nesting.
- **Audit Logging**: `inventory_transactions` provides a full history of all stock movements.

### 3. API Implementation (Part 3)
The low-stock alert endpoint (`GET /api/companies/{id}/alerts/low-stock`) goes beyond status checks by calculating:
- **Burn Rate**: Average daily sales over the last 30 days.
- **Stockout Forecasting**: Estimated `days_until_stockout` to help businesses prioritize reordering.

---

## 💡 Interview Preparation Tips

During the live session, be ready to discuss:
1. **Concurrency**: How we'd handle race conditions when multiple warehouses restock simultaneously.
2. **Scalability**: Moving burn-rate calculations to background workers or materialized views for high-volume data.
3. **Product Vision**: Handling "Bundle" inventory logic (calculating bundle availability vs. physical bundle stock).

---

## 📝 Assumptions Made
- Recent sales activity is defined as any 'sale' within the last 30 days.
- SKUs are unique across the entire StockFlow platform.
- Multi-tenancy is enforced via mandatory `company_id` filters on all primary queries.
