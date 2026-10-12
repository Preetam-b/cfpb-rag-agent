import requests
import json

thread_id = "cce08f1d-7e46-4fb1-8ba9-e5550330bab5"  # from your last response
url = f"http://127.0.0.1:8000/complaints/{thread_id}/resume/stream"
payload = {"answer": "2"}  # pick guidance path for a quick full-completion test

with requests.post(url, json=payload, stream=True) as response:
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            event = json.loads(line[len("data:"):].strip())
            print(event)