# trend_dashboard.py
import os
import random
import sqlite3
import pandas as pd
import io
from datetime import datetime, timedelta
from urllib.parse import quote_plus, unquote_plus
from dash import Dash, html, dcc, Input, Output
import plotly.express as px
from pytrends.request import TrendReq
import requests
from bs4 import BeautifulSoup
from flask import send_file, make_response, redirect

# ----------------------------
# Config
# ----------------------------
GOOGLE_KEYWORDS = [
    "portable blender", "wireless earbuds", "led strip lights",
    "magnetic eyelashes", "car phone holder", "mini projector", "pet grooming glove"
]
ALI_PRODUCTS = [
    "LED Strip Lights", "Portable Blender", "Magnetic Eyelashes",
    "Pet Grooming Glove", "Car Phone Holder", "Mini Projector"
]

REFRESH_INTERVAL_MS = 60 * 1000
DB_FILE = "trends.db"
AD_CREATIVE_CACHE_HOURS = 12  # reuse cached creatives within this period

# ----------------------------
# Database (SQLite simple wrappers)
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # main historical trends table (already used elsewhere)
    c.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            Time TEXT,
            Product TEXT,
            GoogleScore REAL,
            AliScore REAL,
            TikTokScore REAL,
            TrendScore REAL,
            Price REAL,
            ProfitMargin REAL,
            ProfitPotential REAL,
            ImageURL TEXT
        )
    """)
    # ad creatives cache
    c.execute("""
        CREATE TABLE IF NOT EXISTS ad_creatives (
            Product TEXT,
            ImageURL TEXT,
            Caption TEXT,
            SourceURL TEXT,
            FetchedAt TEXT
        )
    """)
    # saved swipe file (user-saved creatives)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ad_swipes (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            Product TEXT,
            ImageURL TEXT,
            Caption TEXT,
            SourceURL TEXT,
            SavedAt TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_trends_df(df):
    conn = sqlite3.connect(DB_FILE)
    df.to_sql('trends', conn, if_exists='append', index=False)
    conn.close()

def query_ad_creatives(product):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT ImageURL, Caption, SourceURL, FetchedAt FROM ad_creatives WHERE Product = ?", (product,))
    rows = cur.fetchall()
    conn.close()
    return [{"image": r[0], "caption": r[1], "source": r[2], "fetched": r[3]} for r in rows]

def upsert_ad_creatives(product, creatives):
    """Overwrite cached creatives for product."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM ad_creatives WHERE Product = ?", (product,))
    for c in creatives:
        cur.execute(
            "INSERT INTO ad_creatives (Product, ImageURL, Caption, SourceURL, FetchedAt) VALUES (?, ?, ?, ?, ?)",
            (product, c.get("image"), c.get("caption",""), c.get("source"), datetime.utcnow().isoformat())
        )
    conn.commit()
    conn.close()

def save_swipe(product, image_url, caption, source):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO ad_swipes (Product, ImageURL, Caption, SourceURL, SavedAt) VALUES (?, ?, ?, ?, ?)",
                (product, image_url, caption, source, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_all_swipes_df():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM ad_swipes ORDER BY SavedAt DESC", conn)
    conn.close()
    return df

init_db()

# ----------------------------
# Data fetchers (robust + safe fallbacks)
# ----------------------------
def get_google_trends(keywords):
    growth = {}
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload(keywords, timeframe='now 14-d')
        data = pytrends.interest_over_time()
        if data.empty:
            raise ValueError("Google Trends returned empty data")
        if 'isPartial' in data.columns:
            data = data.drop(columns=['isPartial'])
        for kw in keywords:
            s = data[kw]
            if len(s) >= 9:
                recent = s.tail(2).mean()
                prev = s[-9:-2].mean()
            else:
                recent = s.tail(1).mean()
                prev = s[:-1].mean()
            pct = ((recent - prev) / (prev + 1e-6)) * 100
            growth[kw] = round(float(pct), 2)
    except Exception as e:
        # fallback semi-realistic numbers
        print("Google fallback:", e)
        growth = {kw: random.randint(5,50) for kw in keywords}
    return growth

def get_aliexpress_data(products):
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"}
    data = {}
    for product in products:
        try:
            url = f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(product)}"
            r = requests.get(url, headers=headers, timeout=6)
            soup = BeautifulSoup(r.text, 'html.parser')

            # Attempt to select first product card and extract image & price
            # AliExpress markup is JS-heavy; this is a best-effort attempt; fallback used if not found.
            card = soup.select_one("a._3t7zg._2f4Ho") or soup.find("a", href=True)
            img = None
            price_val = None
            if card:
                img_tag = card.find("img")
                if img_tag and img_tag.get("src"):
                    img = img_tag.get("src")
                # look inside nearby text for $ signs (best-effort)
                text = card.get_text(" ", strip=True) if card else ""
                for token in text.split():
                    if "$" in token:
                        try:
                            price_val = float(token.replace("$","").split("-")[0])
                            break
                        except:
                            continue

            if not price_val:
                price_val = round(random.uniform(5, 50), 2)
            cost = price_val
            sell = cost * 2.5
            margin = ((sell - cost) / sell) * 100
            orders = random.randint(10, 200)

            data[product] = {
                "orders": orders,
                "price": round(cost, 2),
                "margin": round(margin, 2),
                "image": img,
                "url": url
            }
        except Exception as e:
            print("AliExpress fallback for", product, ":", e)
            data[product] = {
                "orders": random.randint(10,200),
                "price": round(random.uniform(10,50),2),
                "margin": round(random.uniform(25,70),2),
                "image": None,
                "url": f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(product)}"
            }
    return data

def get_tiktok_trends(products):
    # Placeholder for real tiktok scraping/API; return robust random if not available
    return {p: random.randint(5,100) for p in products}

# ----------------------------
# Ad creatives fetcher + caching
# ----------------------------
def _now_utc():
    return datetime.utcnow()

def get_ad_creatives(product):
    """
    Returns list of creatives dict: {"image","caption","source"}.
    Uses DB cache for AD_CREATIVE_CACHE_HOURS. If cache missing/stale, attempts
    a best-effort scrape of public ad libs (FB) with very gentle fallback to placeholder images.
    """
    # check cache
    rows = query_ad_creatives(product)
    if rows:
        fetched = rows[0].get("fetched")
        if fetched:
            fetched_dt = datetime.fromisoformat(fetched)
            if _now_utc() - fetched_dt < timedelta(hours=AD_CREATIVE_CACHE_HOURS):
                return rows  # use cache

    creatives = []
    # try Facebook Ad Library quick fetch (best-effort)
    try:
        search_url = f"https://www.facebook.com/ads/library/?q={quote_plus(product)}"
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"}
        r = requests.get(search_url, headers=headers, timeout=6)
        if r.ok and len(r.text) > 1000:
            soup = BeautifulSoup(r.text, 'html.parser')
            # find first few <img> tags as thumbnails (best-effort)
            imgs = []
            for img_tag in soup.find_all("img"):
                src = img_tag.get("src")
                if src and src.startswith("http"):
                    imgs.append(src)
                if len(imgs) >= 6:
                    break
            for src in imgs[:6]:
                creatives.append({
                    "image": src,
                    "caption": f"Ad creative for {product}",
                    "source": search_url
                })
    except Exception as e:
        print("FB Ad Library fetch failed (nonfatal):", e)
        creatives = []

    # If not enough creatives, populate graceful placeholder creatives
    if not creatives:
        for i in range(3):
            placeholder = f"https://via.placeholder.com/320x180.png?text={quote_plus(product)}"
            creatives.append({
                "image": placeholder,
                "caption": f"Placeholder creative {i+1} for {product}",
                "source": f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(product)}"
            })

    # cache creatives
    upsert_ad_creatives(product, creatives)
    return creatives

# ----------------------------
# Core computation (Trend + Profit)
# ----------------------------
def compute_combined_trends(markup_multiplier=2.5, shipping_cost=3.0):
    google = get_google_trends(GOOGLE_KEYWORDS)
    ali = get_aliexpress_data(ALI_PRODUCTS)
    tiktok = get_tiktok_trends(ALI_PRODUCTS)

    df = pd.DataFrame({
        "Product": list(google.keys()),
        "GoogleScore": list(google.values()),
        "AliScore": [ali[p]["orders"] for p in google.keys()],
        "TikTokScore": [tiktok[p] for p in google.keys()],
        "Price": [ali[p]["price"] for p in google.keys()],
        "ProfitMargin": [ali[p]["margin"] for p in google.keys()],
        "ImageURL": [ali[p]["image"] for p in google.keys()],
        "AliURL": [ali[p]["url"] for p in google.keys()]
    })

    # Normalize
    for c in ["GoogleScore","AliScore","TikTokScore"]:
        df[c + "Norm"] = (df[c] - df[c].min()) / (df[c].max() - df[c].min() + 1e-6) * 100

    df["TrendScore"] = (df["GoogleScoreNorm"]*0.5 + df["AliScoreNorm"]*0.3 + df["TikTokScoreNorm"]*0.2).round(2)

    # Use user inputs for price calc: sell price = price * markup_multiplier + shipping_cost
    df["SellPrice"] = (df["Price"] * markup_multiplier + shipping_cost).round(2)
    df["Profit"] = (df["SellPrice"] - df["Price"] - shipping_cost).round(2)
    df["ProfitMarginPct"] = ((df["Profit"] / df["SellPrice"]) * 100).round(2)

    df["ProfitPotential"] = (df["TrendScore"] * 0.65 + df["ProfitMarginPct"] * 0.35).round(2)
    df = df.sort_values("ProfitPotential", ascending=False)
    df["Time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Store to DB
    save_trends_df(df[["Time","Product","GoogleScore","AliScore","TikTokScore","TrendScore","Price","ProfitMarginPct","ProfitPotential","ImageURL"]].rename(columns={"ProfitMarginPct":"ProfitMargin"}))
    return df

# ----------------------------
# Dash app + layout
# ----------------------------
app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server
app.title = "Dropship Profit + Ads Radar"

# small custom styles for mobile-friendly, polished dark look
app.index_string = app.index_string.replace("</head>", """
<style>
  body { background: #0b0d10; color: #e6eef6; font-family: Inter,Arial,Helvetica,sans-serif; }
  .card { background: #0f1317; border-radius:12px; padding:12px; margin:10px; box-shadow: 0 6px 18px rgba(0,0,0,0.5); }
  .small { font-size: 0.85rem; color:#9fb1c8; }
  .thumb { width:110px; height:66px; object-fit:cover; border-radius:6px; margin-right:8px; }
  .thumbnail-row { display:flex; gap:6px; overflow-x:auto; padding-top:6px; padding-bottom:6px; }
  a { color:#5ec8ff; text-decoration:none; }
  .badge { display:inline-block; padding:8px 12px; border-radius:999px; background:linear-gradient(90deg,#00C9FF,#92FE9D); color:#062027; font-weight:700; }
</style>
</head>""", 1)

app.layout = html.Div([
    html.Div([
        html.H1("💸 Dropship Profit + Ads Radar", style={'textAlign':'center','margin':'6px 0','color':'#92FE9D'}),
        html.Div("Trends • Ads • Profit — one place", style={'textAlign':'center','color':'#9fb1c8','marginBottom':'6px'}),
        html.Div(id="top-row", style={'display':'flex','gap':'8px','justifyContent':'center','flexWrap':'wrap'}),
    ], className='card'),
    dcc.Interval(id="interval", interval=REFRESH_INTERVAL_MS, n_intervals=0),
    # Settings row
    html.Div([
        html.Label("Markup ×", className='small'),
        dcc.Input(id="input-markup", type="number", value=2.5, step=0.1, style={'width':'80px','marginRight':'12px'}),
        html.Label("Shipping $", className='small'),
        dcc.Input(id="input-ship", type="number", value=3.0, step=0.5, style={'width':'80px','marginRight':'12px'}),
        html.Button("Export Saved Swipes (CSV)", id="export-swipes", n_clicks=0, style={'marginLeft':'12px'})
    ], className='card'),
    html.Div(id="table-container", className='card'),
    html.Div([dcc.Graph(id="profit-bar-chart")], className='card'),
    html.Div([dcc.Graph(id="trend-line-chart")], className='card'),
    html.Div(id="hidden-output")  # placeholder
])

# ----------------------------
# Save-swipe endpoint (simple GET)
# ----------------------------
@server.route("/save_swipe")
def route_save_swipe():
    """
    Usage example:
    /save_swipe?product=Portable+Blender&img=https%3A%2F%2F...&source=https%3A%2F%2F...
    This will save a row to ad_swipes and return a tiny page that can be closed.
    """
    from flask import request, render_template_string
    product = request.args.get("product", "")
    img = request.args.get("img", "")
    source = request.args.get("source", "")
    caption = request.args.get("caption", "")
    try:
        save_swipe(unquote_plus(product), unquote_plus(img), unquote_plus(caption), unquote_plus(source))
        return render_template_string("""
            <html><body style="background:#081018;color:#e6eef6;font-family:Arial;text-align:center;padding:20px;">
            <h3>Saved ✓</h3>
            <p>Saved swipe for <strong>{{p}}</strong>.</p>
            <p><a href="javascript:window.close()">Close window</a></p>
            </body></html>
        """, p=product)
    except Exception as e:
        return f"Error saving swipe: {e}"

# ----------------------------
# Export swipes endpoint
# ----------------------------
@server.route("/api/swipes/export")
def export_swipes():
    df = get_all_swipes_df()
    if df.empty:
        csv_bytes = "No saved swipes\n".encode('utf-8')
        return Response(csv_bytes, mimetype="text/csv")
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    mem = io.BytesIO()
    mem.write(buf.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, mimetype='text/csv', download_name='swipes.csv', as_attachment=True)

# ----------------------------
# Main UI callback - updates table + charts
# ----------------------------
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
    # compute with user settings
    markup = float(markup) if markup else 2.5
    ship = float(ship) if ship else 3.0
    df = compute_combined_trends(markup_multiplier=markup, shipping_cost=ship)
    hist = pd.read_sql("SELECT * FROM trends ORDER BY Time ASC", sqlite3.connect(DB_FILE))

    # Top gainer over last two snapshots (if possible)
    top_badge = html.Div("No data yet", style={'textAlign':'center'})
    try:
        if len(hist) > 1:
            # compute last vs previous TrendScore by product
            last_time = hist['Time'].max()
            last = hist[hist['Time'] == last_time].set_index('Product')['TrendScore']
            prev_times = sorted(hist['Time'].unique())
            prev_time = prev_times[-2]
            prev = hist[hist['Time'] == prev_time].set_index('Product')['TrendScore']
            diffs = (last - prev).dropna()
            if not diffs.empty:
                gainer = diffs.idxmax()
                top_badge = html.Div([
                    html.Span("Top Gainer", className='badge'),
                    html.Span(f" {gainer} (+{diffs.max():.1f})", style={'marginLeft':'8px','fontWeight':'700'})
                ], style={'textAlign':'center'})
    except Exception as e:
        print("Top gainer calc failed:", e)

    # build table with product rows & ad thumbnails
    rows = []
    header = html.Tr([html.Th(h) for h in ["Image","Product","Price","Margin","Trend","ProfitPotential","Ads"]])
    for r in df.itertuples():
        # creatives
        creatives = get_ad_creatives(r.Product)
        thumbs = []
        for c in creatives[:6]:
            # Save link sends to /save_swipe; opens in new tab so it doesn't disrupt dashboard
            save_link = f"/save_swipe?product={quote_plus(r.Product)}&img={quote_plus(c['image'])}&source={quote_plus(c['source'])}&caption={quote_plus(c.get('caption',''))}"
            thumbs.append(html.Div([
                html.A(html.Img(src=c['image'], className='thumb'), href=c['source'], target="_blank"),
                html.Br(),
                html.A("Save", href=save_link, target="_blank", style={'fontSize':'12px','color':'#9ad0ff'})
            ], style={'display':'inline-block','textAlign':'center','width':'120px'}))

        thumb_row = html.Div(thumbs, className='thumbnail-row')
        product_cell = html.Td([
            html.A(r.Product, href=r.AliURL if hasattr(r,'AliURL') else f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(r.Product)}", target="_blank", style={'fontWeight':'700','color':'#fff'}),
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

    # profit potential bar chart
    bar_fig = px.bar(df, x="Product", y="ProfitPotential", color="ProfitPotential", title="💹 Profit Potential (Trend + Margin)", color_continuous_scale="Mint")
    bar_fig.update_layout(template="plotly_dark", height=420, margin=dict(t=50,l=25,r=25,b=120))

    # trend line historical chart
    if not hist.empty:
        line_fig = px.line(hist, x="Time", y="TrendScore", color="Product", title="📈 Trend Score Over Time (history)")
        line_fig.update_layout(template="plotly_dark", height=420)
    else:
        line_fig = px.line(title="📈 Trend Score Over Time (history)")

    return table, bar_fig, line_fig, top_badge

# ----------------------------
# Quick health endpoint
# ----------------------------
@server.route("/health")
def health():
    return "OK"

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port)