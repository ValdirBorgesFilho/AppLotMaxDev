import sys
import os
import io
import streamlit as st
import pandas as pd
import xlsxwriter

# --- 1. CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="AppLotMax | Mapeador Web", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. FUNÇÃO DE CACHE (EVITA ERRO DE REDE/AXIOS NO CELULAR) ---
@st.cache_data(show_spinner="Lendo dados da planilha...")
def ler_dados_excel(file, aba):
    try:
        # [pandas.read_excel](https://pandas.pydata.org)
        return pd.read_excel(file, sheet_name=aba)
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return None

# --- 3. CSS PARA OTIMIZAÇÃO (BUBBLE + MOBILE) ---
st.markdown("""
    <style>
    /* Remove menus e rodapés do Streamlit para parecer nativo no Bubble */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Ajusta o espaçamento do topo para o Iframe */
    .block-container { 
        padding-top: 1rem !important; 
        padding-bottom: 0rem !important;
        max-width: 98% !important; 
    }
    
    /* Ajusta altura das caixas de seleção para caber mais itens na tela */
    div[data-baseweb="select"] > div {
        height: 32px !important;
        min-height: 32px !important;
    }

    .mapping-label {
        font-weight: 700;
        color: #2c3e50;
        margin-bottom: 2px;
        font-size: 0.85rem;
        display: block;
    }

    div[data-testid="stSelectbox"] {
        margin-bottom: -12px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. CABEÇALHO (LOGO E TÍTULO) ---
c_logo, c_titulo = st.columns([1, 4])
with c_logo:
    logo_nome = "Lotmax_app_lotmax_2026.png"
    if os.path.exists(logo_nome):
        # [st.image](https://docs.streamlit.io)
        st.image(logo_nome, width=110)
    else:
        st.markdown("### 🚀 LotMax")

with c_titulo:
    st.markdown("<h3 style='margin-top: 10px;'>Mapeador de Planilhas de Pneus</h3>", unsafe_allow_html=True)

st.divider()

# --- 5. BARRA LATERAL (UPLOAD E RESET) ---
with st.sidebar:
    st.markdown("### 📂 Gestão de Arquivo")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx", "xls"], label_visibility="collapsed")
    
    if uploaded_file:
        if st.button("🗑️ Limpar Seleções"):
            # Limpa o [st.session_state](https://docs.streamlit.io)
            st.session_state.map_state = {}
            st.rerun()

# --- 6. LÓGICA DE MAPEAMENTO ---
if uploaded_file:
    # Obtém apenas os nomes das abas primeiro
    xls = pd.ExcelFile(uploaded_file)
    aba_sel = st.selectbox("Selecione a Aba desejada:", xls.sheet_names, key="aba_main")

    if aba_sel:
        # Usa a função com CACHE para estabilidade no celular
        df_origem = ler_dados_excel(uploaded_file, aba_sel)
        
        if df_origem is not None:
            colunas_planilha = df_origem.columns.tolist()

            lista_fixa_base = [
                "Placa ou Estoque","Marca","Recapadora","Tipo","Aplicacao",
                "Codigo aplicado","Condicao","Medida","Vida util atual",
                "Recapes possíveis","Vida util recapes","Codigo comercial",
                "DOT fabricado","Valor da compra"
            ]

            # Inicia o estado do mapeamento
            if 'map_state' not in st.session_state:
                st.session_state.map_state = {item: "(Pular)" for item in lista_fixa_base}

            # Filtra o que já foi selecionado para não repetir nas listas
            selecionados_atualmente = {v for k, v in st.session_state.map_state.items() if v != "(Pular)"}

            # Interface de mapeamento em grade (4 colunas)
            grid = st.columns(4)
            for idx, item_fixo in enumerate(lista_fixa_base):
                with grid[idx % 4]:
                    st.markdown(f"<span class='mapping-label'>{item_fixo}</span>", unsafe_allow_html=True)
                    
                    valor_salvo = st.session_state.map_state.get(item_fixo, "(Pular)")
                    # Regra: Opções disponíveis = (Pular) + Colunas não usadas + Coluna atual deste campo
                    opcoes_disponiveis = ["(Pular)"] + [c for c in colunas_planilha if c not in selecionados_atualmente or c == valor_salvo]
                    
                    try:
                        idx_padrao = opcoes_disponiveis.index(valor_salvo)
                    except ValueError:
                        idx_padrao = 0

                    nova_escolha = st.selectbox(
                        f"seletor_{item_fixo}", 
                        options=opcoes_disponiveis, 
                        index=idx_padrao,
                        key=f"field_{item_fixo}", 
                        label_visibility="collapsed"
                    )
                    
                    # Atualiza o estado se o usuário mudar a opção
                    if nova_escolha != valor_salvo:
                        st.session_state.map_state[item_fixo] = nova_escolha
                        st.rerun()

            # --- 7. EXPORTAÇÃO (DOWNLOAD) ---
            # Cria o dicionário invertido: {Nome_Coluna_Original: Nome_Coluna_Novo}
            mapeamento_final = {v: k for k, v in st.session_state.map_state.items() if v != "(Pular)"}
            
            if mapeamento_final:
                st.divider()
                if st.button("🚀 GERAR PLANILHA CONVERTIDA"):
                    with st.spinner("Preparando download..."):
                        # Filtra colunas e renomeia
                        df_final = df_origem[list(mapeamento_final.keys())].rename(columns=mapeamento_final)
                        
                        # Gera o Excel em memória
                        output = io.BytesIO()
                        # [xlsxwriter](https://xlsxwriter.readthedocs.io)
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_final.to_excel(writer, index=False)
                        
                        st.success("Tudo pronto!")
                        st.download_button(
                            label="📥 BAIXAR AGORA (EXCEL)",
                            data=output.getvalue(),
                            file_name="MapaPneus_Convertido.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
else:
    st.info("Aguardando upload do arquivo Excel pelo menu lateral...")
