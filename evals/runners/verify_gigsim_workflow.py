"""Full account/API/browser approval/restart workflow against disposable owned GigSim."""
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

from evals.runners.verify_owned_gigsim import free_port

ROOT = Path(__file__).resolve().parents[2]


def main():
    state = ROOT / '.local-models' / f'gigsim-workflow-{secrets.token_hex(4)}'
    state.mkdir(parents=True)
    evidence = ROOT / 'evals/results/gigsim_workflow'
    evidence.mkdir(parents=True, exist_ok=True)
    ports = {k: free_port() for k in ['rest', 'mcp', 'api', 'web']}
    urls = {k: f'http://127.0.0.1:{v}' for k, v in ports.items()}
    node = sorted((ROOT / '.local-models/node-runtime').glob('node-*/bin/node'))[-1]
    env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / '.env').items() if v is not None},
           'LLM_BACKEND': 'openai_compat', 'GIGBID_DATA_DIR': str(ROOT / 'data/processed/kaggle_2024_v1'),
           'PORTFOLIO_DIR': str(ROOT / 'data/processed/kaggle_2024_v1'),
           'GIGSIM_DB': str(state / 'sim.sqlite'), 'GIGSIM_TOKENS_JSON': json.dumps({'workflow-rest': 'workflow'}),
           'GIGSIM_API_TOKEN': 'workflow-rest', 'GIGSIM_API_URL': urls['rest'],
           'GIGSIM_CONTRACT': str(ROOT / 'config/gigsim_contract.json'), 'MARKETPLACE_MODE': 'gigsim',
           'MARKETPLACE_MCP_TOKENS': 'workflow-mcp:workflow', 'MARKETPLACE_MCP_TOKEN': 'workflow-mcp',
           'MARKETPLACE_RPM': '1000', 'MARKETPLACE_AUDIT': str(state / 'audit.jsonl'), 'PORT': str(ports['mcp']),
           'GIGBID__marketplace__mode': 'mcp', 'GIGBID__marketplace__url': urls['mcp'] + '/mcp',
           'GIGBID__portfolio__source': 'local', 'GIGBID__workspace__source': 'mcp',
           'GIGBID__workspace__transport': 'stdio', 'WORKSPACE_DB': str(state / 'workspace.sqlite'),
           'DATABASE_URL': f'sqlite:///{state / "checkpoints.sqlite"}', 'RUNS_DB': str(state / 'runs.sqlite'),
           'USERS_DB': str(state / 'users.sqlite'), 'APP_SECRET_KEY': secrets.token_hex(32),
           'REVIEWER_PERSONA': 'ai-ml-engineer', 'GIGBID_DEV_API_URL': urls['api'],
           'PLAYWRIGHT_BROWSERS_PATH': str(ROOT / '.local-models/playwright-browsers'),
           'LD_LIBRARY_PATH': str(ROOT / '.local-models/playwright-libs/root/usr/lib/x86_64-linux-gnu') + ':' + os.environ.get('LD_LIBRARY_PATH', '')}
    processes = {}
    result = {'scope': 'Real Qwen + registered application account + HTTP API + authenticated MCP + owned GigSim + Chromium UI approval; SQLite persistence.',
              'limitations': ['Synthetic marketplace and outcomes; approval is scripted inside disposable sandbox.',
                              'SQLite restarts verified; Postgres durability is a separate assignment requirement.',
                              'This is not live Upwork integration.'], 'checks': [], 'screenshots': []}
    client = httpx.Client(timeout=240)

    def check(name, passed, observed=None):
        result['checks'].append({'name': name, 'passed': bool(passed), 'observed': observed})
        (evidence / 'results.json').write_text(json.dumps(result, indent=2))
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)
        if not passed:
            raise AssertionError(name)

    def start(name):
        commands = {'rest': [sys.executable, '-m', 'uvicorn', 'apps.gigsim.main:create_app', '--factory', '--port', str(ports['rest'])],
                    'mcp': [sys.executable, '-m', 'mcp_servers.marketplace.server'],
                    'api': [sys.executable, '-m', 'uvicorn', 'apps.api.main:create_app', '--factory', '--port', str(ports['api'])],
                    'web': [str(node), str(ROOT / 'apps/web/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', str(ports['web']), '--strictPort']}
        with (state / f'{name}.log').open('a') as log:
            p = subprocess.Popen(commands[name], cwd=ROOT / 'apps/web' if name == 'web' else ROOT, env=env, stdout=log, stderr=log)
        processes[name] = p
        for _ in range(150):
            if p.poll() is not None:
                raise RuntimeError(f'{name} exited; inspect {state / (name + ".log")}')
            try:
                response = client.get(urls[name] + ('/health' if name in ['rest', 'api'] else '/'), timeout=1)
                if response.status_code < 500:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        raise TimeoutError(name)

    def stop(name, kill=False):
        p = processes.get(name)
        if p and p.poll() is None:
            p.kill() if kill else p.terminate()
            p.wait(15)

    def restart():
        # Abrupt exit proves saved state, rather than graceful shutdown flushing.
        for name in ['api', 'mcp', 'rest']:
            stop(name, kill=True)
        for name in ['rest', 'mcp', 'api']:
            start(name)

    def snapshot():
        response = client.get(urls['rest'] + '/v1/balance', headers={'Authorization': 'Bearer workflow-rest'})
        response.raise_for_status()
        return response.json()['balance']

    def settled(rid):
        for _ in range(1200):
            response = client.get(urls['api'] + f'/runs/{rid}', headers=headers)
            response.raise_for_status()
            detail = response.json()
            if detail['status'] not in ['running', 'queued']:
                return detail
            time.sleep(.1)
        raise TimeoutError('Agent run')

    def screenshot(name, path, approve=False):
        file = evidence / (name + '.png')
        browser_env = {**env, 'EVIDENCE_WEB_URL': urls['web'], 'EVIDENCE_EMAIL': email,
                       'EVIDENCE_PASSWORD': password, 'EVIDENCE_PATH': path, 'EVIDENCE_FILE': str(file),
                       'EVIDENCE_APPROVE': '1' if approve else '0'}
        subprocess.run([str(node), 'tests/gigsim-evidence.cjs'], cwd=ROOT / 'apps/web', env=browser_env, check=True, timeout=100)
        result['screenshots'].append(str(file.relative_to(ROOT)))

    try:
        for name in ['rest', 'mcp', 'api', 'web']:
            start(name)
        email, password = 'workflow-reviewer@gigbid.test', secrets.token_urlsafe(18)
        registration = client.post(urls['api'] + '/auth/register', json={'email': email, 'password': password, 'freelancer_id': 'ai-ml-engineer'})
        check('application_account_registration', registration.status_code == 200)
        headers = {'Authorization': 'Bearer ' + registration.json()['token']}
        check('job_discovery', len(client.get(urls['api'] + '/jobs', headers=headers).json()) > 0)
        check('initial_connects', snapshot() == 100)
        screenshot('01-inbox', '/inbox')
        response = client.post(urls['api'] + '/jobs/syn-101281/runs', headers=headers)
        response.raise_for_status()
        rid = response.json()['run_id']
        detail = settled(rid)
        check('agent_reaches_approval_gate', detail['status'] == 'awaiting_approval', detail['status'])
        check('analysis_and_preview_spend_zero_connects', snapshot() == 100)
        check('no_submission_before_approval', client.get(urls['rest'] + '/v1/outcomes', headers={'Authorization': 'Bearer workflow-rest'}).json()['outcomes'] == [])
        check('unauthenticated_approval_rejected', client.post(urls['api'] + f'/runs/{rid}/approval', json={'action': 'approve'}).status_code == 401)
        second = client.post(urls['api'] + '/auth/register', json={'email': 'other-reviewer@gigbid.test', 'password': secrets.token_urlsafe(18), 'freelancer_id': 'data-analyst'}).json()
        check('other_user_cannot_approve', client.post(urls['api'] + f'/runs/{rid}/approval', json={'action': 'approve'}, headers={'Authorization': 'Bearer ' + second['token']}).status_code in [403, 404])
        pending = detail['pending']
        restart()
        check('session_and_account_survive_abrupt_restart', client.get(urls['api'] + '/auth/me', headers=headers).status_code == 200)
        restored = client.get(urls['api'] + f'/runs/{rid}', headers=headers).json()
        check('pending_proposal_survives_restart', restored['pending'] == pending)
        check('balance_survives_restart', snapshot() == 100)
        screenshot('02-restored-approval', f'/studio/{rid}', approve=True)
        final = settled(rid)
        check('browser_approval_submits', final['status'] == 'submitted', final['status'])
        spent = final['summary']['submission']['connects_spent']
        check('exact_connects_deduction', snapshot() == 100 - spent, spent)
        check('repeated_approval_rejected', client.post(urls['api'] + f'/runs/{rid}/approval', headers=headers, json={'action': 'approve'}).status_code == 409)
        check('repeated_approval_no_second_charge', snapshot() == 100 - spent)
        screenshot('03-submitted-pipeline', '/pipeline')
        rest_headers = {'Authorization': 'Bearer workflow-rest'}
        thread = client.get(urls['rest'] + '/v1/threads', headers=rest_headers).json()['threads'][0]['thread_id']
        message_headers = {**rest_headers, 'Idempotency-Key': 'workflow-message'}
        message = client.post(urls['rest'] + f'/v1/threads/{thread}/messages', headers=message_headers,
                              json={'text': 'A synthetic persistence-test message.', 'key': 'workflow-message'})
        message.raise_for_status()
        before_messages = client.get(urls['rest'] + f'/v1/threads/{thread}', headers=rest_headers).json()
        outcomes = client.get(urls['rest'] + '/v1/outcomes', headers=rest_headers).json()
        check('simulated_outcome_recorded', len(outcomes['outcomes']) == 1, outcomes)
        restart()
        check('submitted_proposal_survives_restart', client.get(urls['api'] + f'/runs/{rid}', headers=headers).json()['status'] == 'submitted')
        check('spent_balance_survives_restart', snapshot() == 100 - spent)
        check('messages_survive_restart', client.get(urls['rest'] + f'/v1/threads/{thread}', headers=rest_headers).json() == before_messages)
        check('outcomes_survive_restart', client.get(urls['rest'] + '/v1/outcomes', headers=rest_headers).json() == outcomes)
        screenshot('04-persisted-messages', '/messages')
        conversation = client.post(urls['api'] + '/conversations/conv-0000/runs', headers=headers)
        conversation.raise_for_status()
        cid = conversation.json()['run_id']
        conversation_detail = settled(cid)
        check('workspace_mcp_interview_reaches_approval', conversation_detail['status'] == 'awaiting_approval', conversation_detail['status'])
        offered = conversation_detail['pending']['offered_slots']
        check('workspace_mcp_offers_calendar_slots', len(offered) == 3, offered)

        def workspace_state():
            # Evaluator-only inspection; the application accesses workspace capabilities only via MCP.
            with sqlite3.connect(state / 'workspace.sqlite') as database:
                return json.loads(database.execute('SELECT state FROM workspace WHERE id=1').fetchone()[0])

        check('workspace_no_hold_before_approval', workspace_state()['holds'] == {})
        restart()
        check('workspace_interview_approval_survives_restart', client.get(urls['api'] + f'/runs/{cid}', headers=headers).json()['pending']['offered_slots'] == offered)
        # Conversation UI's run viewer ends with "sent", so approve through the real HTTP endpoint here.
        approved = client.post(urls['api'] + f'/runs/{cid}/approval', headers=headers, json={'action': 'approve'})
        approved.raise_for_status()
        sent = settled(cid)
        check('workspace_mcp_approved_interview_creates_tentative_hold', sent['status'] == 'sent' and sent['summary']['send_result']['hold']['status'] == 'tentative')
        check('workspace_exactly_one_hold', len(workspace_state()['holds']) == 1)
        restart()
        check('workspace_hold_persists_after_restart', len(workspace_state()['holds']) == 1)
        result['status'] = 'passed'
    except Exception as error:
        result['status'] = 'failed'
        result['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        for name in ['web', 'api', 'mcp', 'rest']:
            stop(name)
        client.close()
        result['ports_closed'] = {}
        for name, port in ports.items():
            with socket.socket() as sock:
                result['ports_closed'][name] = sock.connect_ex(('127.0.0.1', port)) != 0
        (evidence / 'results.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
