# myapp/intent_classifier.py
from retriever.embed import embedding_model
import numpy as np

INTENT_EXAMPLES = {
    "greeting": ["hi", "hello", "hey there", "good morning"],
    "goodbye": ["bye", "see you", "take care"],
    "thank_you": ["thanks", "thank you", "appreciate it"],
    "refund_query": ["what is your refund policy", "how can I get a refund", "return item"],
}

# Precompute embeddings for known intent examples
intent_embeddings = {
    label: [embedding_model.encode(q) for q in queries]
    for label, queries in INTENT_EXAMPLES.items()
}

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def classify_intent(user_query: str, threshold=0.85) -> str:
    user_embedding = embedding_model.encode(user_query)
    scores = {}

    for label, embs in intent_embeddings.items():
        max_score = max(cosine_sim(user_embedding, e) for e in embs)
        scores[label] = max_score

    best_label, best_score = max(scores.items(), key=lambda x: x[1])
    return best_label if best_score >= threshold else "unknown"
