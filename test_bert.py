from bert_model import predict_category

test_complaints=["I noticed a charge of $250 on my credit cardstatement for a purchase I never made , and the bank refuses to remove it!",
                "The credit bureau shows an account on my credit report that doesn't belong to me , and its lowering my score.",
                "A debt colector keeps calling me everyday about a debt that I already paid off in 2019, and they will not stop.",
                "My mortgage servicer lost my monthly payment and then charged me a late fee even though I paid on time.",
                "My checking account was overdrawn because of a fee the bank added without telling me, and they will not refund it."
                ]

for text in test_complaints:
    category,confidence=predict_category(text)
    print("-----")
    print("Complaint :",text)
    print("Category :",category)
    print("Confidence :",round(confidence,3))
