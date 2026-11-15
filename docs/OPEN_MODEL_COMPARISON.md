# Real open-model comparison

The `open` and `paid` sections in `agent/config.yaml` are model-routing profiles, not evidence of two measured configurations. `.env.example` contains example settings, not credentials or completed results. Historical heuristic evaluations remain labelled as such.

`evals.runners.open_model_comparison` runs the real `OpenAICompatLLM` through the bid graph, stopping at human approval. It compares two model tags on identical seeded development jobs for all three personas. It holds the graph, prompts, retrieval and verification constant. Per-job output includes model calls, reported token usage, latency, decisions, final proposals and schema/HTTP failures. Failed jobs reduce overall accuracy; they are never replaced with heuristic responses. Final-pass unsupported-claim metrics use the existing lexical verifier and are not human judgments.

Example for a CPU/GPU-constrained local machine:

```bash
python -m scripts.local_models
python -m evals.runners.open_model_comparison \
  --models qwen25-15b qwen25-05b --base-url http://localhost:11435/v1 \
  --hardware 'NVIDIA RTX 4050 Laptop GPU 6GB; Intel i5-13420H; WSL2 7.6GiB RAM; CUDA12.8; llama.cpp b12359' \
  --local --limit 20 --exclude-from evals/results/open_model_exclusions.json \
  --out evals/results/open_model_comparison_after_guards.json
```

The default is all 200 development jobs per persona per model (1,200 graph runs). `--limit` creates a seeded subset and its value is recorded; a subset must not be reported as the full development set. Use a separate output file for pilots. `--resume` continues the same configuration without repeating completed attempts, including failures. It rejects changed data or configuration. Each attempt is saved atomically so interrupted evaluations retain their evidence.

Local inference is recorded as zero API charges, not zero total operating cost. Hardware and electricity are not priced. Completion tokens divided by HTTP wall time measures observed service throughput, including prefill and overhead, rather than pure decoder speed. Model loading and schema repairs are included in latency. Unknown provider token usage remains unknown. Historical results are not overwritten.

The selected initial models are [Qwen2.5 0.5B](https://ollama.com/library/qwen2.5:0.5b) and [Qwen2.5 1.5B](https://ollama.com/library/qwen2.5:1.5b), both distributed with Apache 2.0 license text in the Ollama library. This is a practical small-model comparison, not a claim that either is the best available model. Model digests and the installed runtime version must accompany actual results.

Limitations: development gold is generated synthetic/rule-derived data, retrieval uses the existing hashing baseline, verification is lexical, and neither instructor tests nor real marketplace outcomes are measured here. A calibrated judge and human panel remain separate requirements.

## Current local installation

The WSL project uses the official llama.cpp `b12359` Linux CUDA 12.8 release and matching CUDA runtime archive, unpacked under `.local-models/llama-gpu`. The OpenMP library comes from Ubuntu's `libgomp1` package unpacked under `.local-models/ubuntu-runtime`; system packages were not changed. Model GGUF weights were downloaded from the Ollama registry and linked under `.local-models/gpu-models`. The server binds only to `127.0.0.1:11435` and offloads model layers to the RTX 4050. Runtime aliases are `qwen25-15b` (Qwen2.5 1.5B) and `qwen25-05b` (Qwen2.5 0.5B).

The earlier CPU-only setup and risk-prompt pilot are preserved as partial diagnostic results; their latency and token totals are not mixed into the final GPU comparison. All 19 persona/job pairs in those saved pilots are excluded from final sampling. Risk prompt calibration examples and explicit schema text were added before the final run. Prompt/client hashes are recorded in its metadata.

Start the existing installation with `python -m scripts.local_models`. Then `python -m scripts.run_dataset` loads the project `.env` without overriding already-exported variables. Restarting a terminal does not require downloading models again. The `.local-models` directory is ignored by Git and Docker; it is a local runtime, not part of the submission's source code. Generate the report with `python -m evals.analyze_open_models` after completion; it refuses incomplete results.

For another machine, install llama.cpp or Ollama using their official instructions, obtain the same model weights, record the runtime version/digests and adjust `--base-url`. `scripts.local_models` is a launcher for this specific WSL installation, not a general package installer.

## Completed local run

The paired GPU study completed 120 attempts (60 per model). See [OPEN_MODEL_RESULTS.md](OPEN_MODEL_RESULTS.md) for all measured metrics and the selection rule. Qwen2.5 1.5B was selected and saved in the ignored local `.env` for all six LLM nodes. The launcher now uses the real `openai_compat` backend. Full WSL validation recorded 93 passed and 2 skipped tests, successful repository rules, dataset loading and API startup. Raw validation output is in `evals/results/open_model_validation.json`.

Subsequent real API verification exposed additional guard defects; see [REAL_AGENT_BEHAVIOUR.md](REAL_AGENT_BEHAVIOUR.md). The original model comparison is preserved unchanged and predates that hardening. Use a fresh `--out` path to benchmark the current revision; its new metrics must not be substituted for the historical values. Resume only when the saved prompt/client/data hashes still match.
