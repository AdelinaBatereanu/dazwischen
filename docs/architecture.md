# Architecture 🏗️

Dazwischen has one public MCP surface and three internal vertical MCP providers.

```text
ChatGPT / MCP Inspector
   |
   v
Public Proxy MCP /v1/mcp
   |
   +-- internal Mobility MCP
   +-- internal Internet MCP
   +-- internal Insurance MCP
```

The proxy is the reviewed ChatGPT-facing contract. Vertical MCPs provide internal candidate tools, but the proxy decides what becomes public.

## 🗺️ Code map

| Part | Code | Responsibility |
| --- | --- | --- |
| App composition | [`app/main.py`](../app/main.py) | Creates vertical clients, builds catalog, creates router, mounts `/v1/mcp`, registers review/debug routes. |
| Public MCP adapter | [`app/mcp_server.py`](../app/mcp_server.py) | Converts catalog tools to MCP tools and delegates calls to the router. |
| Internal vertical MCPs | [`app/vertical_mcp/`](../app/vertical_mcp/) | Mock Mobility, Internet, and Insurance MCP servers with tools/resources. |
| Catalog | [`app/catalog/`](../app/catalog/) | Builds the curated public catalog and internal route table. |
| Validation | [`app/validation/`](../app/validation/) | Accepts/rejects internal candidate tools with structured feedback. |
| Routing | [`app/routing/`](../app/routing/) | Validates runtime arguments, calls vertical MCPs, normalizes results/errors. |
| Observability/debug | [`app/observability/`](../app/observability/), [`app/api/`](../app/api/) | In-memory monitoring, sandbox, health, and debug endpoints. |

## 🚀 Startup flow

Implemented in [`app/main.py`](../app/main.py):

```text
create vertical MCP clients
  -> discover internal MCP tools
  -> validate candidates
  -> apply approved public mappings
  -> build catalog registry
  -> create router
  -> mount public MCP app at /v1/mcp
```

The catalog is built once at startup as a curated snapshot. The proxy does not live-forward every vertical tool to ChatGPT.

## 🔁 Tool call flow

Implemented mainly in [`app/mcp_server.py`](../app/mcp_server.py) and [`app/routing/router.py`](../app/routing/router.py):

```text
MCP call: search_mobility_options
  -> proxy catalog lookup
  -> argument schema validation
  -> internal route: mobility.search
  -> internal MCP call
  -> response safety check
  -> MCP structured result or safe error
```

The MCP adapter stays thin. It does not know vertical business logic and does not call verticals directly.

## 🔐 Public vs internal boundary

Public MCP endpoint:

```text
/v1/mcp
```

Public tools:

```text
search_mobility_options
compare_internet_plans
compare_insurance_offers
```

Internal vertical tools such as `book`, `order_plan`, `run_diagnostics_command`, `bind_policy`, and `quote_with_ssn` are not exposed in MCP `list_tools`. Their rejection reasons are visible through `/debug/validation-report` and explained in [`implementation.md`](implementation.md).

## Why this structure

- **Single MCP entry point:** ChatGPT integrates with one stable endpoint, not one MCP per vertical.
- **Clear team ownership:** verticals own internal MCP tools; the proxy owns public names, validation, versioning, and routing.
- **Controlled exposure:** a valid internal MCP tool is still hidden unless there is an approved public mapping.
- **Safe failure boundary:** vertical errors are converted into safe public error codes before returning to the MCP client.
- **Replaceable vertical transport:** current verticals are in-process mocks, but the proxy talks to them through [`VerticalMCPClient`](../app/vertical_mcp/base.py), so remote internal MCP clients could replace them later.

## Related docs

- Implementation details: [`implementation.md`](implementation.md)
- Practical review checklist: [`review-runbook.md`](review-runbook.md)
