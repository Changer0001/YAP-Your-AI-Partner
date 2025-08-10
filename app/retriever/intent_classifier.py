from app.retriever.embed import embedding_model
import numpy as np, re

INTENT_EXAMPLES = {
    "greeting": ["hi", "hello", "hey there", "good morning", "hi there"],
    "goodbye": ["bye", "see you", "take care", "good night"],
    "thank_you": ["thanks", "thank you", "appreciate it"],
    "refund_query": ["what is your refund policy", "how can I get a refund", "return item"],
}

def _embed_norm(text: str) -> np.ndarray:
    v = np.asarray(embedding_model.encode(text), dtype=np.float32)
    n = np.linalg.norm(v) + 1e-9
    return v / n

intent_embeddings = {k: [_embed_norm(q) for q in v] for k, v in INTENT_EXAMPLES.items()}

_GREETING_RX = re.compile(r"\b(hi|hey|hello|good (morning|afternoon|evening))\b", re.I)
_GOODBYE_RX  = re.compile(r"\b(bye|good night|see you|take care)\b", re.I)
_THANKS_RX   = re.compile(r"\b(thanks|thank you|appreciate(d)?|much appreciated)\b", re.I)

def classify_intent(user_query: str, threshold: float = 0.70) -> str:
    q = (user_query or "").strip()
    if not q:
        return "unknown"
    # lexical fast path
    if _GREETING_RX.search(q): return "greeting"
    if _GOODBYE_RX.search(q):  return "goodbye"
    if _THANKS_RX.search(q):   return "thank_you"

    qv = _embed_norm(q)
    best_label, best_score = "unknown", -1.0
    for label, embs in intent_embeddings.items():
        s = max(float(np.dot(qv, e)) for e in embs)  # cos on unit vectors
        if s > best_score:
            best_label, best_score = label, s
    return best_label if best_score >= threshold else "unknown"
