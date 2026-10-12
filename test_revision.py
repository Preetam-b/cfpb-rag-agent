from state import make_initial_state
from classify import classify_node
from crag import research_with_crag
from agents import risk_agent_node,guidance_agent_node
from revision_loop import run_revison_loop

complaint="My bank has charged me a $5 fee I don't recognize on my statement"

state=make_initial_state(complaint)
state=classify_node(state)

retrieved_context,relevance,attempts=research_with_crag(complaint,state["category"])
state["retrieved_context"]=retrieved_context

state=risk_agent_node(state)
state=guidance_agent_node(state)
state=run_revison_loop(state)

print("Revision count:  ",state["revision_count"])
print("Escalated     : ",state["escalated"])
print("Critic Passed : ",state["critic_passed"])
print("Guardrail pass : ",state["output_guardrail_passed"])
print("\n FINAL GUIDANCE TEXT ")
print(state["guidance_text"])