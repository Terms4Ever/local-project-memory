"""Resumable text-index migration. Canonical entries and originals never change.

Base schema stays readable by 1.3.x. Feature text_index=1 owns the new
external-content table. Old writers enqueue IDs via ordinary SQL triggers;
new readers drain that queue before searching. No Python SQL function is
required by an old connection.
"""
import contextlib
import hashlib
import re

FEATURE = 'text_index_v1'
# Encoded image/binary runs are not meaningful search terms. Keep every byte
# in entries.body; only this replaceable search projection omits them.
BINARY_RUN = re.compile(r'[A-Za-z0-9+/=]{4096,}')


def searchable(body):
    return BINARY_RUN.sub('[binary preserved in original record]', body)


@contextlib.contextmanager
def transaction(db):
    nested = db.in_transaction
    if not nested: db.execute('BEGIN IMMEDIATE')
    try:
        yield
        if not nested: db.execute('COMMIT')
    except BaseException:
        if not nested: db.execute('ROLLBACK')
        raise


def state(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='memory_features'").fetchone():
        return None
    row = db.execute('SELECT stage,cursor,target FROM memory_features WHERE name=?', (FEATURE,)).fetchone()
    return dict(zip(('stage','cursor','target'),row)) if row else None


def prepare(db):
    if state(db) is not None: return
    with transaction(db):
        statements = [
            'CREATE TABLE IF NOT EXISTS memory_features(name TEXT PRIMARY KEY,stage TEXT NOT NULL,cursor INTEGER NOT NULL,target INTEGER NOT NULL)',
            'CREATE TABLE IF NOT EXISTS search_dirty(entry_id INTEGER PRIMARY KEY REFERENCES entries(id))',
            'CREATE TABLE IF NOT EXISTS search_documents(entry_id INTEGER PRIMARY KEY REFERENCES entries(id),title TEXT NOT NULL,body TEXT NOT NULL,body_sha256 TEXT NOT NULL,scope_key TEXT NOT NULL,category TEXT NOT NULL)',
            "CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts_v2 USING fts5(title,body,scope_key,category,content='search_documents',content_rowid='entry_id',tokenize='unicode61 remove_diacritics 2')",
            '''CREATE TRIGGER IF NOT EXISTS search_dirty_ai AFTER INSERT ON entries BEGIN
                INSERT OR REPLACE INTO search_dirty VALUES(new.id); END''',
            '''CREATE TRIGGER IF NOT EXISTS search_dirty_au AFTER UPDATE OF title,body,project_id,kind,source,state ON entries BEGIN
                INSERT OR REPLACE INTO search_dirty VALUES(new.id); END''',
            '''CREATE TRIGGER IF NOT EXISTS search_documents_ai AFTER INSERT ON search_documents BEGIN
                INSERT INTO entries_fts_v2(rowid,title,body,scope_key,category) VALUES(new.entry_id,new.title,new.body,new.scope_key,new.category); END''',
            '''CREATE TRIGGER IF NOT EXISTS search_documents_au AFTER UPDATE ON search_documents BEGIN
                INSERT INTO entries_fts_v2(entries_fts_v2,rowid,title,body,scope_key,category) VALUES('delete',old.entry_id,old.title,old.body,old.scope_key,old.category);
                INSERT INTO entries_fts_v2(rowid,title,body,scope_key,category) VALUES(new.entry_id,new.title,new.body,new.scope_key,new.category); END''',
        ]
        for sql in statements: db.execute(sql)
        db.execute('INSERT OR IGNORE INTO memory_features VALUES(?,?,0,?)',
                   (FEATURE,'building',db.execute('SELECT coalesce(max(id),0) FROM entries').fetchone()[0]))


def index_row(db,row):
    body = searchable(row['body'])
    category='notes' if row['source']=='note' else 'history' if row['kind'] in ('prompt','legacy_summary','legacy_observation') else 'raw'
    db.execute('''INSERT INTO search_documents VALUES(?,?,?,?,?,?) ON CONFLICT(entry_id)
        DO UPDATE SET title=excluded.title,body=excluded.body,body_sha256=excluded.body_sha256,
        scope_key=excluded.scope_key,category=excluded.category''',
        (row['id'],row['title'],body,hashlib.sha256(row['body'].encode('utf8')).hexdigest(),'p'+row['project_id'],category))


def sync(db,limit=100):
    feature=state(db)
    if not feature or feature['stage']!='ready': return 0
    return drain(db,limit)


def drain(db,limit):
    if not db.execute('SELECT 1 FROM search_dirty LIMIT 1').fetchone(): return 0
    with transaction(db):
        rows=db.execute('''SELECT e.* FROM search_dirty d JOIN entries e ON e.id=d.entry_id
            ORDER BY e.id LIMIT ?''',(limit,)).fetchall()
        for row in rows:
            index_row(db,row)
            db.execute('DELETE FROM search_dirty WHERE entry_id=?',(row['id'],))
    return len(rows)


def optimize(db,progress=None,batch=40):
    """Build beside the old index, resume after interruption, then atomically swap."""
    prepare(db)
    feature=state(db)
    if feature['stage']=='ready':
        while sync(db,batch): pass
        return feature
    while feature['cursor']<feature['target']:
        rows=db.execute('SELECT * FROM entries WHERE id>? AND id<=? ORDER BY id LIMIT ?',
                        (feature['cursor'],feature['target'],batch)).fetchall()
        if not rows: raise ValueError('Index migration cursor cannot reach target.')
        with transaction(db):
            for row in rows: index_row(db,row)
            db.execute('UPDATE memory_features SET cursor=? WHERE name=?',(rows[-1]['id'],FEATURE))
        feature=state(db)
        if progress: progress(feature)
    while drain(db,batch): pass
    with transaction(db):
        # Finish concurrent 1.3.x writes before switching names.
        while drain(db,batch): pass
        db.execute('DROP TRIGGER IF EXISTS entries_ai')
        db.execute('DROP TRIGGER IF EXISTS entries_au')
        # Keep the old derived index for an explicit rollback. Renaming avoids
        # a long live write lock while SQLite frees gigabytes of binary tokens.
        db.execute('ALTER TABLE entries_fts RENAME TO entries_fts_legacy_v1')
        # Recreate projection triggers explicitly: FTS command-column names must
        # change too, and SQLite table rename does not rename that column in SQL.
        db.execute('DROP TRIGGER search_documents_ai')
        db.execute('DROP TRIGGER search_documents_au')
        db.execute('ALTER TABLE entries_fts_v2 RENAME TO entries_fts')
        db.execute('''CREATE TRIGGER search_documents_ai AFTER INSERT ON search_documents BEGIN
            INSERT INTO entries_fts(rowid,title,body,scope_key,category) VALUES(new.entry_id,new.title,new.body,new.scope_key,new.category); END''')
        db.execute('''CREATE TRIGGER search_documents_au AFTER UPDATE ON search_documents BEGIN
            INSERT INTO entries_fts(entries_fts,rowid,title,body,scope_key,category) VALUES('delete',old.entry_id,old.title,old.body,old.scope_key,old.category);
            INSERT INTO entries_fts(rowid,title,body,scope_key,category) VALUES(new.entry_id,new.title,new.body,new.scope_key,new.category); END''')
        db.execute("INSERT INTO entries_fts(entries_fts,rank) VALUES('integrity-check',1)")
        db.execute("UPDATE memory_features SET stage='ready' WHERE name=?",(FEATURE,))
    return state(db)


def rollback(db):
    """Explicit rollback; rebuilds old FTS from current data, never an old backup."""
    if not state(db) or state(db)['stage']!='ready':return state(db)
    with transaction(db):
        db.execute('DROP TRIGGER search_documents_ai')
        db.execute('DROP TRIGGER search_documents_au')
        db.execute('ALTER TABLE entries_fts RENAME TO entries_fts_v2')
        db.execute('ALTER TABLE entries_fts_legacy_v1 RENAME TO entries_fts')
        db.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        db.execute('''CREATE TRIGGER entries_ai AFTER INSERT ON entries BEGIN
            INSERT INTO entries_fts(rowid,title,body) VALUES(new.id,new.title,new.body); END''')
        db.execute('''CREATE TRIGGER entries_au AFTER UPDATE OF title,body ON entries BEGIN
            INSERT INTO entries_fts(entries_fts,rowid,title,body) VALUES('delete',old.id,old.title,old.body);
            INSERT INTO entries_fts(rowid,title,body) VALUES(new.id,new.title,new.body); END''')
        db.execute('''CREATE TRIGGER search_documents_ai AFTER INSERT ON search_documents BEGIN
            INSERT INTO entries_fts_v2(rowid,title,body,scope_key,category) VALUES(new.entry_id,new.title,new.body,new.scope_key,new.category); END''')
        db.execute('''CREATE TRIGGER search_documents_au AFTER UPDATE ON search_documents BEGIN
            INSERT INTO entries_fts_v2(entries_fts_v2,rowid,title,body,scope_key,category) VALUES('delete',old.entry_id,old.title,old.body,old.scope_key,old.category);
            INSERT INTO entries_fts_v2(rowid,title,body,scope_key,category) VALUES(new.entry_id,new.title,new.body,new.scope_key,new.category); END''')
        db.execute("UPDATE memory_features SET stage='building',cursor=0,target=(SELECT coalesce(max(id),0) FROM entries) WHERE name=?",(FEATURE,))
    return state(db)
