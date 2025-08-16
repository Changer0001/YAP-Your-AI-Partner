# streamlit_booking_snippet.py
import os, requests, streamlit as st
from datetime import date

API_URL = os.getenv("API_URL", "http://localhost:8000")

def reserve_ui():
    st.markdown("### Reserve a table")
    token = st.session_state.get("token", "")
    if not token:
        st.info("Log in first to book.")
        return

    c1, c2 = st.columns(2)
    d = c1.date_input("Date", value=date.today())
    party = c2.number_input("Party size", min_value=1, max_value=20, value=2, step=1)
    name  = st.text_input("Name")
    email = st.text_input("Email")
    phone = st.text_input("Phone")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if st.button("Check availability"):
        try:
            resp = requests.post(f"{API_URL}/book/availability", headers=headers,
                                 json={"date": d.isoformat(), "party_size": int(party)}, timeout=20)
            data = resp.json()
            slots = data.get("slots", [])
            if not slots:
                st.warning("No slots available for that date.")
            else:
                st.success(f"Found {len(slots)} slot(s)")
                st.session_state["chosen_slot"] = st.selectbox("Pick a time", options=slots[:30])
        except Exception as e:
            st.error(f"Availability error: {e}")

    if "chosen_slot" in st.session_state:
        chosen = st.session_state["chosen_slot"]
        st.info(f"Selected: {chosen}")
        if st.button("Create booking"):
            body = {
                "datetime": chosen,
                "party_size": int(party),
                "name": name.strip(),
                "email": email.strip(),
                "phone": phone.strip(),
            }
            try:
                resp = requests.post(f"{API_URL}/book/create", headers=headers, json=body, timeout=30)
                out = resp.json()
                checkout = out.get("checkout_url")
                if checkout:
                    st.success("Booking created! Complete payment to confirm:")
                    st.markdown(f"[Open Stripe Checkout]({checkout})")
                else:
                    st.warning("Booking created without payment link (manual confirm in test mode).")
                    st.json(out)
            except Exception as e:
                st.error(f"Create error: {e}")
