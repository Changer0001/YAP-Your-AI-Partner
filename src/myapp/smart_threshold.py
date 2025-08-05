# myapp/smart_threshold.py

def get_dynamic_threshold(query: str) -> float:
    tokens = len(query.strip().split())
    if tokens <= 3:
        return 1.0
    elif tokens >= 12:
        return 1.8
    return 1.5
