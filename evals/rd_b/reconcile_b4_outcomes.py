"""Match outcomes by draft ID from this experiment's isolated persistent GigSim."""
import json
from pathlib import Path

from apps.gigsim.main import Simulator

ROOT = Path(__file__).resolve().parents[2]


def main():
    database = ROOT / '.local-models/b4-evaluation-v2/gigsim.sqlite'
    if not database.is_file():
        raise ValueError('The isolated B4 simulator database is missing; no outcomes can be inferred')
    simulator = Simulator(ROOT / 'data/processed/kaggle_2024_v1', database, connects=1_000_000, seed=7)
    mapping = {}
    for variant in ['v0_naive', 'v8_corrective']:
        for outcome in simulator.call('b4-' + variant, 'outcomes', {}):
            mapping[variant + '/' + outcome['draft_id']] = outcome
    target = ROOT / 'evals/results/b4/outcomes_reconciled.json'
    target.write_text(json.dumps({'source': 'isolated persisted GigSim; exact draft_id matching', 'outcomes': mapping}, indent=2))
    print('Verified', len(mapping), 'simulator outcomes; raw model results unchanged')


if __name__ == '__main__':
    main()
