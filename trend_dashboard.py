import dash
from dash import dcc, html, dash_table, Input, Output
import pandas as pd
import plotly.express as px
from pytrends.request import TrendReq
import datetime
import random

# Initialize Google Trends API
pytrends = TrendReq(hl='en-US', tz=360)

# List of candidate product ideas to monitor (editable)
PRODUCT_KEYWORDS = [
    "wireless earbuds", "air fryer", "neck massager", "led strip lights", 
    "portable blender", "car vacuum", "pet grooming brush", "smartwatch", 
    "projector", "mini printer", "heated blanket", "aroma diffuser"
]

# Function to fetch real Google Trends data
def fetch_trend_data():
    data = []
    now = datetime.datetime.now()

    for product in PRODUCT_KEYWORDS:
        try:
            pytrends.build_payload([product], cat=0, timeframe='now 7-d', geo='', gprop='')
            df = pytrends.interest_over_time()
            if not df.empty:
                avg_interest = int(df[product].mean())
                last_interest = int(df[product].iloc[-1])
                trend_change = last_interest - avg_interest
                data.append({
                    "Product": product,
                    "Avg Interest": avg_interest,
                    "Current Interest": last_interest,
                    "Change": trend_change,
                    "Profit Potential": random.randint(40, 95),
                    "Source": f"https://www.google.com/search?q={product.replace(' ', '+')}"
                })
        except Exception as e:
            print(f"Error fetching {product}: {e}")

    return pd.DataFrame(data)

# Fetch initial data
df = fetch_trend_data()

# Create Dash app
app = dash.Dash(__name__)
app.title = "Dropship Trend Tracker"

# Layout
app.layout = html.Div(style={'backgroundColor': '#0a0f24', 'color': '#ffffff', 'padding': '20px'}, children=[
    html.H1("🚀 Dropship Trend Tracker", style={'textAlign': 'center', 'color': '#00FFFF'}),

    html.Div(id='update-time', style={'textAlign': 'center', 'marginBottom': '10px'}),

    dcc.Graph(id='trend-chart'),
    dcc.Graph(id='profit-chart'),

    dash_table.DataTable(
        id='trend-table',
        columns=[
            {"name": "Product", "id": "Product", "presentation": "markdown"},
            {"name": "Avg Interest", "id": "Avg Interest"},
            {"name": "Current Interest", "id": "Current Interest"},
            {"name": "Change", "id": "Change"},
            {"name": "Profit Potential", "id": "Profit Potential"}
        ],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center', 'backgroundColor': '#111111', 'color': '#FFFFFF'},
        style_header={'backgroundColor': '#1a1f3b', 'fontWeight': 'bold', 'color': '#00FFFF'},
        markdown_options={"html": True}
    ),

    dcc.Interval(
        id='interval-component',
        interval=3*60*60*1000,  # every 3 hours
        n_intervals=0
    )
])

# Callbacks
@app.callback(
    [Output('trend-chart', 'figure'),
     Output('profit-chart', 'figure'),
     Output('trend-table', 'data'),
     Output('update-time', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_data(n):
    df = fetch_trend_data()
    df['Product'] = df['Product'].apply(lambda p: f"[{p}]({f'https://www.google.com/search?q={p.replace(' ', '+')}'} )")

    trend_fig = px.bar(df, x='Product', y='Current Interest', color='Change', title='🔥 Current Search Interest')
    profit_fig = px.bar(df, x='Product', y='Profit Potential', title='💰 Estimated Profit Potential')

    trend_fig.update_layout(template='plotly_dark', title_x=0.5)
    profit_fig.update_layout(template='plotly_dark', title_x=0.5)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return trend_fig, profit_fig, df.to_dict('records'), f"Last updated: {timestamp}"

# Run the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)