import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.express as px
from pytrends.request import TrendReq
import datetime
import random
import requests

# Initialize Google Trends
pytrends = TrendReq(hl='en-US', tz=360)

PRODUCT_KEYWORDS = [
    "wireless earbuds", "air fryer", "neck massager", "led strip lights",
    "portable blender", "car vacuum", "pet grooming brush", "smartwatch",
    "projector", "mini printer", "heated blanket", "aroma diffuser"
]

# Fetch image from DuckDuckGo
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

# Fetch Google Trends data
def fetch_trend_data():
    data = []
    for product in PRODUCT_KEYWORDS:
        try:
            pytrends.build_payload([product], timeframe='now 7-d')
            df = pytrends.interest_over_time()
            if not df.empty:
