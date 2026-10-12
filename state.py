from typing import TypedDict,Literal,Optional,List
class RetreivedEvidence(TypedDict):
    regulatory_docs:List[str]
    compalint_handling_guidance:List[str]
    similar_historical_complaints:List[str]

class RiskAssessment(TypedDict):
    severity:Literal["high","low"]
    fraud_flag:bool
    reasons:List[str]
    evdience_ids:List[str]
    confidence:float

class ComplaintState(TypedDict):
    complaint_text:str
    input_guardrail_passed:Optional[bool]
    input_guardrail_reason:Optional[str]
    category:Optional[str]
    confidence:Optional[str]
    classifier_used:Optional[str]
    retrieved_context:Optional[RetreivedEvidence]
    risk_assessment:Optional[RiskAssessment]
    wants_drafted_letter:Optional[bool]
    consent_choice:Optional[Literal["draft","guidance","own"]]
    output_type:Optional[Literal["guidance","draft"]]
    own_letter_attempts:Optional[int]
    escalated:Optional[bool]
    guidance_text:Optional[str]
    draft_letter:Optional[str]
    critic_passed:Optional[bool]
    critic_feedback:Optional[str]
    output_guardrail_passed:Optional[bool]
    output_guardrail_feedback:Optional[str]
    revision_count:int
    final_output:Optional[str]

def make_initial_state(complaint_text):
    return{
        "complaint_text":complaint_text,
        "input_guardrail_passed":None,
        "input_guardrail_reason":None,
        "category":None,
        "confidence":None,
        "classifier_used":None,
        "retrieved_context":None,
        "risk_assessment":None,
        "wants_drafted_letter":None,
        "escalated":False,
        "output_type":None,
        "own_letter_attempts":0,
        "guidance_text":None,
        "draft_letter":None,
        "critic_passed":None,
        "output_guardrail_passed":None,
        "output_guardrail_feedback":None,
        "critic_feedback":None,
        "revision_count":0,
        "final_output":None,
        "consent_choice":None
    }
