
# main.py
# Streamlit chat UI for CheerUpBot with:
# - RAG grounding (Chroma + MiniLM)
# - Live treats/recipes offers (TheMealDB + OpenFoodFacts)
# - Consent-first link sharing
# - Single, blended reply (supportive advice + treat ideas) before consent

import os
import re
from typing import Optional, Dict, List

import streamlit as st

# Local modules you already added in previous steps:
from online_food import search_recipes, search_treats
from rag.rag import retrieve, build_prompt
from gemini_requests import gemini_generate


# ---------------------------
# Page & global UI settings
# ---------------------------

import streamlit as st
import os

# ---- Big centered title ----
SITE_TITLE = os.environ.get("SITE_TITLE", "CheerUp bot 😊")

# ---- Page config with old smiley restored everywhere ----
st.set_page_config(
    page_title=SITE_TITLE,
    page_icon="😊",      # ← TAB ICON NOW SET TO 😊
    layout="centered",
)

st.markdown(
    f"""
    <style>
    .cheerup-header {{
        display: flex;
        justify-content: center;
        text-align: center;
        margin-top: 0.5rem;
    }}
    .cheerup-title {{
        font-size: clamp(2.2rem, 5vw, 3.4rem);
        font-weight: 800;
        line-height: 1.2;
    }}
    </style>

    <div class="cheerup-header">
      <h1 class="cheerup-title">{SITE_TITLE}</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# Light, visible disclaimer (non-clinical)
with st.container():
    st.markdown(
        """
        <div style="padding:0.6rem 0.9rem;background:#fff7e6;border:1px solid #ffe2b2;border-radius:10px;">
          <strong>Friendly note:</strong> CheerUpBot offers supportive conversation and gentle ideas (not medical advice).
          If you ever feel unsafe, please contact local emergency services or a trusted hotline.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------
# Session state initialization
# ---------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi, I’m here with you. Tell me what’s on your mind—"
                "we can take it one step at a time. 🌼"
            ),
        }
    ]

if "awaiting_consent" not in st.session_state:
    st.session_state.awaiting_consent = False

if "pending" not in st.session_state:
    # Will hold fetched treats/recipes for link reveal after user agrees
    st.session_state.pending = None  # {"recipes":[...], "treats":[...]}

if "prefs" not in st.session_state:
    st.session_state.prefs = {}  # you can prefill e.g., {"country":"Poland","ingredient":"chocolate"}


# ---------------------------
# Consent detection (EN/PL)
# ---------------------------
ACCEPT_RE = re.compile(r"\b(yes|sure|ok|okay|please|go ahead|tak|poproszę|jasne|spoko|proszę)\b", re.I)
DECLINE_RE = re.compile(r"\b(no|not now|maybe later|nie|nie teraz|dziękuję|thanks but)\b", re.I)

def detect_consent(text: str) -> Optional[str]:
    if ACCEPT_RE.search(text or ""):
        return "yes"
    if DECLINE_RE.search(text or ""):
        return "no"
    return None


# ---------------------------
# Online candidates
# ---------------------------
def fetch_candidates(user_text: str, prefs: Optional[Dict] = None) -> Dict[str, List[Dict]]:
    """
    Pull a few dessert recipes (TheMealDB) + ready-to-buy treats (OpenFoodFacts).
    TheMealDB: search/filter/random/lookup endpoints (public dev/test key documented).
    OpenFoodFacts: tag-based search; provide descriptive User-Agent; search is rate-limited.
    """
    prefs = prefs or {}
    recipes = search_recipes(
        query=user_text,
        category=prefs.get("recipe_category") or "Dessert",
        ingredient=prefs.get("ingredient"),
        limit=3
    )
    treats = search_treats(
        keywords=[prefs["ingredient"]] if prefs.get("ingredient") else None,
        categories=prefs.get("categories") or ["Chocolate", "Biscuits and cookies", "Ice creams"],
        country=prefs.get("country") or "Poland",
        page_size=8,
    )
    return {"recipes": recipes[:3], "treats": treats[:5]}


def make_online_context(recipes: List[Dict], treats: List[Dict], include_links: bool) -> str:
    """
    Produce a compact context block; names-only if include_links=False.
    """
    parts = []
    if recipes:
        parts.append("ONLINE_RECIPES:")
        for r in recipes:
            if include_links and r.get("url"):
                parts.append(f"- {r['title']} — {r['url']}")
            else:
                parts.append(f"- {r['title']}")
    if treats:
        parts.append("\nONLINE_TREATS:")
        for t in treats:
            nm = t.get("product_name") or "Unknown"
            if include_links and t.get("url"):
                parts.append(f"- {nm}{(' ('+t['brands']+')') if t.get('brands') else ''} — {t['url']}")
            else:
                parts.append(f"- {nm}{(' ('+t['brands']+')') if t.get('brands') else ''}")
    return "\n".join(parts)


# ---------------------------
# Core respond() with consent flow
# ---------------------------
def respond(user_text: str, prefs: Optional[Dict] = None) -> str:
    """
    1) If we asked for consent previously:
       - yes: reveal links (same candidates)
       - no: continue supportively without links
    2) Otherwise: blend general advice + treat names in one reply and ask permission for links.
    """
    # 0) RAG from local notes
    local_ctx = retrieve(user_text, k=4)

    # 1) Handle consent decision if pending
    if st.session_state.awaiting_consent:
        decision = detect_consent(user_text)
        if decision == "yes" and st.session_state.pending:
            online_ctx = make_online_context(
                st.session_state.pending["recipes"],
                st.session_state.pending["treats"],
                include_links=True
            )
            prompt = build_prompt(
                user_text,
                [{"text": online_ctx, "meta": {"source": "online"}}] + local_ctx,
                allow_links=True,
            )
            st.session_state.awaiting_consent = False
            st.session_state.pending = None
            return gemini_generate(prompt)

        if decision == "no":
            st.session_state.awaiting_consent = False
            st.session_state.pending = None
            # Continue empathetically without links
            online_ctx = "ONLINE_TREATS:\n- (user declined links)"
            prompt = build_prompt(
                user_text,
                [{"text": online_ctx, "meta": {"source": "online"}}] + local_ctx,
                allow_links=False,
            )
            return gemini_generate(prompt)
        # If unclear, we re-offer below.

    # 2) Not awaiting consent: fetch candidates and blend in one reply (names-only + permission ask)
    st.session_state.pending = fetch_candidates(user_text, prefs or st.session_state.prefs)
    st.session_state.awaiting_consent = True

    offer_ctx = make_online_context(
        st.session_state.pending["recipes"],
        st.session_state.pending["treats"],
        include_links=False
    )

    prompt = build_prompt(
        user_text,
        [{"text": offer_ctx, "meta": {"source": "online"}}] + local_ctx,
        allow_links=False,
    )
    return gemini_generate(prompt)


# ---------------------------
# Utility: ensure API key present
# ---------------------------
def have_gemini_key() -> bool:
    # Prefer Streamlit secrets if present; fallback to env
    key = None
    try:
        key = st.secrets.get("GEMINI_API_KEY", None)  # type: ignore[attr-defined]
    except Exception:
        pass
    key = key or os.environ.get("GEMINI_API_KEY")
    return bool(key)


# ---------------------------
# Chat transcript rendering
# ---------------------------
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])


# ---------------------------
# Consent quick buttons (optional UX)
# ---------------------------
def consent_buttons():
    """Show Yes / No buttons when awaiting consent to reveal links."""
    cols = st.columns(2)
    yes = cols[0].button("✅ Yes, share links", use_container_width=True)
    no = cols[1].button("🚫 No thanks", use_container_width=True)
    return yes, no

if st.session_state.awaiting_consent:
    with st.container():
        st.info("Would you like me to include the links for those treats/recipes?")
        y, n = consent_buttons()
        if y:
            user_msg = "Yes, please share the links."
            st.session_state.messages.append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.markdown(user_msg)
            bot_reply = respond(user_msg)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            st.stop()
        if n:
            user_msg = "No, not now."
            st.session_state.messages.append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.markdown(user_msg)
            bot_reply = respond(user_msg)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            st.stop()


# ---------------------------
# Chat input
# ---------------------------
if not have_gemini_key():
    st.warning(
        "Set your GEMINI_API_KEY (Streamlit Secrets or environment variable) to enable responses."
    )

user_input = st.chat_input("Type here…")
if user_input:
    # Render user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate bot reply via consent-aware respond()
    bot_text = respond(user_input)
    st.session_state.messages.append({"role": "assistant", "content": bot_text})
    with st.chat_message("assistant"):
        st.markdown(bot_text)
