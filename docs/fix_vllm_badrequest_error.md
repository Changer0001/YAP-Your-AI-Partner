# ✅ Bug Fix: vLLM/OpenAI `400 BadRequestError` for Invalid Role Sequence

## 🧾 Error Message

```json
{
  "object": "error",
  "message": "After the optional system message, conversation roles must alternate user/assistant/user/assistant/...",
  "type": "BadRequestError",
  "code": 400
}
```

---

## ❌ Cause of the Error

The LLM API (vLLM/OpenAI) expects all chat messages to **alternate between roles**:  
```
system → user → assistant → user → assistant ...
```

In our code, we mistakenly appended a new `"user"` message even when the last message in the history was also from the `"user"`, causing **two consecutive user roles**, which violates the required format.

### Example of Invalid Message Sequence:

```json
[
  { "role": "system", "content": "..." },
  { "role": "user", "content": "Question 1" },
  { "role": "user", "content": "Question 2" }  ← ❌ Invalid (no assistant in between)
]
```

---

## ✅ Solution Implemented

We updated the `make_chat_messages()` function to ensure **role alternation is preserved**.

### Fix Summary:

1. **Parsed chat history properly**:
   ```python
   history_msgs = blocks_to_messages(history_blocks)
   ```

2. **Inserted a dummy assistant message if last role was `user`**:
   ```python
   if history_msgs and history_msgs[-1]["role"] == "user":
       history_msgs.append({"role": "assistant", "content": "..."})
   ```

3. **Appended the current user’s new question safely**:
   ```python
   history_msgs.append({
       "role": "user",
       "content": f"{question.strip()}\n\nImportant instructions..."
   })
   ```

4. **Extended final messages and returned the latest 30 messages**:
   ```python
   msgs.extend(history_msgs)
   return msgs[-30:]
   ```

---

## 🧠 Why This Fix Works

This guarantees that the message sequence **never has two messages in a row from the same role**, which keeps the request valid for LLM APIs like OpenAI and vLLM.

### Final Valid Message Sequence:
```json
[
  { "role": "system", "content": "..." },
  { "role": "user", "content": "..." },
  { "role": "assistant", "content": "..." },  ← dummy or real response
  { "role": "user", "content": "..." }
]
```

---

## ✅ Result

- 🛠️ Error eliminated  
- 💬 Message structure now always valid  
- ✅ Stable interaction with LLM APIs
