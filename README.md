title: Dazwischen
emoji: 🔌
colorFrom: gray
colorTo: green
sdk: docker
pinned: false

# Dazwischen 🔌  

**Dazwischen** is a ChatGPT-facing MCP proxy demo for aggregating multiple internal CHECK24-style vertical MCP providers behind one public endpoint. It shows how one reviewed MCP surface can curate, validate, version, route, and observe tools owned by separate vertical teams.

```text
ChatGPT / MCP Inspector
   |
   v
Public Proxy MCP /v1/mcp
   |
   +-- internal Mobility MCP server
   +-- internal Internet MCP server
   +-- internal Insurance MCP server
```

ChatGPT connects only to the proxy. The vertical MCP servers are internal providers and are not mounted as separate public endpoints.

---

## 🎯 What this demonstrates

The proxy is the public product contract. Internal vertical MCP tools are treated as candidates, not automatically exposed tools.

The proxy owns:

- the public MCP endpoint: `/v1/mcp`
- public tool names and descriptions
- catalog curation and approved mappings
- conformance validation and rejection feedback
- version metadata
- deterministic routing to internal vertical MCPs
- safe public error responses
- lightweight observability and sandbox/debug surfaces

The vertical MCP providers own:

- internal tool names and implementations
- internal MCP tool descriptors
- vertical-owned metadata such as internal version and safety attestation
- internal resources such as manifests and rejection guidance

---

## 📜 Public tool catalog

The public catalog is deliberately small and curated:

| Public MCP tool | Internal route | Purpose |
| --- | --- | --- |
| `search_mobility_options` | `mobility.search` | Search mobility options for a trip. |
| `compare_internet_plans` | `internet.check_availability` | Compare available home internet plans. |
| `compare_insurance_offers` | `insurance.quote` | Compare indicative insurance offers. |

Internal tools such as `book`, `order_plan`, `run_diagnostics_command`, `bind_policy`, and `quote_with_ssn` are intentionally not exposed. They remain visible in the validation report so reviewers and vertical teams can see why the proxy withheld them.

---

## 🧭 Key design choices

### One public MCP boundary

`/v1/mcp` is the only ChatGPT-facing MCP endpoint. Mobility, Internet, and Insurance run as internal mocked MCP servers behind the proxy.

### Curated catalog

The proxy does not concatenate every vertical tool into one public list. A tool becomes public only if it:

1. passes proxy conformance validation, and
2. has an explicit approved public mapping.

Approved mappings are keyed by:

```text
(vertical, upstream_tool, internal_version)
```

This prevents internal vertical changes from silently changing the public ChatGPT-facing contract.

### Actionable validation feedback

Rejected tools are not silently dropped. They appear in:

```text
GET /debug/validation-report
/debug-ui/validation-report
```

Each rejected candidate includes stable issue codes, human-readable messages, and fields to fix.

### Safe routing boundary

When a public tool is called, the router validates arguments, calls the correct internal MCP provider, checks the structured response, and returns either normalized data or a safe error code. Raw upstream exceptions, hostnames, stack traces, and secrets are not exposed to MCP clients.

### Vertical testing through the proxy

Vertical teams can test an isolated view without bypassing the proxy:

```text
/v1/mcp?vertical=mobility
/v1/mcp?vertical=internet
/v1/mcp?vertical=insurance
```

The filter shows only that vertical's accepted public tools. Rejected tools stay hidden, and cross-vertical calls are blocked with a safe `TOOL_NOT_FOUND` error.

---

## 🔍 Review surfaces

When the app is running, these are the useful review URLs:

| URL | Purpose |
| --- | --- |
| `/v1/mcp` | Public MCP endpoint for ChatGPT / MCP Inspector. |
| `/health` | Health and active version metadata. |
| `/debug-ui` | Human-readable debug dashboard. |
| `/debug/catalog` | Active public catalog and internal routes for review. |
| `/debug/validation-report` | Accepted/rejected candidate tools with reasons. |
| `/debug/monitoring` | In-memory call counts, latency, and error summary. |
| `/debug/verticals` | Per-vertical status summary. |
| `/debug/recent-failures` | Sanitized recent failed invocations. |
| `/debug/conversations` | Tool usage grouped by provided conversation ID. |
| `/debug/vertical-resources` | Internal vertical MCP resources for review. |
| `/sandbox` | Browser sandbox for proxy-routed tool testing. |

Debug and sandbox routes are included for challenge review and local development. In production they should be protected, restricted, or disabled.

---

## Version metadata

The active catalog exposes version information through `/health` and `/debug/catalog`:

```json
{
  "proxy_version": "1.0.0",
  "catalog_version": "2026-05-02.1",
  "public_endpoint_version": "v1",
  "internal_contract_version": "1.0"
}
```

Version meanings:

- `public_endpoint_version`: URL-level public MCP endpoint version, currently `/v1/mcp`.
- `proxy_version`: implementation version of the proxy application.
- `catalog_version`: reviewed public tool catalog version.
- `internal_contract_version`: proxy-to-vertical candidate contract version.
- vertical `internalVersion`: vertical-owned internal tool contract version.

A new internal vertical tool version is not exposed automatically. The proxy team must approve a new mapping and release a catalog update.

---

## 🛠️ Local development

Prerequisites:

- Python 3.14+
- `uv`

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
```

Start the app locally:

```bash
uv run uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/debug-ui
http://127.0.0.1:8000/sandbox
http://127.0.0.1:8000/v1/mcp
```

---

## Docker

Build and run:

```bash
docker build -t dazwischen .
docker run --rm -p 7860:7860 dazwischen
```

Then open:

```text
http://127.0.0.1:7860/health
```

---

## Project structure

```text
app/
  main.py              FastAPI composition root
  mcp_server.py        thin public MCP adapter

  vertical_mcp/        internal Mobility, Internet, Insurance MCP providers
  catalog/             public catalog building, registry, version metadata
  validation/          conformance checks and validation reports
  routing/             deterministic invocation routing and safe errors
  observability/       in-memory monitoring/conversation store
  api/                 health, debug, sandbox, and UI routes
  models/              shared Pydantic contracts
  static/              debug UI and sandbox pages

tests/                 focused behavior and architecture tests
docs/                  deeper architecture notes
```

---

## 🔒 Security and scope

OAuth and production authentication are intentionally out of scope for this demo. The important security boundary is still modeled:

- ChatGPT can reach only the proxy MCP endpoint.
- Vertical MCP providers remain internal.
- Unsafe, destructive, internal/debug, and sensitive-data tools are withheld.
- Runtime arguments are schema-validated before vertical invocation.
- Upstream errors are normalized into safe public error codes.
- Debug endpoints are demo/review aids, not production-public APIs.

A production rollout would add authentication, authorization, audit logs, approval workflows, persistent observability, rate limiting, secret management, and stricter data classification.

---

## 📚 Documentation

More detailed notes are available in `docs/`:

- [`docs/README.md`](docs/README.md) — documentation index
- [`docs/architecture.md`](docs/architecture.md) — architecture, code map, startup flow, and public/internal boundary
- [`docs/implementation.md`](docs/implementation.md) — MCP surface, verticals, catalog, validation, routing, and errors
- [`docs/review-runbook.md`](docs/review-runbook.md) — practical smoke tests, MCP Inspector checks, sandbox checks, and submission checklist

---

## 🔗 Review links

[Public deployment URL](https://huggingface.co/spaces/adelinabatereanu/dazwischen)  
[Demo video URL](https://www.youtube.com/watch?v=ToLgsJfJ-JM)
