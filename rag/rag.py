
# rag/rag.py  (replace build_prompt with this version)
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions

DB_DIR = "rag/chroma_db"

ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
client = chromadb.PersistentClient(path=DB_DIR)
coll = client.get_or_create_collection(
    name="cheerup",
    metadata={"hnsw:space":"cosine"},
    embedding_function=ef
)

def retrieve(query: str, k: int = 4) -> List[Dict]:
    res = coll.query(query_texts=[query], n_results=k)
    out = []
    if res and res.get("documents"):
        for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
            out.append({"text": doc, "meta": meta})
    return out

def build_prompt(user_input: str, contexts: List[Dict], allow_links: bool = False) -> str:
    """
    Build a single blended prompt. If allow_links=False, the assistant must not include URLs,
    but should still integrate treat ideas with general supportive advice and then ask
    for permission to share links.
    """
    # Prepare context blocks (RAG + Online offers)
    context_blocks = "\n\n".join(
        [f"[Source: {c['meta'].get('source','?')} | chunk {c['meta'].get('chunk','?')}] {c['text']}"
         for c in contexts if c.get("text")]
    )

    system_rules = (
        "You are CheerUpBot—empathetic, supportive, and concise.\n"
        "Blend general supportive advice with a few gentle treat ideas in the SAME reply.\n"
        "Use the CONTEXT to ground your suggestions (do NOT invent factual details).\n"
        "Do NOT provide medical/clinical advice; if the user hints at harm, recommend contacting local emergency services or relevant hotlines.\n"
        "Tone: warm, validating, and practical; keep paragraphs short and readable.\n"
    )

    gating_rules = (
        "Consent policy: If links are NOT consented yet, DO NOT include any URLs. "
        "Suggest 2–4 treat ideas by name only, together with general advice, and then ask if the user wants links.\n"
        if not allow_links else
        "Consent granted: You may include the provided URLs alongside the treat suggestions.\n"
    )

    output_style = (
        "Suggested output structure:\n"
        "1) Brief validation (1–2 sentences).\n"
        "2) 2–3 grounded coping tips from CONTEXT.\n"
        "3) 2–4 treat ideas (names only if no consent; include links if consent granted).\n"
        "4) If links were not shared yet, ask a short, explicit permission question.\n"
    )

    return f"""{system_rules}{gating_rules}{output_style}
CONTEXT
-------
{context_blocks if context_blocks else "(no context found)"}

USER
----
{user_input}

ASSISTANT
---------
"""
