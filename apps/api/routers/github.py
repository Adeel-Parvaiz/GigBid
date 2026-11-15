from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from apps.api.deps import get_user

router = APIRouter(prefix='/connections/github', tags=['GitHub MCP'])


class GitHubStatus(BaseModel):
    connected: bool
    status: str
    authorization_url: str | None = None
    authorization_message: str | None = None
    login: str | None = None
    read_only: bool = True


class GitHubImportsOut(BaseModel):
    items: list[dict] = []


@router.get('', response_model=GitHubStatus)
async def status(request: Request, user: dict = Depends(get_user)):
    return request.app.state.github.status(user['user_id'])


@router.post('/authorize', response_model=GitHubStatus)
async def authorize(request: Request, user: dict = Depends(get_user)):
    try:
        return await request.app.state.github.connect(user['user_id'])
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.delete('')
async def disconnect(request: Request, user: dict = Depends(get_user)):
    await request.app.state.github.disconnect(user['user_id'])
    return {'connected': False}


class ImportReadme(BaseModel):
    owner: str = Field(min_length=1, max_length=100)
    repo: str = Field(min_length=1, max_length=100)
    path: str = Field('README.md', min_length=1, max_length=300)
    ref: str | None = Field(None, max_length=200)
    authorship_confirmed: bool = False


@router.post('/imports')
async def import_readme(body: ImportReadme, request: Request, user: dict = Depends(get_user)):
    try:
        item = await request.app.state.github.import_readme(user['user_id'], user['freelancer_id'], **body.model_dump())
        from rag.ingest.store import PortfolioCorpus
        PortfolioCorpus(request.app.state.upwork.vault).ingest(user['user_id'], user['freelancer_id'],
            body.path, item['summary'].encode(), 'readme', {
                'title': item['title'], 'project': f'{body.owner}/{body.repo}', 'skills': [],
                'date': None, 'client_industry': None, 'outcome': None, 'authorship_confirmed': True},
            source=item['source'])
        return item
    except (ValueError, TimeoutError) as error:
        raise HTTPException(409, str(error)) from error


@router.get('/imports', response_model=GitHubImportsOut)
async def imports(request: Request, user: dict = Depends(get_user)):
    items = request.app.state.upwork.vault.list_prefix(user['user_id'], 'github:evidence:')
    return {'items': [{k: v for k, v in item.items() if k != 'summary'} for item in items]}
