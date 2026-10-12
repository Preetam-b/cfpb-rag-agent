from state import make_initial_state
from graph import graph


print("=== TEST 1: Low-risk complaint ===")
state1 = make_initial_state("My bank charged me a $5 fee I don't recognize on my statement.")
final1 = graph.invoke(state1)
print("Output type:", final1.get("output_type"))
print("Escalated  :", final1.get("escalated"))
print("Critic pass:", final1.get("critic_passed"))
print("Critic feedback:", final1.get("critic_feedback"))
print("Guardrail pass:", final1.get("output_guardrail_passed"))
print("Guardrail feedback:", final1.get("output_guardrail_feedback"))
print("Final guidance text:", final1.get("guidance_text"))
print("Retrieved context:", final1.get("retrieved_context"))

print("\n")

state2 = make_initial_state("Someone opened a credit card in my name without my permission.")
final2 = graph.invoke(state2)
print("Output type:", final2.get("output_type"))
print("Escalated  :", final2.get("escalated"))
print("Critic pass:", final2.get("critic_passed"))