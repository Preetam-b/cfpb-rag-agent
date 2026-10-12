from agents import guidance_agent_node,drafting_agent_node,critic_node
from guardrails import output_guardrail_node
from config import MAX_REVISIONS

def run_revision_loop(state):
    while True:
        state=critic_node(state)
        state=output_guardrail_node(state)

        critic_ok= state["critic_passed"]
        guardrail_ok=state["output_guardrail_passed"]

        if critic_ok and guardrail_ok:
            return state
        if state["revision_count"]>=MAX_REVISIONS:
            state["escalated"]=True
            return state

        feedback_parts=[]
        if not critic_ok:
            feedback_parts.append(state["critic_feedback"])
        if not guardrail_ok:
            feedback_parts.append(state["output_guardrail_feedback"])
        combined_feedback=" ".join(feedback_parts)

        state["revision_count"]+=1

        if state["output_type"]=="guidance":
            state=guidance_agent_node(state,feedback=combined_feedback)
        else:
            state=drafting_agent_node(state,feedback=combined_feedback)
            