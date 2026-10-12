import re
import torch
from transformers import BertTokenizerFast,BertForSequenceClassification
from config import BERT_MODEL_PATH,LABELS,MAX_LENGTH,USE_CLEANING

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