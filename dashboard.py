import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import get_status_gamer, get_progresso_hoje

def render_dashboard(conn):
    # Verifica login
    if 'username' not in st.session_state:
        st.warning("Por favor, faça login.")
        return
    u = st.session_state.username

    # --- 1. CABEÇALHO GAMIFICADO ---
    perfil, missoes = get_status_gamer(u)
    
    if not perfil:
        st.info("Perfil não encontrado. Registe o seu primeiro estudo!")
        return

    st.markdown(f"## 🩺 {perfil['titulo']} - Nível {perfil['nivel']}")
    
    # Barra de XP
    xp_atual = perfil['xp_atual']
    xp_prox = perfil['xp_proximo']
    progresso_xp = xp_atual / xp_prox if xp_prox > 0 else 0
    
    col_xp1, col_xp2 = st.columns([4, 1])
    with col_xp1:
        st.progress(progresso_xp)
        st.caption(f"XP: {xp_atual} / {xp_prox} para o próximo nível")
    with col_xp2:
        st.markdown(f"**Total XP:** {perfil['xp_total']}")

    st.divider()

    # --- 2. META DIÁRIA E MISSÕES ---
    col_meta, col_missoes = st.columns([1, 2])
    
    with col_meta:
        st.subheader("🎯 Meta Diária")
        questoes_hoje = get_progresso_hoje(u)
        meta_hoje = 50 # Padrão, ou ler de config
        
        fig_meta = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = questoes_hoje,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Questões Hoje", 'font': {'size': 14}},
            gauge = {
                'axis': {'range': [None, max(meta_hoje, questoes_hoje + 10)], 'tickwidth': 1},
                'bar': {'color': "#10b981"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "#e2e8f0",
                'steps': [{'range': [0, meta_hoje], 'color': "#f1f5f9"}],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': meta_hoje
                }
            }
        ))
        fig_meta.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_meta, use_container_width=True)

    with col_missoes:
        st.subheader("⚔️ Missões do Dia")
        if missoes is None or missoes.empty:
            st.info("Nenhuma missão ativa hoje.")
        else:
            for _, m in missoes.iterrows():
                with st.container(border=True):
                    # Calcula progresso da missão
                    prog_m = m['progresso_atual'] / m['meta_valor'] if m['meta_valor'] > 0 else 0
                    status_m = "✅" if m['concluida'] else "⏳"
                    
                    st.markdown(f"**{status_m} {m['descricao']}**")
                    st.progress(min(prog_m, 1.0))
                    
                    # Detalhes pequenos
                    c_detalhe1, c_detalhe2 = st.columns([1, 1])
                    c_detalhe1.caption(f"Progresso: {m['progresso_atual']}/{m['meta_valor']}")
                    c_detalhe2.caption(f"XP: +{m['xp_recompensa']}")

    st.divider()

    # --- 3. PERFORMANCE POR ÁREA ---
    st.subheader("📊 Desempenho por Especialidade")
    
    # Query que unifica G.O. visualmente caso ainda haja dispersão
    query_perf = """
        SELECT 
            CASE 
                WHEN a.grande_area LIKE 'Gineco%' THEN 'G.O.'
                ELSE a.grande_area 
            END as area,
            SUM(h.acertos) as total_acertos,
            SUM(h.total) as total_questoes
        FROM historico h
        JOIN assuntos a ON h.assunto_id = a.id
        WHERE h.usuario_id = ?
        GROUP BY area
    """
    df_perf = pd.read_sql(query_perf, conn, params=(u,))
    
    if df_perf.empty:
        st.warning("Ainda não há dados de histórico para gerar os gráficos.")
    else:
        df_perf['Taxa de Acerto (%)'] = (df_perf['total_acertos'] / df_perf['total_questoes'] * 100).round(1)
        
        col_bar, col_pie = st.columns([1.8, 1.2])
        
        # Mapa de Cores Padronizado
        color_map = {
            'Cirurgia': '#3b82f6',
            'Clínica Médica': '#10b981',
            'G.O.': '#ec4899',
            'Pediatria': '#f59e0b',
            'Preventiva': '#6366f1',
            'Banco Geral': '#94a3b8'
        }

        with col_bar:
            fig_bar = px.bar(
                df_perf, 
                x='area', 
                y='Taxa de Acerto (%)',
                text='Taxa de Acerto (%)',
                color='area',
                color_discrete_map=color_map,
                title="Aproveitamento (%)"
            )
            # Limpeza do eixo X
            fig_bar.update_xaxes(type='category', title_text=None)
            fig_bar.update_layout(showlegend=False, yaxis_range=[0, 105], height=350, margin=dict(t=50, b=20))
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_pie:
            fig_pie = px.pie(
                df_perf, 
                values='total_questoes', 
                names='area',
                hole=0.4,
                title="Volume de Questões",
                color='area',
                color_discrete_map=color_map
            )
            fig_pie.update_layout(height=350, margin=dict(t=50, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)

    # --- 4. EVOLUÇÃO TEMPORAL ---
    st.divider()
    st.subheader("📈 Evolução da Performance")
    
    periodo = st.radio("Agrupar evolução por:", ["Dia", "Semana", "Mês"], horizontal=True, label_visibility="collapsed")
    
    # Query dinâmica baseada no período
    if periodo == "Dia":
        query_evo = "SELECT data_estudo as periodo, AVG(percentual) as media FROM historico WHERE usuario_id = ? GROUP BY periodo ORDER BY periodo"
    elif periodo == "Semana":
        # Agrupamento por semana (ISO Week)
        query_evo = "SELECT strftime('%Y-%W', data_estudo) as periodo, AVG(percentual) as media FROM historico WHERE usuario_id = ? GROUP BY periodo ORDER BY periodo"
    else:
        # Agrupamento por mês
        query_evo = "SELECT strftime('%Y-%m', data_estudo) as periodo, AVG(percentual) as media FROM historico WHERE usuario_id = ? GROUP BY periodo ORDER BY periodo"
        
    df_evo = pd.read_sql(query_evo, conn, params=(u,))
    
    if not df_evo.empty:
        # Formatação de rótulos para remover informações desnecessárias (timestamp)
        if periodo == "Dia":
            df_evo['label_periodo'] = pd.to_datetime(df_evo['periodo']).dt.strftime('%d/%m/%y')
        elif periodo == "Semana":
            df_evo['label_periodo'] = df_evo['periodo'].apply(lambda x: f"Sem {x.split('-')[1] if '-' in x else x}")
        else:
            df_evo['label_periodo'] = pd.to_datetime(df_evo['periodo']).dt.strftime('%b/%y')

        fig_evo = px.line(
            df_evo, 
            x='label_periodo', 
            y='media',
            markers=True,
            title=f"Aproveitamento Médio por {periodo}",
            labels={'media': 'Acertos (%)', 'label_periodo': 'Período'}
        )
        # Forçar categoria remove a tentativa do Plotly de interpolar datas (limpando o eixo X)
        fig_evo.update_xaxes(type='category', title_text=None)
        fig_evo.update_traces(line_color='#3b82f6', line_width=3, marker=dict(size=8))
        fig_evo.update_layout(yaxis_range=[0, 105], height=400, margin=dict(t=50, b=20))
        st.plotly_chart(fig_evo, use_container_width=True)
    else:
        st.info("Continue a estudar para gerar dados de evolução.")