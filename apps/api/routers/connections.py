"""Per-user live Upwork connection lifecycle; no tokens leave the backend."""
import hashlib
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from apps.api.deps import get_user
from mcp_servers.marketplace.adapters.upwork_live import READS, WRITES, validate_mapping

router = APIRouter(prefix='/connections/upwork', tags=['connections'])


class ConnectionStatus(BaseModel):
    connected: bool
    mode: str
    status: str
    mapped_operations: list[str]
    required_operations: list[str]
    ready: bool
    reads_ready: bool = False


class AuthorizationOut(BaseModel):
    authorization_url: str | None
    status: str


def oauth(request):
    return request.app.state.upwork


@router.get('', response_model=ConnectionStatus)
async def status(request: Request, user: dict = Depends(get_user)):
    service, uid = oauth(request), user['user_id']
    connected = service.vault.get(uid, 'tokens') is not None
    pending = service.pending.get(uid, {})
    mapping = service.vault.get(uid, 'mapping', {})
    return {'connected': connected, 'mode': service.vault.get(uid, 'mode', 'simulator'),
            'status': pending.get('status', 'connected' if connected else 'disconnected'),
            'mapped_operations': sorted(mapping), 'required_operations': sorted(READS | WRITES),
            'ready': connected and (READS | WRITES) <= mapping.keys(),
            'reads_ready': connected and READS <= mapping.keys()}


@router.post('/authorize', response_model=AuthorizationOut)
async def authorize(request: Request, user: dict = Depends(get_user)):
    try:
        return await oauth(request).start(user['user_id'])
    except TimeoutError as error:
        raise HTTPException(504, 'Upwork authorization discovery timed out; retry from Settings') from error


@router.get('/callback')
async def callback(request: Request):
    params = getattr(request.state, 'oauth_callback', {})
    try:
        ok = await oauth(request).finish(params.get('state', ''), params.get('code', ''))
    except (ValueError, TimeoutError) as error:
        raise HTTPException(400, 'Authorization expired or state was invalid; reconnect from Settings') from error
    return RedirectResponse('/upwork-connected' if ok else '/upwork-connection-failed', status_code=303)


@router.get('/catalog')
async def catalog(request: Request, user: dict = Depends(get_user)):
    tools = oauth(request).vault.get(user['user_id'], 'catalog', [])
    digest = hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()
    return {'tools': tools, 'sha256': digest}


class MappingIn(BaseModel):
    catalog_sha256: str
    operations: dict


@router.put('/mapping')
async def mapping(body: MappingIn, request: Request, user: dict = Depends(get_user)):
    service, uid = oauth(request), user['user_id']
    tools = service.vault.get(uid, 'catalog', [])
    digest = hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()
    if not tools or not secrets.compare_digest(digest, body.catalog_sha256):
        raise HTTPException(409, 'Authenticated tool catalog changed; review its schemas before mapping')
    try:
        validate_mapping(body.operations, tools)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    service.vault.put(uid, 'mapping', body.operations)
    return {'mapped_operations': sorted(body.operations)}


class ModeIn(BaseModel):
    mode: str


@router.put('/mode')
async def mode(body: ModeIn, request: Request, user: dict = Depends(get_user)):
    service, uid = oauth(request), user['user_id']
    if body.mode not in {'simulator', 'upwork', 'upwork_readonly'}:
        raise HTTPException(422, 'Choose simulator, upwork or upwork_readonly')
    if body.mode in {'upwork', 'upwork_readonly'}:
        required = READS if body.mode == 'upwork_readonly' else READS | WRITES
        if not service.vault.get(uid, 'tokens') or not required <= service.vault.get(uid, 'mapping', {}).keys():
            raise HTTPException(409, 'Authorize Upwork and validate every operation mapping first')
        service.vault.put(uid, 'binding', secrets.token_hex(16))
    service.vault.put(uid, 'mode', body.mode)
    return {'mode': body.mode}


@router.delete('')
async def disconnect(request: Request, user: dict = Depends(get_user)):
    oauth(request).disconnect(user['user_id'])
    return {'connected': False, 'mode': 'simulator', 'note': 'Local credentials removed. Revoke GigBid in Upwork account settings to revoke provider access.'}
