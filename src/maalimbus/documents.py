"""One writer for every evidence document (D196).

The same crash landed three times from three writers -- the journal row (D194), the frame
document (D195) and the runner's own frame writer (`src/maalimbus/runner.py`) -- because
each of them called `json.dumps` directly and each of them died with
`ValueError: Circular reference detected` on a field that a healthy loop had handed it.

A document is evidence.  So it is written through one function that always produces a
document: a value that cannot be represented becomes its own text and is named under
`document_fields_textualised`, and the row is never lost because of it.
"""
import json
from pathlib import Path

TEXTUALISED = 'document_fields_textualised'


def _representable(value):
    try:
        json.dumps(value, default=str)
    except (TypeError, ValueError):
        return False
    return True


def as_document(data, *, indent=2):
    """The document for `data`: a dict whose unrepresentable values are text."""
    if not isinstance(data, dict):
        return data if _representable(data) else repr(data)[:2000]
    try:
        json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    except (TypeError, ValueError):
        safe, textualised = {}, []
        for key, value in data.items():
            if _representable(value):
                safe[key] = value
            else:
                safe[key] = repr(value)[:2000]
                textualised.append(key)
        if textualised:
            safe[TEXTUALISED] = textualised
        return safe
    return data


def write_document(path, data, *, indent=2):
    """Write `data` as JSON at `path`, always producing a document."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(as_document(data, indent=indent), ensure_ascii=False, indent=indent,
                      default=str) + '\n'
    path.write_text(text, encoding='utf-8')
    return path
