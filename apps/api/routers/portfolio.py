"""Human-controlled evidence ingestion. Agent retrieval stays behind Portfolio MCP."""
import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Request
from mcp.shared.memory import create_connected_server_and_client_session as connect
from pydantic import BaseModel, Field

from apps.api.deps import get_user
from mcp_servers.portfolio.server import build_server
from mcp_servers.portfolio.tools import PortfolioStore
from rag.ingest.store import DocumentMetadata, PortfolioCorpus

router = APIRouter(prefix='/portfolio', tags=['Portfolio ingestion'])


class UploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200, pattern=r'^[^/\\]+$')
    kind: str = Field(pattern='^(cv|case_study|review|past_proposal)$')
    content_base64: str = Field(min_length=1, max_length=2_700_000)
    metadata: DocumentMetadata


class RepositoryIn(BaseModel):
    owner: str = Field(min_length=1, max_length=100)
    repo: str = Field(min_length=1, max_length=100)
    path: str = Field(min_length=1, max_length=300)
    ref: str | None = Field(None, max_length=200)
    kind: str = Field(pattern='^(readme|code)$')
    metadata: DocumentMetadata


def corpus(request):
    return PortfolioCorpus(request.app.state.upwork.vault)


@router.get('/documents')
def documents(request: Request, user: dict = Depends(get_user)):
    return {'items': [PortfolioCorpus.summary(d) for d in corpus(request).documents(user['user_id'])]}


@router.post('/documents')
def upload(body: UploadIn, request: Request, user: dict = Depends(get_user)):
    try:
        content = base64.b64decode(body.content_base64, validate=True)
        return corpus(request).ingest(user['user_id'], user['freelancer_id'], body.filename, content,
                                      body.kind, body.metadata)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(422, str(error)) from error


@router.post('/github')
async def repository(body: RepositoryIn, request: Request, user: dict = Depends(get_user)):
    try:
        item = await request.app.state.github.import_file(user['user_id'], user['freelancer_id'],
            body.owner, body.repo, body.path, body.ref, body.metadata.authorship_confirmed, body.kind, persist=False)
        return corpus(request).ingest(user['user_id'], user['freelancer_id'], body.path,
            item['summary'].encode(), body.kind, body.metadata, source=item['source'])
    except (ValueError, TimeoutError) as error:
        raise HTTPException(409, str(error)) from error


@router.delete('/documents/{document_id}')
def delete(document_id: str, request: Request, user: dict = Depends(get_user)):
    try:
        corpus(request).delete(user['user_id'], document_id)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
    return {'deleted': True}


@router.get('/search')
async def search(request: Request, query: str = 'portfolio', kind: str | None = None, user: dict = Depends(get_user)):
    if not 2 <= len(query) <= 2000:
        raise HTTPException(422, 'Search must contain 2–2000 characters')
    store = PortfolioStore(user_id=user['user_id'], freelancer_id=user['freelancer_id'], vault=request.app.state.upwork.vault)
    async with connect(build_server(store)) as session:
        from rag.ingest.loaders import KINDS
        if kind and kind not in KINDS:
            raise HTTPException(422, 'Unknown evidence type')
        result = await session.call_tool('search_evidence', {'requirement': query, 'k': 10,
                                                         'filters': {'type': kind} if kind else None})
    return result.structuredContent
