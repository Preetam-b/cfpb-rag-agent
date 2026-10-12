from state import make_initial_state
from graph import graph

test_complaints=[
    "My bank charged me a $5 fee I don't recognize on my statement.","bad"
]

for text in test_complaints:
    initial_state=make_initial_state(text)
    final_state=graph.invoke(initial_state)

    print("Complaint   :",text)
    print("Guardrail Passed  :",final_state["input_guardrail_passed"])
    print("Category          :",final_state.get("category"))
    print("Risk Assessment   :",final_state.get("risk_assessment"))
