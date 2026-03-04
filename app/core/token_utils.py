# app/core/token_utils.py
from transformers import AutoTokenizer

# IMPORTANT:
# Use the same model family you're serving on RunPod.
# If you're now serving Qwen2.5, set it to Qwen.
# If you’re still serving Mistral, keep Mistral.
DEFAULT_TOKENIZER_MODEL = "Qwen/Qwen2.5-7B-Instruct"  # <-- change if needed

_tokenizer = None

def get_tokenizer(model_name: str = DEFAULT_TOKENIZER_MODEL):
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    return _tokenizer

def count_tokens(text: str, model_name: str = DEFAULT_TOKENIZER_MODEL) -> int:
    """Count tokens using the HF tokenizer (good match for vLLM / OpenAI-style serving)."""
    tok = get_tokenizer(model_name)
    return len(tok.encode(text))

def trim_messages_by_tokens(messages, max_tokens: int, reserved_completion: int = 300, verbose: bool = False):
    if not messages:
        return []

    system_msg = messages[0]
    system_tokens = count_tokens(system_msg["content"])
    if system_tokens + reserved_completion > max_tokens:
        raise ValueError("System message alone exceeds token limit.")

    total = system_tokens
    trimmed = [system_msg]

    for msg in reversed(messages[1:]):
        tokens = count_tokens(msg.get("content", ""))
        if total + tokens + reserved_completion > max_tokens:
            break
        trimmed.insert(1, msg)
        total += tokens

    if verbose:
        print(f"[trim_messages_by_tokens] Final tokens: {total}, messages kept: {len(trimmed)}")

    return trimmed

def trim_chunks_by_tokens(chunks: list[str], max_tokens: int, verbose: bool = False) -> list[str]:
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
    trimmed_messages = trim_messages_by_tokens(
        messages, max_total_tokens, reserved_completion, verbose=verbose
    )
    msg_token_total = sum(count_tokens(msg.get("content", "")) for msg in trimmed_messages)

    available_doc_tokens = max_total_tokens - msg_token_total - reserved_completion
    if available_doc_tokens < 0:
        available_doc_tokens = 0

    trimmed_docs = trim_chunks_by_tokens(doc_chunks, max_tokens=available_doc_tokens, verbose=verbose)

    if verbose:
        print(f"[allocate_token_budget] Tokens used by messages: {msg_token_total}, available for docs: {available_doc_tokens}")

    return trimmed_messages, trimmed_docs