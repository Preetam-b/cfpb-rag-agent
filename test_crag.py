from crag import research_with_crag

#complaint="My credit card company charged me for a purchase I never made and won't refund it."
complaint=("My mortgage servicer lost my monthly payment and then charged me "
    "a late fee even though I paid on time, and now they are threatening foreclosure."
)
#category="Credit Card"
wrong_category="Retail Banking" 
retrieved_context,relevance,attempts=research_with_crag(complaint,wrong_category)
print("Final relevance:",relevance)
print("Attempts used :",attempts)
print("=== Regulatory docs ===")
for doc in retrieved_context["regulatory_docs"]:
    print("-",doc[:150],"...")
