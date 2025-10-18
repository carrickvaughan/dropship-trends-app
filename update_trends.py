import pandas as pd
import random
import json
from pytrends.request import TrendReq
import requests

PRODUCT_KEYWORDS = [
    "wireless earbuds", "air fryer", "neck massager", "led strip lights",
    "portable blender", "car vacuum", "pet grooming brush", "smartwatch",
    "projector", "mini printer", "heated blanket", "aroma diffuser"
]

pytrends = TrendReq(hl='en-US', tz=360)

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

data = []
for product in PRODUCT_KEYWORDS:
    try:
        pytrends.build_payload([product], timeframe='now 7-d')
        df = pytrends.interest_over_time()
        avg = int(df[product].mean()) if not df.empty else random.randint(20, 80)
        current = int(df[product].iloc[-1]) if not df.empty else random.randint(20, 80)
        change = current - avg
        img = get_image_url(product)
        link = f"https://www.google.com/search?q={product.replace(' ', '+')}"
        data.append({
            "Product": product,
            "Image": img,
            "Link": link,
            "Avg": avg,
            "Current": current,
            "Change": change,
            "Profit": random.randint(40, 95)
        })
    except:
        pass

with open("trend_cache.json", "w") as f:
    json.dump(data, f, indent=2)
print("Trends cached!")
