from config import MAX_REVISIONS
from agents import critic_node
from guardrails import output_guardrail_node
from langgraph.types import interrupt

def read_multiline(prompt_line="> "):
    """
    If the first line is blank, returns "" immediately (used as a
    'keep as-is' signal). Otherwise, keeps reading lines — including
    blank lines between paragraphs — until the user types END on its own line.
    """
    first = input(prompt_line)
    if not first.strip():
        return ""
    lines = [first]
    while True:
        line = input(prompt_line)
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)

def _collect_feedback(state):
    feedback=[]
    if not state["critic_passed"]:
        feedback.append("Quality review: "+state["critic_feedback"])
    if not state["output_guardrail_passed"]:
        feedback.append("Complaince review: "+state["output_guardrail_feedback"])
    return feedback

def own_letter_input_node(state):
    letter_text=interrupt({
        "type":"own_letter_input",
        "question":"Type your complaint letter."
    })
    state["draft_letter"]=(letter_text or "").strip()
    state["output_type"]="draft"
    state["own_letter_attempts"]=0
    return state

def own_letter_check_node(state):
    critic_node(state)
    output_guardrail_node(state)
    if not (state["critic_passed"] and state["output_guardrail_passed"]):
        state["own_letter_attempts"]=state.get("own_letter_attempts",0)
    return state

def own_letter_check_router(state):
    if state["critic_passed"] and state["output_guardrail_passed"]:
        return "passed"
    if state["own_letter_attempts"]>=MAX_REVISIONS:
        return "exhausted"
    return "retry"

def own_letter_revise_node(state):
    feedback=_collect_feedback(state)
    attempts_left=MAX_REVISIONS-state["own_letter_attempts"]
    new_text=interrupt({
        "type":"own_letter_revise",
        "feedback":feedback,
        "attempts_left":attempts_left,
        "question":"Your letter needs some changes . Type your revised letter."
    })
    if new_text and new_text.strip():
        state["draft_letter"]=new_text.strip()
    return state

def own_letter_exhausted_node(state):
    feedback=_collect_feedback(state)
    choice=interrupt({
        "type":"own_letter_exhausted",
        "feedback":feedback,
        "question":"Your letter still doesn't pass review. Send it anyway,"
        "or let the AI draft a letter instead? (send/ai)"
    })
    state["_own_letter_choice"]=(choice or "").strip().lower()
    return state

def own_letter_exhausted_router(state):
    if state.get("_own_letter_choice")=="ai":
        return "ai_takeover"
    return "send"

def finalize_own_letter_node(state):
    state["final_output"]=state["draft_letter"]
    state["escalted"]=False
    return state