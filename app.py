import pandas as pd
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, send_file
from io import StringIO
from datetime import datetime

app = Flask(__name__)
DATA_DIR = Path('data')

def load_table(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

def save_table(name: str, df: pd.DataFrame) -> None:
    path = DATA_DIR / f"{name}.csv"
    df.to_csv(path, index=False)

def identify_c_products(df_products: pd.DataFrame, df_orders: pd.DataFrame):
    if df_products.empty:
        return set()
    df_products['created_at'] = pd.to_datetime(df_products['created_at'])
    df_orders['created_at'] = pd.to_datetime(df_orders['created_at'])
    oldest = df_products.groupby('canonical_sku')['created_at'].min().reset_index()
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=5)
    old_skus = set(oldest[oldest['created_at'] < cutoff]['canonical_sku'])

    orders_2025 = df_orders[(df_orders['created_at'].dt.year == 2025)]
    if not orders_2025.empty:
        orders_2025 = orders_2025.merge(df_products[['offer_id','canonical_sku']], on='offer_id', how='left')
        skus_orders_2025 = set(orders_2025['canonical_sku'].dropna())
    else:
        skus_orders_2025 = set()

    delivered = df_orders[df_orders['status'] == 'Доставлен']
    if not delivered.empty:
        delivered = delivered.merge(df_products[['offer_id','canonical_sku']], on='offer_id', how='left')
        skus_delivered = set(delivered['canonical_sku'].dropna())
    else:
        skus_delivered = set()

    reviews = df_products.groupby('canonical_sku').agg({'reviews_count':'sum','rating_value':'sum'})
    zero_reviews = set(reviews[(reviews['reviews_count']==0) & (reviews['rating_value']==0)].index)

    c_skus = old_skus - skus_orders_2025 - skus_delivered
    c_skus = c_skus & zero_reviews
    return c_skus

def compute_abc(account_id=None):
    products = load_table('dim_product')
    orders = load_table('fact_orders')
    accounts = load_table('dim_account')
    if account_id:
        products = products[products['account_id']==int(account_id)]
        orders = orders[orders['account_id']==int(account_id)]
    if products.empty:
        return [], accounts
    orders = orders.merge(products[['offer_id','canonical_sku','family','title']], on='offer_id', how='left')
    delivered = orders[orders['status']=='Доставлен']
    revenue = delivered.groupby('canonical_sku')['revenue'].sum().sort_values(ascending=False)
    total = revenue.sum()
    if total == 0:
        revenue_share = revenue
    else:
        revenue_share = revenue/total
    cumshare = revenue_share.cumsum()

    def cat(val):
        if val <= 0.8:
            return 'A'
        elif val <= 0.95:
            return 'B'
        else:
            return 'C'
    df = revenue.reset_index().rename(columns={0:'revenue'})
    df['share'] = revenue_share.values
    df['cumshare'] = cumshare.values
    df['ABC'] = df['cumshare'].apply(cat)

    # add missing skus
    meta = products.groupby('canonical_sku').agg({'family':'first','title':'first'}).reset_index()
    df = meta.merge(df, on='canonical_sku', how='left').fillna({'revenue':0,'share':0,'cumshare':0,'ABC':'C'})

    c_skus = identify_c_products(products, orders)
    df.loc[df['canonical_sku'].isin(c_skus), 'ABC'] = 'C'

    return df.to_dict(orient='records'), accounts

@app.route('/')
def index():
    return redirect(url_for('abc'))

@app.route('/abc')
def abc():
    account_id = request.args.get('account_id')
    rows, accounts = compute_abc(account_id)
    return render_template('abc.html', rows=rows, accounts=accounts.to_dict(orient='records'), selected_account=account_id)

@app.route('/export/<table>')
def export_data(table):
    path = DATA_DIR / f"{table}.csv"
    if not path.exists():
        return 'No data', 404
    return send_file(path, as_attachment=True, download_name=f'{table}.csv')

@app.route('/export_abc')
def export_abc():
    account_id = request.args.get('account_id')
    rows, _ = compute_abc(account_id)
    df = pd.DataFrame(rows)
    buf = StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    filename = 'abc.csv' if not account_id else f'abc_{account_id}.csv'
    return send_file(buf, as_attachment=True, download_name=filename, mimetype='text/csv')

@app.route('/import', methods=['GET'])
def import_data():
    return render_template('upload.html')

@app.route('/import/<table>', methods=['POST'])
def upload(table):
    file = request.files.get('file')
    if not file:
        return redirect(url_for('import_data'))
    df = pd.read_csv(file)
    save_table(table, df)
    return redirect(url_for('import_data'))

if __name__ == '__main__':
    app.run(debug=True)
