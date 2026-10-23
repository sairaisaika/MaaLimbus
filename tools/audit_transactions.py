"""Audit: which transaction records the loop writes, and which ones it reads back.

A reservation written before an input, whose reader never runs, is the duplicate-
spend risk the acceptance document names: the next run cannot learn what the
previous one already bought.  The check is derived from the transaction modules'
own method names and from ``MirrorRunner.step``'s AST, so a new method is
classified without editing a list -- and an injected reader (a callable handed to
a helper) counts as a reader, because two of the shop's are exactly that.

Exit 0 when every intent has a reader, 1 when one does not or when a method the
families cannot place is called from the loop.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import transaction_ledger  # noqa: E402


def main(argv=None):
    return transaction_ledger.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
