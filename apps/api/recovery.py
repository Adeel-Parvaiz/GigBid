"""Bounded automatic recovery for queued read-stage marketplace outages."""
import asyncio
import logging
import os

from redis.exceptions import RedisError

from agent.marketplace_context import marketplace_user

logger = logging.getLogger(__name__)


async def recover_once(manager, users, limit=4, arq_pool=None):
    restored = 0
    async with manager.recovery_lock:
        eligible = [r for r in manager.store.all_degraded() if r['origin'] == manager.origin and r['status'] == 'queued_degraded']
        for run in eligible[:limit]:
            user = users.get(run['user_id'])
            if user is None:
                continue
            state = await manager.values(run)
            # Never resume a write or reuse an approval automatically.
            if state.get('approval') or state.get('submission') or state.get('send_result') or await manager.pending(run):
                manager.store.update(run['run_id'], status='needs_attention', degraded=False)
                continue
            expected = state.get('profile', {}).get('_marketplace_binding') or 'simulator'
            if hasattr(manager.deps.port, 'binding') and expected != manager.deps.port.binding(user['user_id']):
                manager.store.update(run['run_id'], status='needs_attention', degraded=False)
                continue
            token = marketplace_user.set(user['user_id'])
            try:
                if await manager.marketplace_ok():
                    if arq_pool is None:
                        await manager.retry(run, user)
                        restored += 1
                    elif manager.store.claim_status(
                        run["run_id"], user["user_id"], "queued_degraded", "running"
                    ):
                        try:
                            await arq_pool.enqueue_job(
                                "continue_queued_run",
                                run["run_id"],
                                _job_id=f"recover:{run['run_id']}:{manager.store.last_event_seq(run['run_id'])}",
                            )
                        except (RedisError, OSError, TimeoutError) as error:
                            manager.store.update(run["run_id"], status="queued_degraded", degraded=True)
                            logger.warning(
                                "Could not enqueue degraded run %s (%s)",
                                run["run_id"],
                                type(error).__name__,
                            )
                        else:
                            restored += 1
            finally:
                marketplace_user.reset(token)
    return restored


async def recovery_loop(manager, users, arq_pool=None):
    interval = max(.25, float(os.environ.get('DEGRADED_RECOVERY_INTERVAL', '5')))
    while True:
        await asyncio.sleep(interval)
        if not manager.store.all_degraded():
            continue
        try:
            await recover_once(manager, users, arq_pool=arq_pool)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Do not expose provider bodies or user data in this background log.
            logger.warning('Degraded-work recovery cycle failed; retained work for the next cycle')
