# Connected tools for the AI-FINDER agent

**Markdown recommendations only. No code, installations, or account connections are included.**

Give the freelancer agent access to external systems: portfolio websites, CV documents, repositories, calendars, and email. These proposals describe MCP servers and API integrations for the agent inside `freelancer_finder_clean`.

## Recommended connections

| Connection | Project use | Priority |
| --- | --- | --- |
| Firecrawl MCP | Search and extract public portfolio evidence | First |
| Docling MCP | Read supplied CVs and portfolio PDFs | First |
| GitHub MCP | Inspect linked software repositories | For developer portfolios |
| Playwright MCP | Navigate portfolio pages requiring interaction | When needed |
| Google Calendar API | Query connected calendars for free/busy intervals | After account linking |
| Resend email API | Send requested invitations | After an invitation workflow exists |
| Custom matching MCP server | Share your existing matching engine with multiple clients | Optional, later |

These priorities are project recommendations. Provider capabilities and setup sources appear in the [catalog](TOOL_CATALOG.md).

Start with **Firecrawl + Docling + the existing matching engine**. Add GitHub if software talent is in scope. Calendar and email need real account and invitation workflows.

## How tools connect

The Python application acts as the MCP host/client. It discovers server tools, supplies their definitions to the agent, executes requested operations, and returns results to the model. MCP standardizes that connection; matching and verification remain application responsibilities. See the [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture).

**Client request ? agent ? selected MCP/API connection ? evidence ? existing matching and checks ? supported recommendation.**

An MCP connection configured in an editor does not automatically reach the agent inside your product. The Python application needs its own MCP client, credentials, and connection lifecycle.

## Documents

- [Connected-tool catalog](TOOL_CATALOG.md): concrete providers and setup needs.
- [Integration instructions](INTEGRATION.md): connect them to the existing Python agent.
- [Roadmap](ROADMAP.md): build order and acceptance scenarios.
- [Agent guidelines](AGENT_GUIDELINES.md): source selection and evidence handling.

The existing SQLite records are fictional samples. External research should become traceable evidence; it should not silently associate real people with sample identities.
