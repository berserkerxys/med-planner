import streamlit as st
from datetime import datetime
import pandas as pd
from database import (
    verificar_login, get_connection, registrar_estudo, 
    registrar_simulado, get_progresso_hoje
)

st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed")

# Estilos CSS
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
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Acessar", type="primary", use_container_width=True):
            ok, nome = verificar_login(u, p)
            if ok:
                st.session_state['logado'] = True
                st.session_state['u_nome'] = nome
                st.rerun()
            else:
                st.error("Erro no login")

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
                # No banco, tratamos como uma área específica chamada 'Banco Geral'
                st.toast(registrar_estudo("Banco Geral - Livre", acerto_bg, total_bg, data_personalizada=dt))
                st.rerun()

        st.divider()
        if st.button("Sair"):
            st.session_state['logado'] = False
            st.rerun()

    # Navegação por Abas
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
        from gerenciar import render_configuracoes
        render_configuracoes(conn)
        
    conn.close()

if st.session_state['logado']:
    app_principal()
else:
    tela_login()