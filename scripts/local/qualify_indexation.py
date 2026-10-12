"""Run the real CPU qualification in a container that has no network interface."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    result = subprocess.run([
        'docker', 'run', '--rm', '--network', 'none', '--memory', '1536m',
        '-v', f'{ROOT / "backend"}:/app:ro',
        '-v', f'{ROOT / ".models/e5"}:/opt/models/e5:ro',
        '-v', f'{ROOT / "evaluation/corpus"}:/evaluation/corpus:ro',
        'assistant-rag-worker:local', 'python', '-m', 'scripts.qualify_resident_embeddings',
    ], cwd=ROOT, text=True, capture_output=True, check=True, timeout=240)
    report = json.loads(result.stdout)
    if report['status'] != 'passed' or report['container_network'] != 'none':
        raise RuntimeError('Offline embedding qualification failed')
    (ROOT / 'evaluation/reports/index-step4-resident-embeddings.json').write_text(
        json.dumps(report, indent=2) + '\n')
    print('Real resident E5 qualification passed with container networking disabled')


if __name__ == '__main__':
    main()
