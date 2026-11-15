param([string]$LinuxProject = '/home/adeel/gigbid')
$ErrorActionPreference = 'Stop'
$b4SourceRoot = Split-Path -Parent $PSScriptRoot
$b4SourceLinux = '/mnt/' + $b4SourceRoot.Substring(0,1).ToLower() + $b4SourceRoot.Substring(2).Replace('\','/')
$b4Python = @'
import pathlib, shutil, subprocess, sys
source, target = map(pathlib.Path, sys.argv[1:3])
if not (target / '.venv-linux/bin/python').is_file():
    raise SystemExit('Use the configured Linux project and virtual environment')
files = [*source.glob('evals/rd_b/b4*.py'), *source.glob('evals/rd_b/review*.py'),
         source/'evals/rd_b/prepare_reviews.py', source/'evals/rd_b/reconcile_b4_outcomes.py',
         source/'evals/rd_b/b4_protocol.json', source/'agent/prompts/proposal_judge.md',
         source/'tests/unit/test_b4_evaluation.py', source/'evals/reviews/b4/review.html']
for path in files:
    destination = target/path.relative_to(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
for path in (source/'.local-models/b4-reviews').glob('*.json'):
    destination = target/'.local-models/b4-reviews'/path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
python = str(target/'.venv-linux/bin/python')
modules = ['evals.rd_b.b4_reset_pilot', 'evals.rd_b.b4_run', 'evals.rd_b.reconcile_b4_outcomes',
           'evals.rd_b.prepare_reviews', 'evals.rd_b.b4_judge', 'evals.rd_b.b4_report']
try:
    for module in modules:
        subprocess.run([python,'-m',module],cwd=target,check=True)
    subprocess.run([python,'-m','evals.rd_b.b4_judge','--target','proposals'],cwd=target,check=True)
    subprocess.run([python,'-m','evals.rd_b.b4_report'],cwd=target,check=True)
finally:
    for directory in ['evals/results/b4','evals/reviews/b4']:
        if (target/directory).exists():
            shutil.copytree(target/directory,source/directory,dirs_exist_ok=True)
    for name in ['panel_key.json','calibration_key.json']:
        path=target/'.local-models/b4-reviews'/name
        if path.exists():
            shutil.copy2(path,source/'.local-models/b4-reviews'/name)
'@
$b4Python | wsl.exe -d Ubuntu -- "$LinuxProject/.venv-linux/bin/python" - "$b4SourceLinux" "$LinuxProject"
if ($LASTEXITCODE -ne 0) { throw 'B4 pipeline stopped; saved results remain resumable. Inspect the error above.' }
