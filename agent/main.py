import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'agent')]

from maa.agent.agent_server import AgentServer
from maa.library import Library
from recognition import LimbusRecognition, LimbusTerminal, TeamAction, InputPreflight


def main():
    import json
    resource = json.loads(os.environ.get('PI_RESOURCE', '{}'))
    locale = resource.get('name', 'en')
    Library.open(Path(os.environ.get('MAAFW_BINARY_PATH', ROOT / 'maafw')), agent_server=True)
    recognition = LimbusRecognition(locale)
    AgentServer.register_custom_recognition('limbus_scene', recognition)
    AgentServer.register_custom_action('limbus_terminal', LimbusTerminal(recognition))
    AgentServer.register_custom_action('limbus_team', TeamAction(recognition))
    AgentServer.register_custom_action('limbus_preflight',InputPreflight(recognition))
    AgentServer.start_up(sys.argv[-1])
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == '__main__':
    main()
