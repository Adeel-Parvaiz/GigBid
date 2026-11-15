"""Pure configuration helpers for isolated evaluation accounts and outcome matching."""
def marketplace_env(base, variant, port):
    if variant not in {'v0_naive', 'v8_corrective'}:
        raise ValueError('Unexpected evaluation variant')
    return {**base, 'PORT': str(port), 'GIGSIM_API_TOKEN': 'b4-rest-' + variant,
            'MARKETPLACE_MCP_TOKENS': f'b4-mcp-{variant}:b4-{variant}',
            'MARKETPLACE_AUDIT': base['MARKETPLACE_AUDIT'].replace('audit.jsonl', variant + '-audit.jsonl')}


def match_outcome(outcomes, submission):
    draft_id = (submission or {}).get('draft_id')
    if not draft_id:
        raise ValueError('A real submitted draft ID is required')
    matches = [o for o in outcomes if o.get('draft_id') == draft_id]
    if len(matches) != 1:
        raise ValueError('Exactly one matching simulator outcome is required')
    return matches[0]
