"""
Gradio frontend for the CFPB Consumer Complaint Assistant, built for HF Spaces'
free Gradio SDK (Docker requires a paid plan; Gradio does not).

Rather than re-implement the LangGraph interrupt/resume pipeline logic here,
this launches the existing, already-tested api.py (FastAPI) as a background
subprocess and talks to it over HTTP exactly the way streamlit_app.py did --
same endpoints, same SSE event stream, same interrupt-type branching. Only
the UI layer changed, not the pipeline.
"""
import html
import json
import subprocess
import sys
import time

import gradio as gr
import requests

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

# --- start the FastAPI backend once, in the background ---------------------
_api_process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"]
)
time.sleep(5)  # give it a moment to come up before the UI starts hitting it


def stream_events(url: str, payload: dict):
    with requests.post(url, json=payload, stream=True) as response:
        if response.status_code != 200:
            yield {"type": "error", "detail": response.text}
            return
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            yield json.loads(line[len("data:"):].strip())


def render_letter(text: str) -> str:
    safe = html.escape(text or "").replace("\n", "<br>")
    return f'<div style="white-space:pre-wrap;border:1px solid #E6EAF0;border-radius:10px;padding:1.2rem;font-family:Georgia,serif;">{safe}</div>'


def render_interrupt_markdown(interrupt: dict) -> str:
    itype = interrupt.get("type")
    lines = []

    if itype == "consent":
        lines.append(f"**Complaint:** {interrupt.get('complaint_text', '')}")
        risk = interrupt.get("risk_assessment", {})
        severity = risk.get("severity", "low")
        lines.append(f"**Risk assessment:** {severity}")
        reasons = risk.get("reasons", [])
        if reasons:
            lines.append("**Why:**")
            for r in reasons:
                lines.append(f"- {r}")
        lines.append("")
        lines.append(f"### {interrupt.get('question', '')}")
        lines.append("1. Have the AI draft a formal letter")
        lines.append("2. Get guidance instead (no letter)")
        lines.append("3. Write my own letter (we'll review it)")

    elif itype == "own_letter_input":
        lines.append(f"### {interrupt.get('question', '')}")

    elif itype == "own_letter_revise":
        lines.append("### Your letter needs some changes")
        for f in interrupt.get("feedback", []):
            lines.append(f"- {f}")
        lines.append(f"\n*{interrupt.get('attempts_left', '?')} revision(s) left*")
        lines.append(f"\n{interrupt.get('question', '')}")

    elif itype == "own_letter_exhausted":
        lines.append("### Your letter still doesn't pass review")
        for f in interrupt.get("feedback", []):
            lines.append(f"- {f}")

    elif itype == "final_review":
        lines.append("### Review your letter")
        lines.append(render_letter(interrupt.get("draft_letter", "")))
        lines.append(f"\n{interrupt.get('question', 'Edit it, or leave blank to keep as-is')}")

    else:
        lines.append(f"### {interrupt.get('question', 'Input needed')}")

    return "\n\n".join(lines)


def render_result_markdown(result: dict) -> str:
    if result.get("rejected"):
        return f"**Your complaint could not be processed.**\n\nReason: {result.get('reason')}"
    if result.get("escalated"):
        return "**This complaint has been escalated for human review.** A specialist will follow up with you directly."
    output_type = result.get("output_type")
    body = render_letter(result.get("final_output"))
    if output_type == "guidance":
        return f"### Guidance\n\n{body}"
    if output_type == "draft":
        return f"### Your complaint letter\n\n{body}"
    return body


def widgets_for_interrupt(itype: str):
    """Returns (consent_visible, answer_visible, answer_label, exhausted_visible, continue_visible)"""
    if itype == "consent":
        return True, False, "", False, True
    if itype == "own_letter_exhausted":
        return False, False, "", True, False
    if itype == "final_review":
        return False, True, "Edit it, or leave blank to keep as-is", False, True
    # own_letter_input, own_letter_revise, and any generic/default question
    return False, True, "Your answer", False, True


def submit_complaint(complaint_text, state):
    if not complaint_text or not complaint_text.strip():
        yield (gr.update(), "", gr.update(visible=False), "", gr.update(visible=False),
               gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
               gr.update(visible=False), "", state)
        return

    state = {"thread_id": None, "interrupt_type": None}
    progress_lines = []

    for event in stream_events(f"{API_BASE}/complaints/stream", {"complaint_text": complaint_text}):
        if event["type"] == "progress":
            progress_lines.append(f"✓ {NODE_LABELS.get(event['node'], event['node'])}")
            yield (gr.update(visible=False), "\n\n".join(progress_lines), gr.update(visible=False), "",
                   gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                   gr.update(visible=False), gr.update(visible=False), "", state)
        elif event["type"] == "error":
            yield (gr.update(visible=True), f"**Something went wrong:** {event['detail']}",
                   gr.update(visible=False), "", gr.update(visible=False), gr.update(visible=False),
                   gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), "", state)
            return
        else:
            final_event = event

    state["thread_id"] = final_event["thread_id"]

    if final_event["type"] == "interrupt":
        interrupt = final_event["interrupt"]
        state["interrupt_type"] = interrupt.get("type")
        consent_vis, answer_vis, answer_label, exhausted_vis, continue_vis = widgets_for_interrupt(interrupt.get("type"))
        yield (gr.update(visible=False), "", gr.update(visible=True), render_interrupt_markdown(interrupt),
               gr.update(visible=consent_vis), gr.update(visible=answer_vis, label=answer_label, value=""),
               gr.update(visible=exhausted_vis), gr.update(visible=continue_vis), gr.update(visible=False), "", state)
    else:
        state["result"] = final_event["result"]
        yield (gr.update(visible=False), "", gr.update(visible=False), "", gr.update(visible=False),
               gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
               gr.update(visible=True), render_result_markdown(final_event["result"]), state)


def submit_answer(answer_value, state, forced_answer=None):
    thread_id = state.get("thread_id")
    answer = forced_answer if forced_answer is not None else answer_value
    url = f"{API_BASE}/complaints/{thread_id}/resume/stream"
    progress_lines = []
    final_event = None

    for event in stream_events(url, {"answer": answer}):
        if event["type"] == "progress":
            progress_lines.append(f"✓ {NODE_LABELS.get(event['node'], event['node'])}")
            yield (gr.update(visible=False), "\n\n".join(progress_lines), gr.update(visible=True), gr.update(),
                   gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                   gr.update(visible=False), gr.update(visible=False), "", state)
        elif event["type"] == "error":
            yield (gr.update(visible=False), f"**Something went wrong:** {event['detail']}",
                   gr.update(visible=True), gr.update(), gr.update(visible=False), gr.update(visible=False),
                   gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), "", state)
            return
        else:
            final_event = event

    if final_event["type"] == "interrupt":
        interrupt = final_event["interrupt"]
        state["interrupt_type"] = interrupt.get("type")
        consent_vis, answer_vis, answer_label, exhausted_vis, continue_vis = widgets_for_interrupt(interrupt.get("type"))
        yield (gr.update(visible=False), "", gr.update(visible=True), render_interrupt_markdown(interrupt),
               gr.update(visible=consent_vis), gr.update(visible=answer_vis, label=answer_label, value=""),
               gr.update(visible=exhausted_vis), gr.update(visible=continue_vis), gr.update(visible=False), "", state)
    else:
        state["result"] = final_event["result"]
        yield (gr.update(visible=False), "", gr.update(visible=False), "", gr.update(visible=False),
               gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
               gr.update(visible=True), render_result_markdown(final_event["result"]), state)


def restart():
    return (
        gr.update(visible=True, value=""),
        "",
        gr.update(visible=False),
        "",
        gr.update(visible=False),
        gr.update(visible=False, value=""),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        {"thread_id": None},
    )


with gr.Blocks(title="CFPB Consumer Complaint Assistant") as demo:
    gr.Markdown("# \U0001F3E6 CFPB Consumer Complaint Assistant")
    gr.Markdown("Get help resolving disputes with banks, lenders, and credit card issuers.")

    state = gr.State({"thread_id": None})

    with gr.Column(visible=True) as input_section:
        complaint_box = gr.Textbox(label="Describe your complaint", lines=5,
                                    placeholder="e.g. Someone opened a credit card in my name without my permission.")
        submit_btn = gr.Button("Submit", variant="primary")

    progress_md = gr.Markdown("")

    with gr.Column(visible=False) as interrupt_section:
        interrupt_info = gr.Markdown("")
        consent_radio = gr.Radio(
            choices=[
                ("Have the AI draft a formal letter", "1"),
                ("Get guidance instead (no letter)", "2"),
                ("Write my own letter (we'll review it)", "3"),
            ],
            label="How would you like to proceed?",
            visible=False,
        )
        answer_box = gr.Textbox(label="Your answer", lines=8, visible=False)
        with gr.Row(visible=False) as exhausted_row:
            send_anyway_btn = gr.Button("Send it anyway")
            ai_takeover_btn = gr.Button("Let the AI draft one instead")
        continue_btn = gr.Button("Continue", visible=False)

    with gr.Column(visible=False) as result_section:
        result_md = gr.Markdown("")
        restart_btn = gr.Button("Start a new complaint")

    outputs = [input_section, progress_md, interrupt_section, interrupt_info, consent_radio,
               answer_box, exhausted_row, continue_btn, result_section, result_md, state]

    submit_btn.click(submit_complaint, inputs=[complaint_box, state], outputs=outputs)

    def continue_click(consent_val, answer_val, state):
        # Both possible answer sources are wired in via `inputs=` (Gradio
        # components can't be read out-of-band); pick whichever one the
        # current interrupt type actually wants.
        itype = state.get("interrupt_type")
        forced = consent_val if itype == "consent" else None
        value = answer_val if itype != "consent" else None
        yield from submit_answer(value, state, forced_answer=forced)

    def send_anyway_click(state):
        yield from submit_answer(None, state, forced_answer="send")

    def ai_takeover_click(state):
        yield from submit_answer(None, state, forced_answer="ai")

    continue_btn.click(continue_click, inputs=[consent_radio, answer_box, state], outputs=outputs)
    send_anyway_btn.click(send_anyway_click, inputs=[state], outputs=outputs)
    ai_takeover_btn.click(ai_takeover_click, inputs=[state], outputs=outputs)
    restart_btn.click(restart, inputs=[], outputs=outputs)

if __name__ == "__main__":
    demo.launch()