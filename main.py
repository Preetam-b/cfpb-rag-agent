from dotenv import load_dotenv
load_dotenv()
from graph import graph as cfpb_graph
from state import make_initial_state
import uuid
from langgraph.types import Command
from own_letter import read_multiline


def get_complaint()->str:
    print("CFPB COnsumer Complaint Assistant")
    complaint=input("\nDescribe your complaint : \n> ").strip()
    while not complaint:
        complaint=input("Please enter a complaint :\n>").strip()
    return complaint

def handle_interrupt(interrupt_obj):
    payload=interrupt_obj.value
    itype=payload.get("type")

    if itype =="consent":
        print("\n HUMAN CHECKPOINT: Consent ")
        print("Complaint: ",payload["complaint_text"])
        print("Risk assessment :",payload["risk_assessment"])
        print("\n"+payload["question"])
        print(" 1. Have the AI draft a formal letter")
        print( "2. Get guidance instead (no letter)")
        print(" 3.Write your own letter  (we'll review it for you)")
        return input("Enter 1,2 or 3: ").strip()
    
    elif itype =="final_review":
        print("\n HUMAN CHECKPOINT")
        print("Draft letter : \n")
        print(payload["draft_letter"])
        print("\n"+payload["question"])
        print("(typr each line and press Enter ; type END on its own line when done)")
        return read_multiline()
    
    elif itype=="own_letter_input":
        print("\n YOUR OWN LETTER")
        print(payload["question"])
        print("(type each line and press Enter: type END on its own line when done)")
        return read_multiline()

    elif itype=="own_letter_revise":
        print("\nYour letter needs some changes before it can be sent: ")
        for line in payload.get("feedback",[]):
            print("-",line)
        print(f"\nYou have {payload.get('attempts_left','?')} revision(s) left.")
        print(payload["question"])
        print("(type each line and press Enter; type END on its own line when done)")
        return read_multiline()

    elif itype =="own_letter_exhausted":
        print("\n"+payload["question"])
        for line in payload.get("feedback",[]):
            print("-",line)
        return input("(send/ai): ").strip().lower()
    
    else:
        print("\n" +str(payload.get("question","Input needed:")))
        return input("> ").strip()

def print_result(final_state:dict)->None:
    if not  final_state.get("input_guardrail_passed",True):
        print("your complaint could not be processed.")
        reason=final_state.get("input_guardrail_reason")
        if reason:
            print(f"Reason : {reason}")
        return
    output_type=final_state.get("output_type")
    escalated=final_state.get("escalated")
    if escalated:
        print("This complaint has been escalated for human review.")
        print("A specialist will follow up with you directly.")
    elif output_type=="guidance":
        print("Here's a guidance for resolving your complaint : \n")
        print(final_state.get("final_output","").strip())
    elif output_type=="draft":
        print("Hers's your complaint letter: \n")
        print(final_state.get("final_output","").strip())
    else:
        print("Result:\n")
        print(final_state.get("final_output","(no output produced)"))

def main()->None:
    complaint_text=get_complaint()
    initial_state=make_initial_state(complaint_text)

    thread_id=str(uuid.uuid4())
    config={"configurable":{"thread_id":thread_id}}

    print("\nProcessing your complaint..\n")
    result=cfpb_graph.invoke(initial_state,config=config)

    while "__interrupt__" in result:
        interrupt_obj=result["__interrupt__"][0]
        answer=handle_interrupt(interrupt_obj)
        result=cfpb_graph.invoke(Command(resume=answer),config=config)

    print_result(result)

if __name__=="__main__":
        main()