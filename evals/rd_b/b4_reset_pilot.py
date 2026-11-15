"""Archive the superseded evaluation pilot; leave all normal GigBid services alone."""
import json
import os
from pathlib import Path
import signal
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evals/results/b4'


def main():
    manifest = OUT / 'manifest.json'
    if not manifest.exists() or json.loads(manifest.read_text())['protocol'].get('execution_revision', 1) >= 2:
        print('No superseded evaluation cohort to archive')
        return
    if os.name != 'posix':
        raise ValueError('Run the pilot reset in the Linux evaluation environment')
    if list((ROOT / '.local-models/b4-reviews').glob('panel-*.json')):
        raise ValueError('Panel ratings exist: preserve their cohort and review the migration manually')
    stopped = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().decode().split('\0')
            pid = int(path.parent.name)
            if args[1:3] == ['-m', 'evals.rd_b.b4_run'] and Path(f'/proc/{pid}/cwd').resolve() == ROOT.resolve():
                if os.getpgid(pid) == pid:
                    os.killpg(pid, signal.SIGINT)
                else:
                    os.kill(pid, signal.SIGINT)
                stopped.append(pid)
        except (ProcessLookupError, FileNotFoundError, PermissionError):
            continue
    for _ in range(200):
        if all(not Path(f'/proc/{pid}').exists() or Path(f'/proc/{pid}/stat').read_text().split()[2] == 'Z' for pid in stopped):
            break
        time.sleep(.1)
    else:
        raise ValueError('Old evaluation is still running; no result files were moved')
    archive = OUT / 'pilot-v1'
    archive.mkdir(exist_ok=True)
    for name in ['manifest.json', 'runs.jsonl', 'summary.json', 'outcomes_reconciled.json', 'judge_proposal_predictions.jsonl']:
        source, target = OUT / name, archive / name
        if source.exists():
            if target.exists():
                raise ValueError('Pilot archive already contains ' + name)
            source.rename(target)
    print('Preserved pilot artifacts; revision 2 uses separate upstream accounts and exact draft-ID outcome matching')


if __name__ == '__main__':
    main()
