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
import pdfplumber
import difflib
import time
import re
import list._pvt_code_lib as pvt

# Força o 'sys' no namespace global para bibliotecas que falham no importlib do 3.14
if 'sys' not in globals():
    globals()['sys'] = sys

#st.write(f"ESTOU LENDO DAQUI: {pvt.__file__}")
#st.stop() # Para o app aqui para você ler o caminho

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
elif executar not in ["listadeveiculos", "mapadepneus", "extratopam"]:
    notcontinue = True
    justificativa = "Chamada inválida, execução cancelada!"

# A partir daqui, o notcontinue só será True se um dos dois falhar.
if notcontinue:
    st.set_page_config(page_title="Erro de Acesso", layout="wide")
    st.error(f"🚨 {justificativa}")
    pvt.log_operacao("Erro de Acesso")
    st.stop()

# Montagem do titulo do app e elementos de uso dos executáveis
# --- 1. Titulos e configuração de interfaces e elementos utilizados ao longo app, definidos aqui para evitar ifs em diversos pontos com o mesmo propósito ---
titulo_app= "App Lotmax"
if executar in ["listadeveiculos", "mapadepneus"]:
    titulo_exec = f"Mapeador e planilhas {"Lista de veiculos" if executar == "listadeveiculos" else "Mapa de Pneus"}"
    arq_list = "lists_mpplanilha"
    arq_saida_tipo = f"AppLotmax_{"lv" if executar == "listadeveiculos" else "mp"}"
elif executar == "extratopam":
    titulo_exec = "Conversor de Extratos PAM"
    arq_list = "lists_extratopam"
    arq_saida_tipo = "AppLotmax_pam"

ano_atual = datetime.date.today().year                  # utilizado ao longo do código

titulo_app= f"{titulo_app} - {titulo_exec}"
versao_app= f"w1.1 {ano_atual}"                              # Arquivo de origem - LotMaxApp_uno_w1_t0 260319 1652.py

st.set_page_config(page_title=titulo_app, layout="wide", initial_sidebar_state="expanded")
#if 'idioma' not in st.session_state:
#    st.session_state.idioma = 'pt-BR'

st.sidebar.info(f"Empresa:  \n{coname}({coid})")

# Carrega o estilo CSS informado, deve ter o arquivo css equivalente, caso informado ou não exista abrirá o estilo padrão
pvt.aplicar_estilo("AppLotMax_std")

# Carrega titulos e logotipo
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
st.markdown("<hr style='margin: 10px 0px; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

# Carrega matriz de regras baseada em arquivos 'rules_*.json' e .utf8 (pasta padrão ./list) com ou sem debug 3o parametro ou usando na url step=matriz_regras, de acordo com o nome do arquivo de regras 
MATRIZ_REGRAS=pvt.carregar_matriz(f"{executar}",f"{arq_list}",False)
# Identificamos quais são os campos obrigatórios na Matriz
campos_criticos_obrigatorios = [item for item, regra in MATRIZ_REGRAS.items() if regra.get("critico") == True]
# Define a lista fixa globalmente para o botão de limpar funcionar
lista_fixa_base = list(MATRIZ_REGRAS.keys())

#aplicável só para listadeveiculos conforme as regras
ano_minimo = ano_atual - 0
ano_maximo = ano_atual + 0

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

# --- 6. BARRA LATERAL E LÓGICA DE UPLOAD ---
with st.sidebar:
    # Trocamos o H3 (###) por uma span com fonte controlada (0.9rem)
    st.markdown("<span style='font-size: 0.9rem; font-weight: 700; color: #2c3e50;'>📂 Seleção de Arquivo</span>", unsafe_allow_html=True)
    if executar == "extratopam":
        tipos_txt = "Carregar arquivos Excel/ODS/PDF"
        tipos_ext = ["xlsx", "xls", "ods","pdf"]
    else:
        tipos_txt = "Carregar arquivos Excel/ODS"
        tipos_ext = ["xlsx", "xls", "ods"]
        
    uploaded_file = st.file_uploader(tipos_txt, type= tipos_ext, label_visibility="collapsed")
    # Substituímos o st.divider() por uma linha CSS mais fina para ganhar espaço
    st.markdown("<hr style='margin: 10px 0px; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
    st.divider()
    if executar != "extratopam":
        st.markdown("<small><span style='color: red;'>*</span> Campos obrigatórios</small>", unsafe_allow_html=True)
    st.markdown("<hr style='margin: 10px 0px; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

if uploaded_file:
    # BLOCO VISUAL (Seu código original com botão)
    col_info, col_reset = st.columns([3, 1])
    with col_info:
        st.markdown(
            f"📄 **Arquivo:** `{uploaded_file.name}`  \n"
            f"<span style='font-size: 0.8em; color: gray;'>"
            f"⚠️ Aviso: Caso o arquivo utilizado sofrer alguma modificação, será necessário fazer o upload novamente para obter as mudanças."
            f"</span>", 
            unsafe_allow_html=True
        )
    if executar != "extratopam":
        with col_reset:
            if st.button("🗑️ Limpar Seleções", use_container_width=True):
                st.session_state.map_state = {item: "(Pular)" for item in lista_fixa_base}
                st.session_state.reset_ctr = st.session_state.get('reset_ctr', 0) + 1
                st.rerun()
    tipo_detectado = None
    regras_ativas = None


# --- 7. LÓGICA CENTRAL ---
if uploaded_file and (executar in ["mapadepneus","listadeveiculos"]):
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

    r_key = st.session_state.get('reset_ctr', 0)
    # 1. Detecta o motor: se for .ods usa 'odf', senão usa 'openpyxl' (para xlsx/xls)
    motor = 'odf' if uploaded_file.name.lower().endswith('.ods') else 'openpyxl'
    # 2. Abre o arquivo com o motor certeiro
    xls = pd.ExcelFile(uploaded_file, engine=motor)
    opcoes_com_contagem = []
    for nome in xls.sheet_names:
        # Lê apenas o necessário para contar as linhas (rápido)
        df_temp = pd.read_excel(uploaded_file, sheet_name=nome, usecols=[0]) 
        opcoes_com_contagem.append(f"{nome} ({len(df_temp)} linhas)")

    aba_formatada = st.selectbox("Selecione a Aba:", opcoes_com_contagem, key=f"aba_main_{r_key}")

    # Para usar no seu código, você limpa o nome (remove o final)

    aba_sel = aba_formatada.split(" (")[0]
#    # 3. Seu seletor continua lendo as abas desse mapa
#    aba_sel = st.selectbox("Selecione a Aba:", xls.sheet_names, key=f"aba_main_{r_key}")
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
                                mask_suspeita_estoque = dados_validar.apply(pvt.aproximacao_palavra,palavra="ESTOQUE")
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
                        if st.button(f"🚀 PROCESSAR ARQUIVOS", use_container_width=True):
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
                                status_text.text("🛠️ Formatando CSV para Lotmax...")
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
                                total_linhas=len(df_csv)

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
                            arq_saida=f"{nome_puro}_{arq_saida_tipo}"            # se executar = arq_saida_tipo AppLotmax + se listadeveidulos lv ou mapadepneus mp ou extratopam pam
                                       
                            st.download_button(f"📥 CSV para upload Lotmax ({total_linhas}) linhas", csv_data, f"{arq_saida}_{agora}.csv", "text/csv", use_container_width=True)
                            st.download_button(f"📄 EXCEL para revisão ({total_linhas}) linhas", out_xlsx.getvalue(), f"{arq_saida}_revisão_{agora}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
elif uploaded_file and executar == "extratopam":
#    st.markdown(
#        f"📄 **Arquivo:** `{uploaded_file.name}`  \n"
#        f"<span style='font-size: 0.8em; color: gray;'>"
#        f"⚠️ Aviso: Caso o arquivo utilizado sofrer alguma modificação, será necessário fazer o upload novamente para obter as mudanças."
#        f"</span>", 
#        unsafe_allow_html=True
#    )

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
        st.sidebar.success(f"✅ Assinatura Reconhecida:  \n &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {tipo_detectado}")
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
        arq_saida=f"{nome_puro}_{arq_saida_tipo}"            # se executar = arq_saida_tipo AppLotmax + se listadeveidulos lv ou mapadepneus mp ou extratopam pam

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
else:
    st.info("Aguardando upload do arquivo ...")
