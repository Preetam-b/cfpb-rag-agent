from langgraph.graph import StateGraph,START,END
from  typing import Literal
from state import ComplaintState
from guardrails import input_guardrail_node
from classify import classify_node
from crag import research_with_crag
from agents import risk_agent_node,guidance_agent_node,drafting_agent_node
from revision_loop import run_revision_loop
from own_letter import (read_multiline,own_letter_input_node,own_letter_check_node
                        ,own_letter_check_router,own_letter_revise_node,own_letter_exhausted_node
                        ,own_letter_exhausted_router,finalize_own_letter_node)
from langgraph.types import interrupt,Command
from langgraph.checkpoint.memory import MemorySaver

def rag_research_node(state):
    retrieved_context,relevance,attempts=research_with_crag(
        state["complaint_text"],state["category"]
    )
    state["retrieved_context"]=retrieved_context
    return state

def hitl_consent_node(state):
    answer=interrupt({
        "type":"consent",
        "complaint_text":state["complaint_text"],
        "risk_assessment":state["risk_assessment"],
        "question":"How would you like to proceed ? "
        "1= AI draft,"
        "2=guidance ,"
        "3=  write own letter"
    })

    if answer == "1":
        state["consent_choice"]="draft"
    elif answer == "3":
        state["consent_choice"]="own"
    else:
        state["consent_choice"]="guidance"
    return state

def input_guardrail_router(state):
    if state["input_guardrail_passed"]:
        return "continue"
    else:
        return "reject"

def risk_split_router(state):
    if state["risk_assessment"]["severity"]=="low":
        return "low_risk"
    else:
        return "high_risk"

def consnent_router(state):
    choice=state.get("consent_choice")
    if choice =="draft":
        return "draft"
    elif choice == "own":
        return "own"
    else:
        return "guidance"

def finalize_guidance_node(state):
    state["final_output"]=state["guidance_text"]
    return state

def hitl_final_review_node(state):
    edited=interrupt({
        "type":"final_review",
        "draft_letter":state["draft_letter"],
        "question":"Keep this letter as it is (or)  send a replacement ? (empty = keep as it is)"
    })
    if edited and edited.strip():
        state["draft_letter"]=edited
    state["final_output"]=state["draft_letter"]
    return state

def  escalation_node(state):
    print("\n ESCALATED TO HUMAN REVIEW")
    print("Complaint :",state["complaint_text"])
    print("Last critic feedback :",state["critic_feedback"])
    print("Last guardrail feedback :",state["output_guardrail_feedback"])
    print("This complaint could not be automatically resolved within the revision limit.")

    state["final_output"]=(
        "This complaint has been escalated for manual review."
        "Automated drafting did not meet quality standards after "
        + str(state["revision_count"])+" attempts"
    )
    return state

def post_revision_router(state):
    if state["escalated"]:
        return "escalated"
    elif state["output_type"]=="guidance":
        return "finalize_guidance"
    else:
        return "hitl_final_review"

builder=StateGraph(ComplaintState)
builder.add_node("input_guardrail",input_guardrail_node)
builder.add_node("classify",classify_node)
builder.add_node("rag_research",rag_research_node)
builder.add_node("risk_agent",risk_agent_node)
builder.add_node("hitl_consent",hitl_consent_node)
builder.add_node("own_letter_input",own_letter_input_node)
builder.add_node("own_letter_check",own_letter_check_node)
builder.add_node("own_letter_revise",own_letter_revise_node)
builder.add_node("own_letter_exhausted",own_letter_exhausted_node)
builder.add_node("finalize_own_letter",finalize_own_letter_node)
builder.add_node("guidance_agent",guidance_agent_node)
builder.add_node("drafting_agent",drafting_agent_node)
builder.add_node("revision_loop",run_revision_loop)
builder.add_node("finalize_guidance",finalize_guidance_node)
builder.add_node("hitl_final_review",hitl_final_review_node)
builder.add_node("escalation_review",escalation_node)

builder.add_edge(START,"input_guardrail")
builder.add_conditional_edges(
    "input_guardrail",input_guardrail_router,{"continue":"classify","reject":END}
)
builder.add_edge("classify","rag_research")
builder.add_edge("rag_research","risk_agent")
builder.add_conditional_edges(
    "risk_agent",risk_split_router,{"low_risk":"guidance_agent","high_risk":"hitl_consent"}
)
builder.add_conditional_edges(
    "hitl_consent",consnent_router,{"draft":"drafting_agent","guidance":"guidance_agent","own":"own_letter_input"}
)
builder.add_edge("own_letter_input","own_letter_check")
builder.add_conditional_edges("own_letter_check",own_letter_check_router,{
    "passed":"finalize_own_letter",
    "retry":"own_letter_revise",
    "exhausted":"own_letter_exhausted"
})
builder.add_edge("own_letter_revise","own_letter_check")
builder.add_conditional_edges("own_letter_exhausted",own_letter_exhausted_router,{
    "send":"finalize_own_letter",
    "ai_takeover":"drafting_agent"
})
builder.add_edge("finalize_own_letter",END)
builder.add_edge("guidance_agent","revision_loop")
builder.add_edge("drafting_agent","revision_loop")
builder.add_conditional_edges("revision_loop",
                              post_revision_router,{
                                  "escalated":"escalation_review",
                                  "finalize_guidance":"finalize_guidance",
                                  "hitl_final_review":"hitl_final_review"
                              })
builder.add_edge("finalize_guidance",END)
builder.add_edge("hitl_final_review",END)
builder.add_edge("escalation_review",END)

checkpointer=MemorySaver()
graph=builder.compile(checkpointer=checkpointer)

