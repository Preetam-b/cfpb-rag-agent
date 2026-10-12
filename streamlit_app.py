import streamlit as st
import requests
import json
import html

API_BASE = "http://127.0.0.1:8000"

NODE_LABELS = {
    "input_guardrail": "Checking your complaint...",
    "classify": "Classifying complaint type...",
    "rag_research": "Researching relevant regulations...",
    "risk_agent": "Assessing risk and fraud signals...",
    "guidance_agent": "Drafting guidance...",
    "drafting_agent": "Drafting your letter...",
    "revision_loop": "Reviewing quality and compliance...",
    "own_letter_check": "Reviewing your letter...",
    "finalize_guidance": "Finalizing guidance...",
    "finalize_own_letter": "Finalizing your letter...",
    "escalation_review": "Escalating for human review...",
}

st.set_page_config(page_title="CFPB Consumer Complaint Assistant", page_icon="🏦", layout="centered")

st.markdown("""
<style>
    .stApp {
        background-color: #F4F6F9;
    }
    .main .block-container {
        max-width: 760px;
        padding-top: 2.5rem;
    }
    h1 {
        color: #0B2545;
        font-weight: 800 !important;
    }
    .subtitle {
        color: #5C6B7A;
        font-size: 1.05rem;
        margin-top: -0.8rem;
        margin-bottom: 1.8rem;
    }
    .stButton button {
        background-color: #1D4ED8;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.4rem;
        font-weight: 600;
    }
    .stButton button:hover {
        background-color: #1538A8;
        color: white;
    }
    .card {
        background-color: white;
        border-radius: 12px;
        padding: 1.5rem 1.8rem;
        box-shadow: 0 1px 4px rgba(11, 37, 69, 0.08);
        border: 1px solid #E6EAF0;
        margin-bottom: 1.2rem;
    }
    .letter-box {
        background-color: #FAFBFC;
        border: 1px solid #E6EAF0;
        border-radius: 10px;
        padding: 1.4rem 1.6rem;
        white-space: pre-wrap;
        font-family: 'Georgia', serif;
        line-height: 1.6;
        color: #1A2B3C;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.8rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }
    .badge-high { background-color: #FDE8E8; color: #C0392B; }
    .badge-low { background-color: #E6F7ED; color: #1E8449; }
</style>
""", unsafe_allow_html=True)


def stream_events(url: str, payload: dict):
    with requests.post(url, json=payload, stream=True) as response:
        if response.status_code != 200:
            yield {"type": "error", "detail": response.text}
            return
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            yield json.loads(line[len("data:"):].strip())


def run_stream(url: str, payload: dict):
    with st.status("Working on it...", expanded=True) as status:
        final_event = None
        for event in stream_events(url, payload):
            if event["type"] == "progress":
                label = NODE_LABELS.get(event["node"], event["node"])
                st.write(f"✓ {label}")
            elif event["type"] == "error":
                status.update(label="Something went wrong", state="error")
                st.error(event["detail"])
                return None
            else:
                final_event = event
        status.update(label="Done", state="complete")
    return final_event


def letter_box(text: str):
    safe_text = html.escape(text or "")
    st.markdown(f'<div class="letter-box">{safe_text}</div>', unsafe_allow_html=True)


def reset():
    for key in ("thread_id", "interrupt", "result"):
        st.session_state.pop(key, None)


st.markdown("<h1>🏦 CFPB Consumer Complaint Assistant</h1>", unsafe_allow_html=True)
st.markdown('<div class="subtitle">Get help resolving disputes with banks, lenders, and credit card issuers.</div>', unsafe_allow_html=True)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "interrupt" not in st.session_state:
    st.session_state.interrupt = None
if "result" not in st.session_state:
    st.session_state.result = None


# ---- Stage 1: no active thread yet — collect the complaint ----
if st.session_state.thread_id is None and st.session_state.result is None:
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        complaint_text = st.text_area("Describe your complaint", height=120, placeholder="e.g. Someone opened a credit card in my name without my permission.")
        submit = st.button("Submit", disabled=not complaint_text.strip())
        st.markdown('</div>', unsafe_allow_html=True)
    if submit:
        final_event = run_stream(f"{API_BASE}/complaints/stream", {"complaint_text": complaint_text})
        if final_event:
            st.session_state.thread_id = final_event["thread_id"]
            if final_event["type"] == "interrupt":
                st.session_state.interrupt = final_event["interrupt"]
            else:
                st.session_state.result = final_event["result"]
        st.rerun()


# ---- Stage 2: paused at a human checkpoint — render the right UI ----
elif st.session_state.interrupt is not None:
    interrupt = st.session_state.interrupt
    itype = interrupt.get("type")
    answer = None

    st.markdown('<div class="card">', unsafe_allow_html=True)

    if itype == "consent":
        st.subheader("How would you like to proceed?")
        st.write(f"**Complaint:** {interrupt['complaint_text']}")
        risk = interrupt.get("risk_assessment", {})
        severity = risk.get("severity", "low")
        badge_class = "badge-high" if severity == "high" else "badge-low"
        st.markdown(f'<span class="badge {badge_class}">{severity} risk</span>', unsafe_allow_html=True)
        with st.expander("Why this assessment?"):
            for reason in risk.get("reasons", []):
                st.write(f"- {reason}")
        choice = st.radio(
            interrupt["question"],
            options=["1", "2", "3"],
            format_func=lambda x: {
                "1": "Have the AI draft a formal letter",
                "2": "Get guidance instead (no letter)",
                "3": "Write my own letter (we'll review it)",
            }[x],
        )
        if st.button("Continue"):
            answer = choice

    elif itype == "own_letter_input":
        st.subheader("Write your complaint letter")
        letter = st.text_area(interrupt["question"], height=250)
        if st.button("Submit letter", disabled=not letter.strip()):
            answer = letter

    elif itype == "own_letter_revise":
        st.subheader("Your letter needs some changes")
        for line in interrupt.get("feedback", []):
            st.warning(line)
        st.caption(f"{interrupt.get('attempts_left', '?')} revision(s) left")
        letter = st.text_area(interrupt["question"], height=250)
        if st.button("Submit revision", disabled=not letter.strip()):
            answer = letter

    elif itype == "own_letter_exhausted":
        st.subheader("Your letter still doesn't pass review")
        for line in interrupt.get("feedback", []):
            st.warning(line)
        col1, col2 = st.columns(2)
        if col1.button("Send it anyway"):
            answer = "send"
        if col2.button("Let the AI draft one instead"):
            answer = "ai"

    elif itype == "final_review":
        st.subheader("Review your letter")
        letter_box(interrupt["draft_letter"])
        edited = st.text_area("Edit it, or leave blank to keep as-is", height=150)
        if st.button("Confirm"):
            answer = edited

    else:
        st.subheader(interrupt.get("question", "Input needed"))
        text = st.text_input("Your answer")
        if st.button("Submit"):
            answer = text

    st.markdown('</div>', unsafe_allow_html=True)

    if answer is not None:
        url = f"{API_BASE}/complaints/{st.session_state.thread_id}/resume/stream"
        final_event = run_stream(url, {"answer": answer})
        if final_event:
            if final_event["type"] == "interrupt":
                st.session_state.interrupt = final_event["interrupt"]
            else:
                st.session_state.interrupt = None
                st.session_state.result = final_event["result"]
        st.rerun()


# ---- Stage 3: done — show the result ----
elif st.session_state.result is not None:
    result = st.session_state.result
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if result.get("rejected"):
        st.error(f"Your complaint could not be processed. Reason: {result.get('reason')}")
    elif result.get("escalated"):
        st.warning("This complaint has been escalated for human review. A specialist will follow up with you directly.")
    elif result.get("output_type") == "guidance":
        st.subheader("Guidance")
        letter_box(result.get("final_output"))
    elif result.get("output_type") == "draft":
        st.subheader("Your complaint letter")
        letter_box(result.get("final_output"))
    else:
        letter_box(result.get("final_output"))

    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Start a new complaint"):
        reset()
        st.rerun()