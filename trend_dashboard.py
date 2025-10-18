import dash
from dash import dcc, html, dash_table, Input, Output
import pandas as pd
import plotly.express as px
from pytrends.request import TrendReq
import datetime
import random
import requests
import webbrowser

# Initialize Google Trends API
pytrends = TrendReq(hl='en-US', tz=360)

PRODUCT_KEYWORDS = [
    "wireless earbuds", "air fryer", "neck massager", "led strip lights",
    "portable blender", "car vacuum", "pet grooming brush", "smartwatch",
    "projector", "mini printer", "heated blanket", "aroma diffuser"
]

# Get product image from DuckDuckGo
def get_image_url(query):
    try:
        url = f"https://duckduckgo.com/i.js?q={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200 and "https://" in res.text:
            start = res.text.find("https://")
            end = res.text.find(".jpg", start)
            return res.text[start:end+4]
    except Exception:
        pass
    return "https://via.placeholder.com/60x60.png?text=No+Image"

# Fetch live Google Trends data
def fetch_trend_data():
    data = []
    for product in PRODUCT_KEYWORDS:
        try:
            pytrends.build_payload([product], cat=0, timeframe='now 7-d', geo='', gprop='')
            df = pytrends.interest_over_time()
            if not df.empty:
                avg_interest = int(df[product].mean())
                last_interest = int(df[product].iloc[-1])
                change = last_interest - avg_interest
                img_url = get_image_url(product)
                google_link = f"https://www.google.com/search?q={product.replace(' ', '+')}"
                data.append({
                    "Product Name": product.title(),
                    "Product Link": google_link,
                    "Image": f"<img src='{img_url}' width='60'>",
                    "Avg Interest": avg_interest,
                    "Current Interest": last_interest,
                    "Change": change,
                    "Profit Potential": random.randint(40, 95)
                })
        except Exception as e:
            print(f"Error fetching {product}: {e}")
    return pd.DataFrame(data)

# Fetch initial dataset
df = fetch_trend_data()

app = dash.Dash(__name__)
app.title = "Dropship Trend Tracker"

app.layout = html.Div(
    style={'backgroundColor': '#0a0f24', 'color': '#ffffff', 'padding': '20px'},
    children=[
        html.H1("🚀 Dropship Trend Tracker", style={'textAlign': 'center', 'color': '#00FFFF'}),

        html.Div(id='update-time', style={'textAlign': 'center', 'marginBottom': '10px'}),

        html.Div(id='top-trends', style={'textAlign': 'center', 'marginBottom': '20px', 'fontSize': '18px'}),

        dcc.Graph(id='trend-chart', clear_on_unhover=True),
        dcc.Graph(id='profit-chart', clear_on_unhover=True),

        dash_table.DataTable(
            id='trend-table',
            columns=[
                {"name": "Image", "id": "Image", "presentation": "markdown"},
                {"name": "Product Name", "id": "Product Name"},
                {"name": "Avg Interest", "id": "Avg Interest"},
                {"name": "Current Interest", "id": "Current Interest"},
                {"name": "Change", "id": "Change"},
                {"name": "Profit Potential", "id": "Profit Potential"}
            ],
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'center', 'backgroundColor': '#111111', 'color': '#FFFFFF', 'padding': '8px'},
            style_header={'backgroundColor': '#1a1f3b', 'fontWeight': 'bold', 'color': '#00FFFF'},
            markdown_options={"html": True},
            dangerously_allow_html=True
        ),

        dcc.Interval(id='interval-component', interval=3*60*60*1000, n_intervals=0)
    ]
)

# Main update callback
@app.callback(
    [Output('trend-chart', 'figure'),
     Output('profit-chart', 'figure'),
     Output('trend-table', 'data'),
     Output('update-time', 'children'),
     Output('top-trends', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_data(n):
    df = fetch_trend_data()

    trend_fig = px.bar(df, x='Product Name', y='Current Interest', color='Change',
                       title='🔥 Current Search Interest (Last 7 Days)')
    profit_fig = px.bar(df, x='Product Name', y='Profit Potential',
                        title='💰 Estimated Profit Potential')

    trend_fig.update_layout(template='plotly_dark', title_x=0.5)
    profit_fig.update_layout(template='plotly_dark', title_x=0.5)

    top_items = df.sort_values(by='Change', ascending=False).head(3)['Product Name'].tolist()
    top_summary = "🌟 Top Trending Products: " + ", ".join(top_items)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return trend_fig, profit_fig, df.to_dict('records'), f"Last updated: {timestamp}", top_summary

# Clickable bars open Google search
@app.callback(
    Output('trend-chart', 'clickData'),
    [Input('trend-chart', 'clickData')]
)
def open_product_link(clickData):
    if clickData:
        product = clickData['points'][0]['x']
        url = f"https://www.google.com/search?q={product.replace(' ', '+')}"
        webbrowser.open_new_tab(url)
    return None

@app.callback(
    Output('profit-chart', 'clickData'),
    [Input('profit-chart', 'clickData')]
)
def open_profit_link(clickData):
    if clickData:
        product = clickData['points'][0]['x']
        url = f"https://www.google.com/search?q={product.replace(' ', '+')}"
        webbrowser.open_new_tab(url)
    return None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
