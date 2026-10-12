"""Opt-in three-call qualification with synthetic public fixtures only."""
import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ENV={**os.environ,'COMPOSE_PROGRESS':'plain'}


def run(args):
    return subprocess.run(['docker','compose',*args],cwd=ROOT,env=ENV,capture_output=True,text=True,check=True,timeout=360)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true',required=True);parser.add_argument('--revalidate-retained',action='store_true');arguments=parser.parse_args()
    try:
        run(['--profile','test','stop','frontend','worker','backend-auth-test','frontend-auth-test','worker-auth-test','llm-test'])
        run(['exec','-T','backend','python','-m','scripts.prepare_evaluation_database'])
        result=run(['--profile','evaluation','run','--rm','--no-deps','-v',str(ROOT/'.secrets')+':/run/secrets/llm:ro','-e','LLM_FREE_PLAN_CONFIRMED=true','-e','LANGSMITH_TRACING=false','worker-evaluation','python','-m','scripts.qualify_answers','--real',*(['--revalidate-retained'] if arguments.revalidate_retained else [])])
        report=json.loads(result.stdout)
        assert report['actual_groq_calls']<=3 and report['final_cases_evaluated']==0
        name='answers-step6-rejected-latest.json' if report['status']=='failed' else 'answers-step6-groq.json'
        (ROOT/'evaluation/reports'/name).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print('Actual Groq calls:',report['actual_groq_calls'],'; status:',report['status'],'; final cases untouched')
        if report['status']=='failed':raise RuntimeError('Public fixture validation failed; inspect saved report before another call')
    except subprocess.CalledProcessError as error:
        print(error.stderr[-1800:])
        raise RuntimeError('Bounded synthetic qualification failed') from None
    finally:run(['up','-d','--no-deps','frontend','worker'])


if __name__=='__main__':main()
