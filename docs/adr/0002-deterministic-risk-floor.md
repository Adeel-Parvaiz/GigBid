# 0002 Deterministic risk floor under the LLM
Risk = max(rule score, LLM score), flags = union. A post that tells the model to report "no risk" cannot lower it. Known weakness: patterns are regexes; paraphrased injections beat them (`injection_eval.json`). Mitigation to try: a classifier pass on the delimited post.
