import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import bcrypt

DB_NAME = 'dados_medcof.db'

def get_connection():
    # Timeout de 30 segundos para dar tempo de outras conexões terminarem [cite: 529]
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=30)

# ==========================================
# ⚙️ MÓDULO 1: INICIALIZAÇÃO
# ==========================================

def inicializar_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS assuntos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, grande_area TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, data_estudo DATE, acertos INTEGER, total INTEGER, percentual REAL, FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, data_agendada DATE, tipo TEXT, status TEXT DEFAULT 'Pendente', FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS conteudos (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, tipo TEXT, subtipo TEXT, titulo TEXT, link TEXT, message_id INTEGER UNIQUE, FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS perfil_gamer (id INTEGER PRIMARY KEY CHECK (id = 1), nivel INTEGER DEFAULT 1, xp_atual INTEGER DEFAULT 0, xp_acumulado_total INTEGER DEFAULT 0, titulo TEXT DEFAULT 'Calouro')''')
        c.execute("INSERT OR IGNORE INTO perfil_gamer (id, nivel, xp_atual, xp_acumulado_total, titulo) VALUES (1, 1, 0, 0, 'Calouro')")
        c.execute('''CREATE TABLE IF NOT EXISTS missoes_hoje (id INTEGER PRIMARY KEY AUTOINCREMENT, data_missao DATE, descricao TEXT, tipo TEXT, meta_valor INTEGER, progresso_atual INTEGER DEFAULT 0, xp_recompensa INTEGER, concluida BOOLEAN DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash BLOB)''')
        conn.commit()
    
    padronizar_areas()

    try:
        from aulas_medcof import DADOS_LIMPOS
        with get_connection() as conn:
            c = conn.cursor()
            if c.execute("SELECT COUNT(*) FROM assuntos").fetchone()[0] == 0:
                c.executemany("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, ?)", DADOS_LIMPOS)
                conn.commit()
    except ImportError:
        pass

def padronizar_areas():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE assuntos SET grande_area = 'G.O.' WHERE grande_area LIKE 'Gineco%'")
        conn.commit()

# ==========================================
# 👤 MÓDULO 2: USUÁRIOS
# ==========================================

def criar_usuario(username, password, nome):
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?,?,?)", (username, nome, hashed))
            conn.commit()
        return True, "Usuário criado!"
    except:
        return False, "Usuário já existe."

def verificar_login(username, password):
    with get_connection() as conn:
        c = conn.cursor()
        user = c.execute("SELECT password_hash, nome FROM usuarios WHERE username=?", (username,)).fetchone()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[0]):
        return True, user[1]
    return False, None

# ==========================================
# 📝 MÓDULO 3: REGISTROS
# ==========================================

def registrar_estudo(nome_assunto, acertos, total, data_personalizada=None):
    dt = data_personalizada if data_personalizada else datetime.now().date()
    with get_connection() as conn:
        c = conn.cursor()
        res = c.execute("SELECT id, grande_area FROM assuntos WHERE nome=?", (nome_assunto,)).fetchone()
        if not res: return "Erro: Assunto não encontrado."
        
        aid, area = res
        c.execute("INSERT INTO historico (assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?)", (aid, dt, acertos, total, (acertos/total*100)))
        c.execute("INSERT INTO revisoes (assunto_id, data_agendada, tipo) VALUES (?,?,?)", (aid, dt + timedelta(days=7), "1 Semana"))
        conn.commit()
    
    adicionar_xp_v2(int(total * 2))
    processar_progresso_missao( "questoes", total)
    return "✅ Registrado!"

def registrar_simulado(dados, data_personalizada=None):
    dt = data_personalizada if data_personalizada else datetime.now().date()
    total_q = 0
    with get_connection() as conn:
        c = conn.cursor()
        for area, v in dados.items():
            if v['total'] > 0:
                total_q += v['total']
                c.execute("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?,?)", (f"Simulado - {area}", area))
                aid = c.execute("SELECT id FROM assuntos WHERE nome=?", (f"Simulado - {area}",)).fetchone()[0]
                c.execute("INSERT INTO historico (assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?)", (aid, dt, v['acertos'], v['total'], (v['acertos']/v['total']*100)))
        conn.commit()
    adicionar_xp_v2(int(total_q * 2.5))
    processar_progresso_missao("questoes", total_q)
    return "✅ Simulado registrado!"

# ==========================================
# 🎮 MÓDULO 4: GAMIFICAÇÃO (XP V2)
# ==========================================

def adicionar_xp_v2(qtd):
    with get_connection() as conn:
        c = conn.cursor()
        n, xp, tot = c.execute("SELECT nivel, xp_atual, xp_acumulado_total FROM perfil_gamer").fetchone()
        xp += qtd; tot += qtd; meta = int(1000 * (1 + (n * 0.15)))
        while xp >= meta: xp -= meta; n += 1; meta = int(1000 * (1 + (n * 0.15)))
        c.execute("UPDATE perfil_gamer SET nivel=?, xp_atual=?, xp_acumulado_total=? WHERE id=1", (n, xp, tot))
        conn.commit()

def processar_progresso_missao(tipo_acao, quantidade):
    hoje = datetime.now().date()
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE missoes_hoje SET progresso_atual = progresso_atual + ? WHERE data_missao = ? AND tipo = ? AND concluida = 0", (quantidade, hoje, tipo_acao))
        concluidas = c.execute("SELECT id, xp_recompensa FROM missoes_hoje WHERE progresso_atual >= meta_valor AND concluida = 0").fetchall()
        for mid, xp in concluidas:
            c.execute("UPDATE missoes_hoje SET concluida = 1 WHERE id = ?", (mid,))
            conn.commit() # Salva conclusão antes de dar XP
            adicionar_xp_v2(xp)
        conn.commit()

# ==========================================
# 📚 MÓDULO 5: VIDEOTECA & AGENDA
# ==========================================

def listar_conteudo_videoteca():
    with get_connection() as conn:
        df = pd.read_sql("""SELECT c.id, a.grande_area, a.nome as assunto, c.tipo, c.subtipo, c.titulo, c.link 
                            FROM conteudos c JOIN assuntos a ON c.assunto_id = a.id ORDER BY a.grande_area""", conn)
    return df

def excluir_conteudo(id_c):
    with get_connection() as conn:
        conn.execute("DELETE FROM conteudos WHERE id=?", (id_c,))
        conn.commit()

def pesquisar_global(t):
    tf = f"%{t.lower()}%"
    with get_connection() as conn:
        df = pd.read_sql("""SELECT c.id, a.grande_area, a.nome as assunto, c.tipo, c.subtipo, c.titulo, c.link 
                            FROM conteudos c JOIN assuntos a ON c.assunto_id = a.id 
                            WHERE lower(c.titulo) LIKE ? OR lower(a.nome) LIKE ?""", conn, params=(tf, tf))
    return df

def get_status_gamer():
    with get_connection() as conn:
        row = conn.execute("SELECT nivel, xp_atual, xp_acumulado_total, titulo FROM perfil_gamer WHERE id = 1").fetchone()
        xp_prox = int(1000 * (1 + (row[0] * 0.15)))
        p = {"nivel": row[0], "xp_atual": row[1], "xp_total": row[2], "titulo": row[3], "xp_proximo": xp_prox}
        m = pd.read_sql("SELECT * FROM missoes_hoje WHERE data_missao = ?", conn, params=(datetime.now().date(),))
    return p, m

def get_progresso_hoje():
    with get_connection() as conn:
        r = conn.execute("SELECT SUM(total) FROM historico WHERE data_estudo=?", (datetime.now().date(),)).fetchone()
    return r[0] if r[0] else 0

def concluir_revisao(rid, acertos, total):
    hoje = datetime.now().date()
    with get_connection() as conn:
        c = conn.cursor()
        rev = c.execute("SELECT assunto_id, tipo FROM revisoes WHERE id=?", (rid,)).fetchone()
        if not rev: return "Erro."
        aid, tipo_atual = rev
        saltos = {"1 Semana": (30, "1 Mês"), "1 Mês": (60, "2 Meses"), "2 Meses": (120, "4 Meses"), "4 Meses": (0, "Finalizado")}
        dias, prox = saltos.get(tipo_atual, (0, "Finalizado"))
        c.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
        if prox != "Finalizado":
            c.execute("INSERT INTO revisoes (assunto_id, data_agendada, tipo) VALUES (?,?,?)", (aid, hoje + timedelta(days=dias), prox))
        conn.commit()
    adicionar_xp_v2(100)
    processar_progresso_missao("revisao", 1)
    return "🚀 Revisado!"

def listar_revisoes_completas():
    with get_connection() as conn:
        df = pd.read_sql("SELECT r.id, a.nome as assunto, a.grande_area, r.data_agendada, r.tipo, r.status FROM revisoes r JOIN assuntos a ON r.assunto_id = a.id", conn)
    return df

def ler_config(k):
    with get_connection() as conn:
        r = conn.execute("SELECT valor FROM configuracoes WHERE chave=?", (k,)).fetchone()
    return r[0] if r else None

def salvar_config(k, v):
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO configuracoes VALUES (?,?)", (k, str(v)))
        conn.commit()

inicializar_db()