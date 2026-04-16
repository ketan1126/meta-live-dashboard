import os
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID", "").strip()
META_API_VERSION = "v22.0"


def get_meta_insights(level="campaign", date_preset="today"):
    if not META_ACCESS_TOKEN or not META_AD_ACCOUNT_ID:
        return {"error": "Missing META_ACCESS_TOKEN or META_AD_ACCOUNT_ID in .env"}

    url = f"https://graph.facebook.com/{META_API_VERSION}/{META_AD_ACCOUNT_ID}/insights"

    fields = [
        "campaign_name",
        "adset_name",
        "ad_name",
        "spend",
        "impressions",
        "reach",
        "cpm",
        "ctr",
        "cpc",
        "actions",
        "action_values",
        "purchase_roas",
    ]

    params = {
        "access_token": META_ACCESS_TOKEN,
        "level": level,
        "date_preset": date_preset,
        "fields": ",".join(fields),
        "limit": 500,
    }

    response = requests.get(url, params=params, timeout=30)
    data = response.json()

    if "error" in data:
        return data

    rows = []
    for item in data.get("data", []):
        actions = item.get("actions", []) or []
        action_values = item.get("action_values", []) or []
        purchase_roas = item.get("purchase_roas", []) or []

        def get_action_value(action_type, source):
            for a in source:
                if a.get("action_type") == action_type:
                    try:
                        return float(a.get("value", 0))
                    except (TypeError, ValueError):
                        return 0.0
            return 0.0

        lpv = get_action_value("landing_page_view", actions)
        atc = get_action_value("add_to_cart", actions)
        ic = get_action_value("initiate_checkout", actions)
        purchases = get_action_value("purchase", actions)
        purchase_value = get_action_value("purchase", action_values)

        roas = 0.0
        if purchase_roas:
            try:
                roas = float(purchase_roas[0].get("value", 0))
            except (TypeError, ValueError, KeyError, IndexError):
                roas = 0.0

        spend = float(item.get("spend", 0) or 0)

        cpa = round(spend / purchases, 2) if purchases > 0 else None
        lpv_to_purchase = round((purchases / lpv) * 100, 2) if lpv > 0 else 0.0

        if purchases >= 3 and roas >= 2.0:
            action = "Protect"
        elif purchases > 0 and roas >= 1.3:
            action = "Hold"
        elif lpv > 0 and purchases == 0:
            action = "Test"
        else:
            action = "Cut"

        name = (
            item.get("campaign_name")
            or item.get("adset_name")
            or item.get("ad_name")
            or "Unnamed"
        )

        rows.append({
            "name": name,
            "spend": round(spend, 2),
            "lpv": int(lpv),
            "atc": int(atc),
            "ic": int(ic),
            "purchases": int(purchases),
            "purchase_value": round(purchase_value, 2),
            "roas": round(roas, 2),
            "cpa": cpa,
            "lpv_to_purchase_rate": lpv_to_purchase,
            "action": action,
        })

    rows.sort(key=lambda x: x["spend"], reverse=True)
    return {"data": rows}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/insights")
def insights():
    level = request.args.get("level", "campaign")
    date_preset = request.args.get("date_preset", "today")
    result = get_meta_insights(level=level, date_preset=date_preset)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
