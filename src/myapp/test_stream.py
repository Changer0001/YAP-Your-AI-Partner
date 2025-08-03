print("Running test_stream.py...")
import requests
print("Import successful.")

url = "http://localhost:8000/ask/stream"
print(f"URL set to: {url}")
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0MSIsImV4cCI6MTc1NDIwOTYzMH0.aAuRwvJqCG42I24R1SRdlLh5nmcHH3sk4Pk3031FR7E",
}
print("Headers set with Authorization token.")
print("Preparing payload...")

payload = {
    "question": "our refund policy",
    "history": [
        {"role": "system", "content": "You are a helpful assistant for a business. Use chat history and document context."}
    ]
}
print("Payload prepared:", payload)

print("Sending POST request to the server...")
response = requests.post(url, headers=headers, json=payload, stream=True)
print("Request sent. Waiting for response...")
for line in response.iter_lines():
    if line:
        decoded = line.decode("utf-8")
        print("🔹 Response Line:", decoded)
print("Request completed.")
print("Test completed successfully.")