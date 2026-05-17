# Implementation ⚙️

This file explains the main implementation pieces behind the proxy. For the high-level diagram and flow, see [`architecture.md`](architecture.md).

## 🌐 Public MCP surface

The only ChatGPT-facing MCP endpoint is:

```text
/v1/mcp
```

Implementation: [`app/mcp_server.py`](../app/mcp_server.py), mounted from [`app/main.py`](../app/main.py).

MCP `list_tools` returns only the curated public tools:

```text
search_mobility_options
compare_internet_plans
compare_insurance_offers
```

The adapter converts [`PublicTool`](../app/models/tools.py) into MCP `Tool` objects and delegates tool calls to [`ToolRouter`](../app/routing/router.py). It does not call vertical MCPs directly.

## 🧩 Internal vertical MCPs

Mock vertical providers live in [`app/vertical_mcp/`](../app/vertical_mcp/):

| Vertical | Accepted internal tool | Public tool | Rejected/internal tools |
| --- | --- | --- | --- |
| Mobility | `search` | `search_mobility_options` | `book` |
| Internet | `check_availability` | `compare_internet_plans` | `order_plan`, `run_diagnostics_command` |
| Insurance | `quote` | `compare_insurance_offers` | `bind_policy`, `quote_with_ssn` |

The proxy talks to them through [`VerticalMCPClient`](../app/vertical_mcp/base.py), currently implemented by [`InProcessVerticalMCPClient`](../app/vertical_mcp/adapters.py). This keeps the rest of the proxy independent from whether vertical MCPs are in-process mocks or remote private MCP servers.

Vertical tools include metadata used by the proxy adapter:

```text
vertical/internalVersion
vertical/safeToExpose
```

`safeToExpose=true` is not enough for public exposure; validation and approved catalog mapping are still required.

## 🗂️ Catalog and versioning

The public catalog is built by [`CatalogBuilder`](../app/catalog/builder.py) and served by [`CatalogRegistry`](../app/catalog/registry.py).

A vertical candidate becomes public only if:

1. it passes conformance validation, and
2. an approved mapping exists for its exact identity:

```text
(vertical, upstream_tool, internal_version)
```

Current mappings are defined in [`DEFAULT_APPROVED_PUBLIC_MAPPINGS`](../app/catalog/builder.py):

```text
("mobility", "search", "1.0") -> search_mobility_options
("internet", "check_availability", "1.0") -> compare_internet_plans
("insurance", "quote", "1.0") -> compare_insurance_offers
```

Version metadata comes from [`CatalogVersionProvider`](../app/catalog/versioning.py) and is visible through `/health` and `/debug/catalog`:

```json
{
  "proxy_version": "1.0.0",
  "catalog_version": "2026-05-02.1",
  "public_endpoint_version": "v1",
  "internal_contract_version": "1.0"
}
```

This means a vertical can change an internal tool version without automatically changing the public ChatGPT-facing catalog.

## ✅ Validation and feedback

Validation is implemented in [`app/validation/conformance.py`](../app/validation/conformance.py).

The validator checks candidate tools for:

- required identity and version fields
- useful descriptions
- object-shaped JSON input schemas
- unsafe/destructive actions
- internal/debug/private leakage
- sensitive data collection
- vertical safety attestation

Rejected tools appear at:

```text
/debug/validation-report
/debug-ui/validation-report
```

Each rejection includes a stable issue code, message, and field to fix. The rejected tools are intentionally included in the demo to show that the proxy can discover internal tools and withhold unsafe ones instead of exposing everything.

Validation models: [`app/models/validation.py`](../app/models/validation.py).

## 🛡️ Routing and safe errors

Routing is implemented in [`app/routing/router.py`](../app/routing/router.py).

Runtime flow:

```text
public tool name
  -> catalog lookup
  -> JSON Schema argument validation
  -> internal ToolRoute lookup
  -> VerticalMCPClient.call_tool(...)
  -> structuredContent safety check
  -> ToolResult
```

Safe error codes are defined in [`app/routing/errors.py`](../app/routing/errors.py):

| Code | Meaning |
| --- | --- |
| `TOOL_NOT_FOUND` | Unknown public tool or blocked cross-vertical filtered call. |
| `INVALID_ARGUMENTS` | Runtime arguments do not match the public schema. |
| `VERTICAL_UNAVAILABLE` | Configured route points to a missing vertical client. |
| `UPSTREAM_TIMEOUT` | Internal MCP call timed out. |
| `UPSTREAM_ERROR` | Internal MCP call failed or returned an MCP error. |
| `MALFORMED_UPSTREAM_RESPONSE` | Upstream response was not safe structured JSON. |

The router records safe observability metadata but does not expose raw exceptions, stack traces, or private hostnames to MCP clients.

## Relevant tests

- [`tests/test_mcp_app.py`](../tests/test_mcp_app.py)
- [`tests/test_vertical_mcp.py`](../tests/test_vertical_mcp.py)
- [`tests/test_catalog.py`](../tests/test_catalog.py)
- [`tests/test_validation.py`](../tests/test_validation.py)
- [`tests/test_routing.py`](../tests/test_routing.py)
- [`tests/test_vertical_testing_mode.py`](../tests/test_vertical_testing_mode.py)
