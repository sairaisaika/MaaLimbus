import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'agent')]
from maalimbus.runtime_paths import ROOT
if getattr(sys, 'frozen', False):
    # maa.agent imports and opens its native library immediately.
    os.environ['MAAFW_BINARY_PATH'] = str(ROOT / 'maafw')

from maa.agent.agent_server import AgentServer
from maa.library import Library
from recognition import LimbusRecognition, LimbusTerminal, TeamAction, InputPreflight, ThemeObservation, DeploymentProof, BattlePlanObservation
from recognition import StarProof,InitialGiftProof,InitialReceiptProof,DifficultyProof
from recognition import MapObservation, BattleObservation


def main():
    import json
    if sys.argv[1:] == ['--self-test']:
        # Read actual installed resources and load native libraries; no controller.
        Library.open(ROOT / 'maafw', agent_server=True)
        for locale in ('en', 'jp'):
            LimbusRecognition(locale)
        from maalimbus.gift_vision import GiftCatalog
        GiftCatalog(ROOT / 'assets/resource/base')
        from maalimbus.theme_vision import ThemeCatalog
        ThemeCatalog(ROOT / 'assets/resource/base')
        print(json.dumps({'passed': True, 'application_root': str(ROOT),
                          'device_controller': False, 'locales': ['en', 'jp']}))
        return
    if len(sys.argv) != 2:
        raise SystemExit('Expected Maa Agent socket identifier or --self-test')
    resource = json.loads(os.environ.get('PI_RESOURCE', '{}'))
    locale = resource.get('name', 'en')
    Library.open(Path(os.environ.get('MAAFW_BINARY_PATH', ROOT / 'maafw')), agent_server=True)
    recognition = LimbusRecognition(locale)
    # MXU owns the actual controller; retain its chosen PI profile for diagnosis.
    recognition.journal.record('pi_controller', profile=json.loads(os.environ.get('PI_CONTROLLER', '{}')))
    AgentServer.register_custom_recognition('limbus_scene', recognition)
    AgentServer.register_custom_action('limbus_terminal', LimbusTerminal(recognition))
    AgentServer.register_custom_action('limbus_team', TeamAction(recognition))
    AgentServer.register_custom_action('limbus_star_proof',StarProof(recognition))
    AgentServer.register_custom_action('limbus_initial_gift_proof',InitialGiftProof(recognition))
    AgentServer.register_custom_action('limbus_initial_receipt_proof',InitialReceiptProof(recognition))
    AgentServer.register_custom_action('limbus_difficulty_proof',DifficultyProof(recognition))
    AgentServer.register_custom_action('limbus_preflight',InputPreflight(recognition))
    AgentServer.register_custom_action('limbus_theme_observe',ThemeObservation(recognition))
    AgentServer.register_custom_action('limbus_deployment_proof',DeploymentProof(recognition))
    AgentServer.register_custom_action('limbus_battle_plan_observe',BattlePlanObservation(recognition))
    # The map and battle observation nodes are read-only recorders that the pipeline
    # names (`MapObserve` / `BattleObserve`) and the toolkit drives directly; a node
    # whose custom_action was never registered cannot run at all, so both names must
    # be here even though no task entry reaches them yet.
    AgentServer.register_custom_action('limbus_map_observe',MapObservation(recognition))
    AgentServer.register_custom_action('limbus_battle_observe',BattleObservation(recognition))
    AgentServer.start_up(sys.argv[-1])
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == '__main__':
    main()
