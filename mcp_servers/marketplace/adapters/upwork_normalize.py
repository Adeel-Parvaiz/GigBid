"""Normalization of observed official Upwork MCP read responses. Unknown values stay unknown."""
from agent.marketplace_port import MarketplaceError


def number(value):
    if isinstance(value, dict):
        value = value.get('rawValue', value.get('displayValue'))
    try:
        return float(str(value).replace('$', '').replace(',', '')) if value is not None else None
    except ValueError:
        return None


def normalize(kind, data, vault, user, arguments):
    if kind == 'official_job_search':
        jobs = []
        for item in data['jobs']:
            jid = str(item['id'])
            vault.put(user, 'search_job:' + jid, item)
            amount = number(item.get('budget'))
            jobs.append({'job_id': jid, 'client_id': 'job-client:' + jid, 'title': item['title'],
                         'description': item.get('description', item.get('description_snippet', '')),
                         'required_skills': item.get('skills', []), 'connects_cost': None,
                         'budget': {'max': amount}, 'url': item.get('url'), 'provenance': 'upwork-live',
                         'connects_cost_note': 'Read full job details for the actual application cost'})
        return jobs
    if kind == 'official_job_detail':
        item = data['data']['marketplaceJobPosting']
        jid = str(item['id'])
        cid = str((item.get('clientCompanyPublic') or {}).get('id') or 'job-client:' + jid)
        terms = item.get('contractTerms', {})
        fixed = (terms.get('fixedPriceContractTerms') or {}).get('amount', {})
        amount = number(fixed)
        record = data.get('client_record', {})
        summary = vault.get(user, 'search_job:' + jid, {})
        client = {'client_id': cid, 'average_rating': number(record.get('feedback_score')),
                  'payment_verified': (summary.get('client', {}).get('verification_status') == 'VERIFIED') if summary.get('client', {}).get('verification_status') else None,
                  'contracts_total': record.get('contracts_total'),
                  'contracts_active': record.get('contracts_active'), 'jobs_posted': record.get('jobs_posted'),
                  'total_spent_usd': number(record.get('spend_total')), 'history': data.get('client_work_history', {}),
                  'feedback': data.get('client_feedback', {}), 'provenance': 'upwork-live',
                  'limitations': 'History is a provider sample; payment verification is unknown unless explicitly returned.'}
        vault.put(user, 'client:' + cid, client)
        vault.put(user, 'client:job-client:' + jid, client)
        job = {'job_id': jid, 'client_id': cid, 'title': item.get('content', {})['title'],
               'description': item.get('content', {}).get('description', ''),
               'required_skills': item.get('skills', summary.get('skills', [])), 'screening_questions': data.get('screening_questions', []),
               'budget': {'max': amount, 'currency': fixed.get('currency', 'USD'),
                          'unit': 'hour' if terms.get('contractType') == 'HOURLY' else 'project'},
               'connects_cost': data.get('connects_cost'), 'can_apply': data.get('can_apply'),
               'url': item.get('url'), 'provenance': 'upwork-live', 'bid_stats_note': data.get('bid_stats_note')}
        if job['connects_cost'] is None:
            raise MarketplaceError('upwork_contract_error', 'Provider did not return the application Connects cost')
        return job
    if kind == 'official_balance':
        value = data['balance']['connectsBalance']
        return {'balance': int(value), 'provenance': 'upwork-live'}
    if kind == 'official_rooms':
        rows = data['data']['rooms']
        out = []
        for row in rows:
            rid = row.get('room_id', row.get('id'))
            if not isinstance(rid, str):
                raise MarketplaceError('upwork_contract_error', 'Room id missing from provider response')
            last = row.get('last_message', '')
            out.append({'thread_id': rid, 'job_id': str(row.get('job_id', '')),
                        'client_id': str(row.get('client_id', '')),
                        'last_message': last.get('text', last.get('message', '')) if isinstance(last, dict) else str(last)})
        return out
    if kind == 'official_messages':
        container = data.get('data', data)
        messages = container.get('messages')
        if not isinstance(messages, list):
            raise MarketplaceError('upwork_contract_error', 'Provider message collection does not match the verified contract')
        out = []
        for row in messages:
            side = str(row.get('from_side', '')).lower()
            sender = 'freelancer' if row.get('from_self') is True or side in {'freelancer', 'talent'} else 'client' if side == 'client' else None
            text, mid = row.get('text', row.get('message')), row.get('id', row.get('story_id'))
            if sender is None or not isinstance(text, str) or mid is None:
                raise MarketplaceError('upwork_contract_error', 'Message text/id or authoritative sender side is missing')
            out.append({'id': str(mid), 'from': sender, 'text': text, 'ts': row.get('created_at', '')})
        return {'thread_id': arguments['thread_id'], 'messages': out}
    raise MarketplaceError('upwork_contract_error', 'Unknown official response normalizer')


def official_read_mapping():
    return {
        'search_jobs': {'tool': 'upwork__find_jobs', 'arguments': {'action': 'search', 'org_uid': '$account.org_uid',
                        'params': {'query': '$query', 'limit': '$limit', 'include_full_details': True}}, 'normalizer': 'official_job_search'},
        'get_job': {'tool': 'upwork__find_jobs', 'arguments': {'action': 'get', 'org_uid': '$account.org_uid',
                    'params': {'id': '$job_id'}}, 'normalizer': 'official_job_detail'},
        'get_client_history': {'source': 'job_detail_client_record'},
        'get_connects_balance': {'tool': 'upwork__get_profile', 'arguments': {'action': 'connects_balance',
                                 'org_uid': '$account.org_uid', 'params': {'limit': 1}}, 'normalizer': 'official_balance'},
        'list_threads': {'tool': 'upwork__get_messages', 'arguments': {'action': 'list_rooms',
                         'org_uid': '$account.org_uid', 'params': {'limit': 20}}, 'normalizer': 'official_rooms'},
        'list_messages': {'tool': 'upwork__get_messages', 'arguments': {'action': 'list_messages',
                          'org_uid': '$account.org_uid', 'params': {'room_id': '$thread_id', 'limit': 20}}, 'normalizer': 'official_messages'},
    }
