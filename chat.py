"""
chat.py

A friendly Linux guide chatbot for new Ubuntu users.

It searches the local Ubuntu docs database for relevant info,
then sends that context + your question to any local LLM
running an OpenAI-compatible API (Ollama, LM Studio, etc.)

"""

import argparse
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI

DEFAULT_ENDPOINT      = "http://localhost:11434/v1" 
DEFAULT_MODEL         = "llama3"
DEFAULT_EMBED_MODEL   = "all-MiniLM-L6-v2"
DB_FOLDER             = "chroma_db"
TOP_K_RESULTS         = 5  

SYSTEM_PROMPT = """You are a friendly Linux guide for brand-new Ubuntu users.
Your job is to help beginners understand Ubuntu and Linux in simple, 
easy-to-understand language. Avoid jargon when possible, and always 
explain what a command or concept does before telling the user to use it.

You will be given relevant documentation snippets from the Ubuntu help site.
Use them to answer the user's question. If the docs don't cover it, say so 
honestly and give your best general advice.

Be encouraging! Linux can feel scary at first, but you're here to help."""


def load_resources(embed_model_name: str):
    """Load the embedding model and the ChromaDB collection."""
    print("Loading embedding model...")
    embedder = SentenceTransformer(embed_model_name)

    print("Opening docs database...")
    try:
        client     = chromadb.PersistentClient(path=DB_FOLDER)
        collection = client.get_collection("ubuntu_docs")
    except Exception:
        print(
            "\n Could not open the database!\n"
            "   Did you run these steps first?\n"
            "   1)  python scrape_docs.py\n"
            "   2)  python build_index.py\n"
        )
        raise SystemExit(1)

    doc_count = collection.count()
    print(f" Database loaded! ({doc_count} chunks indexed)\n")
    return embedder, collection


def search_docs(query: str, embedder, collection, top_k: int) -> str:
    """
    Embed the user's question and find the most relevant doc chunks.
    """
    query_vector = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
    )

    chunks = results["documents"][0]
    sources = results["metadatas"][0]

    if not chunks:
        return "No relevant documentation found."

    combined = ""
    for i, (chunk, meta) in enumerate(zip(chunks, sources), 1):
        source_file = meta.get("source", "unknown")
        combined += f"--- Doc snippet {i} (from {source_file}) ---\n"
        combined += chunk.strip() + "\n\n"

    return combined


def chat_loop(args):
    """Main interactive chat loop."""

    embedder, collection = load_resources(args.embed_model)

    client = OpenAI(
        base_url=args.endpoint,
        api_key="not-needed",
    )

    print("=" * 55)
    print("  Ubuntu Linux Guide  ")
    print("=" * 55)
    print(f"  LLM endpoint : {args.endpoint}")
    print(f"  Model        : {args.model}")
    print(f"  Embed model  : {args.embed_model}")
    print("=" * 55)
    print("  Ask me anything about Ubuntu! Type 'quit' to exit.")
    print("=" * 55)
    print()

    conversation_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n Goodbye! Happy Linux-ing!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye", "q"):
            print(" Goodbye! Happy Linux-ing!")
            break

        print("Searching docs...", end="\r")
        doc_context = search_docs(user_input, embedder, collection, TOP_K_RESULTS)

        context_message = {
            "role": "user",
            "content": (
                f"[Relevant Ubuntu documentation for this question]\n\n"
                f"{doc_context}\n\n"
                f"[User's question]\n{user_input}"
            ),
        }

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += conversation_history
        messages.append(context_message)

        print("Thinking...      ", end="\r")
        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
        except Exception as e:
            print(f"\n Error talking to LLM: {e}")
            print(f"   Is your LLM server running at {args.endpoint}?")
            continue

        print(f"\n🐧 Guide: ", end="", flush=True)
        full_reply = ""
        for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            print(delta, end="", flush=True)
            full_reply += delta
        print("\n") 

        conversation_history.append({"role": "user",      "content": user_input})
        conversation_history.append({"role": "assistant", "content": full_reply})

        if len(conversation_history) > 20:
            conversation_history = conversation_history[-20:]


def parse_args():
    p = argparse.ArgumentParser(
        description="🐧 Ubuntu Linux Guide – RAG chatbot for new Linux users",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chat.py
  python chat.py --endpoint http://localhost:11434/v1 --model llama3
  python chat.py --endpoint http://localhost:1234/v1  --model mistral-7b
  python chat.py --embed-model sentence-transformers/all-mpnet-base-v2
        """,
    )
    p.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"OpenAI-compatible API endpoint of your local LLM (default: {DEFAULT_ENDPOINT})",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name to use for chat (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--embed-model",
        default=DEFAULT_EMBED_MODEL,
        dest="embed_model",
        help=f"HuggingFace embedding model (default: {DEFAULT_EMBED_MODEL})",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    chat_loop(args)
