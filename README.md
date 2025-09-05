# Sales Dashboard

Flask-based dashboard to manage and analyse store sales.

## Features
- Upload or download CSV data for `dim_account`, `dim_canonical_sku`, `dim_product`, `fact_orders`.
- ABC analysis aggregated by canonical SKU with optional store filter.
- Automatic identification of category **C** products:
  - created more than five months ago,
  - no orders recorded in 2025,
  - no delivered orders,
  - zero reviews and zero rating.
- Export ABC results to CSV.

## Setup
```bash
pip install -r requirements.txt
python app.py
```
Visit `http://localhost:5000` in your browser.

## Data
CSV files are stored in the `data/` folder. Use the *Import Data* page to upload new data or download existing files.
