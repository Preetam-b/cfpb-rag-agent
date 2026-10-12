from llm import ask_llm_json
from retrieval import search_all_buckets
from web_fallback import web_search_fallback
MAX_RETRIES=1

def evaluate_relevance(complaint_text,retrieved_context):
    all_docs=(
        retrieved_context["regulatory_docs"]
        +retrieved_context["complaint_handling_guidance"]+
        retrieved_context["similar_historical_complaints"]
    )
    combined_text="\n---\n".join(all_docs)
    prompt=(
        "You are STRICTLY judging whether retrieved documents are relevant to a complaint.\n\n"
        "Complaint: "+complaint_text+"\n\n"
        "Retrieved documents:\n"+combined_text+"\n\n"
        "Follow thsese rules, in order:\n"
        "1. First,check the topic of the complaint(e.g., mortgage,credit card"
        "debt collection,credit reporting,retail banking).If the documents are "
        "about a different topic than the complaint , this is automatically BAD,"
        "even if there is some vague surfce-level similarity(like both involving"
        "money,company,or a dispute).\n"
        "2. Only if the topic geniuenly matches,then judge how well the specific"
        "content of the documents addresses the complaint's  details.\n"
        "3. Be strict. A document above a completely different financial product"
        "or situation is NOT relevant just because both involve consumer complaints.\n\n"
        "Reply only with JSON in this form : \n"
        '{"relevance":"good or ambiguous or bad","reason":"short explaination"}'
        )
    result=ask_llm_json(prompt)
    if result is None:
        return "ambiguous","Evaluator failed to respond , treating as ambiguous."
    relevance=result.get("relevance","ambiguous")
    reason=result.get("reason","")
    if relevance not in ("good","ambiguous","bad"):
        relevance="ambiguous"
    return relevance,reason

def rewrite_query(complaint_text,reason):
    prompt=(
    "The following complaint did not retireve relevant documents.\n"
    "Reason: "+ reason + "\n\n"
    "Complaint: "+complaint_text+"\n\n"
    "Rewrite this as a short,specific search query (a few words)"
    "that would better find relevant regulations and guidance.\n"
    "Reply only with JSON in this form:\n"
    '{"query":"the rewritten search query"}'
    )
    result=ask_llm_json(prompt)
    if result is None:
        return complaint_text
    return result.get("query",complaint_text)

def research_with_crag(complaint_text,category):
    query=complaint_text
    attempts=0
    while True:
        retrieved_context=search_all_buckets(query,category)
        relevance,reason=evaluate_relevance(complaint_text,retrieved_context)
        if relevance=="good":
            return retrieved_context,relevance,attempts
        if attempts>=MAX_RETRIES:
            web_snippets=web_search_fallback(complaint_text)
            if web_snippets:
                retrieved_context["regulatory_docs"]=web_snippets
                relevance,reason=evaluate_relevance(complaint_text,retrieved_context)
            return retrieved_context,relevance,attempts
        query=rewrite_query(complaint_text,reason)
        attempts+=1
