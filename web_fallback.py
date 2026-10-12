from ddgs import DDGS

def web_search_fallback(query,max_results=3):
    scoped_query=query+" site:consumerfinance.gov"
    snippets=[]
    try:
        with DDGS() as ddgs:
            results=ddgs.text(scoped_query,max_results=max_results)
            for result in results:
                snippet=result.get("body","")
                if snippet:
                    snippets.append(snippet)
    except Exception:
        pass
    return snippets