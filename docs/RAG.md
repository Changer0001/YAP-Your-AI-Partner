# RAG Pipeline

Retrieval quality matters more than model size. Qwen 2.5 3B is fine **if** it receives high-quality,
relevant, well-attributed context.

```
question → intent router → (knowledge query)
  → embed (nomic-embed-text, local)
  → metadata filter (site / type / date / source)      ← provenance-aware
  → semantic search (Chroma, cosine)
  → similarity threshold (drop weak matches)
  → dedup + rank
  → context construction (bounded by MAX_CONTEXT_CHARS)
  → Qwen 2.5 3B (temperature 0.1, grounded prompt)
  → answer + citations
```

## Configurable parameters (`.env`)
`CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K`, `SIMILARITY_THRESHOLD`, `MAX_CONTEXT_CHARS`.

## Grounding & hallucination control
- If retrieval returns nothing above threshold, the app answers **"I couldn't find this information
  in the indexed documentation."** *without* calling the model.
- The system prompt forbids outside knowledge, forbids inventing IPs/VLANs/device names/procedures,
  and treats retrieved text as **untrusted data** (prompt-injection defence).
- Answers cite sources by `[n]`; the UI shows filename + page/section + similarity, and only sources
  that were actually retrieved are shown.

## Provenance carried end-to-end
Every chunk keeps: `source_type`, `filename`, `page`, `section`, `site`, `doc_type`, plus dates and
`version` where known — so citations are precise and current-vs-historical reasoning is possible.

## Roadmap (design in `Local-IT-Copilot-Architecture.md` / `Enterprise-Knowledge-Architecture.md`)
- **Hybrid search** (BM25 + dense) for exact tokens (`VLAN 30`, `SW-01`, IPs).
- **Reranking** (bge-reranker) for precision.
- **Temporal / source-authority** ranking — prefer current & authoritative; surface **conflicts**
  ("older SOP says VLAN 20, recent email says VLAN 30 — verify") instead of silently choosing.
- **Deterministic config parsing** (ciscoconfparse2 / Batfish) for config facts — not the LLM.
