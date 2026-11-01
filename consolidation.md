# Conversation consolidation

## What is implemented

One **turn** means one user request plus the agent's model messages, tool activity, and final response. It does not mean one individual LangChain message. A turn with ten tool calls still counts once.

`chat_history.json`, beside `agent2.py`, contains at most five recent turns and one running summary. When a sixth request arrives, Python summarizes the previous five turns first, then begins a new batch with that request. The same happens before turns 11, 16, and so on. This is a five-turn **batch**, not a sliding window retaining the latest five raw turns after every request.

The file is outside `agent_workspace`, so the agent's filesystem tools cannot accidentally rewrite its own history. Python owns this file. The manually curated `agent_workspace/memory.md` remains separate.

## Files and responsibilities

- `chat_memory.py`: JSON persistence, callback recording, context replay, and the consolidation trigger.
- `agent_workspace/skills/chat-consolidation/SKILL.md`: the editable consolidation instructions. The name corrects the spelling in "chat_consoidation".
- `agent2.py`: creates the memory manager and calls `await chat_memory.run(agent, text, summary_model=llm)`.
- `tests/test_chat_memory.py`: offline lifecycle and integration tests.

No new dependencies are needed. The code uses LangChain messages, async callbacks, and the model's existing `ainvoke` interface.

## JSON structure and execution order

The initial file is:

```json
{
  "schema_version": 1,
  "summary": null,
  "next_turn_id": 1,
  "turns": []
}
```

Each turn has a monotonically increasing `turn_id`, a timestamp, status, `messages`, and `events`.

**Messages** use LangChain's own serialization. They retain message types, AI tool-call arguments and IDs, tool results, and the final answer. These are replayed into the next invocation. Previously supplied history is excluded when saving the new turn.

**Events** record what the application observed, in numbered sequence within each turn:

```text
1 user_message
2 ai_message        (includes requested tool calls)
3 tool_start        (run A)
4 tool_start        (run B)
5 tool_end          (run B)
6 tool_end          (run A)
7 ai_message
8 turn_completed
```

Read the total ordering as `(turn_id, sequence)`. UTC timestamps aid inspection; sequence is the ordering authority. Tool starts and completions share a callback `run_id`. AI message tool calls and ToolMessages also retain LangChain's separate `tool_call_id`. Parent run IDs on starts/model outputs help identify nested runs.

Parallel calls may overlap, as above. The event list records callback arrival order, not an invented serial execution order or the remote server's internal timing. AI events are recorded when complete model responses arrive, not token by token. `turn_completed` repeats the final message as a convenient outcome marker; it is not another model call. The replay message list may place parallel tool results in a different order than their completion events.

## Consolidation strategy

Before the next batch, a separate, tool-free model invocation receives the skill as its instructions and the previous summary plus recent turns as JSON data. This is deterministic application routing: the research agent does not decide whether to invoke the skill.

The summary uses six sections: goals and constraints, confirmed facts/preferences, decisions/corrections, tool findings/artifacts, open questions, and a brief chronological record. It aims for 500–800 words, or fewer when sufficient. This is a prompt target, not an enforced token limit.

It preserves exact useful names, numbers, units, variants, paths, sources, explicit preferences, unresolved work, and uncertainty. Later explicit corrections supersede older claims. Suggestions are not converted into preferences. Tool failures and unconfirmed writes remain failures or attempts. Repetition and large raw payloads are compressed into findings with provenance.

The old summary is merged into each new summary, preventing earlier batches from disappearing wholesale. Summary content is replayed as historical conversation context, not promoted into system-level instructions. Current instructions and user corrections still govern the agent.

## Why this approach follows established practice

LangChain describes shortening growing conversation context by trimming or summarizing messages, and normally persists graph state with a checkpointer. Summarization retains useful context that simple deletion would lose. This implementation adopts that principle but uses an intentionally small JSON adapter to meet the requested storage format. It is not a LangGraph checkpointer and does not restore full graph execution state. See [LangChain short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory).

LangGraph's running-summary example extends an existing summary with new history. That is the basis for merging old and new context here. See [LangGraph memory guidance](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/add-memory.mdx).

LangMem explicitly keeps matching tool results with tool-call messages when summarizing. We consolidate whole turns and replay only complete turns, preserving those relationships instead of cutting an arbitrary number of messages. See [LangMem summarization reference](https://langchain-ai.github.io/langmem/reference/short_term/).

Five turns is your experimental policy, not a universal best-practice threshold. Token-based triggers and retention of a few recent raw turns are common alternatives. The summary's sections and word target are implementation choices designed for this research agent, not claims that LangChain requires this exact format.

## Failure handling and limits

Each event is saved immediately using a temporary file and atomic replacement. A failed summary call or empty response leaves the existing batch on disk and stops the new request. Failed agent turns retain their events but are excluded from raw context replay. On restart, a previously running turn becomes interrupted. Failed/interrupted attempts count toward the batch limit and are included as incomplete attempts in consolidation.

This supports one local conversation with one writer. Do not run two agent processes against the same file. It is not a transactional database or a crash-resumable workflow engine. If a crash occurs between an external tool action and its callback, the file cannot prove that action's outcome.

Summaries are lossy and can drift. After successful consolidation, the old raw batch is removed; exact old execution order survives only in the coarse summary. Use a separate append-only archive or LangSmith if you later need permanent audit logs. Five turns can still contain huge tool outputs, and this version does not enforce a token budget. Deep Agents' own within-run context management is separate; if it removes the current user message from returned state, this adapter fails the turn rather than silently saving incorrect replay history.

The JSON contains raw user and tool content and is ignored by Git. The summarizer is instructed not to repeat credentials, but raw logging is not a redaction system. Consolidation uses the configured CampusAI model, which receives the stored batch.

## How to experiment

- Run `.venv/bin/python agent2.py` in WSL. Each run of the existing script adds its configured `text` as a new turn; it does not become an interactive chat loop.
- Change `max_turns=5` in `agent2.py` to change the batch size.
- Edit the consolidation skill to change what survives compression.
- Pass another LangChain chat model as `summary_model` to separate research and summarization models.
- Replace `consolidate()` to try another policy, or replace `JsonChatMemory` later with a LangGraph checkpointer and summarization middleware. Avoid running both history replay mechanisms at once.
- Move or rename `chat_history.json` while the agent is stopped to start a fresh conversation without deleting the old one.

Validation: six offline tests cover reload/replay, overlapping tool completion order, the sixth-turn trigger, recursive consolidation, summary failure preservation, failed-turn exclusion, malformed JSON, and a real Deep Agents graph with a fake model and local file tool. No paid model or remote MCP request was used. These tests verify mechanics, not the semantic quality of real model summaries.
