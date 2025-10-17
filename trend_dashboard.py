# trend_dashboard.py

import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import sqlite3
from urllib.parse import quote_plus
from datetime import datetime

# ------------------------
# Constants
# ------------------------
DB_FILE = "trends.db"
ALI_PRODUCTS = ["Product A","Product B","Product C"]  # replace with your products

# ------------------------
# Helper functions
# ------------------------
def compute_combined_trends(markup_multiplier=2.5, shipping_cost=3.0):
    """
    Return a DataFrame with Product, GoogleScore, AliScore, TikTokScore,
    Price, ProfitMargin, TrendScore, ProfitPotential, ImageURL, AliURL
    Placeholder example; replace with your real computation.
    """
    data = []
    for p in ALI_PRODUCTS:
        data.append({
            "Product": p,
            "GoogleScore": 10,
            "AliScore": 10,
            "TikTokScore": 10,
            "Price": 20,
            "ProfitMargin": 50,
            "TrendScore": 30,
            "ProfitPotential": 30,
            "ImageURL": None,
            "AliURL": f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(p)}"
        })
    return pd.DataFrame(data)

def get_ad_creatives(product_name):
    """
    Return list of ad creatives for a product.
    Each creative is a dict with 'image', 'source', 'caption'.
    This is a placeholder; replace with real fetch.
    """
    return [{"image":"https://via.placeholder.com/120x80.png?text=Ad", "source":"https://example.com", "caption":"Sample Ad"}]

# ------------------------
# Initialize app
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

    html.Div(id="table-container", style={'marginTop':'20px'}),
    
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
    try:
        df = compute_combined_trends(markup_multiplier=markup, shipping_cost=ship)
        if df.empty: raise ValueError("compute_combined_trends returned empty")
    except Exception as e:
        print("Trend computation failed, using fallback:", e)
        df = pd.DataFrame({
            "Product": ALI_PRODUCTS,
            "GoogleScore": [10]*len(ALI_PRODUCTS),
            "AliScore": [10]*len(ALI_PRODUCTS),
            "TikTokScore": [10]*len(ALI_PRODUCTS),
            "Price": [20]*len(ALI_PRODUCTS),
            "ProfitMargin": [50]*len(ALI_PRODUCTS),
            "TrendScore": [30]*len(ALI_PRODUCTS),
            "ProfitPotential": [30]*len(ALI_PRODUCTS),
            "ImageURL": [None]*len(ALI_PRODUCTS),
            "AliURL": [f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(p)}" for p in ALI_PRODUCTS]
        })

    # --- Load history safely ---
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
        except Exception as e:
            print("Creative fetch failed:", e)
            creatives = []

        thumbs = []
        for c in creatives[:6]:
            thumbs.append(html.Div([
                html.A(html.Img(src=c['image'], className='thumb'), href=c['source'], target="_blank"),
                html.Br(),
                html.A("Save", href="#", target="_blank", style={'fontSize':'12px','color':'#9ad0ff'})
            ], style={'display':'inline-block','textAlign':'center','width':'120px'}))

        thumb_row = html.Div(thumbs, className='thumbnail-row')
        product_cell = html.Td([
            html.A(r.Product, href=r.AliURL if hasattr(r,'AliURL') else f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(r.Product)}", target="_blank", style={'fontWeight':'700','color':'#00ffcc'}),
            html.Div(r.ImageURL and html.Img(src=r.ImageURL, style={'width':'80px','borderRadius':'6px','marginTop':'6px'}) or "")
        ])
        rows.append(html.Tr([
            html.Td(html.Img(src=(r.ImageURL or f"https://via.placeholder.com/80x48.png?text={quote_plus(r.Product)}"), style={'width':'80px','borderRadius':'6px'})),
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
        bar_fig = px.bar(df, x="Product", y="ProfitPotential", color="ProfitPotential", title="💹 Profit Potential", color_continuous_scale="Mint")
        bar_fig.update_layout(template="plotly_dark", height=420, margin=dict(t=50,l=25,r=25,b=120))
    except Exception as e:
        print("Bar chart failed:", e)
        bar_fig = px.bar(title="💹 Profit Potential")

    # --- Trend line chart ---
    try:
        if not hist.empty:
            line_fig = px.line(hist, x="Time", y="TrendScore", color="Product", title="📈 Trend Score Over Time")
            line_fig.update_layout(template="plotly_dark", height=420)
        else:
            line_fig = px.line(title="📈 Trend Score Over Time")
    except Exception as e:
        print("Line chart failed:", e)
        line_fig = px.line(title="📈 Trend Score Over Time")

    return table, bar_fig, line_fig, top_badge

# ------------------------
# Run server
# ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)