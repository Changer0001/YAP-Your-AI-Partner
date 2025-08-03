from transformers import AutoTokenizer
from sentencepiece import SentencePieceProcessor
from pathlib import Path

# ✅ Use the exact tokenizer that vLLM uses for mistralai/Mistral-7B
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.3")


sp = SentencePieceProcessor()
model_path = Path(__file__).parent / "tokenizer_assets" / "tokenizer.model"
sp.load(str(model_path.resolve()))  # Make sure this is the same tokenizer used by vLLM

def count_tokens(text: str) -> int:
    return len(sp.encode(text, out_type=str))


def trim_messages_by_tokens(messages, max_tokens: int, reserved_completion: int = 300):
    """
    Trim message list to fit within token limits.
    Always includes the system message (assumed to be first).
    """
    if not messages:
        return []

    # Always include the system message first
    system_msg = messages[0]
    total = count_tokens(system_msg["content"])
    trimmed = [system_msg]

    # Iterate from the latest to the oldest message (excluding system)
    for msg in reversed(messages[1:]):
        tokens = count_tokens(msg["content"])
        if total + tokens + reserved_completion > max_tokens:
            break
        trimmed.insert(1, msg)  # insert after system message
        total += tokens

    return trimmed


def trim_chunks_by_tokens(chunks: list[str], max_tokens: int) -> list[str]:
    """
    Trim document chunks (used for RAG) based on max token count.
    """
    trimmed = []
    total = 0
    for chunk in chunks:
        tokens = count_tokens(chunk)
        if total + tokens > max_tokens:
            break
        trimmed.append(chunk)
        total += tokens
    return trimmed
