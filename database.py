import sqlite3
import re
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "recreio.db")

def init_db(db_path=None):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "recreio.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS contatos (
            id INTEGER PRIMARY KEY,
            titulo TEXT,
            preco TEXT,
            telefone TEXT UNIQUE,
            url TEXT UNIQUE,
            list_id TEXT UNIQUE,
            fonte TEXT,
            mensagem_enviada BOOLEAN DEFAULT 0,
            data_envio TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            descartado BOOLEAN DEFAULT 0,
            motivo_descarte TEXT,
            tipo_mensagem TEXT
        )
    """)
    conn.commit()
    return conn

def salvar_contato(conn, contato):
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR IGNORE INTO contatos (titulo, preco, telefone, url, list_id, fonte)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            contato["titulo"],
            contato["preco"],
            contato["telefone"],
            contato["url"],
            contato["list_id"],
            contato["fonte"],
        ))
        conn.commit()
        return c.rowcount > 0
    except sqlite3.Error as e:
        return False

def buscar_ids_existentes(conn):
    c = conn.cursor()
    rows = c.execute("SELECT list_id FROM contatos WHERE list_id IS NOT NULL").fetchall()
    return {row[0] for row in rows}

def buscar_telefones_existentes(conn):
    c = conn.cursor()
    rows = c.execute("SELECT telefone FROM contatos WHERE telefone IS NOT NULL").fetchall()
    return {row[0] for row in rows}

def buscar_pendentes(conn, limite=5):
    c = conn.cursor()
    return c.execute("""
        SELECT * FROM contatos
        WHERE mensagem_enviada = 0 
        AND telefone IS NOT NULL
        AND (descartado = 0 OR descartado IS NULL)
        LIMIT ?
    """, (limite,)).fetchall()

def marcar_enviado(conn, contato_id, tipo_mensagem):
    c = conn.cursor()
    c.execute("""
        UPDATE contatos SET mensagem_enviada = 1, data_envio = ?, tipo_mensagem = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), tipo_mensagem, contato_id))
    conn.commit()

def padronizar_telefones(conn):
    c = conn.cursor()
    rows = c.execute("SELECT id, telefone FROM contatos").fetchall()
    atualizados = 0
    removidos = 0
    for row in rows:
        id_, tel = row
        tel_limpo = re.sub(r'\D', '', tel)
        try:
            c.execute("UPDATE contatos SET telefone = ? WHERE id = ?", (tel_limpo, id_))
            atualizados += 1
        except sqlite3.IntegrityError:
            # Telefone duplicado — remove o registro mais antigo
            c.execute("DELETE FROM contatos WHERE id = ?", (id_,))
            removidos += 1
    conn.commit()
    print(f"✅ {atualizados} telefones padronizados, {removidos} duplicatas removidas.")