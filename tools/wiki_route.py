"""Project entrypoint for the portable engineering-wiki router."""
import runpy
from pathlib import Path

if __name__=='__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1]/'skills/multi-agent-wiki/scripts/wiki_route.py'),run_name='__main__')
