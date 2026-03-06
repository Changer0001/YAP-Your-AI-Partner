import streamlit as st
import requests, re, json
from textwrap import dedent
import html

def sanitize_for_html(s: str) -> str:
    if s is None:
        return ""
    # Remove control chars (except \n and \t)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    # Escape HTML special chars
    return html.escape(s)

st.set_page_config(page_title="YAP", page_icon="🤖", layout="centered")
API_URL = "http://localhost:8000"

# ───────────────────────── Styles ─────────────────────────
def inject_styles():
    st.markdown(dedent("""
    <style>
      :root{
        --bg:#0a0f1e;
        --panel:#0c1324;
        --text:#e6edf3;
        --muted:#94a3b8;
        --input:#161c2e;
        --border:rgba(148,163,184,.18);
        --glow1:#7dd3fc;   /* cyan */
        --glow2:#c084fc;   /* purple */
      }
      html, body, [class*="css"]{ background:var(--bg); color:var(--text); }

      /* ---- Brand header (shared) ---- */
      .brand-wrap{max-width:860px;margin:0 auto 12px;}
      .brand-box{border-radius:22px;padding:3px;
        background:linear-gradient(90deg,rgba(125,211,252,.45),rgba(192,132,252,.45));
        box-shadow:0 0 0 1px var(--border), 0 20px 45px rgba(56,189,248,.15);
      }
      .brand-inner{border-radius:20px;padding:18px 24px;
        background:linear-gradient(180deg,#0e162b 0%,#0b1325 100%);
        border:1px solid rgba(125,211,252,.22);
      }
      .brand-title{
        font-family: Orbitron, system-ui, sans-serif;
        font-weight:700; font-size:44px; letter-spacing:.6px;
        background:linear-gradient(90deg,var(--glow1),var(--glow2));
        -webkit-background-clip:text; background-clip:text; color:transparent;
        text-shadow:0 0 26px rgba(125,211,252,.10);
      }

      /* ---- Auth card (login + register) ---- */
      .auth-card{
        max-width:860px;margin:8px auto; border-radius:16px; padding:18px;
        background:linear-gradient(180deg,rgba(13,19,35,.85),rgba(10,15,28,.88));
        border:1px solid var(--border);
        box-shadow:inset 0 14px 30px rgba(2,8,23,.35), 0 10px 30px rgba(0,0,0,.25);
      }
      .auth-card label{color:var(--muted); font-weight:600;}
      [data-testid="stForm"]{background:transparent; border:0; padding:0;}

      /* ---- Inputs ---- */
      [data-baseweb="input"] > div{
        background:var(--input); border:1px solid var(--border); border-radius:12px;
      }
      [data-baseweb="input"] input{color:var(--text);}
      [data-baseweb="input"]:focus-within{
        box-shadow:0 0 0 2px rgba(125,211,252,.35), inset 0 0 0 1px rgba(192,132,252,.25);
      }
      svg[data-testid="stPasswordInputVisibilityToggle"]{opacity:.9}

      /* ---- Buttons ---- */
      .stButton > button{
        border-radius:12px; padding:.55rem 1rem; font-weight:600;
        color:var(--text); border:1px solid rgba(148,163,184,.2);
        background:linear-gradient(90deg,rgba(99,102,241,.35),rgba(192,132,252,.35));
        box-shadow:0 10px 24px rgba(99,102,241,.15);
      }
      .stButton > button:hover{filter:brightness(1.08);}
      .stButton > button:focus{outline:none; box-shadow:0 0 0 2px rgba(125,211,252,.35);}

      /* ---- Chat bubbles ---- */
      [data-testid^="stChatMessageAvatar"]{display:none!important;}
      [data-testid="stChatMessage"]{background:transparent!important;padding:0!important;border:0!important;}
      [data-testid="stChatMessage"] > div{background:transparent!important;padding:0!important;box-shadow:none!important;}

      .bubble{max-width:860px;margin:.5rem auto 1rem;border-radius:16px}

      /* glossy USER bubble */
      .user-outer{
        padding:1px;
        background:linear-gradient(135deg, rgba(99,102,241,.55), rgba(56,189,248,.45));
        border-radius:16px;
        box-shadow:0 16px 40px rgba(56,189,248,.12);
      }
      .user-inner{
        background:linear-gradient(135deg, rgba(12,18,34,.96), rgba(10,16,30,.96));
        border:1px solid rgba(148,163,184,.22);
        border-radius:15px;
        padding:.95rem 1.1rem;
        backdrop-filter:blur(6px); -webkit-backdrop-filter:blur(6px);
      }

      /* glossy AI bubble */
      .ai-outer{
        padding:1px;background:linear-gradient(135deg,rgba(56,189,248,.55),rgba(168,85,247,.45));
        border-radius:16px;box-shadow:0 16px 40px rgba(56,189,248,.16)
      }
      .ai-inner{
        background:linear-gradient(135deg,rgba(9,15,27,.96),rgba(11,18,32,.96));
        border:1px solid rgba(125,211,252,.22);border-radius:15px;
        padding:.95rem 1.1rem;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)
      }

      .bubble-title{font-size:.8rem;font-weight:700;letter-spacing:.2px;opacity:.9;margin-bottom:.35rem}
      .bubble-title.user{color:#93c5fd}.bubble-title.ai{color:#c4b5fd}
      .answer ol{margin-left:1.25em;line-height:1.7em;padding-left:.25em}
      .answer p{margin:0 0 .55rem 0}.answer li{margin:.2rem 0}
    </style>
    """), unsafe_allow_html=True)

def brand_header():
    return (
        "<div class='brand-wrap'><div class='brand-box'><div class='brand-inner'>"
        "<div class='brand-title'>YAP</div>"
        "</div></div></div>"
    )

# ───────────────────── Formatting helpers ─────────────────────
def format_answer(text: str) -> str:
    t = sanitize_for_html((text or "").strip())
    t = re.sub(r"(?<!\n)(\d+\.)", r"\n\1", t)
    t = re.sub(r"(?m)^\s*(\d+)\.\s*(.*)", r"<li>\2</li>", t)
    if "<li>" in t:
        t = f"<ol>{t}</ol>"
    return f"<div class='answer' style='font-size:1.05rem; line-height:1.75em; color:#e2e8f0'>{t}</div>"

def _headline(text: str, max_len: int = 60) -> str:
    t = (text or "").strip()
    t = re.split(r'[\\n\\.!?]', t)[0]
    return (t[:max_len] + "…") if len(t) > max_len else t

# ─────────────────────────── State ────────────────────────────
st.session_state.setdefault("token", None)
st.session_state.setdefault("mode", "login")
st.session_state.setdefault("history", [])

# ─────────────────────────── Auth ─────────────────────────────
def login(username, password):
    try:
        r = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if r.status_code == 401:
            st.error("❌ Invalid credentials."); return
        r.raise_for_status()
        token = r.json().get("access_token") or r.json().get("token")
        if not token:
            st.error("Login succeeded but no token returned."); return
        st.session_state.token = token
        st.session_state.history = []
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def register(username, password):
    try:
        r = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        if r.status_code == 400:
            st.error("❌ Username already exists."); return
        r.raise_for_status()
        st.success("✅ Registration successful. Please log in.")
        st.session_state.mode = "login"
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

# ──────────────────────── Streaming (SSE) ─────────────────────
def stream_answer(prompt, history, on_update):
    payload = {"question": prompt}
    headers = {
        "Authorization": f"Bearer {st.session_state.token}",
        "Content-Type": "application/json",
    }

    answer = ""
    current_event = None

    try:
        with requests.post(
            f"{API_URL}/ask/stream",
            json=payload,
            headers=headers,
            stream=True,
            timeout=(10, 300),
        ) as resp:
            if not resp.ok:
                on_update(f"❌ API {resp.status_code}: {resp.text}")
                return "[ERROR]"

            for raw in resp.iter_lines(decode_unicode=True):
                if raw is None:
                    continue

                line = raw.strip()
                if not line:
                    continue

                # SSE event line
                if line.startswith("event:"):
                    current_event = line.split("event:", 1)[1].strip().lower()
                    if current_event in ("done", "end", "complete", "finished"):
                        break
                    continue

                # Ignore comments/retry
                if line.startswith(":") or line.startswith("retry:"):
                    continue

                if line.startswith("data:"):
                    data_str = line.split("data:", 1)[1].strip()

                    # common terminators
                    if data_str in ("[DONE]", "DONE", "__DONE__", ""):
                        break

                    # sources event — store but don't render
                    if current_event == "sources":
                        try:
                            st.session_state["last_sources"] = json.loads(data_str)
                        except Exception:
                            st.session_state["last_sources"] = data_str
                        current_event = None  # ← add this line
                        continue

                    # ── token/content parsing ──────────────────────────────
                    piece = ""
                    try:
                        obj = json.loads(data_str)
                        if isinstance(obj, str):
                            piece = obj
                        elif isinstance(obj, dict):
                            # FIX: handle OpenAI-style choices[0].delta.content
                            piece = (
                                obj.get("token")
                                or obj.get("text")
                                or obj.get("content")
                                or obj.get("answer")
                                or (obj.get("choices") or [{}])[0].get("delta", {}).get("content", "")
                                or ""
                            )
                        else:
                            piece = str(obj)
                    except Exception:
                        piece = data_str

                    if piece:
                        answer += piece
                        on_update(answer)

    except Exception as e:
        on_update(f"❌ Stream error: {e}")
        return "[ERROR]"

    return answer.strip()

# ─────────────────────────── Pages ────────────────────────────
def login_page():
    inject_styles()
    st.markdown(brand_header(), unsafe_allow_html=True)
    st.caption("Sign in to start chatting.")

    st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            login(u, p)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Create an account"):
        st.session_state.mode = "register"
        st.rerun()

def register_page():
    inject_styles()
    st.markdown(brand_header(), unsafe_allow_html=True)
    st.caption("Create your account.")

    st.markdown("<div class='auth-card'>", unsafe_allow_html=True)
    with st.form("register_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Register"):
            register(u, p)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Back to Login"):
        st.session_state.mode = "login"
        st.rerun()

def ask_page():
    inject_styles()
    st.markdown(brand_header(), unsafe_allow_html=True)
    st.caption("Smarter conversations for your business")
    st.divider()

    with st.sidebar:
        st.markdown("## 🧭 Menu")
        if st.button("🗑 Clear chat", key="clear_sidebar", use_container_width=True):
            st.session_state.history = []; st.rerun()
        if st.button("🚪 Log out", key="logout_sidebar", use_container_width=True):
            st.session_state.token = None; st.session_state.mode = "login"; st.rerun()
        st.markdown("---")
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
                    f"</div></div>",
                    unsafe_allow_html=True
                )

    # Composer
    prompt = st.chat_input("Ask your question…")
    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(
                f"<div class='bubble user-outer'><div class='user-inner'>"
                f"<div class='bubble-title user'>You</div>{prompt}"
                f"</div></div>",
                unsafe_allow_html=True
            )

        # Streaming inside glossy AI bubble
        ph = st.empty()

        def paint(current_text: str):
            ph.markdown(
                "<div class='bubble ai-outer'><div class='ai-inner'>"
                "<div class='bubble-title ai'>YAP</div>"
                f"{format_answer(current_text)}"
                "</div></div>",
                unsafe_allow_html=True,
            )

        # FIX: removed paint("") — it was overwriting the bubble with empty content
        answer = stream_answer(prompt, st.session_state.history, on_update=paint)
        if answer and not answer.startswith("[ERROR]"):
            st.session_state.history.append({"role": "assistant", "content": answer})

# ─────────────────────────── Main ──────────────────────────────
def main():
    if st.session_state.token:
        ask_page(); st.stop()
    elif st.session_state.mode == "login":
        login_page()
    else:
        register_page()

main()