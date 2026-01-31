import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import bcrypt

DB_NAME = 'dados_medcof.db'

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# ==========================================
# ⚙️ MÓDULO 1: INICIALIZAÇÃO E MANUTENÇÃO
# ==========================================

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    # Tabelas Base de Dados
    c.execute('''CREATE TABLE IF NOT EXISTS assuntos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, grande_area TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, data_estudo DATE, acertos INTEGER, total INTEGER, percentual REAL, FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS revisoes (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, data_agendada DATE, tipo TEXT, status TEXT DEFAULT 'Pendente', FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS conteudos (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, tipo TEXT, subtipo TEXT, titulo TEXT, link TEXT, message_id INTEGER UNIQUE, FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)''')
    
    # Tabelas de Gamificação e Segurança
    c.execute('''CREATE TABLE IF NOT EXISTS perfil_gamer (id INTEGER PRIMARY KEY CHECK (id = 1), nivel INTEGER DEFAULT 1, xp_atual INTEGER DEFAULT 0, xp_acumulado_total INTEGER DEFAULT 0, titulo TEXT DEFAULT 'Calouro')''')
    c.execute("INSERT OR IGNORE INTO perfil_gamer (id, nivel, xp_atual, xp_acumulado_total, titulo) VALUES (1, 1, 0, 0, 'Calouro')")
    c.execute('''CREATE TABLE IF NOT EXISTS missoes_hoje (id INTEGER PRIMARY KEY AUTOINCREMENT, data_missao DATE, descricao TEXT, tipo TEXT, meta_valor INTEGER, progresso_atual INTEGER DEFAULT 0, xp_recompensa INTEGER, concluida BOOLEAN DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, nome TEXT, password_hash BLOB)''')
    
    conn.commit(); conn.close()
    padronizar_areas()

def padronizar_areas():
    """Unifica Ginecologia e Obstetrícia para G.O. e limpa duplicatas"""
    conn = get_connection()
    conn.execute("UPDATE assuntos SET grande_area = 'G.O.' WHERE grande_area LIKE 'Gineco%' OR grande_area = 'Ginecologia e Obstetrícia'")
    conn.commit(); conn.close()

def resetar_progresso():
    """Resolve ImportError: resetar_progresso"""
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM historico")
    c.execute("DELETE FROM revisoes")
    conn.commit(); conn.close()
    return "🧹 Progresso resetado com sucesso!"

# ==========================================
# 🔐 MÓDULO 2: SEGURANÇA E ACESSO
# ==========================================

def verificar_login(u, p):
    conn = get_connection(); c = conn.cursor()
    user = c.execute("SELECT password_hash, nome FROM usuarios WHERE username = ?", (u,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(p.encode('utf-8'), user[0]): return True, user[1]
    return False, None

def criar_usuario(u, p, n):
    conn = get_connection(); c = conn.cursor()
    try:
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?, ?, ?)", (u, n, hashed))
        conn.commit(); return True, "Usuário criado!"
    except: return False, "Usuário já existe."
    finally: conn.close()

# ==========================================
# 🎮 MÓDULO 3: GAMIFICAÇÃO E XP
# ==========================================

def get_status_gamer():
    """Resolve ImportError: get_status_gamer"""
    conn = get_connection()
    row = conn.execute("SELECT nivel, xp_atual, xp_acumulado_total, titulo FROM perfil_gamer WHERE id = 1").fetchone()
    xp_prox = int(1000 * (1 + (row[0] * 0.15)))
    p = {"nivel": row[0], "xp_atual": row[1], "xp_total": row[2], "titulo": row[3], "xp_proximo": xp_prox}
    m = pd.read_sql("SELECT * FROM missoes_hoje WHERE data_missao = ?", conn, params=(datetime.now().date(),))
    conn.close(); return p, m

def adicionar_xp(qtd, conn):
    c = conn.cursor(); n, xp, tot = c.execute("SELECT nivel, xp_atual, xp_acumulado_total FROM perfil_gamer").fetchone()
    xp += qtd; tot += qtd; meta = int(1000 * (1 + (n * 0.15)))
    while xp >= meta: xp -= meta; n += 1; meta = int(1000 * (1 + (n * 0.15)))
    c.execute("UPDATE perfil_gamer SET nivel=?, xp_atual=?, xp_acumulado_total=? WHERE id=1", (n, xp, tot))

def processar_progresso_missao(tipo_acao, quantidade, area=None):
    """Resolve ImportError: processar_progresso_missao"""
    conn = get_connection(); c = conn.cursor(); hoje = datetime.now().date()
    ativas = c.execute("SELECT id, tipo, meta_valor, progresso_atual, xp_recompensa, descricao FROM missoes_hoje WHERE data_missao = ? AND concluida = 0", (hoje,)).fetchall()
    msgs = []
    for mid, mtipo, meta, prog, xp_rw, desc in ativas:
        if (mtipo == "questoes" and tipo_acao == "questoes") or (mtipo == "revisao" and tipo_acao == "revisao"):
            novo_p = prog + quantidade
            if novo_p >= meta:
                c.execute("UPDATE missoes_hoje SET progresso_atual = ?, concluida = 1 WHERE id = ?", (meta, mid))
                adicionar_xp(xp_rw, conn); msgs.append(f"🏆 {desc}")
            else:
                c.execute("UPDATE missoes_hoje SET progresso_atual = ? WHERE id = ?", (novo_p, mid))
    conn.commit(); conn.close(); return msgs

# ==========================================
# 📅 MÓDULO 4: REGISTROS E LÓGICA SRS (REAGENDAMENTO)
# ==========================================

def registrar_estudo(assunto, acertos, total, data_personalizada=None):
    conn = get_connection(); c = conn.cursor()
    res = c.execute("SELECT id, grande_area FROM assuntos WHERE nome=?", (assunto,)).fetchone()
    
    # Se for Banco Geral (livre), cria o assunto automaticamente se não existir
    if not res:
        if "Banco Geral" in assunto or "Livre" in assunto:
            c.execute("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, 'Banco Geral')", (assunto,))
            res = c.execute("SELECT id, grande_area FROM assuntos WHERE nome=?", (assunto,)).fetchone()
        else:
            conn.close(); return "Erro: Assunto não encontrado."
    
    aid, area = res
    dt = data_personalizada if data_personalizada else datetime.now().date()
    
    # Registra no Histórico
    c.execute("INSERT INTO historico (assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?)", (aid, dt, acertos, total, (acertos/total*100)))
    
    # Agenda a 1ª Revisão (1 Semana) - Apenas para temas específicos
    if "Simulado" not in assunto and "Banco Geral" not in assunto:
        c.execute("INSERT INTO revisoes (assunto_id, data_agendada, tipo, status) VALUES (?,?,?,'Pendente')", (aid, dt + timedelta(days=7), "1 Semana"))
    
    adicionar_xp(int(total * 2), conn)
    processar_progresso_missao("questoes", total, area)
    conn.commit(); conn.close(); return "✅ Registado com sucesso!"

def registrar_simulado(dados, data_personalizada=None):
    """Registo por área conforme programado antes"""
    conn = get_connection(); c = conn.cursor()
    dt = data_personalizada if data_personalizada else datetime.now().date()
    total_questoes_simulado = 0
    for area, v in dados.items():
        if v['total'] > 0:
            total_questoes_simulado += v['total']
            c.execute("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?,?)", (f"Simulado - {area}", area))
            aid = c.execute("SELECT id FROM assuntos WHERE nome=?", (f"Simulado - {area}",)).fetchone()[0]
            c.execute("INSERT INTO historico (assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?)", (aid, dt, v['acertos'], v['total'], (v['acertos']/v['total']*100)))
    
    adicionar_xp(int(total_questoes_simulado * 2.5), conn) # XP extra para simulados
    processar_progresso_missao("questoes", total_questoes_simulado)
    conn.commit(); conn.close(); return "✅ Simulado registado com sucesso!"

def concluir_revisao(rid, acertos, total):
    """Lógica SRS: 1 Sem -> 1 Mês -> 2 Meses -> 4 Meses"""
    conn = get_connection(); c = conn.cursor()
    rev = c.execute("SELECT r.assunto_id, r.tipo, a.grande_area FROM revisoes r JOIN assuntos a ON r.assunto_id = a.id WHERE r.id=?", (rid,)).fetchone()
    if not rev: conn.close(); return "Erro ao encontrar revisão."
    
    aid, tipo_atual, area = rev
    hoje = datetime.now().date()
    
    # Ciclo de saltos (Spaced Repetition)
    saltos = {
        "1 Semana": (30, "1 Mês"),
        "1 Mês": (60, "2 Meses"),
        "2 Meses": (120, "4 Meses"),
        "4 Meses": (0, "Finalizado")
    }
    
    dias, prox = saltos.get(tipo_atual, (0, "Finalizado"))
    
    # 1. Conclui a atual
    c.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (rid,))
    
    # 2. Guarda no histórico de desempenho
    c.execute("INSERT INTO historico (assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?)", (aid, hoje, acertos, total, (acertos/total*100)))
    
    # 3. REAGENDA ATIVAMENTE para a próxima fase
    if prox != "Finalizado":
        nova_data = hoje + timedelta(days=dias)
        c.execute("INSERT INTO revisoes (assunto_id, data_agendada, tipo, status) VALUES (?,?,?, 'Pendente')", (aid, nova_data, prox))
        msg = f"🚀 Reagendado para {prox} ({nova_data.strftime('%d/%m')})!"
    else:
        msg = "🏆 Ciclo finalizado! Conhecimento consolidado."
    
    adicionar_xp(150 + (total * 3), conn)
    processar_progresso_missao("revisao", 1)
    conn.commit(); conn.close(); return msg

def listar_revisoes_completas():
    """Resolve ImportError: listar_revisoes_completas (Necessário para o calendário)"""
    conn = get_connection()
    df = pd.read_sql("""SELECT r.id, a.nome as assunto, a.grande_area, r.data_agendada, r.tipo, r.status 
                        FROM revisoes r JOIN assuntos a ON r.assunto_id = a.id 
                        ORDER BY r.data_agendada ASC""", conn)
    conn.close(); return df

def listar_revisoes_pendentes():
    conn = get_connection()
    df = pd.read_sql("""SELECT r.id, a.nome as assunto, a.grande_area, r.data_agendada, r.tipo, r.status 
                        FROM revisoes r JOIN assuntos a ON r.assunto_id = a.id WHERE r.status = 'Pendente'""", conn)
    conn.close(); return df

# ==========================================
# ⚙️ MÓDULO 5: BUSCA E GESTÃO DE CONTEÚDO
# ==========================================

def listar_conteudo_videoteca():
    """Resolve ImportError: listar_conteudo_videoteca"""
    conn = get_connection()
    df = pd.read_sql("""SELECT c.id, a.grande_area, a.nome as assunto, c.tipo, c.subtipo, c.titulo, c.link 
                        FROM conteudos c JOIN assuntos a ON c.assunto_id = a.id ORDER BY a.grande_area""", conn)
    conn.close(); return df

def pesquisar_global(t):
    conn = get_connection(); tf = f"%{t.lower()}%"
    df = pd.read_sql("""SELECT c.id, a.grande_area, a.nome as assunto, c.tipo, c.subtipo, c.titulo, c.link 
                        FROM conteudos c JOIN assuntos a ON c.assunto_id = a.id 
                        WHERE lower(c.titulo) LIKE ? OR lower(a.nome) LIKE ?""", conn, params=(tf, tf))
    conn.close(); return df

def excluir_conteudo(id_c):
    """Resolve ImportError: excluir_conteudo"""
    conn = get_connection(); conn.execute("DELETE FROM conteudos WHERE id=?", (id_c,)); conn.commit(); conn.close()

def atualizar_nome_assunto(id_a, n):
    conn = get_connection(); conn.execute("UPDATE assuntos SET nome=? WHERE id=?", (n, id_a)); conn.commit(); conn.close(); return True, "Ok"

def deletar_assunto(id_a):
    conn = get_connection(); conn.execute("DELETE FROM assuntos WHERE id=?", (id_a,)); conn.commit(); conn.close()

def registrar_topico_do_sumario(g, n):
    conn = get_connection(); c = conn.cursor()
    try: c.execute("INSERT INTO assuntos (nome, grande_area) VALUES (?,?)", (n, g))
    except: c.execute("UPDATE assuntos SET grande_area=? WHERE nome=?", (g, n))
    conn.commit(); conn.close()

# ==========================================
# ⚙️ MÓDULO 6: CONFIGURAÇÕES E STATS
# ==========================================

def get_progresso_hoje():
    conn = get_connection(); r = conn.cursor().execute("SELECT SUM(total) FROM historico WHERE data_estudo=?", (datetime.now().date(),)).fetchone()
    conn.close(); return r[0] if r[0] else 0

def salvar_config(k, v):
    """Resolve ImportError: salvar_config"""
    conn = get_connection(); conn.execute("INSERT OR REPLACE INTO configuracoes VALUES (?,?)", (k, str(v))); conn.commit(); conn.close()

def ler_config(k):
    conn = get_connection(); r = conn.cursor().execute("SELECT valor FROM configuracoes WHERE chave=?", (k,)).fetchone(); conn.close()
    return r[0] if r else None

inicializar_db()