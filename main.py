
# main.py  (drop-in replacement for your respond() + helpers)
import re
from typing import Optional, Dict, List

from online_food import search_recipes, search_treats
from rag.rag import retrieve, build_prompt
from gemini_requests import gemini_generate

# Simple in-memory session for consent state (adjust if you have multi-user UI)
SESSION = {"awaiting_consent": False, "pending": None, "prefs": {}}

# Multilingual yes/no for PL/EN
ACCEPT_RE = re.compile(r"\b(yes|sure|ok|okay|please|go ahead|tak|poproszę|jasne|spoko|proszę)\b", re.I)
DECLINE_RE = re.compile(r"\b(no|not now|maybe later|nie|nie teraz|dziękuję|thanks but)\b", re.I)

def detect_consent(text: str) -> Optional[str]:
    if ACCEPT_RE.search(text or ""):
        return "yes"
    if DECLINE_RE.search(text or ""):
        return "no"
    return None

def fetch_candidates(user_text: str, prefs: Optional[Dict] = None) -> Dict[str, List[Dict]]:
    """
    Pull a few dessert recipes + ready-to-buy treats.
    TheMealDB: search/filter/random/lookup (public dev/test key documented).
    OpenFoodFacts: tag-based search; requires descriptive User-Agent; 10 req/min.
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
    Produce a compact context block that the model can weave into the SAME message
    as general supportive advice. Names-only if include_links=False.
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

def respond(user_text: str, prefs: Optional[Dict] = None) -> str:
    # 0) RAG context (coping tips, validation snippets, etc.)
    local_ctx = retrieve(user_text, k=4)

    # 1) If awaiting consent, decide
    if SESSION["awaiting_consent"]:
        decision = detect_consent(user_text)
        if decision == "yes" and SESSION["pending"]:
            online_ctx = make_online_context(
                SESSION["pending"]["recipes"], SESSION["pending"]["treats"], include_links=True
            )
            prompt = build_prompt(
                user_text,
                [{"text": online_ctx, "meta": {"source": "online"}}] + local_ctx,
                allow_links=True,
            )
            SESSION["awaiting_consent"] = False
            SESSION["pending"] = None
            return gemini_generate(prompt)

        if decision == "no":
            SESSION["awaiting_consent"] = False
            SESSION["pending"] = None
            # Still blend advice + a gentle close, but no links and no more offers.
            online_ctx = "ONLINE_TREATS:\n- (user declined links)"
            prompt = build_prompt(
                user_text,
                [{"text": online_ctx, "meta": {"source": "online"}}] + local_ctx,
                allow_links=False,
            )
            return gemini_generate(prompt)
        # If unclear, we’ll re-offer once (fallthrough).

    # 2) Not awaiting consent: fetch candidates and **blend** advice + treats in one reply
    SESSION["pending"] = fetch_candidates(user_text, prefs or SESSION.get("prefs"))
    SESSION["awaiting_consent"] = True

    offer_ctx = make_online_context(
        SESSION["pending"]["recipes"], SESSION["pending"]["treats"], include_links=False
    )
    prompt = build_prompt(
        user_text,
        [{"text": offer_ctx, "meta": {"source": "online"}}] + local_ctx,
        allow_links=False,
    )
    return gemini_generate(prompt)
