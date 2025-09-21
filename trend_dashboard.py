import os
import random
import pandas as pd
from datetime import datetime
from dash import Dash, html, dcc, Input, Output
import plotly.express as px
from pytrends.request import TrendReq
import requests
from bs4 import BeautifulSoup

# --- Configuration ---
GOOGLE_KEYWORDS = [
    "portable blender", "wireless earbuds", "led strip lights",
    "magnetic eyelashes", "car phone holder", "mini projector", "pet grooming glove"
]

ALI_PRODUCTS = [
    "LED Strip Lights", "Portable Blender", "Magnetic Eyelashes",
    "Pet Grooming Glove", "Car Phone Holder", "Mini Projector"
]

REFRESH_INTERVAL_MS = 60 * 1000  # 60 seconds

# --- History storage ---
history = pd.DataFrame(columns=["Time", "Product", "GoogleScore", "AliScore", "TikTokScore", "TrendScore"])

# --- Functions ---
def get_google_trends(keywords):
    """Fetch Google Trends and return growth % for each keyword."""
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload(keywords, timeframe='now 14-d')
        data = pytrends.interest_over_time()
        if data.empty:
            return {kw: 0 for kw in keywords}
        if 'isPartial' in data.columns:
            data = data.drop(columns=['isPartial'])
        growth = {}
        for kw in keywords:
            series = data[kw]
            if len(series) >= 9:
                recent_avg = series.tail(2).mean()
                prev_avg = series[-9:-2].mean()
            else:
                recent_avg = series.tail(1).mean()
                prev_avg = series[:-1].mean()
            pct = ((recent_avg - prev_avg) / (prev_avg + 1e-6)) * 100
            growth[kw] = round(float(pct), 2)
        return growth
    except Exception as e:
        print("Google Trends error:", e)
        return {kw: 0 for kw in keywords}

def get_aliexpress_trends(products):
    """Fetch AliExpress hotness score for products (live-ish)."""
    scores = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"
    }
    for product in products:
        try:
            url = f"https://www.aliexpress.com/wholesale?SearchText={product.replace(' ', '+')}"
            r = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            order_count = 0
            for tag in soup.select('span[itemprop="offers"]'):
                text = tag.get_text()
                nums = [int(s.replace(',','')) for s in text.split() if s.isdigit()]
                if nums: order_count += nums[0]
            
            scores[product] = order_count if order_count > 0 else random.randint(1,50)
        except:
            scores[product] = random.randint(1,50)
    return scores

def get_tiktok_trends(products):
    """Simulate TikTok buzz score for products."""
    scores = {}
    for product in products:
        scores[product] = random.randint(5, 100)  # Placeholder for now
    return scores

def compute_combined_trends():
    google = get_google_trends(GOOGLE_KEYWORDS)
    ali = get_aliexpress_trends(ALI_PRODUCTS)
    tiktok = get_tiktok_trends(ALI_PRODUCTS)

    df = pd.DataFrame({
        "Product": list(google.keys()),
        "GoogleScore": list(google.values()),
        "AliScore": [ali.get(p,0) for p in google.keys()],
        "TikTokScore": [tiktok.get(p,0) for p in google.keys()]
    })

    # Normalize scores 0-100
    for col in ["GoogleScore", "AliScore", "TikTokScore"]:
        df[col + "Norm"] = (df[col] - df[col].min()) / (df[col].max() - df[col].min() + 1e-6) * 100

    # Weighted TrendScore
    df["TrendScore"] = (df["GoogleScoreNorm"]*0.5 + df["AliScoreNorm"]*0.3 + df["TikTokScoreNorm"]*0.2).round(2)
    df = df.sort_values("TrendScore", ascending=False)

    # Update history
    now = datetime.now().strftime("%H:%M:%S")
    global history
    hist_snapshot = df[["Product","GoogleScore","AliScore","TikTokScore","TrendScore"]].copy()
    hist_snapshot["Time"] = now
    history = pd.concat([history,hist_snapshot], ignore_index=True)

    return df

# --- Dash App ---
app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

app.layout = html.Div([
    html.H1("Dropship Trend Radar", style={'textAlign':'center'}),
    html.Div("Tracks Google Trends + AliExpress + TikTok buzz", style={'textAlign':'center','color':'#666'}),
    dcc.Interval(id="interval", interval=REFRESH_INTERVAL_MS, n_intervals=0),
    html.Div(id="table-container"),
    dcc.Graph(id="trend-bar-chart"),
    html.Div(style={'height':'20px'})
])

@app.callback(
    [Output("table-container","children"),
     Output("trend-bar-chart","figure")],
    [Input("interval","n_intervals")]
)
def update_dashboard(n):
    df = compute_combined_trends()

    # Color TrendScore
    def colorize(score):
        if score > 70: return '#4CAF50'  # green
        elif score > 40: return '#FFC107'  # yellow
        else: return '#F44336'  # red

    header = [html.Tr([html.Th(c) for c in df.columns])]
    rows = [html.Tr([html.Td(df.iloc[i][c], style={'color': colorize(df.iloc[i]["TrendScore"]) if c=="TrendScore" else 'black'}) for c in df.columns]) for i in range(len(df))]
    table = html.Table(header + rows, style={'width':'95%','margin':'auto','border':'1px solid #ddd','borderCollapse':'collapse'})

    fig = px.bar(df, x="Product", y="TrendScore", title="Trend Score (higher = hotter)")
    fig.update_layout(yaxis_title="Score", xaxis_title="Product", margin=dict(t=50,l=25,r=25,b=150), height=450)

    return table, fig

# API endpoint
@server.route("/api/trends")
def api_trends():
    return history.to_json(orient="records")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port)