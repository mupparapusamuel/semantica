import os
import sys
import json
import tempfile
import re
from pathlib import Path
from collections import Counter, defaultdict
from flask import Flask, request, jsonify, send_from_directory

# Make the repo root importable so we can `import semantica` from the local clone
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

app = Flask(__name__, static_folder='.', static_url_path='')

UPLOAD_DIR = Path(tempfile.gettempdir()) / "semantica_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def safe_serialize(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return repr(obj)


STOPWORDS = set(["the","and","is","in","it","to","of","a","with","for","on","that","this","as","are","an","be"])


def extract_text_from_parsed(parsed, fallback_path=None):
    # semantica.parse.parse_document often returns dicts with `text` or `content`
    if isinstance(parsed, dict):
        for k in ("text", "content", "raw_text", "body"):
            if k in parsed and isinstance(parsed[k], str) and parsed[k].strip():
                return parsed[k]
    if fallback_path:
        try:
            with open(fallback_path, 'rb') as fh:
                data = fh.read()
            try:
                return data.decode('utf-8')
            except Exception:
                try:
                    return data.decode('latin-1')
                except Exception:
                    return ''
        except Exception:
            return ''
    return ''


def top_words(text, n=12):
    words = re.findall(r"[a-z0-9]+", (text or '').lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 1]
    c = Counter(words)
    return c.most_common(n)


def build_cooccurrence_graph(text, top_k=20, window=3):
    words = re.findall(r"[a-z0-9]+", (text or '').lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 1]
    counts = Counter(words)
    top_words_list = [w for w, _ in counts.most_common(top_k)]

    # Build edges when two top words appear within `window` tokens
    edges = defaultdict(int)
    for i, w in enumerate(words):
        if w not in top_words_list:
            continue
        for j in range(i+1, min(i+1+window, len(words))):
            v = words[j]
            if v in top_words_list and v != w:
                a, b = sorted((w, v))
                edges[(a, b)] += 1

    nodes = [{'id': w, 'label': w, 'size': max(5, int(counts[w]))} for w in top_words_list]
    edge_list = [{'source': a, 'target': b, 'weight': w} for (a, b), w in edges.items()]
    return {'nodes': nodes, 'edges': edge_list}


@app.route('/', methods=['GET'])
def index():
    return send_from_directory('.', 'index.html')


@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files') or []
    if not files:
        return jsonify({'error': 'No files provided'}), 400
    if len(files) > 5:
        return jsonify({'error': 'Maximum 5 files allowed'}), 400

    results = []
    for f in files:
        safe_name = f.filename.replace('..', '_')
        dest = UPLOAD_DIR / safe_name
        f.save(dest)

        # Try to import the semantica parse API
        parsed = None
        try:
            from semantica.parse import parse_document

            parsed = parse_document(file_path=str(dest))
            parsed = safe_serialize(parsed)
        except Exception as exc:
            parsed = {'error': str(exc)}

        text = extract_text_from_parsed(parsed, fallback_path=str(dest))
        preview = (text or '')[:2000]
        top = top_words(text, n=12)
        graph = build_cooccurrence_graph(text, top_k=20, window=3) if text else {'nodes': [], 'edges': []}

        # If semantica produced entities or relations, include them if present
        extra = {}
        if isinstance(parsed, dict):
            for k in ('entities', 'relations', 'topics'):
                if k in parsed:
                    extra[k] = parsed[k]

        results.append({
            'filename': safe_name,
            'parsed': parsed,
            'preview': preview,
            'top_words': [{'word': w, 'count': c} for w, c in top],
            'graph': graph,
            'extra': extra,
        })

    return jsonify({'results': results})


if __name__ == '__main__':
    # Helpful startup note
    print(f"Serving upload demo on http://localhost:5000 — upload dir: {UPLOAD_DIR}")
    app.run(host='127.0.0.1', port=5000, debug=True)
