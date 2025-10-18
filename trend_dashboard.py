import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import pandas as pd
import datetime
import json

# Load cached data
def load_trends():
    try:
        with open("trend_cache.json") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except:
        # Fallback demo data
        fallback = [
            {"Product": "Sample Product", "Image": "https://via.placeholder.com/60x60.png?text=Demo",
             "Link": "https://google.com", "Avg": 50, "Current": 60, "Change": 10, "Profit": 80}
        ]
        return pd.DataFrame(fallback)

# Generate HTML table
def generate_table(df):
    header = html.Tr([
        html.Th("Image"), html.Th("Product Name"), html.Th("Avg Interest"),
        html.Th("Current Interest"), html.Th("Change"), html.Th("Profit Potential")
    ])
    rows = []
    for _, row in df.iterrows():
        rows.append(html.Tr([
            html.Td(html.A(html.Img(src=row['Image'], width=60), href=row['Link'], target="_blank")),
            html.Td(html.A(row['Product'].title(), href=row['Link'], target="_blank")),
            html.Td(row['Avg']),
            html.Td(row['Current']),
            html.Td(row['Change']),
            html.Td(row['Profit'])
        ]))
    return html.Table([header] + rows, style={'width': '100%', 'borderCollapse': 'collapse', 'marginTop': '20px'})

# Dash app
app = dash.Dash(__name__)
app.title = "Dropship Trend Tracker"

app.layout = html.Div(
    style={'backgroundColor': '#0a0f24', 'color': '#ffffff', 'padding': '20px'},
    children=[
        html.H1("🚀 Dropship Trend Tracker", style={'textAlign': 'center', 'color': '#00FFFF'}),
        html.Div(id='update-time', style={'textAlign': 'center', 'marginBottom': '10px'}),
        html.Div(id='top-trends', style={'textAlign': 'center', 'marginBottom': '20px', 'fontSize': '18px'}),
        dcc.Graph(id='trend-chart'),
        dcc.Graph(id='profit-chart'),
        html.Div(id='trend-table-container'),
        dcc.Interval(id='interval-component', interval=3*60*60*1000, n_intervals=0)
    ]
)

@app.callback(
    [Output('trend-chart', 'figure'),
     Output('profit-chart', 'figure'),
     Output('trend-table-container', 'children'),
     Output('update-time', 'children'),
     Output('top-trends', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_all(n):
    df = load_trends()
    # Graphs
    trend_fig = px.bar(df, x='Product', y='Current', color='Change', title='🔥 Current Search Interest (Last 7 Days)')
    trend_fig.update_traces(customdata=df['Link'])
    trend_fig.update_layout(template='plotly_dark', title_x=0.5)
    
    profit_fig = px.bar(df, x='Product', y='Profit', title='💰 Estimated Profit Potential')
    profit_fig.update_traces(customdata=df['Link'])
    profit_fig.update_layout(template='plotly_dark', title_x=0.5)
    
    table_html = generate_table(df)
    top_items = df.sort_values(by='Change', ascending=False).head(3)['Product'].tolist()
    top_summary = "🌟 Top Trending Products: " + ", ".join(top_items)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return trend_fig, profit_fig, table_html, f"Last updated: {timestamp}", top_summary

# Client-side callback for clickable bars
app.clientside_callback(
    """
    function(clickData) {
        if(clickData) {
            window.open(clickData.points[0].customdata, '_blank');
        }
        return '';
    }
    """,
    Output('trend-chart', 'clickData'),
    Input('trend-chart', 'clickData')
)

app.clientside_callback(
    """
    function(clickData) {
        if(clickData) {
            window.open(clickData.points[0].customdata, '_blank');
        }
        return '';
    }
    """,
    Output('profit-chart', 'clickData'),
    Input('profit-chart', 'clickData')
)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
