from retrieval import search_all_buckets
complaint="My credit card company charged me for a purchase I never made and won't refund it."
category="Credit Card"

results=search_all_buckets(complaint,category)
print("=== Regulatory docs ===")
for doc in results["regulatory_docs"]:
    print("-",doc[:150],"...")

print("\n=== Complaint-handling guidance ===")
for doc in results["complaint_handling_guidance"]:
    print("-",doc[:150],"...")

print("\n=== Similar historical complaints ===")
for doc in results["similar_historical_complaints"]:
    print("-",doc[:150],"...")