import requests
import json
url="http://127.0.0.1:8000/complaints/stream"
payload={"complaint_text":"Someone opened a credit card in my name without my permission."}

with requests.post(url,json=payload,stream=True) as response:
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            data_str=line[len("data:"):].strip()
            event=json.loads(data_str)
            print(event)