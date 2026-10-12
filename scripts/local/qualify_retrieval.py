"""Sequential local evaluation; restore development services without touching volumes."""
import json
import os
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ENV={**os.environ,'COMPOSE_PROGRESS':'plain'}


def run(args):
    return subprocess.run(['docker','compose',*args],cwd=ROOT,env=ENV,
        capture_output=True,text=True,check=True,timeout=300)


def main():
    try:
        run(['--profile','test','stop','worker','frontend','worker-auth-test','frontend-auth-test','backend-auth-test'])
        run(['exec','-T','backend','python','-m','scripts.prepare_evaluation_database'])
        result=run(['--profile','evaluation','run','--rm','worker-evaluation'])
        report=json.loads(result.stdout)
        if report['status']!='passed' or report['final_cases_evaluated']!=0:raise RuntimeError('Invalid evaluation scope')
        (ROOT/'evaluation/reports/search-step5-development.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(f"Development Recall@5: {report['metrics']['recall_at_5']:.3f}; calibrated threshold: {report['threshold']}; final cases untouched")
    except subprocess.CalledProcessError as error:
        # Corpus is explicitly synthetic; never emit environment variables or connection strings.
        print(error.stderr[-3000:])
        raise RuntimeError('Local evaluation failed') from None
    finally:
        run(['up','-d','--no-deps','frontend','worker'])


if __name__=='__main__':
    main()
