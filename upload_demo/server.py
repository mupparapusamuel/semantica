import os
import sys
import json
import tempfile
import re
from pathlib import Path
from collections import Counter, defaultdict
from flask import Flask, request, jsonify, send_from_directory
import numpy as np

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

        # Semantic grouping and temporal extraction using semantica embedder if available
        try:
            from semantica.embeddings.text_embedder import TextEmbedder

            embedder = TextEmbedder()
            # split text into sentences for semantic grouping
            sentences = re.split(r"(?<=[.!?])\\s+", text.strip()) if text else []
            sentence_embeddings = []
            if sentences:
                try:
                    sentence_embeddings = embedder.embed_sentences(text)
                except Exception:
                    # fallback: embed sentences individually
                    sent_texts = [s for s in sentences if s.strip()]
                    if sent_texts:
                        arr = embedder.embed_batch(sent_texts)
                        sentence_embeddings = [arr[i] for i in range(len(arr))]

            semantic_groups = []
            node_group = {}
            temporal = {}

            if sentence_embeddings:
                # convert to numpy array
                X = np.vstack([np.array(v) for v in sentence_embeddings])
                n = X.shape[0]
                used = [False] * n
                groups = []
                # greedy clustering by cosine similarity
                for i in range(n):
                    if used[i]:
                        continue
                    used[i] = True
                    members = [i]
                    centroid = X[i].copy()
                    for j in range(i+1, n):
                        if used[j]:
                            continue
                        sim = float(np.dot(centroid, X[j]) / ((np.linalg.norm(centroid) * np.linalg.norm(X[j])) + 1e-12))
                        if sim > 0.72:
                            used[j] = True
                            members.append(j)
                            centroid += X[j]
                    groups.append(members)

                # build semantic group labels
                for gi, members in enumerate(groups):
                    combined = ' '.join([sentences[m] for m in members])
                    tops = top_words(combined, n=3)
                    label = ' '.join([w for w, _ in tops]) or f'group_{gi}'
                    semantic_groups.append({'id': f'grp{gi}', 'label': label, 'members': members})

                # map graph nodes (top words) to semantic groups by occurrence in member sentences
                for node in graph.get('nodes', []):
                    word = node.get('label')
                    best_g = None
                    best_count = 0
                    for gi, members in enumerate(groups):
                        cnt = 0
                        for m in members:
                            if re.search(rf"\\b{re.escape(word)}\\b", sentences[m], flags=re.I):
                                cnt += 1
                        if cnt > best_count:
                            best_count = cnt
                            best_g = gi
                    if best_g is not None and best_count > 0:
                        node_group[node.get('id')] = f'grp{best_g}'

            # temporal: find years in sentences and aggregate
            years = Counter()
            sentence_years = {}
            if text:
                for idx, s in enumerate(re.split(r"(?<=[.!?])\\s+", text.strip())):
                    yrs = re.findall(r"\\b(19|20)\\d{2}\\b", s)
                    # yrs returns list of '19'/'20' prefixes due to grouping; instead find full years
                    yrs_full = re.findall(r"\\b(19\\d{2}|20\\d{2})\\b", s)
                    if yrs_full:
                        for y in yrs_full:
                            years[y] += 1
                        sentence_years[idx] = yrs_full
                temporal = {'years': dict(years), 'sentence_years': sentence_years}

            if semantic_groups:
                extra['semantic'] = semantic_groups
            if node_group:
                extra['node_group'] = node_group
            if temporal:
                extra['temporal'] = temporal
        except Exception as e:
            # embedding/model not available or failed; skip semantic features
            try:
                extra['semantic_error'] = str(e)
            except Exception:
                extra['semantic_error'] = repr(e)

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
