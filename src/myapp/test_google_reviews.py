from myapp.get_google_reviews import get_google_reviews

result = get_google_reviews("Sinbad Mediterranean Grill San Diego")

if "reviews" in result:
    for review in result["reviews"]:
        print(f"- {review['author']} ({review['rating']}⭐): {review['text']}")
else:
    print(result.get("error", "No reviews found."))
