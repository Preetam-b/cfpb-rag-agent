# CFPB Consumer Complaint Assistant

An autonomous agentic RAG system that helps consumers resolve financial complaints — credit card fraud, debt collection harassment, mortgage servicing errors, and more — by classifying the complaint, researching the relevant regulations, assessing risk, and either drafting a formal dispute letter or giving plain-language guidance, with a human in the loop at every consequential decision.

Built as an end-to-end portfolio project: multi-agent orchestration, hybrid retrieval, self-correcting quality control, and a real deployed product around it (API + web UI), not just a notebook.

**Live demo:** [huggingface.co/spaces/P-r-e-e-t-a-m/cfpb-agent-rag](https://huggingface.co/spaces/P-r-e-e-t-a-m/cfpb-agent-rag)

---

## What it does

A consumer describes their complaint in plain English. The system figures out what kind of issue it is, looks up the regulations and internal guidance that actually apply, judges how serious it is, and then either:

- **drafts a formal dispute letter** citing the relevant regulation, or
- **gives plain-language guidance** on what to do next, or
- **reviews a letter the consumer writes themselves**, giving real feedback instead of silently rewriting it

At every point where a decision actually matters — how to proceed on a risky complaint, whether a drafted letter is good enough to send — a human is the one who decides. The system does the research and the drafting; it doesn't act on the consumer's behalf unsupervised.

## Architecture

The pipeline is a single LangGraph state machine. Every arrow below is a graph edge; every human-shaped box is a point where execution pauses and waits for real input.

```
User complaint
    │
    ▼
Input guardrail (length, injection, toxicity) ──▶ reject if bad
    │
    ▼
Classify & route (BERT classifier, LLM fallback below confidence threshold)
    │
    ▼
RAG research (regulations, internal guidance, historical complaints — 3 buckets)
    │
    ▼
CRAG evaluator (scores retrieval quality)
    │  bad ──▶ rewrite query ──▶ retry once ──▶ still bad ──▶ web fallback (consumerfinance.gov only)
    ▼
Risk / fraud agent (severity, fraud flag, reasons, cited evidence)
    │
    ├── low risk ──────────────────────────────┐
    │                                           ▼
    └── high risk ──▶ HUMAN: how to proceed?    Guidance agent
         │ draft          │ guidance   │ own letter
         ▼                ▼            ▼
    Drafting agent   Guidance agent   HUMAN writes their own letter
         │                │                │
         └────────┬───────┘                │
                   ▼                        ▼
         Critic (tone / grounded / useful — independent checks)
                   │
                   ▼
         Output guardrail (PII, hallucination, compliance)
                   │
          fail ──▶ feedback ──▶ retry (capped) ──▶ still failing ──▶ escalate to human
                   │ pass
                   ▼
         HUMAN: final review (edit or approve) ──▶ done
```

**Why a human checkpoint at the risk fork, and again at the end:** an agent that silently sends a legal dispute letter on a consumer's behalf is not something to ship confidently. The system does the research and drafting; a person still decides what actually goes out.

**Why classification has two tiers:** a fine-tuned BERT model handles the common case cheaply and fast. When its confidence drops below threshold, an LLM call takes over as fallback — more expensive per call, but far more reliable on ambiguous or unusual complaint text than forcing BERT's answer through regardless of confidence.

**Why retrieval has a self-correction loop (CRAG):** a RAG system that trusts whatever it retrieves on the first try is only as good as its search. A lightweight evaluator checks relevance before the retrieved documents ever reach an agent; if retrieval scores poorly, the query gets rewritten and retried once before falling back to a scoped web search against consumerfinance.gov. The downstream agents never see bad context.

## Tech stack

- **Orchestration:** LangGraph (stateful graph, `interrupt()`-based human-in-the-loop, checkpointed threads so the pipeline can pause and resume across separate HTTP requests)
- **Classification:** fine-tuned BERT (bert-base, trained on CFPB complaint data), with an LLM fallback below a confidence threshold
- **Retrieval:** ChromaDB (vector) + BM25 (keyword), merged via reciprocal rank fusion, evaluated by a CRAG-style relevance checker across three separate document buckets (regulations, internal guidance, historical complaints)
- **LLM inference:** Groq (hosted, used in production), Ollama (local dev) — swappable via a single environment variable, same prompts and logic either way
- **Backend:** FastAPI, with Server-Sent Events streaming live pipeline progress to the client as each node completes
- **Frontend:** Gradio, deployed on Hugging Face Spaces
- **Model hosting:** the fine-tuned BERT weights are hosted on the Hugging Face Model Hub and pulled at startup, rather than bundled into the app itself

## Engineering highlights

A sample of real bugs found and fixed during development — the full log, issue by issue, is in [`PROJECT.MD`](./PROJECT.MD).

- **LLM self-aggregation is a weak point.** Twice (the critic, and the risk agent), asking an LLM to produce free-form reasoning *and* a single aggregate verdict in one response let the final verdict drift from what the reasoning actually supported — e.g. reasoning that clearly described a low-risk billing dispute, followed by `severity: high` anyway. Fix, both times: ask for independent boolean sub-judgments, compute the aggregate (`AND`/`any()`) in code instead of trusting the model to do it.
- **An LLM-as-judge needs an ordered checklist, not an open question.** The CRAG relevance evaluator initially rated clearly wrong-category documents as "good" because an open-ended relevance prompt lets a model find surface-level similarity. Restructuring it into a hard topic-match check *first*, then quality, closed the gap.
- **A misspelled dict key fails silently, not loudly.** Python just creates a new key — `evdidence_ids` instead of `evidence_ids` doesn't error, it just means the real data never gets read. Caught by diffing node code against the state schema directly, not by running the code and watching it "work."
- **Structured decisions need `temperature=0`.** The same borderline complaint returned different risk verdicts on different runs until every structured-judgment LLM call (classification, guardrails, risk, critic) was pinned to zero temperature — content generation stays at default.
- **A TypedDict field rename doesn't propagate on its own.** After splitting the critic/guardrail logic into its own module, one file kept writing to `output_guardrail_feedback` while the state schema still declared `output_guardrail_reason`. TypedDict isn't enforced at runtime, so this surfaced as a plain `KeyError` the first time that code path actually ran — not when the mismatch was introduced.
- **The architecture changed shape to support the API layer, not just the CLI.** A blocking `input()`-based loop can't survive stateless HTTP requests. Moving to `interrupt()` + a checkpointer meant the same human-in-the-loop logic that works from a terminal also works resumed across separate API calls, with no duplicated branching logic between the two.
- **Hosted inference providers don't guarantee model availability per account.** A model name listed as "production" in a provider's public docs still 404'd — turned out the specific account only had access to a different subset of models than the docs implied. Isolating the call (bare script, no graph, no HTTP) in under a minute separated "my code is wrong" from "my account can't see this model."

## Status

Core pipeline, API, and UI are complete and tested end-to-end, and the system is live on Hugging Face Spaces. LLM evals (RAGAS-based) are planned as a follow-up.
