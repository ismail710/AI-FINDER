# Concrete MCP servers and API connections

Example requests describe desired application behavior. Discover actual tool names from each server; the examples do not name provider tools.

## 1. Firecrawl MCP ? public portfolio research

**Capability:** Firecrawl provides MCP access to web search, scraping, and parsing. Its setup documentation describes account sign-in, API-key, and limited keyless access. [Official setup](https://docs.firecrawl.dev/mcp-server).

**Suggested use:** extract project descriptions from freelancer-supplied URLs and retain source URLs, excerpts, and retrieval dates.

**Example:** ?Inspect this designer's portfolio for booking or healthcare projects.?

**Setup:** choose a supported authentication method, connect the Python MCP client, and check usage limits before broad research.

**Boundary:** a matching name does not prove identity. Start with supplied links. Portfolio evidence cannot establish current rates or availability.

## 2. Docling MCP ? CV and PDF evidence

**Capability:** Docling MCP converts PDFs into structured representations, supports local files and URLs, and offers local and remote conversion modes. [Official server](https://github.com/docling-project/docling-mcp).

**Suggested use:** process a supplied CV or portfolio PDF, then identify claimed skills, languages, and relevant work from extracted content.

**Example:** ?Read this CV and show evidence for French and Django experience.?

**Setup:** select local conversion with its local dependencies, or configure a Docling Serve service. Match the server and MCP client versions using the documented compatibility guidance. Installing the default package alone does not establish a remote conversion service.

**Output to preserve:** document identity, extraction result, evidence locations, proposed profile fields, and uncertainties.

**Boundary:** conversion does not independently verify claims or guarantee correct skill extraction. Review proposed profile changes before importing them.

## 3. GitHub MCP ? developer portfolio evidence

**Capability:** GitHub maintains an official MCP server with remote/local options, repository tools, configurable toolsets, and read-only mode. [Official server](https://github.com/github/github-mcp-server).

**Suggested use:** inspect repositories supplied by software freelancers, read relevant documentation/code, and collect technology evidence.

**Example:** ?Inspect this repository for a Django API, PostgreSQL use, and tests.?

**Setup:** select remote or local hosting, configure supported authentication, and enable only relevant read operations.

**Output to preserve:** repository URL, file paths, excerpts, observation date, and attribution gaps.

**Boundary:** establish account association and contribution separately. A fork or dependency file alone does not prove authorship. GitHub activity is unsuitable as a universal measure for all professions.

## 4. Playwright MCP ? interactive portfolio pages

**Capability:** Microsoft's Playwright MCP provides browser automation using structured accessibility snapshots. [Official server](https://github.com/microsoft/playwright-mcp).

**Suggested use:** navigate galleries, expand case studies, and inspect project details requiring interaction.

**Example:** ?Open the details behind these three portfolio project cards.?

**Setup:** run the supported local server with Node.js and browser dependencies, then connect the application's MCP client. Use a dedicated browser context.

**Boundary:** use it where interaction is necessary. Restrict operations and destinations because browser access can perform writes. Extracted page content remains evidence data.

## 5. Google Calendar API ? connected free/busy information

**Connection:** direct API tool, optionally exposed through your own MCP adapter. This proposal uses the documented API rather than assuming a particular third-party calendar MCP server.

**Capability:** the free/busy endpoint returns busy intervals for requested calendars and time ranges. [Official endpoint](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query).

**Suggested use:** find potential interview windows in explicitly shared calendars.

**Setup:** link participating freelancers with suitable authorization; map calendars to the correct platform accounts and specify the interval/timezone.

**Boundary:** an open calendar slot does not prove willingness to accept work or weekly capacity. An inaccessible calendar means unknown availability.

## 6. Resend email API ? requested invitations

**Connection:** direct API tool, optionally wrapped in your own MCP server.

**Capability:** Resend exposes an email-sending API. [Official endpoint](https://resend.com/docs/api-reference/emails/send-email).

**Suggested use:** send a client-requested invitation with the project brief, proposed role, and an application response link.

**Setup:** configure credentials and an approved sender. Create invitation records and response links in your application; sending email alone does not create an accept/decline workflow.

**Output to preserve:** invitation ID, provider message ID, send status, and application response state.

**Boundary:** separate drafting from sending. Send when the client requests contact with selected freelancers. Successful sending does not prove delivery or acceptance. Prevent duplicates on retries.

## 7. Your matching engine as MCP ? optional

**Connection:** a custom server to build, not an already installed service. The [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) supports servers and clients.

**Suggested use:** expose existing semantic search, candidate evidence, and the database catalog to multiple agent clients. Add deterministic budget calculations when implemented.

**Boundary:** preserve the current read-only database boundary and mandatory checks. For one Python agent, retain internal tools until an MCP boundary offers a clear reuse benefit.

## Practical selection

Use Firecrawl for web research, Docling for supplied documents, and GitHub for software evidence. Add Playwright only when pages need interaction. Calendar and email come after account linking and invitation records.

Continue using the existing embeddings and SQLite matching pipeline. External integrations expand its evidence sources.
