from state import make_initial_state
from classify import classify_node

test_complaints=[
    "A deebt collector keeps calling me everyday about a debt that I already paid off in 2025, and they will not stop. ",
    "My credit card compamy reported a late payment to the credit bureaus even though I paid on time, and now my mortgage application was denied.",
    "I have a problem with my account and nobody at the bank is helping me."
    ]

for text in test_complaints:
    state=make_initial_state(text)
    state=classify_node(state)

    print("\n")
    print("Complaint   :",text)
    print("Category    :",state["category"])
    print("confidence  :",round(state["confidence"],3))
    print("Classifier used:",state["classifier_used"])