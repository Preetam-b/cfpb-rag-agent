from llm import ask_llm_json

def build_evidence_block(retrieved_context):
    lines=[]
    id_to_text={}

    for i,doc in enumerate(retrieved_context["regulatory_docs"],start=1):
        evidence_id="reg_doc_"+str(i)
        lines.append("[" +evidence_id+"] "+doc)
        id_to_text[evidence_id]=doc

    for i,doc in enumerate(retrieved_context["complaint_handling_guidance"],start=1):
        evidence_id="guidance_doc_"+str(i)
        lines.append("["+evidence_id+"] "+doc)
        id_to_text[evidence_id]=doc

    for i,doc in enumerate(retrieved_context["similar_historical_complaints"],start=1):
        evidence_id="similar_complaint_"+str(i)
        lines.append("["+evidence_id+"] "+doc)
        id_to_text[evidence_id]=doc

    evidence_text="\n\n".join(lines)
    return evidence_text,id_to_text

def risk_agent_node(state):
    complaint_text=state["complaint_text"]
    category=state["category"]
    retrieved_context=state["retrieved_context"]

    evidence_text,id_to_text=build_evidence_block(retrieved_context)
    valid_ids=list(id_to_text.keys())

    prompt = (
    "You are a risk and fraud assessment agent for consumer financial complaints.\n\n"
    "Complaint category: " + category + "\n"
    "Complaint: " + complaint_text + "\n\n"
    "Evidence available (cite these by their exact ID in brackets):\n"
    + evidence_text + "\n\n"
    "IMPORTANT: Base your assessment of WHAT HAPPENED strictly on the complaint "
    "text itself. The evidence documents describe regulations and general rules "
    "that MAY be relevant to this category of complaint — they are not claims "
    "about what actually happened in this specific case. Do not assume unauthorized "
    "activity, fraud, or theft occurred just because the evidence discusses those "
    "topics in general.\n\n"
    "Answer these four yes/no questions about the complaint text, independently:\n"
    "1. fraud_or_unauthorized: Does the complaint describe suspected fraud or an "
    "unauthorized transaction/account (not just a disputed fee or billing error)?\n"
    "2. identity_theft: Does the complaint describe identity theft, such as an "
    "account or card opened without the consumer's knowledge or consent?\n"
    "3. harassment_or_threats: Does the complaint describe harassment, threats, "
    "or abusive conduct by the company?\n"
    "4. legal_threat: Does the complaint describe an explicit threat of legal "
    "action, such as foreclosure or a lawsuit?\n\n"
    "A routine billing dispute, an incorrect fee, slow or unhelpful customer "
    "service, or a credit score drop caused by a billing error should get \"no\" "
    "on all four questions, even if the consumer is frustrated or money is "
    "involved. Only answer \"yes\" if the complaint text itself clearly describes "
    "that specific situation.\n\n"
    "Also provide:\n"
    "5. reasons: a short list of specific reasons for your answers above.\n"
    "6. evidence_ids: a list of the evidence IDs (exactly as given above, e.g. "
    "\"reg_doc_1\") that actually support your reasoning. Only cite IDs that "
    "are genuinely relevant.\n"
    "7. confidence: your confidence in these answers, as \"low\", \"medium\", or \"high\".\n\n"
    "Reply only with JSON in this form:\n"
    '{"fraud_or_unauthorized": true or false, "identity_theft": true or false, '
    '"harassment_or_threats": true or false, "legal_threat": true or false, '
    '"reasons": ["reason 1", "reason 2"], "evidence_ids": ["id1", "id2"], '
    '"confidence": "low or medium or high"}'
)
    result=ask_llm_json(prompt)
    print("\n[DEBUG] raw risk agent result:", result)
    if result is None:
        state["risk_assessment"]={
            "severity":"high",
            "fraud_flag":False,
            "reasons":["Risk agent failed to respond; escalating as a precaution."],
            "evidence_ids":[],
            "confidence":0.5
        }
        return state
    fraud_or_unauthorized=bool(result.get("fraud_or_unauthorized",False))
    identity_theft=bool(result.get("identity_theft",False))
    harassment_or_threats=bool(result.get("harassment_or_threats",False))
    legal_threat=bool(result.get("legal_threat",False))
    severity="high" if any([
        fraud_or_unauthorized,
        identity_theft,
        harassment_or_threats,
        legal_threat,
    ]) else "low"

    fraud_flag=fraud_or_unauthorized
    reasons=result.get("reasons",[])
    raw_evidence_ids=result.get("evidence_ids",[])
    evidence_ids=[eid for eid in raw_evidence_ids if eid in valid_ids]

    confidence_map={"high":0.9,"medium":0.7,"low":0.5}
    confidence_level=str(result.get("confidence","medium")).lower()
    confidence=confidence_map.get(confidence_level,0.7)
    state["risk_assessment"]={
        "severity":severity,
        "fraud_flag":fraud_flag,
        "reasons":reasons,
        "evidence_ids":evidence_ids,
        "confidence":confidence,
    }
    return state

def guidance_agent_node(state,feedback=None,max_attempts=2):
    complaint_text=state["complaint_text"]
    category=state["category"]
    retrieved_context=state["retrieved_context"]
    evidence_text,_=build_evidence_block(retrieved_context)
    feedback_block=""
    if feedback:
        feedback_block=(
            "\n\nIMPORTANT : a previous version of this guidance was reviewed"  
            "and rejected for this reason : \""+feedback +"\"\n"
            "Fix this specific issue in your new response. \n"
        )
    prompt=(
        "You are writing self-serve guidance for a consumer with financial complaint.\n\n"
        "Complaint category: "+category+"\n"
        "Complaint: "+complaint_text+"\n"
        "Relevant evidence: "+evidence_text+"\n"
        +feedback_block+
        "Write clear, step by step guidance the consumercan follow themselves"
        "to resolve this. Ground your advice in the evidenceabove where relevant"
        "(you can mention what the regulation requires, in plain language, without"
        "citing document IDs). Do not invent specific facts,dates, or numbers that"
        "aren't in the complaint or evidence. Keep it practical and concise.\n\n"
        "Reply only with JSON in this form : \n"
        '{"guidance":"the full guidance text"}'
    )
    for attempt in range(max_attempts):
        result=ask_llm_json(prompt)
        if result is not None and result.get("guidance"):
            state["guidance_text"]=result["guidance"]
            state["output_type"]="guidance"
            return state
    state["guidance_text"]=(
            "We are unable to generate guidance automatically." 
            "This complaint has been flagged for human review."
        )
    state["output_type"]="guidance"
    return state

def drafting_agent_node(state,feedback=None,max_attempts=2):
    complaint_text=state["complaint_text"]
    category=state["category"]
    retrieved_context=state["retrieved_context"]
    risk_assessment=state["risk_assessment"]

    evidence_text,_=build_evidence_block(retrieved_context)

    feedback_block=""
    if feedback:
        feedback_block=("\n\nIMPORTANT: a previous version of this letter was reviwed"
        "and rejected for this reason : \""+feedback+"\"\n"
        "Fix this specific issue in your new response.\n")

    prompt=(
        "You are drafting a formal complaint letter on behalf of a consumer "
        "to be sent to the company involved.\n\n"
        "Complaint category: "+category+"\n"
        "Complaint :"+complaint_text+"\n"
        "Risk assessment : severity="+risk_assessment["severity"]
        +" fraud_flag=" +str(risk_assessment["fraud_flag"])+"\n\n"
        "Relevant evidence:\n"+evidence_text+
        feedback_block+"\n\n"
        "Write a formal, professional letter the consumer could send. Reference "
        "the relevant regulation or rule in plain language where appropriate "
        "(do not cite document IDs in the letter itself). Do not invent specific "
        "facts, account numbers or dates that aren't in the complaint. Keep the "
        "tone firm but professional, not aggressive.\n\n"
        "Reply only with JSON in this form:\n"
        '{"letter": "the full letter text"}'
    )
    for attempt in range(max_attempts):
        result=ask_llm_json(prompt)
        if result is not None and result.get("letter"):
            state["draft_letter"]=result["letter"]
            state["output_type"]="draft"
            return state
    state["draft_letter"]=(
            "We are unable to generate a draft automatically."
            "This complaint has been flagged for human review."
        )
    state["output_type"]="draft"
    return state

def critic_node(state,max_attempts=2):
    output_type=state["output_type"]
    complaint_text=state["complaint_text"]
    retrieved_context=state["retrieved_context"]

    if output_type=="guidance":
        output_text=state["guidance_text"]
    else:
        output_text=state["draft_letter"]

    evidence_text,_=build_evidence_block(retrieved_context)
    prompt = (
        "You are a quality reviewer checking a response written for a consumer "
        "financial complaint, before it goes out.\n\n"
        "Complaint: " + complaint_text + "\n\n"
        "Evidence that was available to the writer:\n" + evidence_text + "\n\n"
        "Response to review:\n" + output_text + "\n\n"
        "Judge these three things INDEPENDENTLY. Each one gets its own true/false "
        "verdict — do not let one affect the others.\n\n"
        "1. tone_ok: true if the tone is professional, respectful, and appropriate. "
        "False only for a real problem (robotic, aggressive, overly casual).\n\n"
        "2. grounded: true if the response sticks to facts from the complaint and "
        "evidence. Before marking this false, you MUST carefully re-read the evidence "
        "and check whether the claim is actually stated there, even if paraphrased. "
        "A REASONABLE SIMPLIFICATION of a precise numeric rule is grounded=true, as "
        "long as it does not understate the consumer's protections or overstate their "
        "liability. For example, simplifying 'the lesser of $50 or the actual "
        "unauthorized amount' to 'limited to $50' is grounded=true, because it never "
        "tells the consumer they have less protection than they actually do. Only "
        "mark grounded=false if a claim is genuinely absent from the evidence, or if "
        "a simplification could mislead the consumer into believing they have fewer "
        "rights or more liability than they actually do.\n\n"
                "3. useful: true only if the response names at least one SPECIFIC, concrete "
        "action tied to this complaint — e.g. closing/disputing a named account, "
        "capping liability at a specific amount, correcting a credit report, "
        "requesting written confirmation within a timeframe. False if the response "
        "is emotional language, a general plea for help ('please help', 'please fix "
        "this'), or any request that does not name a specific institution, account, "
        "or remedy.\n\n"
        "Reply only with JSON in this form:\n"
        '{"tone_ok": true or false, "grounded": true or false, "useful": true or false, '
        '"feedback": "specific feedback on any false verdict, quoting evidence where relevant, '
        'or \'No issues found\' if all true"}'
    )
    for attempt in range(max_attempts):
        result=ask_llm_json(prompt)
        if result is not None and "tone_ok" in result and "grounded" in result and "useful" in result:
            tone_ok=bool(result["tone_ok"])
            grounded=bool(result["grounded"])
            useful=bool(result["useful"])
            state["critic_passed"]=tone_ok and grounded and useful
            state["critic_feedback"]=result.get("feedback","")
            return state

    state["critic_passed"]=False
    state["critic_feedback"]="Critic failed to return a vaild review; treating as failed"
    return state