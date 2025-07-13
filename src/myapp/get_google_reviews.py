import os
import requests
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

def get_place_id(business_name, location):
    search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    full_input = f"{business_name}, {location}" if location else business_name
    params = {
        "input": full_input,
        "inputtype": "textquery",
        "fields": "place_id",
        "key": GOOGLE_API_KEY
    }
    res = requests.get(search_url, params=params)

    # ✅ Debug print here
    print("🔎 Searching for:", full_input)
    print("🔗 Full URL:", res.url)
    print("📄 Raw JSON Response:", res.json())

    res.raise_for_status()
    candidates = res.json().get("candidates")
    if not candidates:
        raise ValueError("❌ No matching place found.")
    return candidates[0]["place_id"]


def get_google_reviews(business_name, location=""):
    try:
        place_id = get_place_id(business_name, location)
    except Exception as e:
        return {"error": str(e)}


    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,rating,reviews,user_ratings_total",
        "key": GOOGLE_API_KEY
    }
    res = requests.get(details_url, params=params)
    res.raise_for_status()
    data = res.json().get("result", {})

    reviews = data.get("reviews", [])
    formatted = [
        {
            "author": r["author_name"],
            "rating": r["rating"],
            "text": r["text"],
            "time": r["relative_time_description"]
        }
        for r in reviews
    ]
    return {
        "name": data.get("name"),
        "rating": data.get("rating"),
        "total_ratings": data.get("user_ratings_total"),
        "reviews": formatted
    }
