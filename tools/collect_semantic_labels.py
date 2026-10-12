"""Collect hash-bound owned-identity teacher proposals with no controller."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.semantic_labels import collect
from maalimbus.storage import write_json

if __name__=='__main__':
    result=collect(ROOT,ROOT/'assets/resource/base/identity-index.json',ROOT/'build/private-owned-inventory.json')
    write_json(ROOT/'build/owned-identity-semantic-labels.json',result)
    print('Automatic native-teacher semantic proposals:',len(result['labels']),'; NN applied:',False)
