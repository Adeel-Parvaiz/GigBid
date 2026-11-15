"""Second human gate: execute a reviewed action on official Upwork MCP, never automatically."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from agent.marketplace_context import approved_write
from agent.marketplace_port import MarketplaceError
from apps.api.deps import get_run
from mcp_servers.marketplace.adapters.upwork_live import marketplace_binding

router = APIRouter(tags=['platform confirmation'])


class PlatformConfirmationIn(BaseModel):
    review_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm_on_upwork: bool
    attachments_choice: str | None = None


@router.post('/runs/{run_id}/platform-confirmation')
async def confirm(body: PlatformConfirmationIn, request: Request, run: dict = Depends(get_run)):
    if not body.confirm_on_upwork:
        raise HTTPException(409, 'Explicit confirmation is required')
    if run['kind'] == 'bid' and body.attachments_choice != 'none':
        raise HTTPException(409, 'Confirm whether files/highlights are wanted. Upload/selection must be completed before submitting with attachments.')
    if run['status'] != 'awaiting_platform_confirmation':
        raise HTTPException(409, 'This run has no pending platform confirmation')
    manager = request.app.state.manager
    values = await manager.values(run)
    field = 'submission' if run['kind'] == 'bid' else 'send_result'
    pending = values.get(field) or {}
    if not pending.get('platform_action_id') or pending.get('review_hash') != body.review_hash:
        raise HTTPException(409, 'Review the current platform preview before confirming')
    approved = approved_write.set(True)
    binding = marketplace_binding.set(values.get('profile', {}).get('_marketplace_binding') or 'simulator')
    try:
        result = await manager.deps.port.confirm_platform_action(pending['platform_action_id'], body.review_hash)
    except MarketplaceError as error:
        raise HTTPException(409, str(error)) from error
    finally:
        approved_write.reset(approved)
        marketplace_binding.reset(binding)
    await manager.graphs[run['kind']].aupdate_state(manager.cfg(run['run_id']), {field: {**pending, 'platform_result': result}, 'status': result['status']})
    manager.store.update(run['run_id'], status=result['status'])
    return {'status': result['status'], 'note': result['note']}
