from apps.api.routers.analytics import measured_output_rate, provider_api_cost


RATES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def test_provider_cost_uses_separate_input_and_output_prices():
    usage = [{
        "model": "gpt-4o-mini",
        "input_tokens": 1_000_000,
        "output_tokens": 2_000_000,
        "exact_usage": True,
    }]
    assert provider_api_cost(usage, RATES, "provider_api") == 1.35


def test_unknown_model_or_estimated_usage_is_unpriced_not_free():
    unknown_model = [{"model": "not-configured", "input_tokens": 1, "output_tokens": 1, "exact_usage": True}]
    estimated = [{"model": "gpt-4o-mini", "input_tokens": 1, "output_tokens": 1, "exact_usage": False}]
    assert provider_api_cost(unknown_model, RATES, "provider_api") is None
    assert provider_api_cost(estimated, RATES, "provider_api") is None
    assert provider_api_cost([], RATES, "provider_api") is None


def test_local_models_never_get_a_dollar_estimate():
    usage = [{"model": "qwen3:4b", "input_tokens": 100, "output_tokens": 50, "exact_usage": True}]
    assert provider_api_cost(usage, RATES, "local") is None


def test_output_throughput_requires_exact_model_usage():
    exact = [{"output_tokens": 50, "duration_seconds": 2, "exact_usage": True}]
    estimated = [{"output_tokens": 50, "duration_seconds": 0.01, "exact_usage": False}]
    assert measured_output_rate(exact) == (25, 50, 2.0)
    assert measured_output_rate(estimated) == (None, 0, 0.0)
