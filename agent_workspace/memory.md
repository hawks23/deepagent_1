# Persistent research memory

## Confirmed project context
- This is a Python research agent built with create_deep_agent.
- The model is configured through CAMPUSAI environment variables; credentials belong in environment configuration, never in this file.
- Remote MCP configuration and discovery are managed in tools/mcp/test_mcp.py.
- Configured server names: langchain_docs, fastmcp_docs, and perfume-finder.
- internet_search provides general web research.
- FilesystemBackend uses agent_workspace as its virtual root. Agent path /perfume.txt maps to agent_workspace/perfume.txt.

## Conversation persistence
- chat_memory.py manages chat_history.json beside agent2.py for one local conversation.
- Up to five turns retain full messages and ordered events. Before the next turn, Python merges the batch with the running summary using skills/chat-consolidation/SKILL.md.
- This automatic conversation history is separate from this manually curated memory file.

## Confirmed user preferences
- No durable personal preferences have been recorded yet.

## Maintenance
- Last initialized: 2026-10-30.
- Add only confirmed information useful across future tasks.
- Store research findings and citations in task output files, not here.
- Correct outdated context when configuration changes are confirmed.
