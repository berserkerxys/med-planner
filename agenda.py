import streamlit as st
import pandas as pd
from datetime import datetime, date
import calendar
from database import listar_revisoes_completas, concluir_revisao

def render_agenda(conn):
    st.header("📅 Agenda de Revisões")
    
    # Cores por Área
    cores_area = {
        'Cirurgia': '#3b82f6',        # Azul
        'Clínica Médica': '#10b981',  # Verde
        'G.O.': '#ec4899',            # Rosa/Púrpura
        'Pediatria': '#f59e0b',       # Laranja/Amarelo
        'Preventiva': '#6366f1',      # Indigo
        'Outros': '#94a3b8'           # Cinza
    }

    # Carrega dados do usuário atual
    u = st.session_state.username
    df_full = listar_revisoes_completas(u)
    hoje = date.today()

    # --- ESTADO E NAVEGAÇÃO ---
    if 'view_mode' not in st.session_state: st.session_state.view_mode = "Calendário"
    if 'cal_month' not in st.session_state: st.session_state.cal_month = hoje.month
    if 'cal_year' not in st.session_state: st.session_state.cal_year = hoje.year
    
    c_btn1, c_btn2, _ = st.columns([1.2, 1.2, 3.6])
    if c_btn1.button("🗓️ Calendário", key="btn_view_cal", use_container_width=True, type="primary" if st.session_state.view_mode == "Calendário" else "secondary"):
        st.session_state.view_mode = "Calendário"
        st.rerun()
    if c_btn2.button("📋 Lista", key="btn_view_list", use_container_width=True, type="primary" if st.session_state.view_mode == "Lista" else "secondary"):
        st.session_state.view_mode = "Lista"
        st.rerun()

    # === MODO CALENDÁRIO ===
    if st.session_state.view_mode == "Calendário":
        col_prev, col_mês, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("⬅️", key="prev_m_nav"):
                if st.session_state.cal_month == 1:
                    st.session_state.cal_month = 12
                    st.session_state.cal_year -= 1
                else: st.session_state.cal_month -= 1
                st.rerun()
        with col_mês:
            nome_mes = calendar.month_name[st.session_state.cal_month]
            st.markdown(f"<h3 style='text-align: center; margin-bottom: 0;'>{nome_mes} {st.session_state.cal_year}</h3>", unsafe_allow_html=True)
            # Botão Voltar para Hoje
            if st.session_state.cal_month != hoje.month or st.session_state.cal_year != hoje.year:
                if st.button("📅 Voltar para Hoje", key="btn_today", use_container_width=True):
                    st.session_state.cal_month = hoje.month
                    st.session_state.cal_year = hoje.year
                    st.rerun()
        with col_next:
            if st.button("➡️", key="next_m_nav"):
                if st.session_state.cal_month == 12:
                    st.session_state.cal_month = 1
                    st.session_state.cal_year += 1
                else: st.session_state.cal_month += 1
                st.rerun()

        # Grade do Calendário
        cal = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        cols_h = st.columns(7)
        for i, d in enumerate(dias_semana): 
            cols_h[i].markdown(f"<p style='text-align:center;font-size:12px;color:#64748b;margin-bottom:5px;'><b>{d}</b></p>", unsafe_allow_html=True)
        
        for semana in cal:
            cols = st.columns(7)
            for i, dia in enumerate(semana):
                if dia == 0:
                    cols[i].write("")
                else:
                    data_dia = date(st.session_state.cal_year, st.session_state.cal_month, dia)
                    tarefas_dia = df_full[pd.to_datetime(df_full['data_agendada']).dt.date == data_dia]
                    
                    bg_cor = "#ffffff"
                    border = "1px solid #e2e8f0"
                    if data_dia == hoje: 
                        bg_cor = "#f0f9ff"
                        border = "2px solid #3b82f6"
                    
                    barrinhas_html = ""
                    for _, t in tarefas_dia.iterrows():
                        cor = cores_area.get(t['grande_area'], cores_area['Outros'])
                        opacidade = "1" if t['status'] == 'Pendente' else "0.5"
                        texto_decor = "none" if t['status'] == 'Pendente' else "line-through"
                        check = "✔ " if t['status'] == 'Concluido' else ""
                        
                        barrinhas_html += f"""
                        <div style="background-color:{cor}; color:white; font-size:10px; padding:2px 6px; border-radius:4px; margin-top:3px; 
                                    opacity:{opacidade}; text-decoration:{texto_decor}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
                                    box-shadow: 0 1px 2px rgba(0,0,0,0.1);" 
                             title="{t['assunto']}">
                            {check}{t['assunto']}
                        </div>
                        """
                    
                    with cols[i]:
                        st.markdown(f"""
                        <div style="background-color:{bg_cor}; border:{border}; border-radius:10px; padding:6px; min-height:120px; font-family:sans-serif; transition: all 0.2s ease;">
                            <p style="margin:0; font-size:13px; font-weight:bold; color:#1e293b;">{dia}</p>
                            {barrinhas_html}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if not tarefas_dia.empty:
                            if st.button("🔍", key=f"det_btn_{data_dia}", use_container_width=True):
                                st.session_state.selected_date = data_dia

        if 'selected_date' in st.session_state:
            st.divider()
            st.subheader(f"Detalhes: {st.session_state.selected_date.strftime('%d/%m/%Y')}")
            dia_f = df_full[pd.to_datetime(df_full['data_agendada']).dt.date == st.session_state.selected_date]
            for _, t in dia_f.iterrows():
                render_task_card(t)

    # === MODO LISTA (RESTAURADO) ===
    else:
        st.subheader("📋 Lista de Pendências")
        
        # Filtros restaurados
        filtro_status = st.multiselect(
            "Filtrar por Status:", 
            ["Atrasada", "Hoje", "Futura", "Concluído"], 
            default=["Atrasada", "Hoje"]
        )
        
        if df_full.empty:
            st.info("Nenhuma revisão encontrada.")
        else:
            count = 0
            df_full = df_full.sort_values('data_agendada')
            
            for _, row in df_full.iterrows():
                dt_ag = datetime.strptime(row['data_agendada'], '%Y-%m-%d').date()
                
                # Classificação
                if row['status'] == 'Concluido': status_calc = "Concluído"
                elif dt_ag < hoje: status_calc = "Atrasada"
                elif dt_ag == hoje: status_calc = "Hoje"
                else: status_calc = "Futura"
                
                if status_calc in filtro_status:
                    render_task_card(row)
                    count += 1
            
            if count == 0:
                st.info("Nenhuma tarefa corresponde aos filtros selecionados.")

def render_task_card(row):
    hoje = date.today()
    dt_ag = datetime.strptime(row['data_agendada'], '%Y-%m-%d').date()
    is_pendente = row['status'] == 'Pendente'
    
    with st.container(border=True):
        c1, c2, c3 = st.columns([2.5, 1.5, 1])
        with c1:
            emoji = "✅" if not is_pendente else ("🔥" if dt_ag < hoje else "⏳")
            st.markdown(f"**{emoji} {row['assunto']}**")
            st.caption(f"{row['grande_area']} | {row['tipo']}")
        with c2:
            if not is_pendente: st.caption("Finalizado")
            elif dt_ag < hoje: st.error(f"Atrasado: {dt_ag.strftime('%d/%m')}")
            elif dt_ag == hoje: st.warning("É Hoje!")
            else: st.info(f"{dt_ag.strftime('%d/%m')}")
        with c3:
            if is_pendente:
                with st.popover("✔ Resolver"):
                    st.write(f"**{row['assunto']}**")
                    q_t = st.number_input("Total Q", 1, 100, 10, key=f"t_list_{row['id']}")
                    q_a = st.number_input("Acertos", 0, q_t, 8, key=f"a_list_{row['id']}")
                    if st.button("Confirmar", key=f"save_list_{row['id']}", use_container_width=True, type="primary"):
                        msg = concluir_revisao(row['id'], q_a, q_t)
                        st.toast(msg)
                        st.rerun()