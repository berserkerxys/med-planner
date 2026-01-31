import streamlit as st
from datetime import datetime
import pandas as pd
from database import (
    verificar_login, criar_usuario, get_connection, registrar_estudo, 
    registrar_simulado, get_progresso_hoje
)

st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed")

# Estilos CSS para centralizar e organizar as abas
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        justify-content: center;
    }
    </style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state:
    st.session_state['logado'] = False

def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🩺 MedPlanner")
        
        # Implementação das abas para Login e Cadastro
        tab_login, tab_cadastro = st.tabs(["Acessar", "Criar Conta"])
        
        with tab_login:
            u = st.text_input("Usuário", key="u_login")
            p = st.text_input("Senha", type="password", key="p_login")
            if st.button("Acessar", type="primary", use_container_width=True, key="btn_login"):
                ok, nome = verificar_login(u, p)
                if ok:
                    st.session_state['logado'] = True
                    st.session_state['u_nome'] = nome
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos")
                    
        with tab_cadastro:
            st.subheader("Nova Conta")
            novo_n = st.text_input("Nome Completo", placeholder="Ex: Dr. Vitor Dinizio")
            novo_u = st.text_input("Nome de Usuário", placeholder="Para fazer login")
            novo_p = st.text_input("Escolha uma Senha", type="password", key="p_new")
            confirmar_p = st.text_input("Confirme a Senha", type="password", key="p_confirm")
            
            if st.button("Cadastrar", use_container_width=True, key="btn_cadastro"):
                if novo_p != confirmar_p:
                    st.warning("As senhas não coincidem.")
                elif novo_u and novo_p and novo_n:
                    # Chama a função que já existe no seu database.py
                    sucesso, msg = criar_usuario(novo_u, novo_p, novo_n)
                    if sucesso:
                        st.success(f"✅ {msg}")
                        st.info("Agora você já pode fazer login na aba 'Acessar'.")
                    else:
                        st.error(msg)
                else:
                    st.warning("Preencha todos os campos obrigatórios.")

def app_principal():
    conn = get_connection()
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.get('u_nome', 'Doc')} 👋")
        st.metric("Questões Hoje", get_progresso_hoje())
        st.divider()
        
        st.subheader("📝 Novo Estudo")
        modo = st.radio("Selecione o Modo:", ["Por Tema", "Simulado Geral", "Banco Geral"], label_visibility="collapsed")
        dt = st.date_input("Data do Registro", datetime.now())
        
        if modo == "Por Tema":
            df_as = pd.read_sql("SELECT nome FROM assuntos ORDER BY nome", conn)
            escolha = st.selectbox("Aula:", df_as['nome'].tolist())
            col1, col2 = st.columns(2)
            total = col1.number_input("Total", 1, 500, 10)
            acerto = col2.number_input("Acertos", 0, 500, 8)
            if st.button("Salvar Registro", type="primary", use_container_width=True):
                st.toast(registrar_estudo(escolha, acerto, total, data_personalizada=dt))
                st.rerun()
                
        elif modo == "Simulado Geral":
            st.info("Insira o desempenho por área (Padrão 20 questões/área)")
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados_simulado = {}
            for area in areas:
                with st.expander(f"📍 {area}", expanded=False):
                    c1, c2 = st.columns(2)
                    t_area = c1.number_input(f"Total - {area}", 0, 100, 20, key=f"t_{area}")
                    a_area = c2.number_input(f"Acertos - {area}", 0, 100, 15, key=f"a_{area}")
                    dados_simulado[area] = {'acertos': a_area, 'total': t_area}
            
            if st.button("Salvar Simulado", type="primary", use_container_width=True):
                st.toast(registrar_simulado(dados_simulado, data_personalizada=dt))
                st.rerun()
                
        elif modo == "Banco Geral":
            st.info("Registro sem área específica (Estudo livre)")
            col1, col2 = st.columns(2)
            total_bg = col1.number_input("Total de Questões", 1, 1000, 50)
            acerto_bg = col2.number_input("Total de Acertos", 0, 1000, 35)
            if st.button("Salvar Banco Geral", type="primary", use_container_width=True):
                st.toast(registrar_estudo("Banco Geral - Livre", acerto_bg, total_bg, data_personalizada=dt))
                st.rerun()

        st.divider()
        if st.button("Sair"):
            st.session_state['logado'] = False
            st.rerun()

    t_dash, t_agenda, t_video, t_config = st.tabs(["📊 DASHBOARD", "📅 AGENDA", "📚 VIDEOTECA", "⚙️ AJUSTES"])
    
    with t_dash:
        from dashboard import render_dashboard
        render_dashboard(conn)
    with t_agenda:
        from agenda import render_agenda
        render_agenda(conn)
    with t_video:
        from videoteca import render_videoteca
        render_videoteca(conn)
    with t_config:
        # Note: 'gerenciar' module was not found in files, but render_configuracoes 
        # is called here based on the original app.py logic
        try:
            from gerenciar import render_configuracoes
            render_configuracoes(conn)
        except ImportError:
            st.warning("Módulo de configurações não encontrado.")
        
    conn.close()

if st.session_state['logado']:
    app_principal()
else:
    tela_login()