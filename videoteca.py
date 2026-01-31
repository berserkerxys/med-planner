import streamlit as st
import pandas as pd
from database import (
    listar_conteudo_videoteca, excluir_conteudo, registrar_estudo, 
    pesquisar_global, processar_progresso_missao
)

def render_videoteca(conn):
    st.subheader("📚 Videoteca & Materiais")
    
    # Busca
    c_busca, _ = st.columns([3, 1])
    termo_busca = c_busca.text_input("🔍 Pesquisar...", placeholder="Ex: Asma, Cirurgia...")
    
    if termo_busca:
        st.caption(f"Resultados para: **'{termo_busca}'**")
        df = pesquisar_global(termo_busca)
        if df.empty: st.warning("Nada encontrado."); return
        renderizar_cards(df)
    else:
        df_full = listar_conteudo_videoteca()
        if df_full.empty: st.info("Videoteca vazia."); return

        areas = df_full['grande_area'].unique()
        area_filtro = st.pills("Filtrar Área:", areas)
        if not area_filtro: st.info("Selecione uma área."); return

        df_area = df_full[df_full['grande_area'] == area_filtro]
        for assunto in df_area['assunto'].unique():
            with st.expander(f"🔹 {assunto}"):
                renderizar_cards(df_area[df_area['assunto'] == assunto])

def renderizar_cards(df):
    # Materiais
    materiais = df[df['tipo'] == 'Material']
    if not materiais.empty:
        st.markdown("###### 📄 Materiais")
        for _, row in materiais.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([0.1, 0.8, 0.1])
                c1.write("⭐" if row['subtipo'] == "Ficha" else "📎")
                c2.markdown(f"[{row['titulo']}]({row['link']})")
                if c3.button("🗑️", key=f"del_m_{row['id']}"):
                    excluir_conteudo(row['id']); st.rerun()

    # Vídeos
    videos = df[df['tipo'] == 'Video']
    if not videos.empty:
        st.markdown("###### 🎥 Aulas")
        for _, row in videos.iterrows():
            label = "⏱️ Rápido" if row['subtipo'] == "Curto" else "📽️ Aula"
            btn_color = "primary" if row['subtipo'] == "Longo" else "secondary"
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1.2, 0.5])
                with c1:
                    st.write(f"**{row['titulo']}**")
                    if 'grande_area' in row: st.caption(f"📌 {row['grande_area']}")
                with c2:
                    st.link_button(label, row['link'], use_container_width=True, type=btn_color)
                with c3:
                    with st.popover("⋮"):
                        # BOTÃO MÁGICO DE CONCLUSÃO
                        if st.button("✅ Concluir", key=f"ok_{row['id']}", use_container_width=True):
                            # 1. Registra no Histórico (conta como 1 acerto simbólico)
                            registrar_estudo(row['assunto'], 1, 1)
                            
                            # 2. Conta para a Missão de VÍDEO especificamente
                            msgs = processar_progresso_missao("video", 1)
                            
                            st.toast(f"Aula Registrada! {' '.join(msgs)}")
                        
                        st.divider()
                        if st.button("🗑️ Excluir", key=f"del_v_{row['id']}", use_container_width=True):
                            excluir_conteudo(row['id']); st.rerun()