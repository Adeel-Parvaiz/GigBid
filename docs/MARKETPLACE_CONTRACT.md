# Marketplace HTTP integration

Update: the user requested a project-owned GigSim, which is now implemented and verified using `config/gigsim_contract.json`. See [our GigSim service](OWN_GIGSIM.md). The fixture discussion below describes the earlier adapter validation; the project now also tests its own actual service through authenticated MCP.

The REST adapter is tested through the actual authenticated marketplace MCP server. It requires an explicit API contract; no instructor GigSim contract or service was supplied. The fixture routes in `tests/fixtures/marketplace_http_contract.json` are local test routes, not claims about GigSim endpoints.

Configuration: `MARKETPLACE_MODE=gigsim`, `GIGSIM_API_URL`, `GIGSIM_CONTRACT` (JSON path), and optionally `GIGSIM_API_TOKEN`. The historical mode name selects the contract adapter; it does not establish instructor compatibility. Keep tokens outside source control.

The contract maps all nine marketplace operations to relative paths, request arguments, and response JSON pointers. The adapter refuses write previews when the contract cannot forward a dry-run flag. Write idempotency keys include the operation name. Failed writes are not retried unless the contract explicitly asserts verified upstream idempotency. Read retries are bounded. Provider response bodies are excluded from surfaced HTTP errors.

Validation exercises HTTP authentication, job/client/balance reads, preview without side effects, draft creation, repeated submission, thread reads, and repeated replies. The local fixture confirms one submission, one sent reply, and one Connects deduction despite repeated requests. This proves the adapter/MCP path against the fixture; actual provider behavior still needs its documented contract and an authorized sandbox.

The latest full regression run passed 109 tests with two infrastructure skips. Raw output is recorded in `evals/results/marketplace_contract_validation.json`.

## When an instructor service becomes available

Obtain its base URL, OpenAPI schema or equivalent request/response documentation, authentication instructions, and a sandbox account. Confirm the nine operation mappings, pagination, error shapes, dry-run behavior, Connects accounting, and idempotency semantics. Create a separate contract from that documentation; do not rename the fixture contract and assume compatibility. Run read-only smoke checks first, then sandbox previews and repeated writes against disposable records. Record actual responses, balance changes, and duplicate suppression before claiming compatibility. Production proposals or messages still require the normal approval gate.

Without those inputs, the deliverable is a tested local integration plus this explicit limitation. A locally implemented simulator can support development, but cannot establish compatibility with an unavailable instructor service.
