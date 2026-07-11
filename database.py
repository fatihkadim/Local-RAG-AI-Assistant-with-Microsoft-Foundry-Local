# TODO: SQLite veritabanı işlemleri burada implemente edilecek
# - init_db()           → Veritabanını ve tabloları oluşturur
# - insert_chunk()      → Belge parçası + embedding ekler
# - get_all_chunks()    → Tüm parçaları ve embedding'leri döndürür
# - clear_db()          → Veritabanını temizler (yeniden ingestion için)

import sqlite3
import json

def init_db():
    conn = sqlite3.connect("vector.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("basarili")

def insert_chunk(text,embedding):
    conn = sqlite3.connect("vector.db")
    cursor = conn.cursor()
    json_emb = json.dumps(embedding)
    cursor.execute('''
        INSERT INTO documents (text, embedding) VALUES (?,?)")
    ''',(text, json_emb))
    conn.commit()
    conn.close()
    print("insert basarili")
    