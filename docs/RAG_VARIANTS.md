# B2 — Configurable RAG variants

B2 implements the mandatory V0 plus four additional variants covering every required group: **V1, V2, V3 and V8**. The optional V4–V7 and V9 are not needed for this coverage and are not claimed as implemented.

| ID | Component | Behavior |
|---|---|---|
| V0 | `rag/variants/v0_naive.py` | Fixed body chunks, one query containing the complete job post, normalized cosine similarity, top-k |
| V1 | `rag/variants/v1_decomposed.py` | One retrieval per extracted requirement, then deduplicate and merge using rank fusion |
| V2 | `rag/variants/v2_hybrid.py` | Independent BM25 and dense searches, reciprocal rank fusion rather than raw-score addition |
| V3 | `rag/variants/v3_rerank.py` | Retrieve a wider dense candidate pool, cross-encode query/document pairs and return top-k |
| V8 | `rag/variants/v8_corrective.py` | Actual LangGraph retrieve → grade → conditional re-query → grade → accept or refuse |

`rag/retriever.py` is the registry. Existing combined configurations (`v1_v2_hybrid_decomposed`, `v1_v2_v3`) also remain available. V2 and V3 now have separate component modules rather than implementations hidden inside the registry.

## Configuration and MCP discipline

Set `rag.variant` in `agent/config.yaml` or use the existing environment override, for example `GIGBID__rag__variant=v8_corrective`. Fixed chunk size/overlap are configured through `rag.chunk_size` and `rag.chunk_overlap` (defaults 1200/150 characters). The same chunks and ownership metadata are used across variants. Already-chunked items are not expanded into duplicate copies. Short sources keep their original ID; longer sources receive stable chunk IDs and `parent_evidence_id` identifies the original evidence item.

Use `rag.embedder=fastembed` and `rag.reranker=fastembed` for the real MiniLM embedding and cross-encoder backends. Hashing embeddings and the lexical reranker remain explicitly identified offline/CI alternatives; lexical ranking is not presented as cross-encoder inference. Missing real-model dependencies/artifacts fail visibly rather than silently using a lexical fallback. The embeddings extra is required for the real backends: `pip install -e ".[dev,embeddings]"`.

Agents still call Portfolio MCP only. Query decomposition and the corrective graph execute client-side, while dense/hybrid/rerank retrieval executes inside the server. The client sends the selected `retrieval_layer` in the validated search filters, and forwards neural model configuration to stdio servers through `PORTFOLIO_RAG_CONFIG`. Independently hosted HTTP servers must set that environment variable themselves; the query selects the layer, not arbitrary server models. The tenant filter remains enforced. Complete job queries are no longer silently truncated to 2000 characters; the server accepts queries up to 100,000 characters.

The Portfolio schema snapshot was intentionally updated for the optional retrieval-layer filter and parent evidence ID. This does not add tool permissions or write capabilities. Candidate ranking now applies the requested evidence type before retrieval, and score ties retain deterministic candidate order.

## V8's bounded corrective graph

The grader is an explicit lexical requirement-coverage rule, **not** a semantic LLM/NLI judge. `rag.corrective_min_coverage` defaults to 0.5. It filters unrelated hits and computes the fraction of requirements covered by the remaining evidence. When coverage is weak, a new query combines the full job context with the missing requirements. The graph performs at most one corrective retrieval, grades again, and returns an empty evidence list if the threshold is still unmet. Transport/tool errors propagate to the application's degraded handling.

`retrieve_with_trace` exposes the nodes visited, coverage, missing requirements and re-query. This makes correction/refusal inspectable rather than describing an ordinary Python retry function as a graph. Empty evidence prevents evidence-based claims; downstream bid/skip and proposal quality remain separately evaluated concerns. Lexical overlap can still mistake wording for relevance, especially with implied skills; no semantic-grounding guarantee is claimed.

## One-command real comparison

```bash
python -m evals.rd_b.compare_variants
```

This runs V0, V1, V2, V3 and V8 on the same development cases for all three personas, using cached real FastEmbed embeddings and the actual ONNX cross-encoder. It regenerates `evals/results/b2/trials.jsonl`, `summary.json` and [the comparison table](../evals/results/b2/comparison.md). Model artifact hashes and corpus/dev hashes are saved. To run an explicitly labeled offline diagnostic instead: `python -m evals.rd_b.compare_variants --embedder hashing --reranker lexical`.

The comparison includes 600 development jobs per variant (3000 retrieval trials). Relevance scores use the 338 cases with nonempty synthetic gold; the other cases remain in latency/refusal records. Gold IDs refer to source evidence, so ranked chunk IDs are mapped to their parent source and deduplicated for source-level metrics. Ten chunks are retrieved; this does not guarantee ten distinct sources. Shared warm caches affect latency. This original five-variant comparison had no preregistered hypothesis. A later one-factor V1+V2+V3 ablation has its own frozen protocol in [RD_B_PREREGISTRATION.md](RD_B_PREREGISTRATION.md) and results in [RD_B_ABLATION_RESULTS.md](RD_B_ABLATION_RESULTS.md); because it followed inspection of the earlier results, it is not an independent replication.

Measured aggregate Recall@5: V0 **0.2600**, V1 **0.3033**, V2 **0.3107**, V3 **0.2785**, V8 **0.3510**. V8 refused evidence for 262/600 cases. This is a retrieval refusal, not a scam or bid/skip judgment. Cross-encoder V3 had p95 retrieval latency of approximately **560 ms**, compared with **47 ms** for V8, and did not beat hybrid V2 on Recall@5. These development results do not automatically change the application's shipping default. The 88 source summaries are short enough to produce 88 chunks in this corpus; separate long-document tests exercise actual chunk splitting and metadata preservation.

## Verification

The full Python suite passed **163 tests**, with two infrastructure skips. New checks cover fixed chunks/metadata, full-post requests, MCP layer routing, rank fusion, bounded successful correction, refusal and outage propagation. The final focused rerun passed ten variant checks after making the coverage threshold configurable.

`python -m evals.rd_b.verify_mcp_variants` additionally runs all five variants over an official SDK MCP client with real neural models. It verifies tenant isolation, the requested server layers, the actual cross-encoder class and a real MCP-backed refusal trace. See [MCP verification](../evals/results/b2/mcp_verification.json) and [validation record](../evals/results/b2_validation.json). Original historical retrieval reports remain unchanged; use the B2 comparison for the current implementation.
