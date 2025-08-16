import streamlit as st
import requests, re, json, os
from textwrap import dedent
from datetime import datetime, timedelta, date

# ───────────────────────── Config ─────────────────────────
st.set_page_config(page_title="YAP", page_icon="🤖", layout="centered")
API_URL = os.getenv("YAP_API_URL", "http://localhost:8000")  # YAP API base

# Optional: configurable list of collections for routing (no hardcoded keywords)
def _load_collections():
    try:
        data = json.loads(os.getenv("YAP_COLLECTIONS", "[]"))
        if isinstance(data, list):
            # expect [{"id":"menu_docs","label":"Menu & FAQs"}, ...]
            return [c for c in data if isinstance(c, dict) and c.get("id")]
    except Exception:
        pass
    return []
COLLECTIONS = _load_collections()

# ───────────────────────── Styles ─────────────────────────
def inject_styles():
    st.markdown(dedent("""
    <style>
      :root{
        --bg:#0a0f1e; --panel:#0c1324; --text:#e6edf3; --muted:#94a3b8;
        --input:#161c2e; --border:rgba(148,163,184,.18);
        --glow1:#7dd3fc; --glow2:#c084fc;
      }
      html, body, [class*="css"]{ background:var(--bg); color:var(--text); }

      .brand-wrap{max-width:860px;margin:0 auto 12px;}
      .brand-box{border-radius:22px;padding:3px;
        background:linear-gradient(90deg,rgba(125,211,252,.45),rgba(192,132,252,.45));
        box-shadow:0 0 0 1px var(--border), 0 20px 45px rgba(56,189,248,.15); }
      .brand-inner{border-radius:20px;padding:18px 24px;
        background:linear-gradient(180deg,#0e162b 0%,#0b1325 100%);
        border:1px solid rgba(125,211,252,.22);}
      .brand-title{
        font-family: Orbitron, system-ui, sans-serif; font-weight:700; font-size:44px;
        background:linear-gradient(90deg,var(--glow1),var(--glow2));
        -webkit-background-clip:text; background-clip:text; color:transparent;
        text-shadow:0 0 26px rgba(125,211,252,.10); }

      .auth-card{max-width:860px;margin:8px auto; border-radius:16px; padding:18px;
        background:linear-gradient(180deg,rgba(13,19,35,.85),rgba(10,15,28,.88));
        border:1px solid var(--border);
        box-shadow:inset 0 14px 30px rgba(2,8,23,.35), 0 10px 30px rgba(0,0,0,.25); }
      .auth-card label{color:var(--muted); font-weight:600;}
      [data-testid="stForm"]{background:transparent; border:0; padding:0;}

      [data-baseweb="input"] > div{ background:var(--input); border:1px solid var(--border); border-radius:12px; }
      [data-baseweb="input"] input{color:var(--text);}
      [data-baseweb="input"]:focus-within{ box-shadow:0 0 0 2px rgba(125,211,252,.35), inset 0 0 0 1px rgba(192,132,252,.25); }
      svg[data-testid="stPasswordInputVisibilityToggle"]{opacity:.9}

      .stButton > button{
        border-radius:12px; padding:.55rem 1rem; font-weight:600;
        color:var(--text); border:1px solid rgba(148,163,184,.2);
        background:linear-gradient(90deg,rgba(99,102,241,.35),rgba(192,132,252,.35));
        box-shadow:0 10px 24px rgba(99,102,241,.15);}
      .stButton > button:hover{filter:brightness(1.08);}
      .stButton > button:focus{outline:none; box-shadow:0 0 0 2px rgba(125,211,252,.35);}

      [data-testid^="stChatMessageAvatar"]{display:none!important;}
      [data-testid="stChatMessage"]{background:transparent!important;padding:0!important;border:0!important;}
      [data-testid="stChatMessage"] > div{background:transparent!important;padding:0!important;box-shadow:none!important;}

      .bubble{max-width:860px;margin:.5rem auto 1rem;border-radius:16px}
      .user-outer{ padding:1px; background:linear-gradient(135deg, rgba(99,102,241,.55), rgba(56,189,248,.45));
        border-radius:16px; box-shadow:0 16px 40px rgba(56,189,248,.12); }
      .user-inner{ background:linear-gradient(135deg, rgba(12,18,34,.96), rgba(10,16,30,.96));
        border:1px solid rgba(148,163,184,.22); border-radius:15px; padding:.95rem 1.1rem;
        backdrop-filter:blur(6px); -webkit-backdrop-filter:blur(6px);}
      .ai-outer{ padding:1px;background:linear-gradient(135deg,rgba(56,189,248,.55),rgba(168,85,247,.45));
        border-radius:16px;box-shadow:0 16px 40px rgba(56,189,248,.16) }
      .ai-inner{ background:linear-gradient(135deg,rgba(9,15,27,.96),rgba(11,18,32,.96));
        border:1px solid rgba(125,211,252,.22);border-radius:15px; padding:.95rem 1.1rem;
        backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px) }
      .bubble-title{font-size:.8rem;font-weight:700;letter-spacing:.2px;opacity:.9;margin-bottom:.35rem}
      .bubble-title.user{color:#93c5fd}.bubble-title.ai{color:#c4b5fd}
      .answer ol{margin-left:1.25em;line-height:1.7em;padding-left:.25em}
      .answer p{margin:0 0 .55rem 0}.answer li{margin:.2rem 0}
    </style>
    """), unsafe_allow_html=True)

def brand_header():
    return ("<div class='brand-wrap'><div class='brand-box'><div class='brand-inner'>"
            "<div class='brand-title'>YAP</div></div></div></div>")

# ───────────────────── Formatting helpers ─────────────────────
def format_answer(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"(?<!\n)(\d+\.)", r"\n\1", t)
    t = re.sub(r"(?m)^\s*(\d+)\.\s*(.*)", r"<li>\2</li>", t)
    if "<li>" in t: t = f"<ol>{t}</ol>"
    return f"<div class='answer' style='font-size:1.05rem; line-height:1.75em; color:#e2e8f0'>{t}</div>"

def _headline(text: str, max_len: int = 60) -> str:
    t = (text or "").strip()
    t = re.split(r'[\n\.!?]', t)[0]
    return (t[:max_len] + "…") if len(t) > max_len else t

# ─────────────────────────── State ────────────────────────────
st.session_state.setdefault("token", None)
st.session_state.setdefault("mode", "login")
st.session_state.setdefault("history", [])
st.session_state.setdefault("pending", {})      # booking state
st.session_state.setdefault("collection", None) # selected KB (optional)

# ─────────────────────────── Auth ─────────────────────────────
def login(username, password):
    try:
        r = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if r.status_code == 401: st.error("❌ Invalid credentials."); return
        r.raise_for_status()
        token = r.json().get("access_token") or r.json().get("token")
        if not token: st.error("Login succeeded but no token returned."); return
        st.session_state.token = token
        st.session_state.history = []
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def register(username, password):
    try:
        r = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        if r.status_code == 400: st.error("❌ Username already exists."); return
        r.raise_for_status()
        st.success("✅ Registration successful. Please log in.")
        st.session_state.mode = "login"; st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def auth_headers():
    tok = st.session_state.get("token")
    return {"Authorization": f"Bearer $tok".replace("$tok", tok) , "Content-Type": "application/json"} if tok else {}

# ───────────────────────── Booking API ────────────────────────
def api_availability(d: date, party: int):
    body = {"date": d.strftime("%Y-%m-%d"), "party_size": party}
    r = requests.post(f"{API_URL}/book/availability", json=body, headers=auth_headers(), timeout=15)
    r.raise_for_status(); return r.json()

def api_create(datetime_local_iso: str, party: int, name: str, email: str, phone: str):
    body = {"datetime": datetime_local_iso, "party_size": party, "name": name, "email": email, "phone": phone}
    r = requests.post(f"{API_URL}/book/create", json=body, headers=auth_headers(), timeout=20)
    r.raise_for_status(); return r.json()

def api_status(booking_id: str):
    r = requests.get(f"{API_URL}/book/status/{booking_id}", headers=auth_headers(), timeout=10)
    r.raise_for_status(); return r.json()

# ──────────────────────── Streaming (SSE) ─────────────────────
def stream_answer(prompt, history, on_update, collection=None):
    payload = {"question": prompt, "history": history}
    if collection:
        payload["collection"] = collection  # optional — backend decides grounding
    headers = auth_headers()
    answer = ""
    try:
        with requests.post(f"{API_URL}/ask/stream", json=payload, headers=headers, stream=True, timeout=(10, 120)) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw: continue
                if raw.startswith((":", "retry:", "event:")):
                    if raw.strip() == "event: done": break
                    continue
                if raw.startswith("data:"):
                    data_str = raw.split("data:", 1)[1].strip()
                    if not data_str or data_str in ("[DONE]", "{}"): continue
                    try:
                        payload_obj = json.loads(data_str)
                        delta = payload_obj.get("choices", [{}])[0].get("delta", {})
                        piece = delta.get("content", "")
                        if piece:
                            answer += piece
                            on_update(answer)
                    except Exception:
                        continue
    except Exception as e:
        on_update(f"❌ Stream error: {e}")
        return "[ERROR]"
    return answer.strip()

# ───────────────────── Booking intent logic ───────────────────
def parse_intent(text: str):
    t = (text or "").lower().strip()

    # Booking only when clearly present
    booking_context = any(k in t for k in [
        "availability","available","reserve","reservation","book","booking",
        "status","confirm","pay","payment","checkout","table","appointment","slot"
    ])

    intent = None
    if booking_context:
        if ("availability" in t or "available" in t) or ("check" in t and "availability" in t):
            intent = "availability"
        elif "status" in t or "booking id" in t:
            intent = "status"
        elif "pay" in t or "payment" in t or "checkout" in t:
            intent = "pay"
        elif "book" in t or "reserve" in t or "confirm" in t:
            intent = "book"

    # party size
    m_party = re.search(r"(?:for|of)\s+(\d{1,2})", t)
    party = int(m_party.group(1)) if m_party else None

    # date shorthands
    if "tomorrow" in t: d = date.today() + timedelta(days=1)
    elif "today" in t:  d = date.today()
    else:               d = None

    # time like 7pm/19:00
    m_time = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    hhmm = None
    if m_time:
        hh = int(m_time.group(1)); mm = int(m_time.group(2) or 0); ap = (m_time.group(3) or "").lower()
        if ap == "pm" and hh < 12: hh += 12
        if ap == "am" and hh == 12: hh = 0
        if 0 <= hh <= 23 and 0 <= mm <= 59: hhmm = (hh, mm)

    return {"intent": intent, "party": party, "date": d, "time": hhmm}

def nearest_slot(slots, desired_hhmm):
    if not slots: return None
    if not desired_hhmm: return slots[0]
    want = desired_hhmm[0]*60 + desired_hhmm[1]
    best, diff = None, 10**9
    for s in slots:
        dt = datetime.fromisoformat(s); mins = dt.hour*60 + dt.minute
        d = abs(mins - want)
        if d < diff: diff, best = d, s
    return best or slots[0]

def booking_panel():
    b_id = st.session_state.pending.get("booking_id")
    if not b_id: return
    with st.container():
        st.markdown("### 📌 Current booking")
        try:
            s = api_status(b_id)
            when = datetime.fromisoformat(s["start_local"]).strftime("%a %b %d • %I:%M %p")
            st.write(f"**ID:** `{b_id}`  \n**When:** {when}  \n**Party:** {s['party_size']}  \n**Status:** **{s['status']}**")
            if s["status"] != "confirmed":
                st.info("Complete Stripe Checkout, then click **Refresh**.")
            cols = st.columns(3)
            if st.session_state.pending.get("checkout_url"):
                cols[0].link_button("💳 Pay deposit", st.session_state.pending["checkout_url"])
            if cols[1].button("Refresh"):
                st.rerun()
        except Exception as e:
            st.error(f"Status error: {getattr(e, 'response', None) and e.response.text or str(e)}")

# ─────────────────────────── Pages ────────────────────────────
def login_page():
    inject_styles()
    st.markdown(brand_header(), unsafe_allow_html=True)
    st.caption("Sign in to start chatting.")

    st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"): login(u, p)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Create an account"):
        st.session_state.mode = "register"; st.rerun()

def register_page():
    inject_styles()
    st.markdown(brand_header(), unsafe_allow_html=True)
    st.caption("Create your account.")

    st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
    with st.form("register_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Register"): register(u, p)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Back to Login"):
        st.session_state.mode = "login"; st.rerun()

def ask_page():
    inject_styles()
    st.markdown(brand_header(), unsafe_allow_html=True)
    st.caption("Smarter conversations for your business")
    st.divider()

    with st.sidebar:
        st.markdown("## 🧭 Menu")
        if st.button("🗑 Clear chat", key="clear_sidebar", use_container_width=True):
            st.session_state.history = []; st.session_state.pending = {}; st.rerun()
        if st.button("🚪 Log out", key="logout_sidebar", use_container_width=True):
            st.session_state.token = None; st.session_state.mode = "login"; st.rerun()
        st.markdown("---")

        # Optional KB selector (no hardcoding; driven by YAP_COLLECTIONS)
        if COLLECTIONS:
            labels = [c.get("label") or c["id"] for c in COLLECTIONS]
            default_idx = 0
            chosen = st.selectbox("Knowledge base", labels, index=default_idx)
            st.session_state.collection = next(c["id"] for c in COLLECTIONS if (c.get("label") or c["id"]) == chosen)

        st.markdown("### 📜 Chat history")
        if not st.session_state.history:
            st.caption("No conversation yet.")
        else:
            for i in range(0, len(st.session_state.history), 2):
                try:
                    user_msg = st.session_state.history[i]["content"]
                    st.markdown(f"- **{_headline(user_msg)}**")
                except Exception:
                    pass

    # Render history with glossy bubbles
    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(
                    f"<div class='bubble ai-outer'><div class='ai-inner'>"
                    f"<div class='bubble-title ai'>YAP</div>"
                    f"{format_answer(msg['content'])}"
                    f"</div></div>", unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div class='bubble user-outer'><div class='user-inner'>"
                    f"<div class='bubble-title user'>You</div>{msg['content']}"
                    f"</div></div>", unsafe_allow_html=True
                )

    # Composer
    prompt = st.chat_input("Ask anything (e.g., vegan options) or say “check availability for 2 tomorrow 7pm”…")
    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(
                f"<div class='bubble user-outer'><div class='user-inner'>"
                f"<div class='bubble-title user'>You</div>{prompt}"
                f"</div></div>", unsafe_allow_html=True
            )

        # ---- INTENT HANDLER first; else fallback to streaming ----
        p = parse_intent(prompt)
        party = p["party"] or st.session_state.pending.get("party") or 2
        the_date = p["date"] or date.today() + timedelta(days=1)

        handled = False
        reply = ""

        try:
            if p["intent"] == "availability":
                avail = api_availability(the_date, party)
                st.session_state.pending["last_avail"] = avail
                st.session_state.pending["party"] = party
                slots = avail.get("slots", [])
                tz = avail.get("timezone", "local")
                if not slots:
                    reply = f"Sorry, no open slots on **{the_date}**."
                else:
                    best = nearest_slot(slots, p["time"])
                    st.session_state.pending["candidate_slot"] = best
                    human = datetime.fromisoformat(best).strftime("%a %b %d at %I:%M %p")
                    reply = f"Nearest time on **{the_date}** (TZ {tz}): **{human}**. Say **book it** to reserve."
                handled = True

            elif p["intent"] in ("book", "confirm"):
                slot = st.session_state.pending.get("candidate_slot")
                if not slot:
                    avail = api_availability(the_date, party)
                    slots = avail.get("slots", [])
                    if not slots:
                        reply = f"Sorry, no slots on **{the_date}**."
                        handled = True
                    else:
                        slot = nearest_slot(slots, p["time"])
                        st.session_state.pending["candidate_slot"] = slot
                if slot:
                    created = api_create(slot, party, name="Alex", email="alex@example.com", phone="555-0100")
                    st.session_state.pending["booking_id"] = created["booking_id"]
                    st.session_state.pending["checkout_url"] = created.get("checkout_url")
                    if created.get("checkout_url"):
                        reply = (f"Booked! ID `{created['booking_id']}`. "
                                 f"[**Pay deposit**]({created['checkout_url']}) to confirm, "
                                 f"then say **status**.")
                    else:
                        reply = (f"Booking created as **pending** (no checkout link). "
                                 f"ID: `{created['booking_id']}`. Say **status** to check.")
                    handled = True

            elif p["intent"] == "pay":
                b_id = st.session_state.pending.get("booking_id")
                if not b_id:
                    reply = "I don’t have a booking yet. Ask me to book a time first."
                else:
                    s = api_status(b_id)
                    if s.get("status") == "confirmed":
                        reply = f"Already confirmed ✅. Booking `{b_id}`."
                    else:
                        url = st.session_state.pending.get("checkout_url") or "(checkout link was shown above)"
                        reply = f"Open the Stripe checkout link to pay: {url}  \nAfter paying, say **status**."
                handled = True

            elif p["intent"] == "status":
                b_id = st.session_state.pending.get("booking_id")
                if not b_id:
                    reply = "I don’t have a booking id yet. Ask me to book a time first."
                else:
                    s = api_status(b_id)
                    human = datetime.fromisoformat(s["start_local"]).strftime("%a %b %d at %I:%M %p")
                    pi = s.get("payment_intent_id") or "—"
                    reply = (f"Booking `{b_id}` • {human} • party {s['party_size']}  \n"
                             f"**Status:** **{s['status']}**  \nPayment intent: `{pi}`")
                handled = True

        except Exception as e:
            reply = f"Oops, something went wrong: {getattr(e, 'response', None) and e.response.text or str(e)}"
            handled = True

        if handled:
            st.session_state.history.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(
                    "<div class='bubble ai-outer'><div class='ai-inner'>"
                    "<div class='bubble-title ai'>YAP</div>"
                    f"{format_answer(reply)}"
                    "</div></div>", unsafe_allow_html=True,
                )
        else:
            # Fallback to LLM for general queries (backend enforces doc-only answers)
            collection = st.session_state.get("collection")
            ph = st.empty()
            def paint(current_text: str):
                ph.markdown(
                    "<div class='bubble ai-outer'><div class='ai-inner'>"
                    "<div class='bubble-title ai'>YAP</div>"
                    f"{format_answer(current_text)}"
                    "</div></div>", unsafe_allow_html=True,
                )
            paint("")
            answer = stream_answer(prompt, st.session_state.history, on_update=paint, collection=collection)
            if answer and not answer.startswith("[ERROR]"):
                st.session_state.history.append({"role": "assistant", "content": answer})

    # Live booking panel under chat (pay / refresh)
    booking_panel()

# ─────────────────────────── Main ──────────────────────────────
def main():
    if st.session_state.token:
        ask_page(); st.stop()
    elif st.session_state.mode == "login":
        login_page()
    else:
        register_page()

main()
