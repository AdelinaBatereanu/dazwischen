# Review Runbook 🔍

Use this as a quick checklist for inspecting a running deployment. The root [`README.md`](../README.md) explains what the project is; this file focuses on expected review checks and results.

## Public URL placeholders

```text
Base URL: TODO
MCP endpoint: TODO/v1/mcp
Demo video: TODO
```

## ✅ Quick smoke test

| Check | URL | Expected result |
| --- | --- | --- |
| Health/version | `/health` | `status: ok`, `proxy_version`, `catalog_version`, `public_endpoint_version`. |
| Public catalog | `/debug/catalog` | Exactly three public tools: mobility, internet, insurance comparison/search tools. |
| Validation report | `/debug/validation-report` | Accepted and rejected internal vertical candidates with reason codes. |
| Debug UI | `/debug-ui` | Human-readable dashboard loads. |
| Sandbox | `/sandbox` | Browser-based proxy-routed tool testing loads. |
| Vertical resources | `/debug/vertical-resources` | Internal manifests/rejection guidance are visible for review. |
| Hidden vertical MCPs | `/mobility/mcp`, `/internet/mcp`, `/insurance/mcp` | `404`, because vertical MCPs are not public. |

## 🔌 MCP Inspector checks

Connect MCP Inspector or ChatGPT to:

```text
BASE_URL/v1/mcp
```

Expected `list_tools` result:

```text
search_mobility_options
compare_internet_plans
compare_insurance_offers
```

Rejected/internal names such as `book`, `order_plan`, `run_diagnostics_command`, `bind_policy`, and `quote_with_ssn` should not appear.

## Example tool calls

### Mobility success

Tool:

```text
search_mobility_options
```

Arguments:

```json
{
  "origin": "Munich",
  "destination": "Berlin",
  "date": "2026-06-01"
}
```

Expected: successful structured result from the mocked Mobility MCP provider.

### Invalid arguments

Tool:

```text
search_mobility_options
```

Arguments:

```json
{
  "origin": "Munich"
}
```

Expected: safe `INVALID_ARGUMENTS` error.

## Vertical-filter checks

Use the same public MCP endpoint with a vertical filter:

```text
BASE_URL/v1/mcp?vertical=mobility
BASE_URL/v1/mcp?vertical=internet
BASE_URL/v1/mcp?vertical=insurance
```

Expected tools:

| Filter | Expected tools |
| --- | --- |
| `mobility` | `search_mobility_options` |
| `internet` | `compare_internet_plans` |
| `insurance` | `compare_insurance_offers` |

A call to a different vertical's tool through a filtered endpoint should return `TOOL_NOT_FOUND`.

## 🧪 Sandbox checks

Sandbox endpoints are useful if MCP Inspector is not available:

```text
GET  /debug/sandbox/tools
POST /debug/sandbox/invoke
```

Expected behavior:

- lists only accepted public tools
- supports optional vertical filtering
- invokes through [`ToolRouter`](../app/routing/router.py)
- records events with source `sandbox`
- never exposes rejected/internal tools

## Observability checks

After invoking tools, inspect:

```text
/debug/monitoring
/debug/verticals
/debug/recent-failures
/debug/conversations
```

Expected behavior:

- successful and failed calls are counted
- failures use safe error codes
- per-vertical status is visible
- conversation grouping works when `X-Conversation-ID` or sandbox `conversation_id` is provided

Implementation: [`app/observability/store.py`](../app/observability/store.py).

## 🚢 Final submission checks

Before sharing the repo/deployment:

- replace the TODO public URL and video URL in this file and root README
- confirm `/v1/mcp` is publicly reachable
- confirm direct vertical MCP paths return 404
- run `uv run pytest`
- run `uv run ruff check .`
