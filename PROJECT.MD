# CFPB Agentic RAG — Project Notes

## Architecture Status
- ✅ Input guardrail (length, injection, toxicity)
- ✅ Classify and route (BERT + LLM fallback, confidence-gated)
- ✅ RAG research (3 buckets: regulations, guidance, historical complaints — category-filtered, hybrid search)
- ✅ CRAG evaluator + retry (query rewrite, capped at 1)
- ✅ Output guardrail (PII, hallucination, compliance) — built, awaiting real content from agents
- ⬜ Risk/fraud agent
- ⬜ Guidance agent, Drafting agent
- ⬜ Critic agent
- ⬜ Revision loop
- ⬜ HITL consent + HITL final review
- ⬜ Graph wiring (LangGraph)
- ⬜ LangSmith tracing
- ⬜ LLM evals (RAGAS) — deferred ~1 month post-completion
- ⬜ FastAPI + Streamlit + deployment

---

## Key Issues & Fixes

### 1. LLM classification fallback: transient failures needed retry logic
**Context:** `classify.py`'s LLM fallback occasionally failed validation (bad JSON,
or a category string not matching our label list) on a single attempt, even
though the same complaint succeeded cleanly when run again moments later.

**Root cause:** No retry — a single failed LLM call silently fell back to
trusting BERT's low-confidence answer instead, defeating the purpose of having
a fallback at all.

**Fix:** Added a bounded retry loop (`max_attempts=2`) inside the fallback
classifier. Only after all attempts fail does it fall back to BERT, and this
is now a rare, genuine failure rather than routine.

**Lesson:** LLM calls are not perfectly reliable even with valid inputs —
production-adjacent code needs retry logic around them by default, not as
an afterthought.

---

### 2. CRAG evaluator was too lenient (LLM-as-judge failure mode)
**Context:** Deliberately stress-tested the CRAG evaluator by feeding it a
mortgage complaint while forcing retrieval to search the wrong category
(Retail Banking). Retrieval correctly returned Retail Banking documents,
completely unrelated to the complaint — but the evaluator rated this "good."

**Root cause:** The evaluator prompt asked an open-ended relevance question.
LLM judges given open-ended questions tend to find loose, surface-level
similarity ("both involve a dispute and money") and rate it as relevant,
rather than strictly checking whether the actual topic matches.

**Fix:** Restructured the evaluator prompt into an explicit, ordered
checklist: first, a hard topic-match check (auto-fail on category/topic
mismatch), and only then a subjective quality judgment. Re-ran the same
adversarial test — evaluator now correctly returns "bad."

**Lesson:** LLM-as-judge systems need explicit, ordered evaluation criteria,
not open-ended questions, or they default to lenient, surface-level judgments.
Also validated the value of adversarial testing (deliberately breaking the
input) rather than only testing the happy path — this bug would have shipped
silently otherwise, since every earlier test used correctly-classified
complaints.


### 3. CRAG web fallback: appending bad+good results together defeated the evaluator
**Context:** Added a scoped web-search fallback (consumerfinance.gov only) that
fires when local retrieval still fails after the query-rewrite retry. First
version appended the web results onto the existing (already-failed) local
documents, rather than replacing them.

**Root cause:** The evaluator judges a whole bucket of documents as one block,
not document-by-document. With 2 wrong-category local docs still mixed in
alongside 3 genuinely relevant web snippets, the strict evaluator correctly
flagged the mixed batch as still containing bad documents, so the overall
judgment stayed "bad" even though the web content alone was good.

**Fix:** When the web fallback succeeds, it now replaces the local regulatory
docs entirely rather than appending to them. Local retrieval had already
failed the relevance check by this point, so there was no reason to keep it
around to dilute the web content's quality.

**Lesson:** An "all-or-nothing" relevance judgment over a batch of documents
doesn't compose well with a "top up with more documents" fallback strategy —
mixing confirmed-bad and untested-good content in the same evaluation batch
punishes the good content by association. Fallback results should generally
replace, not supplement, content that already failed a quality gate.

---

---

### 5. Misspelled dictionary keys fail silently, not loudly
**Context:** `agents.py` had two typos — `"evdidence_ids"` instead of
`"evidence_ids"`, and `"risk_assesment"` instead of `"risk_assessment"` (in
the fail-safe branch only).

**Root cause:** Python dictionaries don't validate key names. A misspelled
key doesn't raise an error — it just creates a new, differently-named key
that silently diverges from what the rest of the code (and state.py's
expected shape) actually uses.

**Fix:** Corrected both spellings to match state.py's RiskAssessment shape
exactly.

### 6. Guidance/drafting agents had no retry, unlike every other LLM call
**Context:** While discussing why a failed guidance generation should escalate
to a human rather than fall back to raw web search, realized guidance_agent_node
and drafting_agent_node called the LLM only once, with no retry — inconsistent
with classify_with_llm and guardrail_check, which both retry before giving up.

**Root cause:** Oversight when first writing these two functions — copied the
"fail safe to human escalation" pattern without also copying the retry pattern
that makes that escalation a genuine last resort rather than a first response
to an ordinary transient hiccup.

**Fix:** Added the same max_attempts retry loop used elsewhere in the project.

**Lesson:** Consistency audits across similar functions catch real bugs —
this one surfaced from asking "why does this design choice exist" about an
edge case, not from a test failing. Worth periodically comparing similar
functions against each other, not just testing each one in isolation.

**Lesson:** Dictionary key typos are a uniquely dangerous category of bug —
no error, no warning, just data quietly ending up somewhere other than
expected. Worth comparing a dict's keys against state.py's defined shape
directly after writing any node, rather than assuming print output alone
would reveal a mismatch (it won't, since print() happily shows whatever
key names actually exist).

### 7. Critic agent caught a real hallucination in guidance text
**Context:** First real test run of critic_node against actual guidance_text
output (not a hand-crafted test case). The critic failed the response,
flagging that it claimed "your bank may have stopped charging NSF fees" —
a claim not supported by any retrieved evidence.

**What this validates:** the guidance agent, despite explicit instructions
not to invent facts, still introduced an ungrounded claim (likely pulling
from general training knowledge about real-world banking trends rather than
the specific evidence it was given). The critic correctly caught this on
its own, with no test specifically designed to trigger it.

**Why this matters:** this is the multi-layer defense in the locked
architecture actually working as intended — no single agent is trusted
blindly; the critic exists specifically to catch exactly this kind of
subtle, plausible-sounding but ungrounded claim that passes a casual read.

**Next step:** this result should trigger the revision loop (send feedback
back to guidance_agent_node, regenerate, max 2 retries) — this is the next
piece to build.

### 8. Revision loop recovered a failing response within the retry cap
**Context:** First full test of run_revision_loop against a complaint that
had previously triggered a hallucination (the guidance agent inventing a
claim about banks "stopping NSF fees" not supported by evidence).

**What happened:** The loop used both of its allowed revisions (revision_count
reached 2) before producing a response that passed both the critic and the
output guardrail. The final version correctly cited Regulation E by name,
included the real $50/$500 liability figures from the actual regulation
document, and contained no unsupported claims.

**Why this matters:** validates the full revision loop end-to-end on a real,
previously-problematic case — not a hand-picked easy example. Confirms the
feedback mechanism (telling the writer agent exactly what was wrong) is
specific enough to actually fix the flagged issue across multiple attempts,
and confirms MAX_REVISIONS=2 is a reasonable cap: this case needed every
available attempt, but still succeeded within the limit rather than needing
escalation.

### 9. Risk agent let retrieved evidence's topic bleed into judgment of facts
**Context:** First full graph test (input guardrail → classify → RAG research →
risk agent) flagged a routine "$5 unrecognized fee" complaint as high severity
with fraud_flag=true, citing "potential identity theft" — even though the
complaint never mentioned theft or unauthorized access. This contradicted an
earlier isolated test of the same complaint through risk_agent_node directly,
which correctly returned low/no-fraud.

**Root cause:** Retrieval correctly returned Regulation E's unauthorized-
transfer-liability documents (genuinely relevant to the Retail Banking
category in general). But the risk agent's prompt didn't clearly distinguish
between "evidence describing what rules might apply" and "facts about what
actually happened in this complaint." The model let the evidence's topic
(unauthorized activity) leak into its judgment of the complaint's facts, even
though the complaint itself described something far more mundane.

**Fix:** Added an explicit instruction block to the risk agent's prompt,
telling it to base factual judgments strictly on the complaint text, and
clarifying that evidence describes possibly-relevant rules, not confirmed
facts about the specific case.

**Lesson:** This is a subtle but important RAG-adjacent failure mode: an LLM
given both "the question" and "retrieved context" can conflate the topic of
the context with the content of the question, especially when the context is
written in a way that assumes the described scenario (e.g., regulation text
about handling unauthorized transfers reads as if unauthorized activity is
the default situation). Worth explicitly telling the model which input is
ground truth (the complaint) versus general reference material (the
evidence) rather than assuming the distinction is obvious from structure alone.

### 10. Critic's own reasoning contradicted its final verdict (LLM self-aggregation failure)
**Context:** After fixing the risk agent's evidence-vs-fact conflation bug, the
critic began failing guidance text for citing "liability limited to $50" —
which is the first-pass, correct, evidence-grounded claim. First prompt fix
(telling the critic to verify claims against evidence before flagging them)
revealed something deeper: the critic's own reasoning explicitly stated "this
does not understate the consumer's protections" — correctly applying the
asymmetric-simplification rule it was given — and then still returned
"passed": false, directly contradicting its own stated analysis.

**Root cause:** Asking an LLM to produce detailed free-form reasoning AND a
single aggregate pass/fail judgment in the same response allows the final
verdict to drift away from what the reasoning actually supports. The model
correctly worked through the sub-question, but its holistic "overall verdict"
instinct overrode its own correct, specific conclusion — a known failure
mode where LLMs are more reliable at narrow judgments than at aggregating
their own judgments into one combined decision.

**Fix:** Restructured critic_node to ask for three INDEPENDENT boolean
judgments (tone_ok, grounded, useful) instead of one combined "passed"
field, then computed the final pass/fail in plain Python
(`tone_ok and grounded and useful`) rather than trusting the LLM's own
aggregation. This removes the opportunity for a reasoning/verdict mismatch
entirely, since the model never produces the final combined decision — it
only answers narrower questions that code then combines deterministically.

**Lesson:** When an LLM's job includes checking multiple independent
criteria and producing one final decision, don't trust the model to compute
that final decision itself — have it output the independent sub-judgments,
and compute the aggregate in code. This is a more general, reusable pattern:
anywhere an LLM is asked to "check several things and give one verdict," the
individual checks are usually reliable, but the aggregation step is the
weak point and should be handled outside the model wherever possible.

**Issue 11: Risk agent over-flagged routine billing disputes as high severity (LLM label vs. reasoning drift)**
A disputed late fee with no fraud, no unauthorized activity, and no threats consistently came back severity: high, even after tightening the prompt's wording to list four closed high-severity categories explicitly. The model's own reasons field didn't even cite one of those four categories — it described "a billing error" and "lack of transparency and accountability," then still output high anyway. Root cause: same class of bug as Issue 10 (critic) — asking an LLM to produce free-form reasoning and a single aggregate label in one response lets the final label drift from what the reasoning actually supports, regardless of how precisely the prompt's wording is tuned. Fix: restructured the prompt to ask for four independent yes/no booleans (fraud_or_unauthorized, identity_theft, harassment_or_threats, legal_threat) with a concrete negative example, then compute severity = "high" if any(...) else "low" in Python code — removing the LLM's ability to assign severity directly. Lesson: tightening prompt wording alone doesn't fix label/reasoning drift — the fix is always to stop asking the LLM for the aggregate judgment and compute it in code from independent sub-answers. This is now the second time this exact pattern (Issue 10, Issue 11) has shown up and been fixed the same way — worth treating as a standing design principle for any future agent in this project that outputs a judgment alongside its reasoning.

**Issue 12: Drafting agent would crash on every normal call (prompt block nested inside a conditional)**
While building the user-written-letter review feature, drafting_agent_node's prompt=(...) block was accidentally indented one level too deep — nested inside `if feedback:` instead of sitting after it. Since every normal first-attempt draft call passes feedback=None, `prompt` was never defined at all in that case, and the function crashed with NameError the moment it tried to call ask_llm_json(prompt). This specifically broke the new "let the AI draft instead" fallback path, since that path calls drafting_agent_node with no feedback. Caught immediately on first test of that path, before it shipped. Lesson: an indentation slip that nests code one block too deep doesn't always throw an error where the mistake was made — it throws later, at the first call that takes the untaken branch. Worth testing every branch of a function (feedback=None and feedback=<something>) separately, not just the one that happens to be hit first in testing.

**Issue 13: Feedback parameter accepted but silently unused (two functions, same bug)**
Both guidance_agent_node and drafting_agent_node take a feedback parameter and build a feedback_block string, but neither one actually inserted feedback_block into the prompt text — the revision loop's feedback was being computed and then discarded every time. This went unnoticed because the functions still ran without error and still returned valid output; there was no crash or visible symptom, only a silently weaker revision loop than intended. Likely a regression from manual retyping at some point (a stray misspelled unused variable, feedback_bloc, sitting right next to the correctly-spelled one was the giveaway). Fix: insert +feedback_block+ into both prompts, right after the evidence line. Lesson: a parameter that's accepted and processed but never referenced in the final prompt string is invisible in testing unless you specifically check that a second revision attempt actually reads differently from the first — "it ran without error" is not the same as "it used the input I gave it."

**Issue 14: Terminal multi-line input broke on real letters (blank line used as both a paragraph separator and a stop signal)**
The first version of the "type a replacement letter" input used a blank line as the signal that input was finished. This breaks immediately on any real letter, which naturally has blank lines between paragraphs — the function would silently stop capturing after the first paragraph break, discarding everything after it with no error. Fix: switched the terminator to a literal line reading END, so blank lines inside the letter are preserved as paragraph breaks and only an explicit END stops input. Lesson: a terminal input convention has to account for what real content normally looks like — "blank line means done" is a reasonable default only when blank lines never legitimately appear inside the content itself.


**Issue 15: State schema and node code disagreed on key names after the critic/guardrail split (KeyError at runtime)**
own_letter.py's _collect_feedback() read state["output_guardrail_feedback"], and guardrails.py's output_guardrail_node() wrote to that exact key — but state.py's ComplaintState TypedDict still declared the old field name output_guardrail_reason, a leftover from before the critic/guardrail split. Separately, own_letter_attempts (the counter actually used by own_letter_check_node and own_letter_check_router) was declared in ComplaintState under the stale name own_letter_complaints, and was missing from make_initial_state() entirely. Both went unnoticed until the own-letter revision path was actually exercised — any node that reads a key before it's ever been written raises a plain Python KeyError, so this surfaced as a crash on the very first retry, not at the point the mismatch was introduced. Fix: renamed the field to output_guardrail_feedback and own_letter_attempts in both the TypedDict and make_initial_state(), matching what the node code already used. Lesson: TypedDict field names aren't enforced at runtime (same root cause as Issue 5) — a rename in one file silently stops synchronizing with the others unless every file touching that state is checked together, not just the one being edited.

**Issue 16: Critic's "useful" criterion was too lenient on vague, non-actionable letters**
The own-letter review path is meant to reject a letter that's pure emotional venting with no concrete ask, but a test letter ("someone opened a card in my name, please fix this ASAP") passed the critic's useful check anyway. The criterion's wording already said "false if vague or missing a concrete next step," but allowed a generic plea like "you can escalate" to still count as useful=true, which let the reviewing LLM read "please fix this" as sufficient. Fix: rewrote the useful criterion to require the response name a SPECIFIC action tied to the complaint (closing a named account, a specific liability cap, a named timeframe for written confirmation) and explicitly list generic pleas for help as an automatic false. Lesson: a true/false criterion with permissive example language ("still useful=true as long as...") gives an LLM judge room to be lenient on cases just inside that example's boundary — tightening the actual acceptance bar, not just adding more instructions, is what changes the verdict.

**Issue 17: print_result() lost its "draft" branch during the interrupt/Command rewrite**
After restructuring main.py's control flow from a single blocking app.invoke() call to the interrupt()-based loop (invoke → while "__interrupt__" in result: handle_interrupt → resume), print_result() was carried over with only an elif output_type=="guidance" branch and a generic else — the elif output_type=="draft" branch that prints "Here's your complaint letter:" had been dropped somewhere in the rewrite. Every draft-letter run still completed successfully and printed real content, just under the wrong generic "Result:" header, so this had no functional impact and was only caught by inspecting the full file side by side with its pre-rewrite version. Lesson: when a function is carried over unchanged during a larger structural rewrite, it still needs to be diffed against its previous version, not just assumed safe because "nothing about it was supposed to change."
## Design Decisions (for reference, not bugs)

- **LLM fallback confidence:** self-reported as low/medium/high, mapped to
  0.5/0.7/0.9, rather than a fixed value or a raw float. Raw floats from LLMs
  are falsely precise and poorly calibrated; a fixed value would misrepresent
  fallback classifications as more reliable than they are.
- **Retrieval scoping:** search is filtered by the already-classified category
  before running, rather than searching all categories and filtering after.
- **Hybrid search:** vector search (semantic) + BM25 (keyword) merged via
  Reciprocal Rank Fusion, rather than vector-only. Chosen because documents
  are short and clean, and category filtering already narrows the search space
  significantly.
- - **Web-search fallback (CRAG retry):** built. Scoped to consumerfinance.gov
  via `site:` search operator (required switching from the deprecated
  `duckduckgo_search` package to its maintained fork, `ddgs`, since the
  deprecated version didn't reliably honor the `site:` operator). On success,
  replaces the local regulatory docs rather than appending to them.
- **Guidance documents:** the 5 complaint-handling guidance docs are
  self-written, modeled on realistic bank policy structure — not sourced from
  a real institution (real internal policies aren't public). Regulation docs,
  by contrast, are verbatim public-domain text from eCFR/consumerfinance.gov.

 - Own-letter review feature (own_letter_node, own_letter.py): lets the user write their own complaint letter instead of an AI draft, reusing critic_node and output_guardrail_node unchanged — no AI rewriting, just real feedback shown back to the user, capped at MAX_REVISIONS attempts. If still failing after that, the user chooses to send it as-is or fall back to the AI draft path, which routes straight into the existing drafting_agent → revision_loop pipeline with zero duplicated logic. This is terminal-only scaffolding (input()-based); the multi-line collection logic (read_multiline, END-terminated) will be replaced by a real text area once Streamlit is built, so no further effort should go into polishing terminal paste behavior.

 - own_letter.py / graph.py / main.py restructured from a single blocking app.invoke() call to interrupt() + Command(resume=...) + a checkpointer (langgraph.checkpoint.memory), specifically as groundwork for the planned FastAPI wrapper. A blocking input()-based loop can't survive across stateless HTTP requests; the checkpointer persists graph state between calls under a thread_id, so a future API can return control to the client at a human checkpoint and resume later from the same point. own_letter_node's single while-loop was split into five separate graph nodes (own_letter_input, own_letter_check, own_letter_revise, own_letter_exhausted, finalize_own_letter) so each interrupt() call sits alone in its own node with no LLM call hiding in front of it — this was required by LangGraph's resume semantics (a node that re-runs on resume would redundantly re-call the LLM before reaching its interrupt). This is the same pattern hitl_consent and hitl_final_review already used; own_letter.py was the one holdout still using a plain while-loop with no interrupt.

 