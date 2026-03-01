### para rodar em teste aplicar o comando a seguir no terminal
### python -m streamlit run .\LotMaxApp_mapadepneus_conversaoplanilhaexcel_v0_t2web.py --global.developmentMode false --server.port 8501


import sys
import warnings
# Correção essencial para compatibilidade com Python 3.14
sys.modules['warnings'] = warnings

import streamlit as st
import pandas as pd
import datetime
import io
import os
import xlsxwriter

# 1. CONFIGURAÇÃO DA INTERFACE
st.set_page_config(page_title="AppLotMax | Mapeador Web", layout="wide")

# --- CSS DE CONTROLE TOTAL (RESET DE COMPONENTES) ---
st.markdown("""
    <style>
    /* 1. DISTÂNCIA DO TOPO */
    .block-container { padding-top: 4rem !important; max-width: 98% !important; }
    
    /* 2. RESET DE ALTURA DE TODAS AS SELECTBOXES */
    /* Atacamos o container de texto (ValueContainer) e o texto em si (SingleValue) */
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] [class*="ValueContainer"],
    div[data-baseweb="select"] [class*="StyledSingleValue"] {
        height: 24px !important;
        min-height: 24px !important;
        line-height: 24px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
        margin-top: 0px !important;
        margin-bottom: 0px !important;
        display: flex !important;
        align-items: center !important;
    }

    /* 3. GARANTIR QUE O TEXTO SEJA VISÍVEL (COR E TAMANHO) */
    div[data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
    div[data-baseweb="select"] span {
        color: #1a1c24 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        opacity: 1 !important;
    }

    /* 4. AJUSTE DOS TÍTULOS (ITENS) */
    .mapping-label {
        font-weight: 700;
        color: #2c3e50;
        margin-bottom: 1px !important;
        font-size: 0.85rem;
    }

    /* 5. APROXIMAR AS LINHAS VERTICALMENTE */
    div[data-testid="stSelectbox"] {
        margin-bottom: -15px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. CABEÇALHO (LOGO E TÍTULO)
c_logo, c_titulo = st.columns([1, 5])
with c_logo:
    try:
        # Busca a logo conforme o [st.image](https://docs.streamlit.io)
        st.image("Lotmax_app_lotmax_2026.png", width=110)
    except:
        st.write("Logo")
with c_titulo:
    st.markdown("<h3 style='margin-top: 15px;'>AppLotMax - Mapeador de Planilhas</h3>", unsafe_allow_html=True)

st.divider()

# 3. SIDEBAR (UPLOAD)
with st.sidebar:
    st.markdown("### 📂 Arquivo")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx", "xls"], label_visibility="collapsed")
    if uploaded_file and st.button("🗑️ Resetar Seleções"):
        st.session_state.map_state = {}
        st.rerun()

if uploaded_file:
    # [pandas.ExcelFile](https://pandas.pydata.org)
    xls = pd.ExcelFile(uploaded_file)
    aba_sel = st.selectbox("Escolha a Aba:", xls.sheet_names, key="aba_main")

    if aba_sel:
        # [pandas.read_excel](https://pandas.pydata.org)
        df_origem = pd.read_excel(uploaded_file, sheet_name=aba_sel)
        colunas_planilha = df_origem.columns.tolist()

        lista_fixa_base = ["Placa ou Estoque","Marca","Recapadora","Tipo","Aplicacao","Codigo aplicado","Condicao","Medida","Vida util atual","Recapes possíveis","Vida util recapes","Codigo comercial","DOT fabricado","Valor da compra"]

        # Controle de Estado Persistente
        if 'map_state' not in st.session_state or not st.session_state.map_state:
            st.session_state.map_state = {item: "(Pular)" for item in lista_fixa_base}

        # Filtro: o que já foi escolhido por outros campos
        selecionados_global = {v for k, v in st.session_state.map_state.items() if v != "(Pular)"}

        # --- GRADE DE MAPEAMENTO ---
        grid = st.columns(4)
        for idx, item_fixo in enumerate(lista_fixa_base):
            with grid[idx % 4]:
                st.markdown(f"<span class='mapping-label'>{item_fixo}</span>", unsafe_allow_html=True)
                
                escolha_salva = st.session_state.map_state.get(item_fixo, "(Pular)")
                
                # Regra de ouro: A lista de opções deve conter o item já selecionado para ele não sumir
                opcoes_filtradas = ["(Pular)"] + [c for c in colunas_planilha if c not in selecionados_global or c == escolha_salva]
                
                # Localizar o índice correto para manter a visibilidade
                try:
                    idx_default = opcoes_filtradas.index(escolha_salva)
                except ValueError:
                    idx_default = 0

                # [st.selectbox](https://docs.streamlit.io)
                nova_escolha = st.selectbox(
                    f"Seletor_{item_fixo}",
                    options=opcoes_filtradas,
                    index=idx_default,
                    key=f"field_{item_fixo}",
                    label_visibility="collapsed"
                )
                
                # Se mudar, atualiza e recarrega para filtrar os demais
                if nova_escolha != st.session_state.map_state.get(item_fixo):
                    st.session_state.map_state[item_fixo] = nova_escolha
                    st.rerun()

        # --- BOTÃO DE DOWNLOAD ---
        mapeamento_final = {v: k for k, v in st.session_state.map_state.items() if v != "(Pular)"}
        if mapeamento_final:
            st.divider()
            if st.button("🚀 GERAR PLANILHA"):
                df_final = df_origem[list(mapeamento_final.keys())].rename(columns=mapeamento_final)
                output = io.BytesIO()
                # [XlsxWriter](https://xlsxwriter.readthedocs.io)
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=False)
                st.download_button("📥 BAIXAR AGORA", output.getvalue(), "MapaPneus_Convertido.xlsx")
else:
    st.info("Aguardando upload no menu lateral...")
