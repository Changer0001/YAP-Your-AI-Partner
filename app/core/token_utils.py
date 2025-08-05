from transformers import AutoTokenizer
from sentencepiece import SentencePieceProcessor
from pathlib import Path

# ✅ Use the exact tokenizer that vLLM uses for mistralai/Mistral-7B
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.3")

sp = SentencePieceProcessor()
model_path = Path(__file__).parent / "tokenizer_assets" / "tokenizer.model"
sp.load(str(model_path.resolve()))  # Must match vLLM's tokenizer.model

def count_tokens(text: str) -> int:
    """Count tokens using SentencePiece as vLLM does."""
    return len(sp.encode(text))

def trim_messages_by_tokens(messages, max_tokens: int, reserved_completion: int = 300, verbose: bool = False):
    """
    Trim chat messages to fit within the model's token limit.
    Always includes the system prompt (first message).
    """
    if not messages:
        return []

    system_msg = messages[0]
    system_tokens = count_tokens(system_msg["content"])
    if system_tokens + reserved_completion > max_tokens:
        raise ValueError("System message alone exceeds token limit.")

    total = system_tokens
    trimmed = [system_msg]

    # Walk backward from most recent to oldest (excluding system)
    for msg in reversed(messages[1:]):
        tokens = count_tokens(msg["content"])
        if total + tokens + reserved_completion > max_tokens:
            break
        trimmed.insert(1, msg)
        total += tokens

    if verbose:
        print(f"[trim_messages_by_tokens] Final tokens: {total}, messages kept: {len(trimmed)}")

    return trimmed

def trim_chunks_by_tokens(chunks: list[str], max_tokens: int, verbose: bool = False) -> list[str]:
    """
    Trim document chunks for RAG based on token limit.
    """
    trimmed = []
    total = 0
    for chunk in chunks:
        tokens = count_tokens(chunk)
        if total + tokens > max_tokens:
            break
        trimmed.append(chunk)
        total += tokens

    if verbose:
        print(f"[trim_chunks_by_tokens] Final tokens: {total}, chunks kept: {len(trimmed)}")

    return trimmed

def allocate_token_budget(messages, doc_chunks, max_total_tokens=4096, reserved_completion=300, verbose=False):
    """
    Dynamically trims both chat messages and document context to fit within total context limit.
    """
    trimmed_messages = trim_messages_by_tokens(messages, max_total_tokens, reserved_completion, verbose=verbose)
    msg_token_total = sum(count_tokens(msg["content"]) for msg in trimmed_messages)
    
    available_doc_tokens = max_total_tokens - msg_token_total - reserved_completion
    trimmed_docs = trim_chunks_by_tokens(doc_chunks, max_tokens=available_doc_tokens, verbose=verbose)

    if verbose:
        print(f"[allocate_token_budget] Tokens used by messages: {msg_token_total}, available for docs: {available_doc_tokens}")

    return trimmed_messages, trimmed_docs
