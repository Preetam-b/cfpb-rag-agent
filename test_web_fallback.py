from web_fallback import web_serach_fallback

results=web_serach_fallback("mortgage servicer error resolution foreclosure")
print("Results found:",len(results))
for snippet in results:
    print("-",snippet[:200],"...")
    