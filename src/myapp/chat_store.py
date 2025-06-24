import os
import json

CHAT_HISTORY_FILE = "data/chat_history.json"

def load_chat_history():
    if not os.path.exists(CHAT_HISTORY_FILE):
        return {}
    with open(CHAT_HISTORY_FILE, "r") as f:
        return json.load(f)

def save_chat_history(username: str, question: str, answer: str):
    history = load_chat_history()
    if username not in history:
        history[username] = []
    history[username].append({"question": question, "answer": answer})
    with open(CHAT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def get_user_history(username: str):
    history = load_chat_history()
    return history.get(username, [])
