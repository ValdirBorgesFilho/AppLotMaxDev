import streamlit as st  
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
import re
import pdfplumber


# --- 0. CAPTURA DE PARÂMETROS E CADEADOS DE SEGURANÇA (URL) ---
params = st.query_params
executar = params.get("exec", "desconhecido")
coid = params.get("ci", "desconhecido")
coname = params.get("cn", "desconhecido")

notcontinue = False
justificativa = ""

if executar == "desconhecido" or coid == "desconhecido" or coname == "desconhecido":
    notcontinue = True
    justificativa = "Informações básicas não fornecidas na URL"
elif executar not in ["listadeveiculos", "mapadepneus", "extratopam"]: 
    notcontinue = True
    justificativa = "Chamada inválida, execução cancelada!"

if notcontinue:
    st.set_page_config(page_title="Erro de Acesso", layout="wide")
    st.error(f"🚨 {justificativa}")
    st.stop()

# --- 1. CONFIGURAÇÃO DE INTERFACE E TÍTULOS ---
titulo_app = "Lista de veiculos" if executar == "listadeveiculos" else "Mapa de Pneus"
if executar == "extratopam": titulo_app = "Conversor de Extratos PAM"
titulo_app = f"App Lot Max - {titulo_app}" 
versao_app = "w1.0"

st.set_page_config(page_title=titulo_app, layout="wide", initial_sidebar_state="expanded")

if 'idioma' not in st.session_state:
    st.session_state.idioma = 'pt-BR'

st.sidebar.info(f"Empresa: {coname} ({coid})")
ano_atual = datetime.date.today().year

# --- 2. CSS CUSTOMIZADO (IDENTIDADE VISUAL LOTMAX) ---
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
       5. COMPACTAÇÃO DA SIDEBAR E CAIXA DE AVISOS FLEXÍVEL (VERSÃO FINAL)
       ======================================================================== */
    
    /* BLOCO DE AVISOS (st.info / st.warning / st.error): Torna a caixa elástica */
    [data-testid="stSidebar"] [data-testid="stNotification"] {
        display: flex !important;
        flex-direction: column !important; /* Texto flui para baixo */
        align-items: flex-start !important; 
        padding: 8px 12px !important;       
        margin-bottom: 5px !important;
        height: auto !important;            /* A caixa cresce com o texto */
        min-height: fit-content !important; /* Ajusta ao conteúdo */
        overflow: visible !important;       /* Garante que nada fique escondido */
    }

    /* Esconde o ícone nativo (i, ⚠️, ❌) para dar mais largura ao texto */
    [data-testid="stSidebar"] [data-testid="stNotification"] svg { 
        display: none !important; 
    }
    
    /* AJUSTE CRÍTICO: Captura o Markdown interno do st.error para não vazar */
    [data-testid="stSidebar"] [data-testid="stNotification"] div[data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stNotification"] div[data-testid="stMarkdownContainer"] p {
        font-size: 0.85rem !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.3 !important;
        width: 100% !important;
        word-wrap: break-word !important;
        white-space: normal !important;
        display: block !important; /* Garante que o container se comporte como texto */
    }

    /* --- AJUSTES DE ESPAÇO E SUPRESSÃO DO NOME DO ARQUIVO --- */
    [data-testid="stSidebarContent"] { padding-top: 0.8rem !important; }

    /* Remove o nome do arquivo (34.9KB) que "empurra" o layout para baixo */
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



# --- 3. CARGA DAS MATRIZES E BIBLIOTECAS (JSON + UTF-8) ---
pasta_config = "./list"
arquivo_matrizregras = os.path.join(pasta_config, f"rules_{executar}.json")
arquivo_listas = os.path.join(pasta_config, "lists_extratoPAM.utf8")

# TESTE DE CAMINHO (Coloque isso aqui!)
#st.write(f"Tentando ler: {arquivo_matrizregras}")
def carregar_biblioteca_listas(caminho):
    biblioteca = {} 
    bloco_atual = None
    if not os.path.exists(caminho): return {}
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha: continue
            if linha.startswith("[") and linha.endswith("]"):
                bloco_atual = linha[1:-1].strip()
                biblioteca[bloco_atual] = []
            elif bloco_atual:
                biblioteca[bloco_atual].append(linha)
    return biblioteca

try:
    repo_listas = carregar_biblioteca_listas(arquivo_listas)
    if os.path.exists(arquivo_matrizregras):
        with open(arquivo_matrizregras, "r", encoding="utf-8") as f:
            MATRIZ_REGRAS = json.load(f)
    else:
        st.error(f"🚨 Matriz '{arquivo_matrizregras}' não encontrada.")
        st.stop()

    # --- FASE DE ACOPLAGEM (Injeção Dinâmica) ---
    falhas_configuracao = []

    for item_nome, configuracao in MATRIZ_REGRAS.items():
        # Precisamos de uma chave de busca (assinatura ou cod)
        chave_busca = configuracao.get("assinatura") or configuracao.get("cod")
        
        # Percorre TODAS as chaves da configuração (valores, nomeabas, informacao, etc)
        for chave, valor in configuracao.items():
            if valor == "externalfile":
                if chave_busca in repo_listas:
                    # Substitui o termo 'externalfile' pela lista real do repo
                    configuracao[chave] = repo_listas[chave_busca]
                else:
                    falhas_configuracao.append(f"❌ Bloco **[{chave_busca}]** (para '{chave}') não localizado.")

#    bloco suspenso, sem garantias de funcionamento
#    for nivel_1, conteudo_nivel_1 in MATRIZ_REGRAS.items():
#        # Percorre o segundo nível (os blocos de configuração como COID, Placa, etc.)
#        if isinstance(conteudo_nivel_1, dict):
#            for pai, bloco in conteudo_nivel_1.items():
#                # Se o bloco for um dicionário (ex: {"ler": "parametro", ...})
#                if isinstance(bloco, dict):
#                    for filho, conteudo_filho in bloco.items():
#                        # GATILHO UNIVERSAL: Achou "parametro"? 
#                        if conteudo_filho == "parametro":
##                           bloco[filho]= pai.lower()
#                           # Em vez de: bloco[filho] = pai.lower()
#                           # Use isto:
#                           bloco[filho] = lambda n=pai.lower(): st.session_state.get(n) or globals().get(n)

# O restante do código segue...
    campos_criticos_obrigatorios = [item for item, regra in MATRIZ_REGRAS.items() if regra.get("critico") == True]
    lista_fixa_base = list(MATRIZ_REGRAS.keys())

except Exception as e:
    st.error(f"Falha na leitura dos dados: {e}")
    st.stop()

ativardebug = False                         # True mostra o conteúdo da matriz, o padrão é false
if ativardebug:
# --- INSPEÇÃO TÉCNICA (DEBUG) ---
    with st.expander("🔍 Ver Estrutura da Matriz (Debug)"):
        st.write("Configuração atual da MATRIZ_REGRAS:")
        st.json(MATRIZ_REGRAS) # O st.json deixa tudo identado e bonito para ler
    st.stop()

# --- 4. FUNÇÃO DE LEITURA ESTÁVEL ---
@st.cache_data(show_spinner="Lendo dados...", max_entries=10)
def ler_dados_excel(file, aba):
    try:
        engine_type = 'odf' if file.name.endswith('.ods') else 'openpyxl'
        df = pd.read_excel(file, sheet_name=aba, engine=engine_type)
        return df.copy()
    except Exception as e:
        st.error(f"Erro na leitura da aba {aba}: {e}")
        return None

# --- 5. CABEÇALHO VISUAL ---
c_logo, c_titulo = st.columns([1, 4])
with c_logo:
    logo_nome = "Lotmax_app_lotmax_2026.png"
    if os.path.exists(logo_nome): st.image(logo_nome, width=110)
    else: st.markdown("### 🚀 App LotMax")

with c_titulo:
    st.markdown(f"""
        <h3 style='margin-top: 15px; margin-bottom: 0px;'>
            {titulo_app} <span style='font-size: 0.85rem; font-weight: 400; color: #7f8c8d; margin-left: 8px;'>{versao_app}</span>
            <span style='color: transparent; font-size: 0.5rem; user-select: text;'>Py: {sys.version} | ST: {st.__version__}</span>
        </h3>
    """, unsafe_allow_html=True)

#st.divider()

# --- 6. BARRA LATERAL E LÓGICA DE UPLOAD ---
with st.sidebar:
    st.markdown("<span style='font-size: 0.9rem; font-weight: 700; color: #2c3e50;'>📂 Gestão de Arquivo</span>", unsafe_allow_html=True)
#    uploaded_file = st.file_uploader("Upload Excel/ODS", type=["xlsx", "xls", "ods"], label_visibility="collapsed")
    uploaded_file = st.file_uploader("Upload Excel/ODS/PDF", type=["xlsx", "xls", "ods", "pdf"], label_visibility="collapsed")
    st.markdown("<hr style='margin: 10px 0px; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

   

if uploaded_file:
    st.markdown(
        f"📄 **Arquivo:** `{uploaded_file.name}`  \n"
        f"<span style='font-size: 0.8em; color: gray;'>"
        f"⚠️ Aviso: Caso o arquivo utilizado sofrer alguma modificação, será necessário fazer o upload novamente para obter as mudanças."
        f"</span>", 
        unsafe_allow_html=True
    )

    tipo_detectado = None
    regras_ativas = None
    # EXTRAÇÃO REAL DA EXTENSÃO (Pega apenas o final, ex: '.pdf')
    extensao = os.path.splitext(uploaded_file.name)[1].lower()
    # --- 1. IDENTIFICAÇÃO PARA PDF ---
    if '.pdf' in extensao:
        with pdfplumber.open(uploaded_file) as pdf:
            # Extração da primeira página para identificação
            texto_extraido = pdf.pages[0].extract_text() or ""
            
            for nome_op, config in MATRIZ_REGRAS.items():
                dna = config.get("chavebusca")
                
                # Normaliza: se for lista, pega o primeiro; se não, usa direto
                termo_busca = dna[0] if isinstance(dna, list) else dna

                # Validação direta por conteúdo
                if termo_busca and str(termo_busca).lower() in texto_extraido.lower():
                    tipo_detectado, regras_ativas = nome_op, config
                    break
   # --- 2. IDENTIFICAÇÃO PARA EXCEL/ODS ---
    elif extensao in ['.xlsx', '.xls', '.ods']:
        motor = 'odf' if extensao == '.ods' else 'openpyxl'
        xls = pd.ExcelFile(uploaded_file, engine=motor)
        abas_no_arquivo = xls.sheet_names

        for nome_op, config in MATRIZ_REGRAS.items():
            dna = config.get("chavebusca")
            
            # Caso 1: DNA Estrutural (Abas)
            if isinstance(dna, list) and len(dna) > 1:
                if any(aba in abas_no_arquivo for aba in dna):
                    tipo_detectado, regras_ativas = nome_op, config
                    break
            
            # Caso 2: DNA de Conteúdo
            elif dna:
                termo = dna[0] if isinstance(dna, list) else dna
                for aba in abas_no_arquivo:
                    df_check = pd.read_excel(xls, sheet_name=aba, nrows=40, header=None)
                    if df_check.astype(str).apply(lambda x: x.str.contains(str(termo), case=False, na=False)).any().any():
                        tipo_detectado, regras_ativas = nome_op, config
                        break
                if tipo_detectado: break

    # --- 3. VEREDITO FINAL (SEM PROCESSAMENTO AINDA) ---
    if tipo_detectado:
        st.sidebar.success(f"✅ **Assinatura Reconhecida:** {tipo_detectado}")
    else:
        st.sidebar.error("❌ Assinatura não identificada.")
        st.stop()


    # --- 4. MOTOR DE EXTRAÇÃO DINÂMICO (COM DEBUG DE ROTEAMENTO) ---
    config = regras_ativas
    tipo_op = config.get("tipo")
    
    # 1. Inicialização obrigatória das listas sincronizadas
    pedagio_lista = []
    estacto_lista = []
    
    # 2. Roteador: Mapeia o prefixo limpo para a variável de lista
    destinos = {
        "pedagio": pedagio_lista,
        "estacto": estacto_lista
    }

    # --- 4. MOTOR DE EXTRAÇÃO DINÂMICO (Transcrição Fiel de Máscara) ---
    if tipo_op == "leituraabas":
        for chave_aba, nome_real_aba in config["abasuso"].items():
            if nome_real_aba not in abas_no_arquivo: continue
            
            # Prefixo equalizado: 'pedagio_aba' -> 'pedagio'
            prefixo = chave_aba.split("_")[0] 
            alvo_lista = destinos.get(prefixo)
            
            df_dados = pd.read_excel(xls, sheet_name=nome_real_aba, header=0)
#           st.write(f"🔍 **Debug Aba `{nome_real_aba}`:** Prefixo `{prefixo}` localizado.")

            for i, linha in df_dados.iterrows():
                try:
                    registro = {config["COID"]["sai"]: coid}

                    for chave_matriz, acao in config.items():
                        if str(chave_matriz).startswith(f"{prefixo}_"):
                            
                            # 1. LEITURA (Conforme Matriz)
                            ref_ler = acao.get("ler")
                            if isinstance(ref_ler, dict):
                                # Fusão DATA + HORA (ou qualquer outra combinação)
                                v_raw = " ".join([str(linha[col]) for col in ref_ler.values() if col in df_dados.columns])
                            else:
                                v_raw = linha[ref_ler]

                            # 2. SAÍDA (Conforme Matriz - Extração de Chave String)
                            ref_sai = acao.get("sai")
                            nome_col_sai = list(ref_sai.keys())[0] if isinstance(ref_sai, dict) else ref_sai

                            # 3. FORMATAÇÃO DINÂMICA (DIRETO DO JSON SEM TRADUÇÃO)
                            fmt = acao.get("formatosaida")
                            v_final = v_raw

                            if fmt == "upper":
                                v_final = str(v_raw).upper()
                            elif fmt == "numerico":
                                # Converte para float real respeitando a vírgula decimal
                                v_final = float(str(v_raw).replace(',', '.'))
                            elif fmt and "%" in str(fmt):
                                # Se o formato no JSON contém '%', aplica o strftime direto sem o mapa_traducao
                                try:
                                    dt_obj = pd.to_datetime(v_raw, dayfirst=True)
                                    v_final = dt_obj.strftime(str(fmt))
                                except:
                                    v_final = v_raw # Mantém original se a data estiver corrompida


                            registro[nome_col_sai] = v_final

                    # Append na lista sincronizada
                    if alvo_lista is not None:
                        alvo_lista.append(registro)
                    
#                   # DEBUG DA PRIMEIRA LINHA
#                  if i == 0:
#                       st.write(f"✅ **Linha {i} Transcrita:**", registro)

                except Exception as e:
                    if i == 0: st.error(f"❌ Erro na transcrição (Campo `{chave_matriz}`): `{e}`")
                    continue
            
#           st.success(f"🏁 Processamento da aba `{nome_real_aba}` concluído.")

    # --- FLUXO B: MESCLADO (Ex: Conect Car) ---
    elif tipo_op == "mesclado":
        # mapeamento_trabalho normalizado para garantir consistência
        mapeamento_trabalho = config["abasuso"].items() if isinstance(config["abasuso"], dict) else [("unica", config["abasuso"])]
        
        for tipo_aba, nome_aba_m in mapeamento_trabalho:
            if nome_aba_m not in abas_no_arquivo: continue
            
            df_raw = pd.read_excel(xls, sheet_name=nome_aba_m, header=None)
            termo_m = config.get("pontoinicio")
            
            # Localiza Marco Zero
            mask = df_raw.astype(str).apply(lambda x: x.str.contains(str(termo_m), case=False, na=False)).any(axis=1)
            idx_m = df_raw[mask].index
            
            if not idx_m.empty:
                df_dados = df_raw.iloc[idx_m[0] + 1:].copy()
                df_dados.columns = df_raw.iloc[idx_m[0]]
                
                # Função interna para pegar índice por nome ou por Letra (Coluna_F)
                def get_idx(df, ref):
                    alvo = list(ref.keys())[0] if isinstance(ref, dict) else ref
                    if "coluna_" in str(alvo).lower():
                        letra = alvo.split("_")[-1].upper()
                        return ord(letra) - 65
                    return df.columns.get_loc(alvo)

                idx_placa = get_idx(df_dados, config["pedagio_placa"]["ler"])
                idx_data_ref = get_idx(df_dados, config["pedagio_data"]["ler"])
                idx_valor = get_idx(df_dados, config["pedagio_valor"]["ler"])

                for _, linha in df_dados.iterrows():
                    try:
                        # Filtro de Integridade (Regex)
                        celula_f = str(linha.iloc[idx_data_ref]).strip()
                        datas = re.findall(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2})", celula_f)
                        if not datas: continue 

                        # Extração e Formatação
                        data_final = datas[0]
                        local_final = celula_f.split(data_final)[0].strip("- ").strip()
                        valor_final = abs(float(str(linha.iloc[idx_valor]).replace(',', '.')))

                        # Chave de saída dinâmica para Data
                        ref_sai_dt = config["pedagio_data"]["sai"]
                        nome_dt = list(ref_sai_dt.keys())[0] if isinstance(ref_sai_dt, dict) else ref_sai_dt

                        registro = {
                            config["COID"]["sai"]: coid,
                            config["pedagio_placa"]["sai"]: str(linha.iloc[idx_placa]).upper(),
                            nome_dt: data_final,
                            config["pedagio_valor"]["sai"]: valor_final
                        }

                        # Segregação Sincronizada
                        if tipo_aba == "pedagio_aba" or len(datas) == 1:
                            registro[config["pedagio_praca"]["sai"]] = local_final
                            pedagio_lista.append(registro)
                        else:
                            chave_est = config.get("estacto_praca", {}).get("sai", "01-ESTABELECIMENTO")
                            registro[chave_est] = local_final
                            estacto_lista.append(registro)
                    except: continue

    elif tipo_op == "hibrido_pdf_regex":
        placa_atual = None
        alvo_encontrado = False 
        contexto_atual = "pedagio" 

        # 1. Transforma o PDF (já aberto) em lista de linhas
        todas_as_linhas = []
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                todas_as_linhas.extend(texto.split('\n'))

        # 2. Varredura e Alimentação (Fiel à Matriz)
        for i, linha in enumerate(todas_as_linhas):
            
            # --- DEBUG: PESQUISADO ---
#            st.text(f"PESQUISADO [{i}]: {linha}")

            # --- MANOBRA: CAPTURA DA PLACA ---
            match_placa = re.search(r'([A-Z]{3}-?\d[A-Z\d]\d{2})', linha)
            if match_placa:
                placa_atual = match_placa.group(1).replace("-", "")
#                st.write(f"PLACA_ATUAL: {placa_atual}")

            # --- MANOBRA: GATILHO (LIDO DA MATRIZ) ---
            # Busca o termo exato definido em 'pontoinicio' (ex: "Pedágio")
            termo_inicio = config.get("pontoinicio")
            if termo_inicio and termo_inicio in linha:
                alvo_encontrado = True
                # O contexto muda para 'pedagio' ou 'estacto' se o termo for achado
                contexto_atual = "pedagio" if "Pedágio" in linha else "estacto"
#                st.write(f"PONTO_INICIO_DETECTADO: {linha}")

            if not alvo_encontrado:
                continue 

            # --- MANOBRA: EXTRAÇÃO VIA REGEX ---
            regex_transacao = r'(\d{2}/\d{2}/\d{2,4})\s+(\d{2}:\d{2})\s+(.*?)\s+(-?\d+,\d{2})'
            match_trans = re.search(regex_transacao, linha)
            
            if match_trans and placa_atual:
                data_bruta, hora_bruta, estab, valor = match_trans.groups()
                
                # --- DEBUG: LIDO ---
#                st.write(f"LIDO: {data_bruta} | {hora_bruta} | {estab} | {valor}")

                # --- MONTAGEM DO REGISTRO (CONFORME MATRIZ 'SAI') ---
                # Pega as chaves 'sai' dinamicamente da matriz baseada no contexto
                registro = {
                    config["COID"]["sai"]: coid,
                    config[f"{contexto_atual}_placa"]["sai"]: placa_atual,
                    # Para a data, extrai a chave do dicionário 'sai' da matriz
                    list(config[f"{contexto_atual}_data"]["sai"].keys())[0]: f"{data_bruta} {hora_bruta}",
                    config[f"{contexto_atual}_praca"]["sai"]: estab,
                    config[f"{contexto_atual}_valor"]["sai"]: float(valor.replace(",", ".")) * -1,      # transforma para positivo
                    config[f"{contexto_atual}_tag"]["sai"]: ""                                          # tag não consta do arquivo
                }

                # --- DEBUG: REGISTRADO ---
 #               st.write("REGISTRADO:")
 #               st.write(registro)

                # --- ALIMENTAÇÃO DO DESTINO EXTERNO ---
                destinos[contexto_atual].append(registro)


        # --- 5. EXIBIÇÃO SINCRONIZADA ---
    st.markdown("---")
    t1, t2 = st.tabs(["🛣️ Pedágios", "🅿️ Estacionamentos"])
    col_id = config["COID"]["sai"]

    with t1:
        if pedagio_lista:
            st.dataframe(pd.DataFrame(pedagio_lista).drop(columns=[col_id]), use_container_width=True)
        else: st.info("Nenhum registro de pedágio localizado.")

    with t2:
        if estacto_lista:
            st.dataframe(pd.DataFrame(estacto_lista).drop(columns=[col_id]), use_container_width=True)
        else: st.info("Nenhum registro de estacionamento localizado.")

    # --- FASE DE POUSO FINAL: CONSOLIDADO SIDEBAR (UTF-8-SIG) ---
    with st.sidebar:
        st.markdown("---")
        st.subheader("📥 Downloads Disponíveis")
        
        # Telemetria de Nome e Data
        agora = datetime.datetime.now().strftime("%y%m%d_%H%M")
        nome_puro = os.path.splitext(uploaded_file.name)[0]
        arq_saida = (f"{nome_puro}_App_LotMax_pam")
        # --- STATUS DO SISTEMA ---
        if not pedagio_lista and not estacto_lista:
            st.info("🛰️ Aguardando processamento...")
        else:
            st.success("✅ Arquivo(s) pronto(s).")

        # --- LOTE 1: PEDÁGIOS ---
        if pedagio_lista:
            df_p = pd.DataFrame(pedagio_lista)
            
            # Geração do CSV puro para o Bubble (UTF-8-SIG para acentuação)
            csv_pedagio = df_p.to_csv(index=False, sep=';', encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
            
            st.download_button(
                label=f"🛣️ Baixar Pedágios ({len(pedagio_lista)} itens)",
                data=csv_pedagio,
                file_name=f"{arq_saida}_pedagio_{agora}.csv",
                mime="text/csv",
                use_container_width=True
            )

        # --- LOTE 2: ESTACIONAMENTOS ---
        if estacto_lista:
            df_e = pd.DataFrame(estacto_lista)
            
            # Mesma configuração técnica para o segundo arquivo
            csv_estacto = df_e.to_csv(index=False, sep=';', encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
            
            st.download_button(
                label=f"🅿️ Baixar Estacionamentos ({len(estacto_lista)} itens)",
                data=csv_estacto,
                file_name=f"{arq_saida}_estacto_{agora}.csv",
                mime="text/csv",
                use_container_width=True
            )
