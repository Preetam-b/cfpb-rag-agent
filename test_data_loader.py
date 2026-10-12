from data_loader import load_text_folder,load_sample_complaints,REGULATIONS_FOLDER,GUIDANCE_FOLDER

regulations=load_text_folder(REGULATIONS_FOLDER)
guidance=load_text_folder(GUIDANCE_FOLDER)
complaints=load_sample_complaints()

print("Regulations loaded :",len(regulations))
print("Guidance loaded  :",len(guidance))
print("Complaints loaded :",len(complaints))

print(complaints[0]["category"])
print(complaints[0]["text"][:150],"...")
print("\n")
print(regulations[0]["source"])
print(regulations[0]["text"][:150],"...")
print("\n")
from collections import Counter
category_counts=Counter(c["category"] for c in complaints)
for category,count in category_counts.items():
    print(category,":",count)