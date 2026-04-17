"""
build_index.py

Reads all the .txt files from ./docs/ and builds a local vector database
using HuggingFace sentence-transformers for embeddings + ChromaDB for storage.

Run this AFTER scrape_docs.py.
"""

import os
import glob
import argparse
import chromadb
from sentence_transformers import SentenceTransformer

DOCS_FOLDER   = "docs"
DB_FOLDER     = "chroma_db"

DEFAULT_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split a big wall of text into smaller overlapping chunks.
    This keeps each piece small enough for the embedding model.
    """
    chunks = []
    start  = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def build_index(embedding_model_name: str):
    """Load docs, embed them, and save to ChromaDB."""

    print(f"Loading embedding model: {embedding_model_name}")
    print("   (First run will download the model – give it a minute)\n")
    model = SentenceTransformer(embedding_model_name)

    print(f"Opening database at: ./{DB_FOLDER}/")
    client     = chromadb.PersistentClient(path=DB_FOLDER)

    try:
        client.delete_collection("ubuntu_docs")
    except Exception:
        pass

    collection = client.create_collection("ubuntu_docs")

    doc_files = glob.glob(os.path.join(DOCS_FOLDER, "*.txt"))

    if not doc_files:
        print(f"No .txt files found in ./{DOCS_FOLDER}/")
        print("   Did you run  python scrape_docs.py  first?")
        return

    print(f"Found {len(doc_files)} doc files. Chunking and embedding...\n")

    all_chunks    = []
    all_ids       = []
    all_metadatas = []
    chunk_id      = 0

    for filepath in doc_files:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

        for chunk in chunks:
            if len(chunk.strip()) < 50:
                continue
            all_chunks.append(chunk)
            all_ids.append(f"chunk_{chunk_id}")
            all_metadatas.append({"source": filepath})
            chunk_id += 1

    print(f"Total chunks to embed: {len(all_chunks)}")
    print("Embedding... (this takes a few minutes the first time)\n")

    BATCH = 64
    for i in range(0, len(all_chunks), BATCH):
        batch_texts     = all_chunks[i : i + BATCH]
        batch_ids       = all_ids[i : i + BATCH]
        batch_metas     = all_metadatas[i : i + BATCH]
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()

        collection.add(
            documents  = batch_texts,
            embeddings = batch_embeddings,
            ids        = batch_ids,
            metadatas  = batch_metas,
        )

        done = min(i + BATCH, len(all_chunks))
        print(f"   Embedded {done}/{len(all_chunks)} chunks...")

    print(f"\nIndex built! {len(all_chunks)} chunks stored in ./{DB_FOLDER}/")


def parse_args():
    p = argparse.ArgumentParser(description="Build the RAG index from docs.")
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"HuggingFace sentence-transformer model name (default: {DEFAULT_MODEL})",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = build_index(parse_args().model)
