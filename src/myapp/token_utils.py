# myapp/token_utils.py

import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))

def trim_messages_by_tokens(messages, max_tokens: int):
    total = 0
    trimmed = []
    for msg in reversed(messages):
        tokens = count_tokens(msg["content"])
        if total + tokens > max_tokens:
            break
        trimmed.insert(0, msg)
        total += tokens
    return trimmed

def trim_chunks_by_tokens(chunks: list[str], max_tokens: int) -> list[str]:
    trimmed = []
    total = 0
    for chunk in chunks:
        tokens = count_tokens(chunk)
        if total + tokens > max_tokens:
            break
        trimmed.append(chunk)
        total += tokens
    return trimmed
