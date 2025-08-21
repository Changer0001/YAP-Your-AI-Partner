# app/integrations/yap_extract.py
import requests, os

def extract_ticket(user_text: str) -> dict:
    """
    Call your existing YAP backend model to return a JSON with:
    short_description, description, urgency, impact, category, subcategory, caller_id
    """
    api = os.getenv("YAP_API_URL","http://localhost:8000")
    prompt = (
      "Extract a ServiceNow incident from this message. "
      "Return a JSON with keys: short_description, description, urgency (high/medium/low), "
      "impact (high/medium/low), category, subcategory, caller_id (email or name if present). "
      f"Text: {user_text}"
    )
    # Example if you already have an /ask endpoint that returns structured text:
    r = requests.post(f"{api}/ask", json={"question": prompt, "history":[]}, timeout=20)
    r.raise_for_status()
    # Parse/validate here based on your /ask contract
    try:
        return r.json()  # adjust as needed
    except:
        return {}
