# Documentation 📚

This folder keeps the project documentation compact. The root [`README.md`](../README.md) is the main landing page; these docs provide focused implementation details.

## 🧭 Reading path

| Document | Purpose |
| --- | --- |
| [`architecture.md`](architecture.md) | High-level architecture, code map, startup flow, tool call flow, and public/internal boundary. |
| [`implementation.md`](implementation.md) | Public MCP surface, internal vertical MCPs, catalog/versioning, validation, routing, and safe errors. |
| [`review-runbook.md`](review-runbook.md) | Practical smoke tests, MCP Inspector checks, vertical-filter checks, sandbox checks, and final submission checklist. |

## Main code areas

```text
app/
  main.py              FastAPI composition root
  mcp_server.py        public MCP adapter
  vertical_mcp/        internal mocked vertical MCP providers
  catalog/             public catalog building and registry
  validation/          conformance checks and reports
  routing/             tool invocation routing and safe errors
  observability/       in-memory monitoring store
  api/                 health, debug, sandbox, and UI routes
  models/              shared Pydantic contracts
```

## 🔍 Most useful endpoints

```text
/v1/mcp                         public MCP endpoint
/health                         health and version metadata
/debug-ui                       human-readable debug dashboard
/debug/catalog                  active public catalog and routes
/debug/validation-report        accepted/rejected candidate tools
/debug/monitoring               call/error/latency summary
/debug/verticals                per-vertical status
/debug/recent-failures          sanitized failure timeline
/debug/conversations            conversation-level tool usage
/debug/vertical-resources       internal vertical MCP resources
/sandbox                        browser sandbox for proxy-routed calls
```

For older working notes and drafts, see [`docs_old/`](../docs_old/).
