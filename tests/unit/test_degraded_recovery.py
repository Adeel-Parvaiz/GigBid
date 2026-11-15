import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langgraph.checkpoint.memory import InMemorySaver

from agent.marketplace_port import MarketplaceError
from apps.api.recovery import recover_once
from apps.api.runs import RunManager, RunStore


async def queued(manager, user, profile, extra=None):
    run = manager.store.create(user['user_id'], 'bid', 'job-001')
    await manager.graphs['bid'].aupdate_state(manager.cfg(run['run_id']),
        {'job_id': 'job-001', 'profile': profile, 'status': 'error', 'errors': ['marketplace_unavailable'], **(extra or {})}, as_node='load_job')
    manager.store.update(run['run_id'], status='queued_degraded', degraded=True)
    return run


async def test_recovery_only_reanalyses_and_stops_at_approval(make_deps, profile):
    manager = RunManager(make_deps(), InMemorySaver(), RunStore())
    user = {'user_id': 'alice', 'freelancer_id': profile['freelancer_id']}
    old = await queued(manager, user, profile)
    assert await recover_once(manager, SimpleNamespace(get=lambda uid: user)) == 1
    await asyncio.gather(*list(manager.tasks))
    assert manager.store.get(old['run_id'])['status'] == 'superseded'
    runs = manager.store.list('alice')
    assert any(r['status'] == 'awaiting_approval' for r in runs)
    assert manager.deps.port.balance == 100 and not manager.deps.port.submissions


async def test_recovery_refuses_prior_approval_or_changed_marketplace(make_deps, profile):
    deps = make_deps()
    manager = RunManager(deps, InMemorySaver(), RunStore())
    user = {'user_id': 'alice', 'freelancer_id': profile['freelancer_id']}
    users = SimpleNamespace(get=lambda uid: user)
    approved = await queued(manager, user, profile, {'approval': {'action': 'approve'}})
    manager.retry = AsyncMock()
    assert await recover_once(manager, users) == 0
    assert manager.store.get(approved['run_id'])['status'] == 'needs_attention'
    changed = await queued(manager, user, {**profile, '_marketplace_binding': 'simulator'})
    deps.port = SimpleNamespace(binding=lambda uid: 'upwork:changed', get_connects_balance=AsyncMock(return_value={'balance': 100}))
    assert await recover_once(manager, users) == 0
    assert manager.store.get(changed['run_id'])['status'] == 'needs_attention'
    manager.retry.assert_not_awaited()


async def test_outage_during_pricing_resumes_its_checkpoint_before_approval(make_deps, profile):
    deps = make_deps()
    deps.port.get_connects_balance = AsyncMock(side_effect=[MarketplaceError('marketplace_unavailable'), {'balance': 100}, {'balance': 100}])
    manager = RunManager(deps, InMemorySaver(), RunStore())
    user = {'user_id': 'alice', 'freelancer_id': profile['freelancer_id']}
    run = await manager.start(user, 'bid', 'job-001')
    await asyncio.gather(*list(manager.tasks))
    assert manager.store.get(run['run_id'])['status'] == 'queued_degraded'
    assert await recover_once(manager, SimpleNamespace(get=lambda uid: user)) == 1
    await asyncio.gather(*list(manager.tasks))
    assert manager.store.get(run['run_id'])['status'] == 'awaiting_approval'
    assert deps.port.balance == 100 and not deps.port.submissions


async def test_marketplace_rate_limit_queues_read_only_job_for_recovery(make_deps, profile):
    from unittest.mock import AsyncMock

    deps = make_deps()
    deps.port.get_job = AsyncMock(side_effect=MarketplaceError("rate_limited"))
    manager = RunManager(deps, InMemorySaver(), RunStore())
    user = {'user_id': 'alice', 'freelancer_id': profile['freelancer_id']}
    run = await manager.start(user, 'bid', 'job-001')
    await asyncio.gather(*list(manager.tasks))
    assert manager.store.get(run['run_id'])['status'] == 'queued_degraded'
    assert deps.port.get_job.await_count == 3
