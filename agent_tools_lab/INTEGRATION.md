# Connecting tools to the existing Python agent

These are future implementation instructions. No packages or connections have been configured.

## 1. Add an MCP client to the application

Keep Ollama as the model provider and LangChain as the orchestrator. Add a backend MCP client layer to connect to servers and load selected tools.

Current LangChain documentation offers `MCPAdapter`, which discovers tools for `create_agent`. Its `langchain.mcp` namespace requires `langchain[mcp]>=1.4.0` and is beta. Earlier integrations use `langchain-mcp-adapters`; select a compatible integration and consult migration guidance. [Official MCP guide](https://docs.langchain.com/oss/python/langchain/mcp).

The project currently declares `langchain>=1.0.0` without an MCP dependency. That lower bound does not establish that the newer adapter is installed. Check and pin compatible versions during implementation.

## 2. Define each connection

Record purpose, approved operations, official server package/address, transport, authentication, credential source, runtime dependencies, timeout, and result limits.

Use local stdio for appropriate subprocess servers and Streamable HTTP for supported remote endpoints. Keep credentials in backend configuration. Per-user calendar access needs account-specific authorization.

Editor MCP settings provide tools to that editor's agent. Your product's Python agent needs its own setup.

## 3. Connect, discover, select, execute

Establish the session, discover tools, allowlist needed operations, and pass definitions to the agent. Validate requested arguments, execute through the client, normalize results, and return evidence to the model.

Use discovered provider names. Do not expose every operation or invent tool names. Limit calls and result sizes so the local model receives manageable evidence.

## 4. Wire the existing routes

| Current area | Suggested integration |
| --- | --- |
| `agent/service.py` | Client lifecycle, approved external tools, execution limits |
| `matching/planner.py` | Decide whether stored data suffices or external evidence helps |
| `matching/search.py` | Preserve retrieval and database requirement checks |
| `matching/review.py` | Review external citations alongside stored evidence |
| `data/memory.py` | Preserve validated requirements through research/follow-ups |
| Maintenance workflow | Review/import evidence and refresh affected embeddings |

The automatic matching route currently plans and invokes the reviewed workflow directly. Adding MCP tools only to the generic agent's registry will not make them run throughout that route. Introduce an explicit research step where useful, and pass its evidence to review.

Start with ?inspect this supplied portfolio URL.? Keep stored-data matching working when optional research fails.

## 5. Separate research from importing data

External results first become evidence records: source, retrieval time, candidate association, and excerpt. Proposed profile updates pass through normalization and review before a separate authorized import.

Confirm identity before merging sources. A portfolio page should not silently replace rates or availability. Preserve provenance and refresh affected vectors after approved changes to embedded content.

## 6. Use direct APIs where appropriate

Calendar and email API wrappers can be callable tools without MCP. Use MCP when a standard connection to multiple clients/services is useful.

Resolve the correct linked calendar account and interval. For sending, require an explicit client request, create a durable invitation, and retain its provider ID. Keep budget arithmetic in deterministic application logic.

## 7. Verify actual execution

Check connection, discovery, approved tool execution, cited evidence, and a real agent-selected call. Then check that existing hard requirements remain enforced.

Record tool name, result status, latency, and evidence references. Server startup alone does not prove the integration works. A model's final prose alone does not prove a tool ran.
