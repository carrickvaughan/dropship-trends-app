# trend_dashboard.py

import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import sqlite3
from urllib.parse import quote_plus
from datetime import datetime, timedelta
import random

# ------------------------
# Constants
# ------------------------
DB_FILE = "trends.db"
ALI_PRODUCTS = ["Product A","Product B","Product C"]  # replace with your products

# ------------------------
# Initialize database
# ------------------------
conn = sqlite3.connect(DB_FILE)
conn.execute("""
CREATE TABLE IF NOT EXISTS trends (
    Time TEXT,
    Product TEXT,
    TrendScore REAL,
    ProfitPotential REAL
)
""")
conn.close()

# ------------------------
# Seed sample data if empty
# ------------------------
def seed_sample_trends():
    conn = sqlite3.connect(DB_FILE)
    times = [datetime.now() - timedelta(hours=i) for i in range(5, 0, -1)]
    rows = []
    for t in times:
        for p in ALI_PRODUCTS:
            rows.append({
                "Time": t.strftime("%Y-%m-%d %H:%M:%S"),
                "Product": p,
                "TrendScore": random.randint(20, 80),
                "ProfitPotential": random.randint(20, 80)
            })
    df_seed = pd.DataFrame(rows)
    df_seed.to_sql("trends", conn, if_exists="append", index=False)
    conn.close()

# Run seeding if empty
conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM trends")
if cur.fetchone()[0] == 0:
    print("Seeding database with sample trends...")
    seed_sample_trends()
conn.close()

# ------------------------
# Helper functions
# ------------------------
def compute_combined_trends(markup_multiplier=2.5, shipping_cost=3.0):
    data = []
    for p in ALI_PRODUCTS:
        price = random.randint(10,50)
        profit_margin = random.randint(20,70)
        trend_score = random.randint(10,80)
        profit_potential = round(profit_margin * price / 100,2)
        data.append({
            "Product": p,
            "GoogleScore": random.randint(10,50),
            "AliScore": random.randint(10,50),
            "TikTokScore": random.randint(10,50),
            "Price": price,
            "ProfitMargin": profit_margin,
            "TrendScore": trend_score,
            "ProfitPotential": profit_potential,
            "ImageURL": None,
            "AliURL": f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(p)}"
        })
    return pd.DataFrame(data)

def get_ad_creatives(product_name):
    return [{"image":"https://via.placeholder.com/120x80.png?text=Ad", "source":"https://example.com", "caption":"Sample Ad"}]

def save_trends_to_db(df):
    conn = sqlite3.connect(DB_FILE)
    df_to_save = df[["Product", "TrendScore", "ProfitPotential"]].copy()
    df_to_save["Time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_to_save.to_sql("trends", conn, if_exists="append", index=False)
    conn.close()

# ------------------------
# Initialize Dash
# ------------------------
app = dash.Dash(__name__)
app.title = "Dropship Trend Dashboard"

# ------------------------
# Layout
# ------------------------
app.layout = html.Div([
    html.H1("📊 Dropship Trend Dashboard", style={'textAlign':'center','color':'#00ffcc'}),
    
    html.Div(id="top-row", style={'margin':'20px 0'}),
    
    html.Div([
        html.Label("Markup Multiplier:"),
        dcc.Input(id="input-markup", type="number", value=2.5, step=0.1),
        html.Label("Shipping Cost:"),
        dcc.Input(id="input-ship", type="number", value=3.0, step=0.5),
        html.Button("Export Swipes", id="export-swipes")
    ], style={'textAlign':'center','margin':'10px'}),

    # Make table horizontally scrollable on mobile
    html.Div(id="table-container", style={'overflowX': 'auto', 'width': '100%', 'paddingBottom':'10px'}),
    
    html.Div([
        dcc.Graph(id="profit-bar-chart"),
        dcc.Graph(id="trend-line-chart")
    ], style={'display':'flex','flexDirection':'column', 'gap':'20px'}),

    dcc.Interval(id="interval", interval=5*60*1000)  # refresh every 5 min
], style={'backgroundColor':'#111','color':'#fff','fontFamily':'sans-serif','padding':'10px'})

# ------------------------
# Callback
# ------------------------
@app.callback(
    [Output("table-container","children"),
     Output("profit-bar-chart","figure"),
     Output("trend-line-chart","figure"),
     Output("top-row","children")],
    [Input("interval","n_intervals"),
     Input("input-markup","value"),
     Input("input-ship","value"),
     Input("export-swipes","n_clicks")]
)
def update_dashboard(n, markup, ship, export_clicks):
    try: markup = float(markup)
    except: markup = 2.5
    try: ship = float(ship)
    except: ship = 3.0

    # --- Compute trends safely ---
    df = compute_combined_trends(markup_multiplier=markup, shipping_cost=ship)

    # --- Save to DB ---
    try:
        save_trends_to_db(df)
    except Exception as e:
        print("Failed to save trends:", e)

    # --- Load historical data ---
    try:
        hist = pd.read_sql("SELECT * FROM trends ORDER BY Time ASC", sqlite3.connect(DB_FILE))
    except:
        hist = pd.DataFrame()

    # --- Top gainer ---
    top_badge = html.Div("No data yet", style={'textAlign':'center'})
    try:
        if len(hist) > 1:
            last_time = hist['Time'].max()
            last = hist[hist['Time'] == last_time].set_index('Product')['TrendScore']
            prev_time = sorted(hist['Time'].unique())[-2]
            prev = hist[hist['Time'] == prev_time].set_index('Product')['TrendScore']
            diffs = (last - prev).dropna()
            if not diffs.empty:
                gainer = diffs.idxmax()
                top_badge = html.Div([
                    html.Span("🏆 Top Gainer:", className='badge'),
                    html.Span(f" {gainer} (+{diffs.max():.1f})", style={'marginLeft':'8px','fontWeight':'700'})
                ], style={'textAlign':'center'})
    except Exception as e:
        print("Top gainer calc failed:", e)

    # --- Build table ---
    rows = []
    header = html.Tr([html.Th(h) for h in ["Image","Product","Price","Margin","Trend","ProfitPotential","Ads"]])
    for r in df.itertuples():
        try:
            creatives = get_ad_creatives(r.Product)
        except:
            creatives = []

        thumbs = []
        for c in creatives[:6]:
            thumbs.append(html.Div([
                html.A(html.Img(src=c['image'], style={"width":"120px","maxWidth":"100%","borderRadius":"4px"}), href=c['source'], target="_blank"),
                html.Br(),
                html.A("Save", href="#", target="_blank", style={'fontSize':'12px','color':'#9ad0ff'})
            ], style={'textAlign':'center'}))

        thumb_row = html.Div(
            thumbs,
            className='thumbnail-row',
            style={"display":"flex","overflowX":"auto","gap":"8px","paddingBottom":"4px"}
        )

        product_cell = html.Td([
            html.A(r.Product, href=r.AliURL, target="_blank", style={'fontWeight':'700','color':'#00ffcc'}),
            html.Div(r.ImageURL and html.Img(src=r.ImageURL, style={'width':'80px','maxWidth':'100%','borderRadius':'6px','marginTop':'6px'}) or "")
        ])
        rows.append(html.Tr([
            html.Td(html.Img(src=(r.ImageURL or f"https://via.placeholder.com/80x48.png?text={quote_plus(r.Product)}"), style={'width':'80px','maxWidth':'100%','borderRadius':'6px'})),
            product_cell,
            html.Td(f"${r.Price:.2f}"),
            html.Td(f"{r.ProfitMargin:.1f}%"),
            html.Td(f"{r.TrendScore:.1f}"),
            html.Td(f"{r.ProfitPotential:.1f}"),
            html.Td(thumb_row)
        ]))
    table = html.Table([header] + rows, style={'width':'100%','borderSpacing':'10px'})

    # --- Profit potential bar chart ---
    try:
        bar_fig = px.bar(df, x="Product", y="ProfitPotential", color="ProfitPotential",
                         title="💹 Profit Potential", color_continuous_scale=px.colors.sequential.Mint)
        bar_fig.update_layout(template="plotly_dark", height=420, margin=dict(t=50,l=25,r=25,b=120))
    except:
        bar_fig = px.bar(title="💹 Profit Potential")

    # --- Trend line chart ---
    try:
        if not hist.empty:
            line_fig = px.line(hist, x="Time", y="TrendScore", color="Product", title="📈 Trend Score Over Time",
                               markers=True)
            line_fig.update_layout(template="plotly_dark", height=420)
        else:
            line_fig = px.line(title="📈 Trend Score Over Time")
    except:
        line_fig = px.line(title="📈 Trend Score Over Time")

    return table, bar_fig, line_fig, top_badge

# ------------------------
# Run server
# ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)