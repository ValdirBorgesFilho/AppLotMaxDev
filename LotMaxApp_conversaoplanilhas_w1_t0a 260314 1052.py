import streamlit as st  # <-- SEMPRE o primeiro do Streamlit
import sys
import os
import io
import datetime
import pandas as pd
import json
import unicodedata
import xlsxwriter
import importlib
import csv
import odf
import difflib

# Força o 'sys' no namespace global para bibliotecas que falham no importlib do 3.14
#if 'sys' not in globals():
#    globals()['sys'] = sys

# Captura todos os parâmetros da URL
params = st.query_params

# Extrai os valores (com um 'None' ou padrão caso não existam)
executar = params.get("exec", "desconhecido")
coid = params.get("ci", "desconhecido")
coname = params.get("cn","desconhecido")

notcontinue = False
justificativa = ""

# CADEADO 1: Verifica se falta algum dado essencial
if executar == "desconhecido" or coid == "desconhecido" or coname == "desconhecido":
    notcontinue = True
    justificativa = "Informações básicas não fornecidas na URL"

# CADEADO 2: Só checa a validade se o primeiro cadeado passou (usando elif)
elif executar not in ["listadeveiculos", "mapadepneus"]:
    notcontinue = True
    justificativa = "Chamada inválida, execução cancelada!"

# A partir daqui, o notcontinue só será True se um dos dois falhar.
if notcontinue:
    st.set_page_config(page_title="Erro de Acesso", layout="wide")
    st.error(f"🚨 {justificativa}")
    st.stop()

# --- 1. Titulos e configuração de interfaces ---
titulo_app = "Lista de veiculos" if executar == "listadeveiculos" else "Mapa de Pneus"
titulo_app= f"App Lot Max - Mapeador de Planilhas - {titulo_app}" 
versao_app="w1.0"                 # Arquivo de origem - LotMaxApp_conversaoplanilhas_w1_t0 260314 1052.py

st.set_page_config(page_title=titulo_app, layout="wide", initial_sidebar_state="expanded")
if 'idioma' not in st.session_state:
    st.session_state.idioma = 'pt-BR'

st.sidebar.info(f"Empresa: {coname}({coid})")

#aplicável só para lista de veículos conforme as regras
ano_atual = datetime.date.today().year
ano_minimo = ano_atual - 0
ano_maximo = ano_atual + 0

#   remoçãpo de acentos para comparação com conteúdo do arquivo, as regras já devem estar sem acentuações
#def remover_acentos(texto):
#    if not isinstance(texto, str):
#        return texto
#    # Normaliza para decompor caracteres (ex: 'ó' vira 'o' + '´')
#    nfkd_form = unicodedata.normalize('NFKD', texto)
#    # Filtra apenas o que não for acento (Non-Spacing Mark)
#    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

# 1. DEFINE OS CAMINHOS (Apontando para a subpasta .\list)
pasta_config = "./list"  # Ou "./list" 
arquivo_matrizregras = os.path.join(pasta_config, f"rules_{executar}.json")
arquivo_listas = os.path.join(pasta_config, "lists.utf8")

# 2. FUNÇÃO MINERADORA (Blindada para a subpasta)
def carregar_biblioteca_listas(caminho):
    # 1. Nasce aqui e nunca mais é reiniciada
    biblioteca = {} 
    bloco_atual = None
    
    if not os.path.exists(caminho):
        return {}

    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha: 
                continue
            
            # Detecta o [bloco]
            if linha.startswith("[") and linha.endswith("]"):
                bloco_atual = linha[1:-1].strip()
                # 2. Só cria a chave se ela não existir, preservando o dicionário
                biblioteca[bloco_atual] = []
                
            elif bloco_atual:
                # 3. Empilha o item na lista do bloco aberto
                biblioteca[bloco_atual].append(linha)
                
    return biblioteca # 4. Devolve o "prédio inteiro", não só o último andar

## --- CHAMADA DA FUNÇÃO (O motor liga) ---
#repo_listas = carregar_biblioteca_listas(arquivo_listas)

# --- AQUI É ONDE O PILOTO VÊ O RADAR ---
#st.subheader("📡 Relatório de Mineração")
#st.write(f"📂 Arquivo lido: `{arquivo_listas}`")
#
#if not repo_listas:
#    st.error("❌ A biblioteca está VAZIA! O arquivo não foi lido ou não tem blocos [ ].")
#else:
#    st.success(f"✅ Sucesso! Encontrei {len(repo_listas)} blocos.")
#    st.write("Lista de chaves encontradas:", list(repo_listas.keys()))
#    
#    with st.expander("📄 Ver conteúdo completo da Biblioteca"):
#        st.json(repo_listas)
# AGORA SIM, o freio de mão para inspeção
#st.stop()

# 3. EXECUÇÃO DA CARGA DINÂMICA
try:
    # A. Carrega o "Dicionário" de listas do TXT
    repo_listas = carregar_biblioteca_listas(arquivo_listas)

    # B. Carrega o "Manual" JSON específico do App
    if os.path.exists(arquivo_matrizregras):
        with open(arquivo_matrizregras, "r", encoding="utf-8") as f:
            MATRIZ_REGRAS = json.load(f)
    else:
        st.error(f"🚨 Matriz '{arquivo_matrizregras}' não encontrada na pasta ./list")
        st.stop()

    # --- FASE DE ACOPLAGEM E INJEÇÃO DE REGRAS (PLUG & PLAY) ---
    falhas_configuracao = []

    for item_nome, configuracao in MATRIZ_REGRAS.items():
        # 1. INJEÇÃO DE LISTAS EXTERNAS
        # Verifica se o campo deve buscar dados no arquivo .utf8
        if configuracao.get("valores") == "externalfile":
            chave_busca = configuracao.get("cod")
            
            # Busca rigorosa na biblioteca minerada (repo_listas)
            if chave_busca in repo_listas:
                # Acoplamento bem-sucedido
                configuracao["valores"] = repo_listas[chave_busca]
            else:
                # Falha de sincronia: bloco não encontrado ou erro de digitação
                configuracao["valores"] = [] # Evita que o Selectbox quebre
                falhas_configuracao.append(f"❌ Bloco **[{chave_busca}]** não localizado no arquivo de listas.")

        # 2. CALIBRAGEM DINÂMICA DE ANOS (Offset Temporal)
        if configuracao.get("tipo") == "anointervalo":
            # Calcula os anos REAIS baseados no deslocamento do JSON
            lim_min = ano_atual + configuracao.get("ano_minimo", 0)
            lim_max = ano_atual + configuracao.get("ano_maximo", 0)
            
            # Injeta os limites numéricos para o motor de validação
            configuracao["limite_minimo"] = lim_min
            configuracao["limite_maximo"] = lim_max
            
            # Concatena o texto explicativo com o intervalo calculado
            prefixo = configuracao.get("warning", "⚠️ O ano deve estar entre")
            configuracao["warning"] = f"{prefixo} {lim_min} e {lim_max}"

    # --- EXIBIÇÃO DE ALERTAS NA SIDEBAR (O "LOG DINÂMICO") ---
    if falhas_configuracao:
        with st.sidebar.expander("⚠️ **ERROS DE MAPEAMENTO**", expanded=True):
            for erro in falhas_configuracao:
                st.error(erro)
            st.caption("Entre em cintato com o suporte App Lotmax e informe (falhas entre regras e blocos).")

    # D. Define a lista base para o mapeamento
    lista_fixa_base = list(MATRIZ_REGRAS.keys())

except Exception as e:
    st.error(f"Falha na leitura dos dados, notifique ao suporte App LotMax: {e}")
    st.stop()

# Função auxiliar para detectar "quase" estoque (deve ficar fora do loop)
def eh_parecido_com_estoque(texto):
    alvo = "ESTOQUE"
    texto = str(texto).upper().strip()
    if texto == alvo or texto == "": return False
    # Ratio de 0.7 pega "ESLOQUE", "ESTOQ", mas ignora coisas nada a ver
    return difflib.SequenceMatcher(None, texto, alvo).ratio() >= 0.7


ativardebug = False
if ativardebug:
# --- INSPEÇÃO TÉCNICA (DEBUG) ---
    with st.expander("🔍 Ver Estrutura da Matriz (Debug)"):
        st.write("Configuração atual da MATRIZ_REGRAS:")
        st.json(MATRIZ_REGRAS) # O st.json deixa tudo identado e bonito para ler
    st.stop()

# Identificamos quais são os campos obrigatórios na Matriz
campos_criticos_obrigatorios = [item for item, regra in MATRIZ_REGRAS.items() if regra.get("critico") == True]

# Define a lista fixa globalmente para o botão de limpar funcionar
lista_fixa_base = list(MATRIZ_REGRAS.keys())

# --- 3. FUNÇÃO DE LEITURA (ESTÁVEL 3.12) ---
@st.cache_data(show_spinner="Lendo dados...", max_entries=10)
def ler_dados_excel(file, aba):
    try:
        engine_type = 'odf' if file.name.endswith('.ods') else 'openpyxl'
        df = pd.read_excel(file, sheet_name=aba, engine=engine_type)
        return df.copy()
    except Exception as e:
        st.error(f"Erro: {e}")
        return None

# --- 4. CSS ---
st.markdown("""
<style>
    /* ========================================================================
       1. CONFIGURAÇÕES GERAIS DE PÁGINA E INTERFACE
       ======================================================================== */
    
    /* Esconde o menu de hambúrguer e o rodapé nativo do Streamlit */
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    
    /* Torna o cabeçalho invisível mas mantém o ícone de expandir sidebar (>) */
    header[data-testid="stHeader"] {
        background-color: rgba(0,0,0,0) !important;
        color: rgba(0,0,0,0) !important;
    }
    
    /* Garante que o botão de recolher a sidebar esteja visível e clicável */
    button[data-testid="stSidebarCollapseIcon"] {
        visibility: visible !important;
        color: #2c3e50 !important;
        z-index: 99999 !important;
    }

    /* Ajusta o espaçamento do corpo da página e largura total */
    .block-container { 
        padding-top: 1.5rem !important; 
        padding-bottom: 0rem !important; 
        max-width: 98% !important; 
    }

    /* ========================================================================
       2. ESTILIZAÇÃO DOS SELECTBOX (MAPEAMENTO)
       ======================================================================== */
    
    /* Reduz a altura dos seletores para ganhar espaço vertical */
    div[data-baseweb="select"] > div { 
        height: 28px !important; 
        min-height: 28px !important; 
        display: flex !important; 
        align-items: center !important; 
    }
    
    /* Ajusta o tamanho da fonte do mapeamento */
    div[data-baseweb="select"] span { 
        font-size: 0.8rem !important; 
        line-height: 1 !important; 
    }

    /* Ajusta as opções da lista suspensa (dropdown) */
    ul[role="listbox"] { padding: 0px !important; }
    ul[role="listbox"] li { 
        padding: 0px !important; 
        margin: 0px !important; 
        min-height: 22px !important; 
        display: flex !important; 
        align-items: center !important; 
    }

    /* ========================================================================
       3. CUSTOMIZAÇÃO DO UPLOADER (BLINDADO PARA SERVIDOR/DEPLOY)
       ======================================================================== */
    
    /* 1. Tradução do "Drag and drop" */
    [data-testid="stFileUploaderDropzoneInstructions"] > div > span { display: none !important; }
    [data-testid="stFileUploaderDropzoneInstructions"] > div::before {
        content: "Arraste e solte o arquivo aqui";
        display: block !important;
        font-size: 0.8rem !important;
        color: #555 !important;
    }
    
    /* 2. Esconde o texto do limite de tamanho (20MB) */
    [data-testid="stFileUploaderDropzoneInstructions"] > div > small { display: none !important; }

    /* 3. Tradução do Botão (Independente de ser 'secondary' ou não) */
    [data-testid="stFileUploaderDropzone"] button {
        color: transparent !important; 
        position: relative !important;
        width: 100% !important;
        border: 1px solid #d3d3d3 !important;
        background-color: white !important;
        height: 34px !important;
    }
    
    /* Injeta o texto novo exatamente no centro do botão */
    [data-testid="stFileUploaderDropzone"] button::after {
        content: "📁 Selecionar arquivo";
        visibility: visible !important;
        color: #2c3e50 !important;
        font-weight: 600 !important;
        position: absolute !important;
        left: 0; top: 0; width: 100%; height: 100%;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 0.75rem !important;
    }

    /* ========================================================================
       4. LABELS, ERROS E ALERTAS DE CAMPO
       ======================================================================== */
    
    /* Nomes das colunas acima dos selectboxes */
    .mapping-label { 
        font-weight: 700; 
        color: #2c3e50; 
        margin-bottom: 1px; 
        font-size: 0.82rem; 
        display: block; 
    }
    
    /* Aproxima o selectbox do erro abaixo dele */
    div[data-testid="stSelectbox"] { margin-bottom: -10px !important; }
    
    /* Cores e fontes para erros críticos e alertas (warnings) */
    .val-error { color: #d63031; font-size: 0.65rem; font-weight: 700; margin-top: 2px; line-height: 1.1; }
    .val-warning { color: #f39c12; font-size: 0.65rem; font-weight: 700; margin-top: 2px; line-height: 1.1; }
            
    /* ========================================================================
       5. COMPACTAÇÃO DA SIDEBAR E CAIXA DE AVISOS FLEXÍVEL
       ======================================================================== */
    
    /* BLOCO DE AVISOS (st.info / st.warning): Torna a caixa elástica */
    [data-testid="stSidebar"] [data-testid="stNotification"] {
        display: flex !important;
        align-items: flex-start !important; /* Alinha o texto no topo */
        padding: 8px 12px !important;       /* Respiro interno equilibrado */
        margin-bottom: 5px !important;
        height: auto !important;             /* ESSENCIAL: A caixa cresce com o texto */
        min-height: 20px !important;         /* Remove a altura mínima forçada */
    }

    /* Esconde o ícone nativo (i) para dar mais largura ao texto */
    [data-testid="stSidebar"] [data-testid="stNotification"] svg { 
        display: none !important; 
    }
    
    /* Ajuste do texto interno: Garante que ele ocupe 100% e quebre linha corretamente */
    [data-testid="stSidebar"] [data-testid="stNotification"] p {
        font-size: 0.85rem !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;      /* Espaço confortável entre linhas */
        width: 100% !important;
        word-wrap: break-word !important;  /* Força a quebra de palavras se necessário */
        white-space: normal !important;    /* Garante que o texto não tente ficar em uma linha só */
    }

    /* --- AJUSTES DE ESPAÇO E SUPRESSÃO DO NOME DO ARQUIVO --- */
    [data-testid="stSidebarContent"] { padding-top: 0.8rem !important; }

    /* Remove o nome do arquivo que "empurra" o layout para baixo */
    [data-testid="stFileUploaderFileData"], 
    .st-emotion-cache-1ky9v3, 
    .st-emotion-cache-12mif3y,
    div[data-testid="stFileUploader"] > section + div { 
        display: none !important; 
    }

    /* Aproximação dos componentes */
    div[data-testid="stFileUploader"] { margin-top: -10px !important; margin-bottom: -15px !important; }
    [data-testid="stSidebar"] .stElementContainer { margin-bottom: -0.6rem !important; }
    [data-testid="stSidebar"] hr { margin: 10px 0px !important; }
       
</style>
""", unsafe_allow_html=True)



# --- 5. CABEÇALHO ---
c_logo, c_titulo = st.columns([1, 4])
with c_logo:
    logo_nome = "Lotmax_app_lotmax_2026.png"
    if os.path.exists(logo_nome): 
        st.image(logo_nome, width=110)
    else: 
        st.markdown("### 🚀 App LotMax")

with c_titulo:
    # Título principal + Versão + Debug oculto (selecionável com mouse)
    st.markdown(f"""
        <h3 style='margin-top: 15px; margin-bottom: 0px;'>
            {titulo_app} 
            <span style='font-size: 0.85rem; font-weight: 400; color: #7f8c8d; margin-left: 8px;'> 
                {versao_app}
            </span>
            <span style='color: transparent; font-size: 0.5rem; user-select: text;'>
                 Py: {sys.version} | ST: {st.__version__} | Path: {sys.executable}
            </span>
        </h3>
    """, unsafe_allow_html=True)



st.divider()

# --- 6. BARRA LATERAL (UPLOAD APENAS) ---
with st.sidebar:
    # Trocamos o H3 (###) por uma span com fonte controlada (0.9rem)
    st.markdown("<span style='font-size: 0.9rem; font-weight: 700; color: #2c3e50;'>📂 Gestão de Arquivo</span>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Excel/ODS", type=["xlsx", "xls", "ods"], label_visibility="collapsed")
    # Substituímos o st.divider() por uma linha CSS mais fina para ganhar espaço
    st.markdown("<hr style='margin: 10px 0px; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
    st.markdown("<small><span style='color: red;'>*</span> Campos obrigatórios</small>", unsafe_allow_html=True)
#    st.markdown("### 📂 Gestão de Arquivo")
#    uploaded_file = st.file_uploader("Upload Excel/ODS", type=["xlsx", "xls", "ods"], label_visibility="collapsed")
#    st.divider()
#    st.markdown("<small><span style='color: red;'>*</span> Campos obrigatórios</small>", unsafe_allow_html=True)


# --- 7. LÓGICA CENTRAL ---
if uploaded_file:
    # DETECÇÃO AUTOMÁTICA DE TROCA DE ARQUIVO
    if st.session_state.get('ultimo_arquivo_nome') != uploaded_file.name:
        # 1. Limpa o dicionário de mapeamento
        st.session_state.map_state = {item: "(Pular)" for item in lista_fixa_base}
        # 2. Salva o nome do arquivo atual para a próxima comparação
        st.session_state.ultimo_arquivo_nome = uploaded_file.name
        # 3. MUITO IMPORTANTE: Incrementa o contador para forçar o reset dos widgets
        st.session_state.reset_ctr = st.session_state.get('reset_ctr', 0) + 1
        # 4. Rerun para aplicar a nova 'key' em todos os selectboxes abaixo
        st.rerun()

    # BLOCO VISUAL (Seu código original com botão)
    col_info, col_reset = st.columns([3, 1])
    with col_info:
#        st.markdown(f"📄 Arquivo: `{uploaded_file.name}`  \n* Aviso: Caso o arquivo original no seu computador sofrer alguma modificação, será necessário fazer o upload novamente para aplicar as mudanças.")
        st.markdown(
            f"📄 **Arquivo:** `{uploaded_file.name}`  \n"
            f"<span style='font-size: 0.8em; color: gray;'>"
            f"⚠️ Aviso: Caso o arquivo utilizado sofrer alguma modificação, será necessário fazer o upload novamente para obter as mudanças."
            f"</span>", 
            unsafe_allow_html=True
        )
    with col_reset:
        if st.button("🗑️ Limpar Seleções", use_container_width=True):
            st.session_state.map_state = {item: "(Pular)" for item in lista_fixa_base}
            st.session_state.reset_ctr = st.session_state.get('reset_ctr', 0) + 1
            st.rerun()


    r_key = st.session_state.get('reset_ctr', 0)
    # 1. Detecta o motor: se for .ods usa 'odf', senão usa 'openpyxl' (para xlsx/xls)
    motor = 'odf' if uploaded_file.name.lower().endswith('.ods') else 'openpyxl'
    # 2. Abre o arquivo com o motor certeiro
    xls = pd.ExcelFile(uploaded_file, engine=motor)
    # 3. Seu seletor continua lendo as abas desse mapa
    aba_sel = st.selectbox("Selecione a Aba:", xls.sheet_names, key=f"aba_main_{r_key}")
    if aba_sel:
        df_origem = ler_dados_excel(uploaded_file, aba_sel)
        if df_origem is not None:
            colunas_planilha = df_origem.columns.tolist()
            
            # --- 🛡️ SEGURANÇA: REMOVEMOS O BANHO DE LOJA DAQUI ---
            # O df_origem permanece original para não estragar dados se o usuário errar o mapeamento.

            if 'map_state' not in st.session_state:
                st.session_state.map_state = {item: "(Pular)" for item in lista_fixa_base}

            selecionados_atualmente = {v for k, v in st.session_state.map_state.items() if v != "(Pular)"}
            campos_com_erro_critico = []

            def format_rows(mask):
                lista_linhas = mask[mask].index.map(lambda x: int(x) + 2).tolist()
                t = len(lista_linhas)
                return f"{lista_linhas[:3]}... (+{t - 3})" if t > 3 else str(lista_linhas)
            
            grid = st.columns(4)
            contaitemobrigatorio = 0
            for idx, item_fixo in enumerate(lista_fixa_base):
                with grid[idx % 4]:
                    regra = MATRIZ_REGRAS[item_fixo]
                    marcaitemobrigatorio = "*" if regra.get("critico") else ""
                    st.markdown(f"<span class='mapping-label'>{item_fixo}{marcaitemobrigatorio} </span>", unsafe_allow_html=True)
                    valor_salvo = st.session_state.map_state.get(item_fixo, "(Pular)")
                    opcoes_disponiveis = ["(Pular)"] + [c for c in colunas_planilha if c not in selecionados_atualmente or c == valor_salvo]
                    
                    idx_p = opcoes_disponiveis.index(valor_salvo) if valor_salvo in opcoes_disponiveis else 0
                    nova_escolha = st.selectbox(f"sel_{item_fixo}", options=opcoes_disponiveis, index=idx_p, key=f"f_{item_fixo}_{r_key}", label_visibility="collapsed")
                    if nova_escolha != valor_salvo:
                        st.session_state.map_state[item_fixo] = nova_escolha
                        st.rerun()
                    # --- MOTOR DE VALIDAÇÃO (Dentro do loop, para cada item_fixo) ---
#                    regra = MATRIZ_REGRAS[item_fixo]
                    if nova_escolha != "(Pular)" and regra["tipo"] != "nenhum":
                        contaitemobrigatorio += 1 if regra.get("critico") else 0
#                        st.sidebar.write(f"DEBUG: {contaitemobrigatorio} - {len(campos_criticos_obrigatorios)}")
                        # 1. RESET DO DUBLÊ: Sempre do tanque original (df_origem)
                        # 1. Tira a cópia pura (mantém NaNs como nulos reais, não como texto)
                        dados_puros = df_origem[nova_escolha].copy()
                        dados_validar = dados_puros.astype(str).str.strip().replace(['nan', 'None', 'NaT', 'N/D'], '')
                        
                        # 2. BANHO DE LOJA (No Dublê conforme a Matriz)
                        formato = regra.get("formato")
                        if formato == "upper":
                            dados_validar = dados_validar.str.upper()
                        elif formato == "lower":
                            dados_validar = dados_validar.str.lower()
                        elif formato == "capital":
                            dados_validar = dados_validar.str.capitalize()

                        # Criamos o 'dados_limpos' APENAS para o texto do erro "Digitado: [X]"
                        dados_limpos = dados_validar.replace(['nan', 'None', ''], pd.NA).dropna()
                        
                        mask = None
                        msg_aviso = regra.get("warning", "")

                        # 3. SENSORES DE ÓRBITA (Todas as Regras)
                        if regra["tipo"] == "lista":
                            # 1. SENSOR DE LISTA (Equalizando tipos para String e limpando rastro)
                            dados_str_lista = dados_validar.astype(str).str.strip()
                            mask = (~dados_str_lista.isin(['nan', 'None', '', 'NAT'])) & (~dados_str_lista.isin(regra["valores"]))
                            
                            # 2. MONTAGEM DA SUGESTÃO (Injetando na msg_aviso para casar com o markdown)
                            if mask.any():
                                opcoes = regra.get("valores", [])
                                # Pegamos os 4 primeiros como amostra de sucesso
                                amostra = ", ".join(map(str, opcoes[:4])) 
                                if len(opcoes) > 4: amostra += "..."
                                
                                # A sua frase exata acoplada ao warning do JSON
                                msg_aviso = f"Dados válidos: [{amostra}] <br>{regra.get('warning', '')}"

                        elif regra["tipo"] == "placa":
                            # --- 🛰️ TELEMETRIA DE CAMPO (DEBUG VISUAL PRESERVADO) ---
                            ativardebug = False
                            if ativardebug:
                                st.sidebar.warning(f"🔎 Scanner: {item_fixo}")
                                for i in range(8, 12): 
                                    if len(dados_validar) > i:
                                        val_raw = dados_validar.iloc[i]
                                        st.sidebar.write(f"Linha {i+1}: ---{val_raw}--- | Tipo: {type(val_raw)}")
                            
                                if not st.sidebar.button(f"🚀 Liberar {item_fixo}", key=f"btn_{item_fixo}"):
                                    st.stop()

                            chk_vazio = regra["validar"]["vazio"]
                            chk_tamanho = regra["validar"]["limite"]
                            chk_repeticao = regra["validar"]["duplicado"]
                            chk_estoque = regra["validar"]["permitir_estoque"]

                            # --- 1. SENSORES DE ESTADO (BLINDAGEM CONTRA NAN/VAZIO) ---
                            # Usamos dados_puros para detectar o vazio real e dados_validar para strings
                            mask_vazio = (dados_puros.isna() | (dados_validar == ""))
                            mask_erro_vazio = mask_vazio if chk_vazio else pd.Series(False, index=dados_validar.index)
                            
                            # Escudo para a palavra ESTOQUE
                            mask_eh_estoque = (dados_validar.str.upper() == "estoque") if chk_estoque else pd.Series(False, index=dados_validar.index)

                            # --- 2. SENSORES DE ERRO (AGORA PROTEGIDOS PELO MASK_VAZIO) ---
                            # Erro de Tamanho: Não é vazio, não é estoque e tamanho != limite
                            mask_tamanho = (~mask_vazio) & (~mask_eh_estoque) & (dados_validar.str.len() != chk_tamanho)
                            
                            # Erro de Duplicidade: Não é vazio, não é estoque e repete
                            mask_duplicado = (~mask_vazio) & (~mask_eh_estoque) & dados_validar.duplicated(keep=False) if chk_repeticao else pd.Series(False, index=dados_validar.index)


                            # --- 3. RELATÓRIO DE DANOS (O SEU ROTEIRO) ---
                            mask = mask_erro_vazio | mask_tamanho | mask_duplicado
                            erros_locais = []

                            # Analisa grafia quando estoque for permitido
                            if mask_erro_vazio.any(): 
                                erros_locais.append(f"🚫 Sem informação: {format_rows(mask_erro_vazio)}")
                            
                            if mask_tamanho.any(): 
                                texto_estoque = ' ou a palavra "estoque"' if chk_estoque else ""
                                erros_locais.append(f"📏 A placa deve ter {chk_tamanho} caracteres (letras e números){texto_estoque}: {format_rows(mask_tamanho)}")
                            
                            if mask_duplicado.any(): 
                                dups = dados_validar[mask_duplicado].unique().tolist()
                                erros_locais.append(f"❌ Placa(s) repetida(s): {format_rows(mask_duplicado)} (Ex: {dups[:2]})")

                            if chk_estoque:
                                mask_suspeita_estoque = dados_validar.apply(eh_parecido_com_estoque)
                                if mask_suspeita_estoque.any():
                                    # Isso não trava a gravação (mask principal não muda), apenas avisa o usuário, mostra o conteúdo de dados_puros, sem alterações
                                    sugestoes = dados_puros[mask_suspeita_estoque].unique().tolist()
                                    erros_locais.append(f"⚠️ Atenção: Encontramos grafias que parecem 'estoque' mas podem estar erradas: {format_rows(mask_suspeita_estoque)} (Ex: {sugestoes})")

#                            if chk_estoque and mask_eh_estoque.any():
#                                # Mantive o seu alerta opcional de itens em estoque
#                                erros_locais.append(f"📦 Itens em ESTOQUE detectados: {format_rows(mask_eh_estoque)}")

                            # --- FINALIZAÇÃO ---
                            msg_aviso = "<br>".join(erros_locais)

                        elif regra["tipo"] == "tamanho_texto":
                            mask = dados_validar.apply(lambda x: len(str(x)) != regra["limite"] if x != "nan" else False)

                        elif regra["tipo"] == "tamanho_minimo":
                            mask = dados_validar.apply(lambda x: len(str(x)) < regra["limite"] if x != "nan" else False)

                        elif regra["tipo"] == "unico":
                            mask = dados_validar.duplicated(keep=False) & (dados_validar != "nan")

                        elif regra["tipo"] == "numerico":
                            mask = dados_puros.notna() & (dados_validar != "") & pd.to_numeric(dados_validar, errors='coerce').isna()

                        elif regra["tipo"] == "tamanho_fixo":
                            mask = (dados_validar != "nan") & (dados_validar.str.len() != regra["limite"])

                        elif regra["tipo"] == "padrao_dot":
                            # 1. Normalização: Recupera o zero (ex: 124 -> 0124) para strings numéricas
                            dados_dot = dados_validar.apply(lambda x: x.zfill(4) if x.isdigit() else x)
                            
                            # 2. A MÁSCARA (Linha Única): Erro se (Não for vazio) E (Não for dígito OU SS(digitos a esquerda fora de 01-52) OU AA (digitos a direita) inválido)
                            mask = (dados_puros.notna() & (dados_validar != "")) & ((~dados_dot.str.isdigit()) | (pd.to_numeric(dados_dot.str[:2], errors='coerce') < 1) | (pd.to_numeric(dados_dot.str[:2], errors='coerce') > 52) | (pd.to_numeric(dados_dot.str[2:], errors='coerce').isna()))
                            
                            # 3. Preparação da Mensagem de Alerta (Warning)
                            if mask.any():
                                amostra = dados_puros[mask].unique().tolist()[:2]
                                msg_aviso = f"⚠️ Digitado: {amostra} <br>{regra.get('warning', '')}"
                        elif regra["tipo"] == "valido":
                            # Se não for vazio e não estiver na lista (ex: ["Sim"]), ERRO!
                            mask = (dados_validar != "nan") & ~dados_validar.isin(regra["valores"])

                        elif regra["tipo"] == "anointervalo":
                            ano_num = pd.to_numeric(dados_validar, errors='coerce')
                            # Erro se não for número OU se estiver fora do range (conforme definido antea da matriz de regras)
                            mask = (dados_validar != "nan") & (ano_num.isna() | (ano_num < regra.get("limite_minimo")) | (ano_num > regra.get("limite_maximo")))

                        # --- PROCESSAMENTO DO ERRO ---
                        if mask is not None and mask.any():
                            if regra.get("critico"): campos_com_erro_critico.append(item_fixo)
                            contaitemobrigatorio -= 1 if regra.get("critico") else 0
#                            st.sidebar.write(f"DEBUG: {contaitemobrigatorio} - {len(campos_criticos_obrigatorios)}")
                            classe = "val-error" if regra.get("critico") else "val-warning"
                            invalidos = f"<br>❌ Digitado: {dados_limpos[mask].unique().tolist()[:2]}" if regra["tipo"] == "lista" else ""
                            st.markdown(f"<p class='{classe}'>Linhas: {format_rows(mask)}{invalidos}<br>{msg_aviso}</p>", unsafe_allow_html=True)


            # --- 8. EXPORTAÇÃO DIFERENCIADA (EXCEL REVISÃO vs CSV pra LotMax) ---
            mapeamento_final = {v: k for k, v in st.session_state.map_state.items() if v != "(Pular)"}
            
            # --- CENTRO DE COMANDO NA SIDEBAR (LÓGICA INTEGRAL PRESERVADA) ---
            if mapeamento_final:
 #               st.sidebar.write(f"DEBUG: {contaitemobrigatorio} - {len(campos_criticos_obrigatorios)}")
                with st.sidebar:
                    if len(campos_com_erro_critico) > 0:
                        st.error(f"⚠️ **Download Bloqueado.** Corrija erros críticos em: {', '.join(set(campos_com_erro_critico))}")
                    elif  contaitemobrigatorio == len(campos_criticos_obrigatorios):
                        if st.button("🚀 PROCESSAR ARQUIVOS", use_container_width=True):
                            # 1. Criamos a base do progresso na lateral
                            progresso_bar = st.progress(0)
                            status_text = st.empty() # Espaço para mensagens dinâmicas
                            
                            with st.spinner("Iniciando ignição dos motores..."):
                                # A. CONSTRUÇÃO DO EXCEL
                                df_excel = pd.DataFrame(index=df_origem.index)
                                total_itens = len(lista_fixa_base)
                                
                                for i, item in enumerate(lista_fixa_base):
                                    # Atualiza a barra de progresso (0.0 a 1.0)
                                    percentual = (i + 1) / total_itens
                                    progresso_bar.progress(percentual)
                                    status_text.text(f"🛰️ Processando: {item} ({i+1}/{total_itens})")
                                    
                                    col_user = st.session_state.map_state.get(item)
                                    if col_user and col_user != "(Pular)":
                                        regra = MATRIZ_REGRAS.get(item, {})
                                        formato = regra.get("formato")
#                                        dado = df_origem[col_user].astype(str).str.strip()  
                                        dado = df_origem[col_user].astype(str).str.strip().replace('nan', '')  
                                        # --- BANHO DE LOJA (Aplica o Rigor) ---
                                        if formato == "upper":
                                            df_excel[item] = dado.str.upper()
                                        elif formato == "lower":
                                            df_excel[item] = dado.str.lower()
                                        elif formato == "capital":
                                            df_excel[item] = dado.str.capitalize()
                                        elif formato == "ssaa":
                                            # 1. Se for puramente numérico, aplica o zfill(4) para recuperar o zero
                                            # 2. Se tiver letras (como 'abcd'), mantém o valor original (dado)
                                            df_excel[item] = dado.apply(lambda x: str(x).strip().zfill(4) if str(x).strip().isdigit() else x)                                        
                                        elif formato == "permitir_esgtoque":                # matriz de regras item do tipo "placa"
                                            df_excel[item] = dado.str.upper()
                                            if chk_estoque:
                                                df_excel[item] = dado.apply(lambda x: "estoque" if str(x).strip().upper() == "ESTOQUE" else str(x).strip().upper())
                                        else:
                                            df_excel[item] = dado
                                    else:
                                        df_excel[item] = ""

                                #   # B. CONSTRUÇÃO DO CSV (Herda a limpeza e aplica o rigor técnico)
                                status_text.text("🛠️ Formatando CSV para o LotMax...")
                                df_csv = df_excel.copy()

                                # --- CIRURGIA DA MATILDE: Troca Vírgula por Ponto em Campos Numéricos ---
                                for item in lista_fixa_base:
                                    regra = MATRIZ_REGRAS.get(item, {})
                                    # Se na Matriz o tipo for "numerico", a Matilde entra em ação para o Bubble
                                    if regra.get("tipo") == "numerico":
                                        df_csv[item] = df_csv[item].astype(str).str.replace(',', '.', regex=False)

                                # Renomeia para os códigos técnicos (IDs do Bubble)
                                nomes_tecnicos = {item: MATRIZ_REGRAS[item]["cod"] for item in lista_fixa_base}
                                df_csv = df_csv.rename(columns=nomes_tecnicos)

                                df_csv.insert(0, '0-Company_ID', coid)

                                if executar == "mapadepneus":

                                   # --- CONCATENAÇÃO "TUDO JUNTO" (SEM PIPE) ---
                                    c_marca = MATRIZ_REGRAS["Marca"]["cod"]
                                    c_tipo  = MATRIZ_REGRAS["Tipo"]["cod"]
                                    c_cod   = MATRIZ_REGRAS["Código aplicado"]["cod"]

                                    # Removemos os pipes e espaços. Ex: pn-Pireliso12345
                                    df_csv["01-Pneu_string"] = "pn-" + \
                                    df_csv[c_marca].astype(str).str[:4] + \
                                    df_csv[c_tipo].astype(str).str[:4] + \
                                    df_csv[c_cod].astype(str)

                                    # 3. Cálculo de Vida Útil Total
                                    c_atual = MATRIZ_REGRAS["Vida util atual"]["cod"]
                                    c_rec_q = MATRIZ_REGRAS["Recapes possíveis"]["cod"]
                                    c_rec_v = MATRIZ_REGRAS["Vida util recapes"]["cod"]

                                    v_at = pd.to_numeric(df_csv[c_atual], errors='coerce').fillna(0)
                                    v_rq = pd.to_numeric(df_csv[c_rec_q], errors='coerce').fillna(0)
                                    v_rv = pd.to_numeric(df_csv[c_rec_v], errors='coerce').fillna(0)

                                    df_csv ["03-Vida_novo_recapes"] = (v_at + (v_rq * v_rv)).astype(int)

                                # C. GERAÇÃO DOS ARQUIVOS (O Pouso final)
                                status_text.text("💾 Preparando arquivos para download...")

                                agora = datetime.datetime.now().strftime("%y%m%d_%H%M")
                                nome_puro = os.path.splitext(uploaded_file.name)[0]
                                
                                # Preparar Excel em memória
                                out_xlsx = io.BytesIO()
                                with pd.ExcelWriter(out_xlsx, engine='xlsxwriter') as writer:
                                    df_excel.to_excel(writer, index=False)
                                
                                # Preparar CSV
                                csv_data = df_csv.to_csv(index=False, sep=';', encoding='utf-8-sig',quoting=csv.QUOTE_MINIMAL)

                            # Limpa o texto de status e finaliza a barra
                            status_text.empty()
                            progresso_bar.empty()
                            st.success(f"✅ Concluído! {total_itens} colunas.")
                            # MENSAGEM FIXA: O "Farol" para o usuário
                            # font-size: 11px deixa a letra bem pequena, estilo "nota de rodapé"
                            st.sidebar.markdown(
                                f"<p style='font-size: 12px; color: gray; line-height: 1; margin-bottom: 15px;'>"
                                f"💡 <b>Dica:</b> Ao clicar nos botões abaixo, os arquivos serão enviados para sua pasta de Downloads."
                                f"</p>", 
                                unsafe_allow_html=True)
                            # Botões de download empilhados na sidebar
                            st.download_button("📥 CSV LotMax para upload", csv_data, f"{nome_puro}_App_LotMax_LV_{agora}.csv", "text/csv", use_container_width=True)
                            st.download_button("📄 EXCEL para revisão ", out_xlsx.getvalue(), f"{nome_puro}_revisão_LV_{agora}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

else:
    st.info("Aguardando upload do arquivo Excel ou ODS...")
