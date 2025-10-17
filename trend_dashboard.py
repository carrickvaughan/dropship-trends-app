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
    # Ensure numeric inputs
    try:
        markup = float(markup)
    except:
        markup = 2.5
    try:
        ship = float(ship)
    except:
        ship = 3.0

    # Compute trends safely
    try:
        df = compute_combined_trends(markup_multiplier=markup, shipping_cost=ship)
        if df.empty:
            raise ValueError("compute_combined_trends returned empty")
    except Exception as e:
        print("Trend computation failed, using fallback:", e)
        # placeholder data
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
            "AliURL": [f"https://www.aliexpress.com/wholesale?SearchText={p}" for p in ALI_PRODUCTS]
        })

    # Load history for trend line chart
    try:
        hist = pd.read_sql("SELECT * FROM trends ORDER BY Time ASC", sqlite3.connect(DB_FILE))
    except:
        hist = pd.DataFrame()

    # Compute top gainer safely
    top_badge = html.Div("No data yet", style={'textAlign':'center'})
    try:
        if len(hist) > 1:
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

    # Build table
    rows = []
    header = html.Tr([html.Th(h) for h in ["Image","Product","Price","Margin","Trend","ProfitPotential","Ads"]])
    for r in df.itertuples():
        # Safe ad creatives fetch
        try:
            creatives = get_ad_creatives(r.Product)
        except Exception as e:
            print("Creative fetch failed:", e)
            creatives = []

        thumbs = []
        for c in creatives[:6]:
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

    # Profit potential bar chart
    try:
        bar_fig = px.bar(df, x="Product", y="ProfitPotential", color="ProfitPotential", title="💹 Profit Potential (Trend + Margin)", color_continuous_scale="Mint")
        bar_fig.update_layout(template="plotly_dark", height=420, margin=dict(t=50,l=25,r=25,b=120))
    except Exception as e:
        print("Bar chart failed:", e)
        bar_fig = px.bar(title="💹 Profit Potential (Trend + Margin)")

    # Trend line historical chart
    try:
        if not hist.empty:
            line_fig = px.line(hist, x="Time", y="TrendScore", color="Product", title="📈 Trend Score Over Time (history)")
            line_fig.update_layout(template="plotly_dark", height=420)
        else:
            line_fig = px.line(title="📈 Trend Score Over Time (history)")
    except Exception as e:
        print("Line chart failed:", e)
        line_fig = px.line(title="📈 Trend Score Over Time (history)")

    return table, bar_fig, line_fig, top_badge