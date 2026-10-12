from state import make_initial_state
from classify import classify_node
from crag import research_with_crag
from agents import risk_agent_node,guidance_agent_node,drafting_agent_node

complaint="My bank charged me a $5 fee I don't recognize on my statement."

state=make_initial_state(complaint)
state=classify_node(state)

retrrieved_context,relevance,attempts=research_with_crag(complaint,state["category"])
state["retrieved_context"]=retrrieved_context

state=risk_agent_node(state)
print("Risk assessment:",state["risk_assessment"])

state=guidance_agent_node(state)
print("\nGuidance")
print(state["guidance_text"])

state=drafting_agent_node(state)
print("\nDraft Letter")
print(state["draft_letter"])