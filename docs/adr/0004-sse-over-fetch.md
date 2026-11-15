# 0004 SSE via fetch, stream ends at the approval gate
EventSource cannot send Authorization. The stream closes at `interrupt`/`done`; the client reconnects with `after=<seq>` after a decision. Pending approvals are read from the checkpoint, so refresh and API restart lose nothing.
