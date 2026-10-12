import os
import csv
REGULATIONS_FOLDER="data/regulations"
COMPLAINTS_CSV="data/complaints/complaints.csv.csv"
GUIDANCE_FOLDER="data/guidance"

CSV_CATEGORY_TO_LABEL={
    "credit_card":"Credit Card",
    "credit_reporting":"Credit Reporting",
    "debt_collection":"Debt Collection",
    "mortgages_and_loans":"Mortgages and Loans",
    "retail_banking":"Retail Banking"
}
COMPLAINTS_PER_CATEGORY=50

def extract_category_from_text(text):
    for line in text.splitlines():
        if line.startswith("Category:"):
            return line.replace("Category:","").strip()
    return "Unknown"

def load_text_folder(folder_path):
    documents=[]
    for filename in os.listdir(folder_path):
        if not filename.endswith(".txt"):
            continue
        file_path=os.path.join(folder_path,filename)
        with open(file_path,"r",encoding="utf-8") as f:
            text=f.read()
        category=extract_category_from_text(text)
        documents.append({
            "text":text,
            "source":filename,
            "category":category
        })
    return documents

def load_sample_complaints():
    counts={}
    samples=[]
    with open(COMPLAINTS_CSV,"r",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        for row in reader:
            csv_category=row["product"]
            label=CSV_CATEGORY_TO_LABEL.get(csv_category)
            if label is None:
                continue
            current_count=counts.get(label,0)
            if current_count>=COMPLAINTS_PER_CATEGORY:
                continue
            samples.append({
                "text":row["narrative"],
                "category":label,
                "source":"historical_complaint"
            })
            counts[label]=current_count+1
    return samples