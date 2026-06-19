# -*- coding: utf-8 -*-
import sqlite3
db = sqlite3.connect(r'd:\lian\praPro\e\backend\app\static\qa_database.db')
c = db.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('TABLES:', [r[0] for r in c.fetchall()])
for t in ['pdf_files', 'categories', 'questions', 'user_progress', 'tags', 'review_logs']:
    try:
        c.execute(f'PRAGMA table_info({t})')
        cols = [r[1] for r in c.fetchall()]
        print(f'{t} cols:', cols)
        c.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'{t} rows:', c.fetchone()[0])
    except Exception as e:
        print(t, 'ERROR', e)
print('--- pdf_files ---')
for row in c.execute('SELECT * FROM pdf_files'):
    print(row)
print('--- questions (first 3) ---')
for row in c.execute('SELECT * FROM questions LIMIT 3'):
    print(row)
db.close()
