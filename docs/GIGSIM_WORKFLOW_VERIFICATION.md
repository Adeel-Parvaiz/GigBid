# Full GigSim workflow verification

Verified on 14 November 2026 using real local Qwen, the HTTP API, authenticated marketplace MCP, our GigSim REST service, SQLite checkpoints and Chromium. The extended run includes Workspace MCP: all **27 checks passed**. Raw observations are in [results.json](../evals/results/gigsim_workflow/results.json).

| Requested verification | Observed result |
|---|---|
| Account → Connects → discovery → analysis | Registered a new application account; initial balance 100; jobs discovered; real model reached approval. |
| Approval → submission → outcome | Clicked Approve in Chromium after restart; submitted proposal; charged exactly 12 Connects; one synthetic outcome recorded. |
| Persistence | Abruptly killed API, MCP and GigSim, restarted against the same databases; account/session and pending payload survived. Killed/restarted again after submission; submitted status, balance, messages and outcomes survived. |
| Approval enforcement | No Connects spent and no submissions before approval; unauthenticated and different-user approvals rejected; repeated approval rejected without another charge. |
| Screenshots | Four actual Chromium screenshots saved below. |
| Workspace MCP | Three interview slots retrieved over MCP; no hold before approval; approval restored after restart; one tentative hold created after approval and persisted through another restart. |

Evidence screenshots:

- [Job inbox](../evals/results/gigsim_workflow/01-inbox.png)
- [Restored proposal awaiting approval](../evals/results/gigsim_workflow/02-restored-approval.png)
- [Submitted pipeline](../evals/results/gigsim_workflow/03-submitted-pipeline.png)
- [Messages after restart](../evals/results/gigsim_workflow/04-persisted-messages.png)

Reproduce from the configured WSL checkout with `python -m evals.runners.verify_gigsim_workflow`. This launches four isolated services on temporary ports and stops them afterward. The result confirms all ports closed. Credentials and working SQLite files stay in ignored local state; public evidence contains no session tokens.

Limitations: approval is scripted in a disposable synthetic marketplace, not a human user study or a real Upwork send. This demonstrates SQLite persistence; the assignment's separate Postgres checkpointer requirement remains unverified. The saved message was written directly to the sandbox to check persistence, rather than through a conversation-agent approval; conversation approval behavior has separate tests. The local setup connects one upstream marketplace account; different-user approval denial tests application run ownership, not per-user upstream OAuth/account routing.

## Exact assignment requirement check

The source [assignment PDF](../Assignment-II_AI-4016-GigBid.docx.pdf) explicitly requires external integration:

- Page 3: live mode uses official Upwork MCP; if a student has an Upwork account, GigBid must run against it. Live outcomes are not graded.
- Page 6, A4: connect through `MultiServerMCPClient` over Streamable HTTP, complete OAuth, encrypt tokens per user and map tools onto the common marketplace port. GigBid approval is followed by Upwork's required confirmation.
- Page 6, A5: use official Upwork MCPS plus another third-party server, with trust rationales.
- Page 11 describes an instructor-provided `gigsim/` directory that must not be modified. No such package was supplied here. Our implementation is separately located at `apps/gigsim/`.

Therefore, our simulator does **not** complete A4/A5. The live Upwork integration was subsequently implemented and authorized; see `docs/UPWORK_LIVE.md`. GitHub remains separate work. The dataset notice addresses dataset selection and documentation; it does not state that live integration is waived. The owned simulator is a useful local deliverable, but acceptance as a substitute for the provided grading service has not been established. This is a reading of the supplied assignment, not an instructor ruling.
