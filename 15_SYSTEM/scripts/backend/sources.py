"""Explicit, local source ingestion. Raw records are authoritative; the index is disposable."""
import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
import unicodedata
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DATA = Path('.brain-data')
KINDS = ('document', 'research', 'conversation', 'generated')
FORMATS = ('text', 'codex-jsonl', 'claude-stream-json', 'cursor-stream-json')


def validate_record(folder):
    folder = Path(folder)
    if folder.is_symlink() or (folder / 'metadata.json').is_symlink() or (folder / 'raw.txt').is_symlink():
        raise ValueError('symbolic links are not permitted in source records')
    meta = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
    raw = (folder / 'raw.txt').read_bytes()
    kind, origin, source_format = meta['kind'], meta['origin'], meta.get('format', 'text')
    if kind not in KINDS or not isinstance(origin, str) or not origin.strip() or source_format not in FORMATS:
        raise ValueError('invalid source metadata')
    if source_format != 'text' and kind != 'conversation':
        raise ValueError('structured harness source requires conversation kind')
    digest = hashlib.sha256(raw).hexdigest()
    expected = hashlib.sha256((kind + '\0' + origin + '\0' + digest).encode('utf-8')).hexdigest()
    if meta['id'] != folder.name or meta['id'] != expected or meta['sha256'] != digest:
        raise ValueError('source identity or checksum mismatch')
    for field in ('filename', 'imported_at'):
        if not isinstance(meta[field], str) or not meta[field]:
            raise ValueError('invalid source metadata: ' + field)
    body = extract_text(raw, source_format)
    if not body.strip():
        raise ValueError('source is empty')
    return meta, raw, body


def extract_text(raw, source_format):
    text = raw.decode('utf-8-sig')
    if source_format == 'text':
        return text
    if source_format not in FORMATS:
        raise ValueError('unsupported source format')
    messages = []
    sessions = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError as exc:
            raise ValueError('invalid JSON on line %s' % number) from exc
        if not isinstance(item, dict):
            continue
        if source_format in ('claude-stream-json', 'cursor-stream-json'):
            session = item.get('session_id')
            if session is not None:
                if not isinstance(session, str) or not session.strip():
                    raise ValueError('invalid session id on line %s' % number)
                sessions.add(session)
                if len(sessions) > 1:
                    raise ValueError('stream contains more than one session')
        if source_format == 'codex-jsonl':
            if item.get('type') != 'response_item':
                continue
            payload = item.get('payload')
            if not isinstance(payload, dict) or payload.get('type') != 'message':
                continue
            role = payload.get('role')
            allowed = ('input_text', 'output_text')
        else:
            role = item.get('type')
            payload = item.get('message')
            allowed = ('text',)
            if not isinstance(payload, dict) or payload.get('role') != role:
                continue
        if role not in ('user', 'assistant'):
            continue
        content = payload.get('content')
        if isinstance(content, str) and source_format == 'claude-stream-json':
            parts = [content]
        elif isinstance(content, list):
            parts = [part['text'] for part in content if isinstance(part, dict)
                     and part.get('type') in allowed and isinstance(part.get('text'), str)]
        else:
            continue
        if parts:
            content_text = '\n'.join(parts)
            if source_format == 'cursor-stream-json' and role == 'assistant' and messages and messages[-1][0] == role:
                messages[-1] = (role, messages[-1][1] + content_text)
            else:
                messages.append((role, content_text))
    if not messages:
        raise ValueError('no supported user or assistant messages in JSONL')
    return '\n\n'.join(role + ': ' + content for role, content in messages)


def _atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(path.parent), prefix='.tmp-')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content if isinstance(content, bytes) else content.encode('utf-8'))
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def ingest(root, file, kind, origin, source_format='text'):
    """Import one explicitly selected UTF-8 file; duplicate content + origin is idempotent."""
    file = Path(file).resolve(strict=True)
    return ingest_bytes(root, file.read_bytes(), file.name, kind, origin, source_format)


def ingest_bytes(root, raw, filename, kind, origin, source_format='text'):
    """Import a validated snapshot of bytes, preserving the original filename."""
    if kind not in KINDS or not str(origin).strip() or source_format not in FORMATS:
        raise ValueError('a supported kind and nonempty origin are required')
    if source_format != 'text' and kind != 'conversation':
        raise ValueError('structured harness source requires conversation kind')
    body = extract_text(raw, source_format)
    if not body.strip():
        raise ValueError('source is empty')
    digest = hashlib.sha256(raw).hexdigest()
    identity = hashlib.sha256((kind + '\0' + origin + '\0' + digest).encode('utf-8')).hexdigest()
    source_dir = Path(root) / DATA / 'sources'
    if source_dir.is_symlink():
        raise ValueError('source directory cannot be a symbolic link')
    folder = source_dir / identity
    metadata = {'id': identity, 'kind': kind, 'origin': origin, 'filename': filename,
                'sha256': digest, 'format': source_format,
                'imported_at': datetime.now(timezone.utc).isoformat()}
    if folder.exists() or folder.is_symlink():
        if not (folder / 'metadata.json').is_file() or not (folder / 'raw.txt').is_file():
            raise ValueError('existing source is incomplete; inspect it before retrying')
        old, old_raw, _ = validate_record(folder)
        if old.get('format', 'text') != source_format:
            raise ValueError('source already imported with a different format')
        if old_raw != raw:
            raise ValueError('existing source is incomplete or corrupted')
        return old
    source_dir.mkdir(parents=True, exist_ok=True)
    folder.mkdir(exist_ok=False)
    _atomic(folder / 'raw.txt', raw)
    _atomic(folder / 'metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    return metadata


def rebuild(root):
    """Rebuild atomically from completed source records, preserving the old index on failure."""
    base = Path(root) / DATA
    base.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=str(base), prefix='.index-', suffix='.sqlite')
    os.close(fd)
    try:
        db = sqlite3.connect(temp)
        try:
            db.execute('CREATE TABLE sources (id TEXT PRIMARY KEY, kind TEXT, origin TEXT, filename TEXT, imported_at TEXT, body TEXT)')
            db.execute('CREATE TABLE document_lengths (id TEXT PRIMARY KEY, length INTEGER NOT NULL)')
            db.execute('CREATE TABLE term_counts (term TEXT NOT NULL, id TEXT NOT NULL, frequency INTEGER NOT NULL, PRIMARY KEY (term, id))')
            source_dir = base / 'sources'
            if source_dir.is_symlink():
                raise ValueError('source directory cannot be a symbolic link')
            folders = sorted(source_dir.iterdir()) if source_dir.exists() else []
            for folder in folders:
                if not folder.is_dir() or folder.is_symlink():
                    raise ValueError('unexpected item in source directory: %s' % folder.name)
                if not (folder / 'metadata.json').is_file() or not (folder / 'raw.txt').is_file():
                    raise ValueError('incomplete source record: %s' % folder.name)
                meta, raw, body = validate_record(folder)
                db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?)',
                           (meta['id'], meta['kind'], meta['origin'], meta['filename'], meta['imported_at'], body))
                tokens = re.findall(r'\w+', _normalise(body), re.UNICODE)
                db.execute('INSERT INTO document_lengths VALUES (?,?)', (meta['id'], len(tokens)))
                db.executemany('INSERT INTO term_counts VALUES (?,?,?)',
                               ((term, meta['id'], frequency) for term, frequency in Counter(tokens).items()))
            db.commit()
            count = db.execute('SELECT count(*) FROM sources').fetchone()[0]
        finally:
            db.close()
        os.replace(temp, str(base / 'index.sqlite'))
        return count
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _normalise(text):
    return unicodedata.normalize('NFKC', text).casefold().translate(str.maketrans({'ي': 'ی', 'ك': 'ک'}))


def search_scan(root, query, limit=10):
    """Compatibility search for indexes made before term statistics were introduced."""
    query = str(query).strip()
    if not query or not 1 <= limit <= 100:
        raise ValueError('query and limit (1-100) are required')
    index = Path(root) / DATA / 'index.sqlite'
    if not index.is_file():
        raise ValueError('index missing; run rebuild first')
    with closing(sqlite3.connect(str(index))) as db:
        rows = db.execute('SELECT id, kind, origin, filename, imported_at, body FROM sources').fetchall()
    terms = list(dict.fromkeys(re.findall(r'\w+', _normalise(query), re.UNICODE)))
    if not terms:
        return []
    documents = []
    for row in rows:
        tokens = re.findall(r'\w+', _normalise(row[5]), re.UNICODE)
        counts = Counter(tokens)
        frequencies = [sum(count for token, count in counts.items() if term in token) for term in terms]
        documents.append((row, len(tokens), frequencies))
    if not documents:
        return []
    count = len(documents)
    avg_length = sum(doc[1] for doc in documents) / count or 1
    frequencies_in_docs = [sum(1 for _, _, tf in documents if tf[i]) for i in range(len(terms))]
    scored = []
    for row, length, tf in documents:
        if not all(tf):
            continue
        score = 0.0
        for i, frequency in enumerate(tf):
            inverse = math.log(1 + (count - frequencies_in_docs[i] + 0.5) / (frequencies_in_docs[i] + 0.5))
            score += inverse * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / avg_length))
        scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], item[1][0]))
    return [dict(zip(('id', 'kind', 'origin', 'filename', 'imported_at', 'text'), row))
            for _, row in scored[:limit]]


def search(root, query, limit=10):
    query = str(query).strip()
    if not query or not 1 <= limit <= 100:
        raise ValueError('query and limit (1-100) are required')
    index = Path(root) / DATA / 'index.sqlite'
    if not index.is_file():
        raise ValueError('index missing; run rebuild first')
    terms = list(dict.fromkeys(re.findall(r'\w+', _normalise(query), re.UNICODE)))
    if not terms:
        return []
    with closing(sqlite3.connect(str(index))) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'document_lengths', 'term_counts'}.issubset(tables):
            return search_scan(root, query, limit)
        count, avg_length = db.execute('SELECT count(*), avg(length) FROM document_lengths').fetchone()
        if not count:
            return []
        avg_length = avg_length or 1
        frequencies = []
        for term in terms:
            rows = db.execute('SELECT id, sum(frequency) FROM term_counts '
                              'WHERE instr(term, ?) > 0 GROUP BY id', (term,)).fetchall()
            frequencies.append(dict(rows))
        candidates = set(frequencies[0])
        for term_frequencies in frequencies[1:]:
            candidates.intersection_update(term_frequencies)
        if not candidates:
            return []
        lengths = dict(db.execute('SELECT id, length FROM document_lengths'))
        scored = []
        for identity in candidates:
            length = lengths[identity]
            score = 0.0
            for term_frequencies in frequencies:
                tf = term_frequencies[identity]
                df = len(term_frequencies)
                inverse = math.log(1 + (count - df + 0.5) / (df + 0.5))
                score += inverse * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / avg_length))
            scored.append((score, identity))
        scored.sort(key=lambda item: (-item[0], item[1]))
        result = []
        for _, identity in scored[:limit]:
            row = db.execute('SELECT id, kind, origin, filename, imported_at, body FROM sources WHERE id = ?',
                             (identity,)).fetchone()
            if row is None:
                raise ValueError('index is inconsistent; rebuild it')
            result.append(dict(zip(('id', 'kind', 'origin', 'filename', 'imported_at', 'text'), row)))
        return result
