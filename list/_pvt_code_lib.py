"""  _pvt_code_lib
    contém conjunto de funções compartilháveis por multiplos códigos, como:
        carregamento de estilos
        carregamento de regras
        nomenclatura de arquivos (parametros)     nome, complemento, se aplica ou não datahora, extensão
"""
import sys
import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import inspect
import unicodedata
import difflib

# --- CONFIGURAÇÃO DE BASE ---
PASTA_DA_LIB = Path(__file__).parent

def log_operacao(identificador="comum", mensagem= "vazia", tipo="info"):
    agora = datetime.now()
    data_hora = agora.strftime("%d/%m/%Y %H:%M:%S")
    data_arquivo = agora.strftime("%Y%m%d")
    
    stack = inspect.stack()
    
    # 1. Valor Inicial de Segurança (Pega quem chamou o log agora)
    nome_app = os.path.basename(stack[1].filename)
    linha_codigo = stack[1].lineno 

    # 2. Refinamento: Busca o App real ignorando a Lib e o Motor do Streamlit
    for frame in stack:
        f_nome = os.path.basename(frame.filename)
        # Se NÃO for a lib, NEM o motor do Streamlit, esse é o seu App!
        if "_pvt_code_lib" not in f_nome and "script_runner" not in f_nome and "runtime" not in f_nome:
            nome_app = f_nome
            linha_codigo = frame.lineno
            break 
    
    tipo = tipo.capitalize()
    pasta_logs = Path("logs")
    pasta_logs.mkdir(parents=True, exist_ok=True)
    
    caminho_log = pasta_logs / f"log_{identificador}_{data_arquivo}.txt"
    linha_log = f"[{data_hora}] [{tipo}] [{identificador} {nome_app}:{linha_codigo}] {mensagem}\n"
    
    with open(caminho_log, "a", encoding="utf-8") as f:
        f.write(linha_log)
    
    print(f"Log ... {tipo} | {nome_app}:{linha_codigo} | {mensagem}")

def checar_ambiente():
    versao = sys.version_info
    return f"Python {versao.major}.{versao.minor} operando nominalmente."

def gerar_nome_arquivo(nome_base="arquivo_de_testes", complemento=None, incluir_data=True, extensao="csv"):
    """
    Gera o nome do arquivo. Identifica se o chamador é o App ou uma função da Lib.
    """
    if complemento is None:
        stack = inspect.stack()
        idx_chamador = 1
        
        # Verifica se o nível 1 é a própria LIB
        nome_arquivo_nivel_1 = Path(stack[1].filename).stem
        if "_pvt_code_lib" in nome_arquivo_nivel_1:
            idx_chamador = 2
            
        arquivo_origem = Path(stack[idx_chamador].filename).stem
        complemento = arquivo_origem

    base_limpa = nome_base.replace(" ", "_")
    bloco_comp = f"_{complemento}" if complemento else ""
    bloco_data = f"_{datetime.now().strftime('%Y%m%d_%H%M')}" if incluir_data else ""
    
    return f"{base_limpa}{bloco_comp}{bloco_data}.{extensao}"

def salvar_dados(df, nome_base="arquivo_de_testes", pasta_destino="temp", extensao="csv", **kwargs):
    """
    Salva Dados com nome automático e garante a criação da pasta de destino.
    """
    nome_final = gerar_nome_arquivo(
        nome_base=nome_base, 
        extensao=extensao, 
        incluir_data=True
    )
    
    caminho_pasta = Path(pasta_destino)
    caminho_pasta.mkdir(parents=True, exist_ok=True)
    caminho_completo = caminho_pasta / nome_final

    try:
        if extensao.lower() == "csv":
            df.to_csv(caminho_completo, encoding="utf-8-sig", **kwargs)
        elif extensao.lower() in ["xlsx", "excel"]:
            df.to_excel(caminho_completo, **kwargs)
        
        log_operacao(f"Sucesso ao salvar: {nome_final} em {pasta_destino}")
        return caminho_completo
    except Exception as e:
        log_operacao(f"Erro ao salvar {nome_final}: {e}", tipo="erro")
        return None

def aplicar_estilo(id_estilo="padrao"):
    """
    Esconder Elementos: O menu de hambúrguer (#MainMenu) e o rodapé (footer) somem sozinhos.
    Cabeçalho (st.set_page_config): Fica transparente automaticamente.
    Selectbox (st.selectbox): Todos ficarão com altura reduzida (28px) e fonte menor.
    File Uploader (st.file_uploader): Todos aparecerão traduzidos ("Arraste e solte", "Selecionar arquivo") e sem o nome do arquivo aparecendo embaixo.
    Avisos na Sidebar (st.sidebar.error/info): Ficam elásticos e sem o ícone nativo automaticamente.
    2. Estilos Manuais (Classes que você criou)
    Para usar estes, você precisa usar st.markdown com o parâmetro unsafe_allow_html=True:
    .mapping-label: Use para títulos personalizados acima de campos.
    Exemplo: st.markdown('<p class="mapping-label">Coluna de Origem</p>', unsafe_allow_html=True)
    .val-error: Use para mensagens de erro curtas e vermelhas (abaixo de campos).
    Exemplo: st.markdown('<p class="val-error">Campo obrigatório!</p>', unsafe_allow_html=True)
    .val-warning: Use para alertas curtos e laranjas.
    Exemplo: st.markdown('<p class="val-warning">Atenção: formato incomum</p>', unsafe_allow_html=True)
    3. Tags Globais
    h1: Qualquer título de nível 1 criado via markdown (# Título) ou HTML seguirá a cor e fonte que você definiu no CSS (se houver).
    .block-container: Toda a sua página agora ocupa 98% da largura por padrão.
    Dica de Houston: Como você compactou os selectboxes para 28px, se você usar o label nativo do Streamlit (st.selectbox("Label", ...)), ele pode ficar um pouco distante. O ideal com esse seu CSS é deixar o label do Streamlit vazio "" e usar o seu .mapping-label logo acima para um visual mais profissional.
    """
    nome_arquivo = f"{id_estilo}.css"
    caminho_css = PASTA_DA_LIB / nome_arquivo

    if not caminho_css.exists():
        caminho_css = PASTA_DA_LIB / "padrao.css"

    if caminho_css.exists():
        with open(caminho_css, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.error(f"⚠️ Alerta: CSS '{id_estilo}' não encontrado.")

def remover_acentos(texto):
    if not isinstance(texto, str):
        return texto
    # Normaliza para decompor caracteres (ex: 'ó' vira 'o' + '´')
    nfkd_form = unicodedata.normalize('NFKD', texto)
    # Filtra apenas o que não for acento (Non-Spacing Mark)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def aproximacao_palavra(textopesquisa="",palavra=""):
    """ 
    Detecta aproximacao de palavras dentro de um texto
    :param textopesquisa: texto a ser comparado
    :param palavra: palavra a utilizar para comparação
    Ex. ESTOQUE em GUARDAMOS ESTOQE
    Ratio de 0.7 pega, mas ignora coisas não tão próximas
    caso necessite de passar o segundo parametro para chamadas dentro de outras funções, utilize palavra=("otermoaserenviado")
        exemplo:   mask_suspeita_estoque = dados_validar.apply(pvt.aproximacao_palavra,palavra="ESTOQUE")
    """
    if textopesquisa == palavra or palavra == "": return False
    return difflib.SequenceMatcher(None, textopesquisa, palavra).ratio() >= 0.7

def carregar_biblioteca_listas(caminho):                    ## substituida por lor_blocos_em_arquivos
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

def ler_blocos_em_arquivos(caminho_arquivo, nome_bloco):
    """
    Busca de elementos em um arquivo texto os elementos dever estar iniciados a partir de um Bloco entre colchetes [], p.ex, [LISTA_CORES], os itens subsequentes até o próximo [bloco] ou fim do arquivo,
    Retorna uma lista de strings ou None se o bloco não existir.
    """
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        return None

    linhas_do_bloco = []
    identificado = False
    tag_alvo = f"[{nome_bloco}]"

    with open(caminho, 'r', encoding='utf-8') as f:
        for linha in f:
            ln = linha.strip()
            if not ln: continue

            # Detecta cabeçalhos de bloco [Exemplo]
            if ln.startswith("[") and ln.endswith("]"):
                if ln == tag_alvo:
                    identificado = True
                    continue
                elif identificado:
                    break # Encontrou o início do próximo bloco, para a leitura
            
            if identificado:
                linhas_do_bloco.append(ln)
                
    return linhas_do_bloco if linhas_do_bloco else None

def check_step(nome_do_passo):
    """
    Verifica se o parâmetro 'step' na URL coincide com o ponto de parada.
    A simples presença do step correto já ativa o debug visual.
    """
    if 'st' in globals() and hasattr(st, 'query_params'):
        # Pega o que está na URL: .../?step=matriz_regras
        step_na_url = st.query_params.get("step", "")
        
        # Se o que está na URL for IGUAL ao nome que demos ao checkpoint:
        return step_na_url == nome_do_passo
    return False

def carregar_matriz(matriz, externalfile, debug=False):
    """
    :param matriz: Nome do arquivo extensão 'rules_*.json' que deve estar na pasta ./list (ex: './list/rules_veiculos.json')
    :param externalfile: Nome do arquivo de lista extensão .utf8 (ex: '.list/lists.utf8')
    :param debug: True ativa o modo debug e mostra o conteúdo da matriz e interrompe o processamento

    Motor de Carga Universal Ancorado na PASTA_DA_LIB (que é a pasta ./list).
    """
    # 1. Como PASTA_DA_LIB já é a pasta 'list', usamos ela diretamente
    caminho_abs_matriz = PASTA_DA_LIB / (f"rules_{matriz}.json" if not matriz.endswith(".json") else matriz)
    arquivo_listas = PASTA_DA_LIB / (f"{externalfile}.utf8" if not externalfile.endswith(".utf8") else externalfile)
    
    nome_curto = caminho_abs_matriz.name
    log_operacao(f"Iniciando carga da matriz: {nome_curto}", "Info")

    def processar_recursivo(elemento):
        if isinstance(elemento, dict):
            novo_dict = {}
            for k, v in elemento.items():
                print(f"passei aqui item {k}")
                print(f"item V {v}")
                print(f"item elemento {elemento}")
                print(f"item novo_dict {novo_dict}")
                if isinstance(v, str) and v.startswith("externalfile-"):
                    bloco_alvo = v.replace("externalfile-", "").strip()
                    
                    # Usa a função utilitária independente
                    conteudo = ler_blocos_em_arquivos(arquivo_listas, bloco_alvo)
                    
                    if conteudo is not None:
                        novo_dict[k] = conteudo
                    else:
                        log_operacao(f"Bloco [{bloco_alvo}] não localizado em {arquivo_listas.name}", "Error")
                        novo_dict[k] = []
                elif v == "anointervalo":
 
                    # Calcula os anos REAIS baseados no deslocamento do JSON e sobrescreve os valores antes de eles serem lidos novamente e serem gerados na posição e com os valores atualizados
                    ano_atual = datetime.now().year                                             ## atenção a datetime com a condição do import, da forma como está na lib deve ser desta forma
                    elemento["ano_minimo"] = ano_atual + elemento.get("ano_minimo",0)
                    elemento["ano_maximo"] = ano_atual + elemento.get("ano_maximo",0)
                    elemento["warning"] = f"{elemento.get('warning')} {elemento['ano_minimo']} e {elemento['ano_maximo']}"
                    novo_dict[k] = processar_recursivo(v)
                else:
                    novo_dict[k] = processar_recursivo(v)
            return novo_dict
        elif isinstance(elemento, list):
            return [processar_recursivo(item) for item in elemento]
        return elemento

    try:
        if not caminho_abs_matriz.exists():
            log_operacao(f"Matriz não encontrada em: {caminho_abs_matriz}", "Critical")
            return None
            
        with open(caminho_abs_matriz, 'r', encoding='utf-8') as f:
            matriz_final = processar_recursivo(json.load(f))
        
        log_operacao(f"Carga da matriz {nome_curto} concluída com sucesso.", "Success")

    except Exception as e:
        log_operacao(f"Falha crítica no motor de carga: {str(e)}", "Critical")
        return None
    
    if debug or check_step("matriz_regras"):
        log_operacao("debug ativado")
        if 'st' in globals() and hasattr(st, 'session_state'):
            with st.expander(f"🛰️ STEP DEBUG: {matriz}"):
                st.subheader(f"🛰️ Configuração atual da {nome_curto}:")
                st.json(matriz_final)
            st.info(f"Pausa programada no step: **matriz_regras**")
            st.stop()
        else:
            # Fallback Terminal
            print(f"\n{'!'*20} STEP: matriz_regras {'!'*20}")
            print(f" 🛰️ DEBUG - MATRIZ CARREGADA VIA LIB: {nome_curto}")
            print("!"*70)
            print(json.dumps(matriz_final, indent=4, ensure_ascii=False))
            print("!"*70)
            log_operacao("Execução interrompida pelo modo Debug.", "Warning")
            sys.exit()
            # ... print e exit ...

    return matriz_final

