import re
import os
from config import BERT_MODEL_PATH,LABELS,MAX_LENGTH,USE_CLEANING

# On a memory-constrained deploy target (e.g. Render free tier, 512MB RAM),
# set USE_BERT=false to skip loading torch/transformers + the BERT weights
# entirely and classify purely via the Groq LLM fallback path that already
# exists in classify.py. Defaults to true so local dev is unchanged.
USE_BERT=os.getenv("USE_BERT","true").lower()=="true"

tokenizer=None
model=None

if USE_BERT:
    import torch
    from transformers import BertTokenizerFast,BertForSequenceClassification

    print("Loading BERT model ...")
    tokenizer=BertTokenizerFast.from_pretrained(BERT_MODEL_PATH)
    model=BertForSequenceClassification.from_pretrained(BERT_MODEL_PATH)
    model.eval()
    print("BERT model loaded !")

def clean_text(text):
    text=str(text).lower()
    text=re.sub(r"x{2,}","",text)
    text=re.sub(r"[^a-zA-Z\s]","",text)
    text=re.sub(r"\s+"," ",text).strip()
    return text

def predict_category(text,use_cleaning=USE_CLEANING):
    if not USE_BERT:
        return None,0.0

    if use_cleaning:
        text=clean_text(text)

    inputs=tokenizer(text,truncation=True,max_length=MAX_LENGTH,return_tensors="pt")

    with torch.no_grad():
        logits=model(**inputs).logits
    probs=torch.softmax(logits,dim=1)[0]
    predicted_idx=probs.argmax().item()
    category=LABELS[predicted_idx]
    confidence=probs[predicted_idx].item()

    return category,confidence