
# rag/build_index.py
from pathlib import Path
import re, uuid
import chromadb
from chromadb.utils import embedding_functions

DATA_DIR = Path(__file__).parent / "knowledge"
DB_DIR = Path(__file__).parent / "chroma_db"

# Local, free, small model (~80MB, 384-dim), great on CPU
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

client = chromadb.PersistentClient(path=str(DB_DIR))
coll = client.get_or_create_collection(
    name="cheerup",
    metadata={"hnsw:space": "cosine"},
    embedding_function=ef,
)

def read_docs():
    for p in DATA_DIR.glob("*.*"):
        text = p.read_text(encoding="utf-8")
        yield p.name, text

def chunk(text, max_chars=800):
    parts = re.split(r"\n{2,}", text.strip())
    buf, cur = [], 0
    for part in parts:
        if cur + len(part) + 2 > max_chars and buf:
            yield "\n\n".join(buf)
            buf, cur = [part], len(part)
        else:
            buf.append(part)
            cur += len(part) + 2
    if buf:
        yield "\n\n".join(buf)

def main():
    # Rebuild from scratch (fine for tiny KBs)
    try:
        client.delete_collection("cheerup")
    except Exception:
        pass
    coll = client.get_or_create_collection(
        name="cheerup",
        metadata={"hnsw:space": "cosine"},
        embedding_function=ef,
    )
    ids, docs, metas = [], [], []
    for fname, raw in read_docs():
        for i, ch in enumerate(chunk(raw)):
            ids.append(str(uuid.uuid4()))
            docs.append(ch)
            metas.append({"source": fname, "chunk": i})
    if docs:
        coll.add(ids=ids, documents=docs, metadatas=metas)
        print(f"Indexed {len(docs)} chunks into {DB_DIR}")
    else:
        print("No documents found. Add files to rag/knowledge/ (optional).")

if __name__ == "__main__":
    main()
