
# streamlit_app.py
import streamlit as st
import requests

# --- Config ---
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_MODEL = "gemini-2.0-flash"  # free-tier-friendly

st.set_page_config(page_title="CheerUp Bot", page_icon="😊")
st.title("CheerUp — a supportive space to vent 💛")
st.caption(
    "Friendly emotional support, not medical advice. "
    "If you're in crisis, contact local emergency services immediately."
)

# --- Session state ---
if "history" not in st.session_state:
    st.session_state.history = []
if "style" not in st.session_state:
    st.session_state.style = "gentle"

# --- Input UI ---
user_text = st.text_area("What's on your mind today?", height=150)
col1, col2 = st.columns([1, 1])
with col1:
    style = st.selectbox("Preferred tone", ["gentle", "practical", "light-humor"])
with col2:
    suggestions_on = st.checkbox("Include cheer-up suggestions", value=True)

def gemini_reply(prompt):
    """Send prompt to Gemini via REST."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }
    r = requests.post(url, headers=headers, params=params, json=body, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def build_prompt(history, msg, style, suggestions):
    system = (
        "You are a warm, empathetic companion. Validate emotions first. "
        "Avoid medical or clinical advice. Avoid diagnosing. "
        "Keep answers under ~160 words. "
        "If user opted in, include 2–3 gentle, optional cheer-up ideas."
    )
    style_line = f"Tone: {style}."
    sugg_line = (
        "Offer 2–3 optional micro-suggestions." if suggestions else "No suggestions."
    )
    convo = "\n".join(
        [f"User: {h['u']}\nYou: {h['b']}" for h in history[-3:]]
    )
    return (
        f"{system}\n\n{style_line}\n{sugg_line}\n\n"
        f"Conversation so far:\n{convo}\n\n"
        f"New message from user:\n{msg}\n\n"
        f"Your supportive reply:"
    )

# Crisis keyword check
CRISIS_TERMS = [
    "suicide", "end my life", "self harm", "kill myself", "can't go on"
]

if st.button("Send", type="primary") and user_text.strip():
    if any(term in user_text.lower() for term in CRISIS_TERMS):
        st.error(
            "I'm really sorry you're feeling this way. "
            "If you're in immediate danger or feeling unsafe, "
            "please contact local emergency services right now."
        )
    else:
        prompt = build_prompt(
            st.session_state.history, user_text, style, suggestions_on
        )
        reply = gemini_reply(prompt)
        st.session_state.history.append({"u": user_text, "b": reply})
        st.session_state.style = style

# --- Chat transcript ---
st.markdown("---")
for turn in st.session_state.history[-6:]:
    st.markdown(f"**You:** {turn['u']}")
    st.markdown(f"**CheerUp:** {turn['b']}")
