"""Official action-specific two-stage writes. Never used by connection/read smoke tests."""
import asyncio
import hashlib
import json

import jsonschema

from agent.marketplace_port import MarketplaceError


async def call(adapter, name, arguments):
    catalog = adapter.oauth.vault.get(adapter.user, 'catalog', [])
    tool = next((t for t in catalog if t['name'] == name), None)
    if not tool:
        raise MarketplaceError('upwork_capability_unmapped', name)
    jsonschema.validate(arguments, tool['inputSchema'])
    try:
        async with asyncio.timeout(35):
            async with adapter.oauth.client(adapter.user).session('upwork') as session:
                result = await session.call_tool(name, arguments)
        if result.isError:
            raise MarketplaceError('upwork_tool_error', 'Provider rejected the action; check your account before retrying')
        if result.structuredContent is not None:
            return result.structuredContent
        return json.loads(next(c.text for c in result.content if getattr(c, 'type', None) == 'text'))
    except MarketplaceError:
        raise
    except Exception as error:
        raise MarketplaceError('upwork_write_uncertain', 'Provider response unavailable; automatic write retry is disabled') from error


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    if isinstance(value, list):
        for child in value:
            yield from walk(child)


async def preflight(adapter, org, job_id):
    # Provider help makes both checks mandatory. If a page is incomplete, refuse a new proposal.
    for action, status in [('invitations', 'pending'), *[('list', s) for s in ['Accepted', 'Pending', 'Declined', 'Offered', 'Activated', 'Hired', 'Withdrawn', 'Archived']]]:
        params = {'limit': 25, 'status': status}
        if action == 'invitations':
            params['job_posting_id'] = job_id
        result = await call(adapter, 'upwork__list_freelancer_proposals', {'action': action, 'org_uid': org, 'params': params})
        if any(isinstance(x, dict) and (x.get('hasMore') is True or x.get('hasNextPage') is True) for x in walk(result)):
            raise MarketplaceError('upwork_preflight_incomplete', 'Existing proposals extend beyond the verified page; review them before creating a new one')
        if not any(isinstance(x, list) for x in walk(result)):
            raise MarketplaceError('upwork_contract_error', 'Could not verify the existing-proposal collection')
        if any(isinstance(x, (str, int)) and str(x) == str(job_id) for x in walk(result)):
            raise MarketplaceError('upwork_existing_proposal', 'An invitation or proposal already references this job; use its existing workflow')


async def prepare(adapter, operation, payload, key):
    vault, user = adapter.oauth.vault, adapter.user
    org = vault.get(user, 'account', {}).get('org_uid')
    if not org:
        raise MarketplaceError('upwork_account_required')
    action_id = hashlib.sha256(f'{operation}|{key}'.encode()).hexdigest()[:24]
    if operation == 'proposal_draft':
        await preflight(adapter, org, payload['job_id'])
        job = await adapter.get_job(payload['job_id'])
        if job.get('can_apply') is False:
            raise MarketplaceError('upwork_cannot_apply', 'Upwork reports that this account cannot apply to the job')
        questions, answers = job.get('screening_questions', []), payload.get('screening_answers', [])
        if len(questions) != len(answers):
            raise MarketplaceError('upwork_screening_required', 'Provide an answer for every screening question')
        params = {'job_reference': payload['job_id'], 'cover_letter': payload['cover_letter'],
                  'charged_amount': payload['bid_amount']}
        if questions:
            params['answers'] = [{'question': q, 'answer': a} for q, a in zip(questions, answers, strict=True)]
        preview = await call(adapter, 'upwork__manage_proposals', {'action': 'create', 'org_uid': org, 'params': params})
        preview_id = preview.get('preview_id') or (preview.get('preview') or {}).get('preview_id')
        if not isinstance(preview_id, str):
            raise MarketplaceError('upwork_contract_error', 'Provider returned no server-issued proposal preview id; nothing will be confirmed')
        tool, args = 'upwork__confirm_preview', {'action': 'confirm', 'org_uid': org, 'params': {'type': 'proposal', 'preview_id': preview_id}}
    else:
        # Upwork exposes a direct send tool, not a message-preview tool. Stage text locally first.
        preview = {'kind': 'message_draft', 'room_id': payload['thread_id'], 'message': payload['text'],
                   'notice': 'Not sent. A separate confirmation will call Upwork Send Message.'}
        tool, args = 'upwork__send_message', {'action': 'send', 'org_uid': org,
                                             'params': {'room_id': payload['thread_id'], 'message': payload['text']}}
    digest = hashlib.sha256(json.dumps(preview, sort_keys=True).encode()).hexdigest()
    vault.put(user, 'platform:' + action_id, {'tool': tool, 'arguments': args, 'preview': preview,
                                             'review_hash': digest, 'status': 'pending', 'binding': vault.get(user, 'binding')})
    return {'status': 'awaiting_platform_confirmation', 'platform_action_id': action_id,
            'review_hash': digest, 'platform_preview': preview, 'replayed': False}


async def confirm(adapter, action_id, review_hash):
    vault, user = adapter.oauth.vault, adapter.user
    pending = vault.get(user, 'platform:' + action_id)
    if not pending or pending['review_hash'] != review_hash:
        raise MarketplaceError('upwork_review_changed', 'Review the current platform preview before confirming')
    if pending.get('binding') != vault.get(user, 'binding'):
        raise MarketplaceError('marketplace_changed', 'Reconnect changed the account binding; prepare a fresh draft')
    claim = 'platform-confirm:' + action_id
    if not vault.claim(user, claim, {'status': 'started'}):
        previous = vault.get(user, claim)
        if previous.get('receipt'):
            return {**previous['receipt'], 'replayed': True}
        raise MarketplaceError('upwork_write_uncertain', 'Confirmation already started; inspect Upwork instead of repeating it')
    # No arbitrary tool may be injected through stored pending action records.
    if pending['tool'] not in {'upwork__confirm_preview', 'upwork__send_message'}:
        raise MarketplaceError('upwork_contract_error')
    response = await call(adapter, pending['tool'], pending['arguments'])
    receipt = {'status': 'platform_confirmation_recorded', 'provider_response': response,
               'note': 'The provider response is recorded. Verify submitted proposals/messages on Upwork; no hiring outcome is implied.',
               'replayed': False}
    vault.put(user, claim, {'status': 'finished', 'receipt': receipt})
    return receipt
