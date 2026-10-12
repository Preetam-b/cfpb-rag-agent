from dotenv import load_dotenv
load_dotenv()
import os
key = os.getenv("GROQ_API_KEY")
print(f"Key loaded: {bool(key)}, starts with: {key[:7] if key else None}, length: {len(key) if key else 0}")