# scripts/probe_rrf_hyde.py
import os
import argparse
import logging

from app.core.chroma_config import client
from app.retriever.embed import embedding_model
from app.retriever.rrf_hyde import build_context_from_collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

def main():
    p = argparse.ArgumentParser("Probe RRF+HYDE against a Chroma collection")
    p.add_argument("--collection", default="example_business_docs")
    p.add_argument("--query", required=True, help="Your test question")
    p.add_argument("--k-each", type=int, default=8, help="Top-K per retriever before fusion")
    p.add_argument("--k-final", type=int, default=6, help="Final fused chunks in context")
    p.add_argument("--no-hyde", action="store_true", help="Disable HYDE expansions")
    args = p.parse_args()

    # Ensure we can embed queries (critical!)
    col = client.get_or_create_collection(
        name=args.collection,
        embedding_function=embedding_model,
    )
    logging.info(f"📚 Collection '{args.collection}' count = {col.count()}")

    # Build fused context
    ctx, rows = build_context_from_collection(
        collection=args.collection,
        query=args.query,
        use_real_hyde=not args.no_hyde,
        k_each=args.k_each,
        k_final=args.k_final,
    )

    print("\n────────────────────────────────────────────────────────────────────")
    print(f"QUERY: {args.query}")
    print(f"CTX CHARS: {len(ctx)}")
    print(f"ROWS: {len(rows)}")
    if rows:
        print("TOP SOURCES:")
        for i, (rid, text, meta) in enumerate(rows, start=1):
            title = meta.get("title") or meta.get("source_file") or meta.get("source") or rid
            page = meta.get("page")
            print(f"  {i}. {title}{(' (p'+str(page)+')') if page else ''}  [{rid}]")
            preview = (text or "").strip().replace("\n", " ")
            print(f"     └─ {preview[:140]}{'…' if len(preview) > 140 else ''}")

    print("────────────────────────────────────────────────────────────────────")
    if len(ctx) == 0 or len(rows) == 0:
        logging.warning("⚠️ Retrieval returned no context. Check ingestion, persist path, or embeddings.")

    # Optional: print a tiny slice of context for sanity
    print("\nCTX PREVIEW:")
    print(ctx[:800] + ("…" if len(ctx) > 800 else ""))

if __name__ == "__main__":
    # If you’re on Windows and need Poppler/Tesseract for OCR ingestion,
    # set POPPLER_PATH / ensure tesseract.exe is in PATH before ingesting.
    main()
