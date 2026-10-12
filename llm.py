import json
import ollama
import os
from groq import Groq

from config import OLLAMA_MODEL,GROQ_MODEL

LLM_PROVIDER=os.getenv("LLM_PROVIDER","ollama")
_groq_client=Groq(api_key=os.getenv("GROQ_API_KEY")) if LLM_PROVIDER =="groq" else None

def _chat(prompt,json_mode=False):
    if LLM_PROVIDER=="groq":
        kwargs={
            "model":GROQ_MODEL,
            "messages":[{"role":"user","content":prompt}]
        }
        if json_mode:
            kwargs["response_format"]={"type":"json_object"}
            kwargs["temperature"]=0
        response=_groq_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    kwargs={
        "model":OLLAMA_MODEL,
        "messages":[{"role":"user","content":prompt}]
    }
    if json_mode:
        kwargs["format"]="json"
        kwargs["options"]={"temperature":0}
    response=ollama.chat(**kwargs)
    return response["message"]["content"]

def ask_llm(prompt):
    return _chat(prompt,json_mode=False)

def ask_llm_json(prompt):
    text=_chat(prompt,json_mode=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None