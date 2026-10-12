from state import make_initial_state
from classify import classify_node
from crag import research_with_crag
from agents import risk_agent_node,guidance_agent_node,critic_node

complaint="My bank has charged me a $5 fee I don't recognise on my statement"

state=make_initial_state(complaint)
state=classify_node(state)

retrieved_context,relevance,attempts=research_with_crag(complaint,state["category"])
state["retrieved_context"]=retrieved_context

state=risk_agent_node(state)
state=guidance_agent_node(state)
state=critic_node(state)

print("GUIDANCE TEXT\n")
print(state["guidance_text"])

print("CRITIC REVIEW\n")
print("Passed : ",state["critic_passed"])
print("feedback  :",state["critic_feedback"])