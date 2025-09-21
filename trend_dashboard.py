import dash
from dash import html, dcc
import plotly.express as px
import pandas as pd

# Example dataset (later we’d plug in real dropshipping trend data)
df = pd.DataFrame({
    "Product": ["Wireless Earbuds", "LED Lights", "Pet Grooming Kit", "Portable Blender"],
    "SearchVolume": [12000, 15000, 8000, 11000]
})

app = dash.Dash(__name__)
app.layout = html.Div([
    html.H1("Dropship Trend Dashboard"),
    dcc.Graph(
        figure=px.bar(df, x="Product", y="SearchVolume", title="Hot Products")
    )
])

server = app.server  # for Render

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8050))
    app.run_server(host="0.0.0.0", port=port)