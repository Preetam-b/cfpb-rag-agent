from state import make_initial_state
from crag import research_with_crag
from classify import classify_node
from agents import risk_agent_node

test_complaints=["Someone opened a credit card in my name without my permission and I've never even applied for it.",
                 "My bank charged me a $5 fee I don't recognize on my statement"]
for text in test_complaints:
    state=make_initial_state(text)
    state=classify_node(state)
    retrieved_context,relevance,attempts=research_with_crag(text,state["category"])
    state["retrieved_context"]=retrieved_context
    state=risk_agent_node(state)

    print("Complaint :",text)
    print("Category  :",state["category"])
    print("Risk      :",state["risk_assessment"])