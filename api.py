from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from typing import Optional,Any,Dict
import uuid
from fastapi.responses import StreamingResponse
import json as json_lib

from graph import graph as cfpb_graph
from state import make_initial_state
from langgraph.types import Command

app=FastAPI(title="CFPB Agentic RAG API")

class ComplaintRequest(BaseModel):
    complaint_text:str

class ResumeRequest(BaseModel):
    answer:str

class ComplaintResponse(BaseModel):
    thread_id:str
    status:str
    interrupt:Optional[Dict[str,Any]]=None
    result:Optional[Dict[str,Any]]=None

def build_result(final_state:dict)->Dict[str,Any]:
    if not final_state.get("input_guardrail_passed",True):
        return{
            "rejected":True,
            "reason":final_state.get("input_guardrail_reason")
        }
    output_type=final_state.get("output_type")
    escalated=final_state.get("escalated")
    return{
        "rejected":False,
        "escalated":bool(escalated),
        "output_type":output_type,
        "final_output":final_state.get("final_output")
    }

def build_response(thread_id:str,result:dict)->ComplaintResponse:
    if "__interrupt__" in result:
        interrupt_obj=result["__interrupt__"][0]
        return ComplaintResponse(
            thread_id=thread_id,
            status="interrupted",
            interrupt=interrupt_obj.value
        )
    return ComplaintResponse(
        thread_id=thread_id,status="done",result=build_result(result)
    )

@app.post("/complaints",response_model=ComplaintResponse)
def create_complaint(req:ComplaintRequest):
    thread_id=str(uuid.uuid4())
    config={"configurable":{"thread_id":thread_id}}

    initial_state=make_initial_state(req.complaint_text)
    result=cfpb_graph.invoke(initial_state,config=config)

    return build_response(thread_id,result)

@app.post("/complaints/{thread_id}/resume",response_model=ComplaintResponse)
def resume_complaint(thread_id:str,req:ResumeRequest):
    config={"configurable":{"thread_id":thread_id}}

    state_snapshot=cfpb_graph.get_state(config)
    if not state_snapshot.next:
        raise HTTPException(
            status_code=400,
            detail="This thread is not currently paused at a checkpoint."
        )
    result=cfpb_graph.invoke(Command(resume=req.answer),config=config)
    return build_response(thread_id,result)

def event_stream(stream_input,config:dict,thread_id:str):
    for update in cfpb_graph.stream(stream_input,config=config,stream_mode="updates"):
        if "__interrupt__" in update:
            continue
        for node_name in update.keys():
            payload={"type":"progress","node":node_name}
            yield f"data: {json_lib.dumps(payload)}\n\n"

    snapshot=cfpb_graph.get_state(config)
    if snapshot.next:
            interrupt_obj=snapshot.tasks[0].interrupts[0]
            payload={"type":"interrupt","thread_id":thread_id,"interrupt":interrupt_obj.value}
    else:
            payload={"type":"done","thread_id":thread_id,"result":build_result(snapshot.values)}
    yield f"data:{json_lib.dumps(payload)}\n\n"

@app.post("/complaints/stream")
def create_complaint_stream(req:ComplaintRequest):
    thread_id=str(uuid.uuid4())
    config={"configurable":{"thread_id":thread_id}}
    initial_state=make_initial_state(req.complaint_text)
    return StreamingResponse(
        event_stream(initial_state,config,thread_id),
        media_type="text/event-stream"
    )
@app.post("/complaints/{thread_id}/resume/stream")
def resume_complaint_stream(thread_id:str,req:ResumeRequest):
    config={"configurable":{"thread_id":thread_id}}
    state_snapshot=cfpb_graph.get_state(config)
    if not state_snapshot.next:
        raise HTTPException(
            status_code=400,
            detail="This thread is not currently paused at a checkpoint."
        )
    return StreamingResponse(
        event_stream(Command(resume=req.answer),config,thread_id),
        media_type="text/event-stream"
    )

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)