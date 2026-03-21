
# gemini_requests.py
import streamlit as st
import os
import requests
import time

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GEMINI_MODEL = "gemini-2.5-flash"  # free-tier-friendly
RETRIES = 3
DELAY = 5

def gemini_generate(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """
    Calls Gemini's REST API using plain requests.
    Expects GEMINI_API_KEY in the environment.
    """
    key = os.environ["GEMINI_API_KEY"]
    url = f"{BASE}/{model}:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }
    for i in range(0, RETRIES):
        resp = requests.post(url, headers=headers, params=params, json=body, timeout=30)
        time.sleep(DELAY)
        if resp.status_code==200: break
    resp.raise_for_status()
    data = resp.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return "(No response generated.)"
