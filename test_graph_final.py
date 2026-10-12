from state import make_initial_state
from graph import graph

state1=make_initial_state("My bank charged me a $5 fee I don't recognize on my statement.")
final1=graph.invoke(state1)
print("Output type  :",final1.get("output_type"))
print("Escalated    :",final1.get("escalated"))
print("\nFinal output :\n",final1.get("final_output"))

state2=make_initial_state("Someone opened a credit card in my name without my permission.")
final2=graph.invoke(state2)
print("Output type  :",final2.get("output_type"))
print("Escalated    :",final2.get("escalated"))
print("\nFinal output  :\n",final2.get("final_output"))