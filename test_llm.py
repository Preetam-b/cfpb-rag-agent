from llm import ask_llm,ask_llm_json

print(ask_llm("Say hello in one short senetnce."))
result=ask_llm_json('Reply with JSON like {"ok":true,"word":"hi}')
print(result)
print(type(result))