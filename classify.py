from bert_model import predict_category
from llm import ask_llm_json
from config import LABELS,CONFIDENCE_THRESHOLD

CONFIDENCE_MAP={"high":0.9,"medium":0.7,"low":0.5}

def classify_with_llm(complaint_text,max_attempts=2):
    categories=" ,".join(LABELS)
    prompt=(
    "You are classifying a consumer financial complaint. \n"
    "Pick exactly ONE category from this list: "+categories+"\n\n"
    "Complaint: "+complaint_text+ "\n\n"
    "Reply only with JSON in this form : \n"
    '{"category":"<one category from the list>","confidence":"low or medium or high}'
    )
    for attempt in range(max_attempts):
        result=ask_llm_json(prompt)
        if result is None:
           continue

        category=result.get("category")
        level=str(result.get("confidence","")).lower()
        if category  in LABELS:
            confidence=CONFIDENCE_MAP.get(level,0.5)
            return category,confidence

    return None,None

def classify_node(state):
    text=state["complaint_text"]
    bert_category,bert_confidence=predict_category(text)

    # predict_category returns (None, 0.0) when USE_BERT=false (BERT not
    # loaded at all on this deploy target) -- that's treated the same as
    # "below confidence threshold", routing straight to the LLM fallback.
    if bert_category is not None and bert_confidence>=CONFIDENCE_THRESHOLD:
        state["category"]=bert_category
        state["confidence"]=bert_confidence
        state["classifier_used"]="bert"
        return state

    llm_category,llm_confidence=classify_with_llm(text)
    if llm_category is None:
        if bert_category is not None:
            state["category"]=bert_category
            state["confidence"]=bert_confidence
            state["classifier_used"]="bert"
        else:
            # BERT unavailable on this deploy AND the LLM fallback failed
            # (e.g. Groq hiccup) -- last-resort default rather than crashing.
            state["category"]=LABELS[0]
            state["confidence"]=0.0
            state["classifier_used"]="failed_defaulted"
    else:
        state["category"]=llm_category
        state["confidence"]=llm_confidence
        state["classifier_used"]="llm_fallback"
    return state