"""Check that the granularity experiment measures the requested operation and values."""
from evals.rd_a.llm_experiment import GROUPS, aggregate, canonical, score_selection, task_request
from evals.rd_a.run_experiment import load_tasks


def test_coarse_catalog_has_three_groups_covering_all_fifteen_operations():
    assert len(GROUPS) == 3
    names = [name for group in GROUPS.values() for name in group]
    assert len(names) == len(set(names)) == 15
    correct, operation, values = score_selection('marketplace_operations', {
        'operation': 'get_job', 'arguments': {'job_id': 'job-001'}}, 'get_job', True)
    assert correct and operation == 'get_job' and values == {'job_id': 'job-001'}
    assert not score_selection('marketplace_operations', {
        'operation': 'search_jobs', 'arguments': {}}, 'get_job', True)[0]
    assert not score_selection('portfolio_operations', {
        'operation': 'get_job', 'arguments': {}}, 'get_job', True)[0]


def test_tasks_expose_required_values_without_the_gold_tool_or_input_object():
    tasks = load_tasks()['tasks']
    assert len(tasks) == 40
    for task in tasks:
        request = task_request(task)
        assert task['expected_tool'] not in request
        assert 'expected_tool' not in request and '"arguments"' not in request
    assert 'rdA-draft-001' in task_request(tasks[21])
    assert '300 USD' in task_request(tasks[21])


def test_argument_defaults_and_actual_provider_token_aggregation():
    schema = {'properties': {'limit': {'default': 20}}}
    assert canonical({}, schema) == canonical({'limit': 20}, schema)
    nested = {'$defs': {'Proposal': {'properties': {'screening_answers': {'default': []}}}},
              'properties': {'proposal': {'$ref': '#/$defs/Proposal'}}}
    assert canonical({'proposal': {}}, nested) == canonical({'proposal': {'screening_answers': []}}, nested)
    rows = [{'condition': 'fine', 'tool_selection_correct': True, 'argument_accuracy': True,
             'schema_valid': True, 'result_correct': True,
             'usage': {'prompt_tokens': 100, 'completion_tokens': 10, 'total_tokens': 110}},
            {'condition': 'fine', 'tool_selection_correct': False, 'argument_accuracy': False,
             'schema_valid': True, 'result_correct': False,
             'usage': {'prompt_tokens': 120, 'completion_tokens': 30, 'total_tokens': 150}}]
    result = aggregate(rows)['fine']
    assert result['tool_selection_accuracy'] == result['argument_accuracy'] == .5
    assert result['mean_tokens_per_task'] == 130
