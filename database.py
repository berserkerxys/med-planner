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
    
    # Tabelas Base
    c.execute('''CREATE TABLE IF NOT EXISTS assuntos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, grande_area TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS historico 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, data_estudo DATE, 
                  acertos INTEGER, total INTEGER, percentual REAL, 
                  FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS revisoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, data_agendada DATE, 
                  tipo TEXT, status TEXT DEFAULT 'Pendente', 
                  FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS conteudos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, assunto_id INTEGER, tipo TEXT, 
                  subtipo TEXT, titulo TEXT, link TEXT, message_id INTEGER UNIQUE, 
                  FOREIGN KEY(assunto_id) REFERENCES assuntos(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes 
                 (chave TEXT PRIMARY KEY, valor TEXT)''')
    
    # Gamificação
    c.execute('''CREATE TABLE IF NOT EXISTS perfil_gamer 
                 (id INTEGER PRIMARY KEY CHECK (id = 1), nivel INTEGER DEFAULT 1, 
                  xp_atual INTEGER DEFAULT 0, xp_acumulado_total INTEGER DEFAULT 0, 
                  titulo TEXT DEFAULT 'Calouro')''')
    
    c.execute("INSERT OR IGNORE INTO perfil_gamer (id, nivel, xp_atual, xp_acumulado_total, titulo) VALUES (1, 1, 0, 0, 'Calouro')")
    
    c.execute('''CREATE TABLE IF NOT EXISTS missoes_hoje 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data_missao DATE, descricao TEXT, 
                  tipo TEXT, meta_valor INTEGER, progresso_atual INTEGER DEFAULT 0, 
                  xp_recompensa INTEGER, concluida BOOLEAN DEFAULT 0)''')
    
    # Usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (username TEXT PRIMARY KEY, nome TEXT, password_hash BLOB)''')
    
    conn.commit(); conn.close()
    
    padronizar_areas()

    # --- AUTO-POPULAÇÃO DAS AULAS (DADOS LIMPOS) ---
    try:
        from aulas_medcof import DADOS_LIMPOS
        conn = get_connection(); c = conn.cursor()
        contagem = c.execute("SELECT COUNT(*) FROM assuntos").fetchone()[0]
        if contagem == 0:
            c.executemany("INSERT OR IGNORE INTO assuntos (nome, grande_area) VALUES (?, ?)", DADOS_LIMPOS)
            conn.commit()
        conn.close()
    except ImportError:
        pass

def padronizar_areas():
    """Garante que as áreas tenham nomes consistentes para os gráficos."""
    conn = get_connection(); c = conn.cursor()
    mapeamento = {
        'Ginecologia e Obstetrícia': 'G.O.',
        'Ginecologia': 'G.O.',
        'Obstetrícia': 'G.O.',
        'Cirurgia Geral': 'Cirurgia'
    }
    for antigo, novo in mapeamento.items():
        c.execute("UPDATE assuntos SET grande_area=? WHERE grande_area=?", (novo, antigo))
    conn.commit(); conn.close()

# ==========================================
# 👤 MÓDULO 2: USUÁRIOS E SEGURANÇA
# ==========================================

def criar_usuario(username, password, nome):
    conn = get_connection(); c = conn.cursor()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO usuarios (username, nome, password_hash) VALUES (?,?,?)", 
                  (username, nome, hashed))
        conn.commit()
        return True, "Usuário criado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Este nome de usuário já existe."
    finally:
        conn.close()

def verificar_login(username, password):
    conn = get_connection(); c = conn.cursor()
    user = c.execute("SELECT password_hash, nome FROM usuarios WHERE username=?", (username,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[0]):
        return True, user[1]
    return False, None

# ==========================================
# 📝 MÓDULO 3: REGISTROS DE ESTUDO
# ==========================================

def registrar_estudo(nome_assunto, acertos, total, data_personalizada=None):
    conn = get_connection(); c = conn.cursor()
    dt = data_personalizada if data_personalizada else datetime.now().date()
    
    # Pega ID do assunto
    assunto = c.execute("SELECT id FROM assuntos WHERE nome=?", (nome_assunto,)).fetchone()
    if not assunto: return "Assunto não encontrado."
    
    assunto_id = assunto[0]
    perc = (acertos/total)*100
    
    # Salva no histórico
    c.execute("INSERT INTO historico (assunto_id, data_estudo, acertos, total, percentual) VALUES (?,?,?,?,?)",
              (assunto_id, dt, acertos, total, perc))
    
    # Agenda Revisão Espaçada (SRS) automática
    intervalos = [7, 30] # 1 semana e 1 mês
    for dias in intervalos:
        data_rev = dt + timedelta(days=dias)
        c.execute("INSERT INTO revisoes (assunto_id, data_agendada, tipo) VALUES (?,?,?)",
                  (assunto_id, data_rev, f"Revisão {dias}d"))
    
    conn.commit(); conn.close()
    return f"Registro salvo! {acertos}/{total} ({perc:.1f}%)"

def registrar_simulado(dados_dict, data_personalizada=None):
    """Registra várias áreas de uma vez (Simulado)."""
    msg = []
    for area, dados in dados_dict.items():
        if dados['total'] > 0:
            res = registrar_estudo(f"Simulado: {area}", dados['acertos'], dados['total'], data_personalizada)
            msg.append(area)
    return f"Simulado registrado para: {', '.join(msg)}"

# ==========================================
# 📅 MÓDULO 4: AGENDA E REVISÕES
# ==========================================

def listar_revisoes_completas():
    conn = get_connection()
    query = """
        SELECT r.id, a.nome as assunto, a.grande_area, r.data_agendada, r.tipo, r.status
        FROM revisoes r
        JOIN assuntos a ON r.assunto_id = a.id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def concluir_revisao(id_revisao):
    conn = get_connection()
    conn.execute("UPDATE revisoes SET status='Concluido' WHERE id=?", (id_revisao,))
    conn.commit(); conn.close()

# ==========================================
# 🎮 MÓDULO 5: GAMIFICAÇÃO
# ==========================================

def get_status_gamer():
    conn = get_connection()
    perfil = pd.read_sql("SELECT * FROM perfil_gamer WHERE id=1", conn).iloc[0]
    
    # Lógica de XP para próximo nível: Nível * 100
    xp_proximo = perfil['nivel'] * 100
    
    status = {
        'nivel': perfil['nivel'],
        'xp_atual': perfil['xp_atual'],
        'xp_total': perfil['xp_acumulado_total'],
        'titulo': perfil['titulo'],
        'xp_proximo': xp_proximo
    }
    
    missoes = pd.read_sql("SELECT * FROM missoes_hoje WHERE data_missao = CURRENT_DATE", conn)
    conn.close()
    return status, missoes

# ==========================================
# ⚙️ MÓDULO 6: CONFIGURAÇÕES E STATS
# ==========================================

def get_progresso_hoje():
    conn = get_connection()
    r = conn.cursor().execute("SELECT SUM(total) FROM historico WHERE data_estudo=?", 
                             (datetime.now().date(),)).fetchone()
    conn.close()
    return r[0] if r[0] else 0

def ler_config(chave):
    conn = get_connection()
    r = conn.cursor().execute("SELECT valor FROM configuracoes WHERE chave=?", (chave,)).fetchone()
    conn.close()
    return r[0] if r else None

def salvar_config(chave, valor):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?,?)", (chave, str(valor)))
    conn.commit(); conn.close()