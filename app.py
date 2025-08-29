import os
from pathlib import Path
from datetime import timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
import yfinance as yf
import time
import random

st.set_page_config(page_title="Acompanhamento Cotação", layout="wide", page_icon="💰")

# >>> AJUSTES AQUI <<<
PASTA_ARQUIVOS = Path(os.getenv("XLS_DIR", r"./data")).resolve()
INCLUIR_SUBPASTAS = False

# MAPEAMENTO DE NOMES PARA AS ABAS:
MAPEAMENTO_NOMES = {
    "açucar-cristal": "Açúcar Branco (Mercado Externo)",
    "açucar-santos": "Açúcar (Santos)",
    "açucar-vhp": "Açúcar VHP (Mercado Externo)",
    "café-arabica": "Café Arábica",
    "dolar": "Dólar",
    "milho": "Milho",
    "robusta": "Café Robusta",
    "soja-paranagua": "Soja (Paranaguá)",
    "etanol-diario-bovespa": "Etanol (Diário Bovespa)",
    "soja-parana": "Soja (Paraná)",
    "soja-chicago": "Soja (Chicago)",
}

# MAPEAMENTO DE UNIDADES PARA CADA COMMODITY
UNIDADES_COMMODITIES = {
    "açucar-cristal": "saca de 50kg",
    "açucar-santos": "saca de 50kg", 
    "açucar-vhp": "tonelada",
    "café-arabica": "saca de 60kg",
    "dolar": "",
    "milho": "saca de 60kg",
    "robusta": "saca de 60kg",
    "soja-paranagua": "saca de 60kg",
    "etanol-diario-bovespa": "litro",
    "soja-parana": "saca de 60kg",
    "soja-chicago": "tonelada",
}

st.title("Acompanhamento Cotações - CEPEA/ESALQ")

# ---------- utilidades ----------
def aplicar_correcao_etanol(df: pd.DataFrame, nome_arquivo: str) -> pd.DataFrame:
    """Aplica correção específica para etanol - divide valores por 1000"""
    if "etanol" in nome_arquivo.lower() and "À vista R$" in df.columns:
        df = df.copy()
        df["À vista R$"] = df["À vista R$"] / 1000
    return df

def obter_unidade_commodity(nome_arquivo: str) -> str:
    """Obtém a unidade da commodity baseada no nome do arquivo"""
    nome_arquivo = nome_arquivo.lower()
    for chave, unidade in UNIDADES_COMMODITIES.items():
        if chave in nome_arquivo:
            return unidade
    return ""

@st.cache_data(ttl=7200, show_spinner=False)
def buscar_dados_soja_chicago():
    """Busca dados da soja de Chicago com tratamento de rate limiting"""
    try:
        time.sleep(random.uniform(1, 3))
        soja = yf.Ticker("ZS=F")
        
        try:
            dados = soja.history(period="6mo")
        except:
            time.sleep(2)
            dados = soja.history(period="3mo")
        
        if dados.empty:
            raise Exception("Dados vazios retornados da API")
        
        df_soja = pd.DataFrame()
        df_soja["Data"] = dados.index.date
        df_soja["À vista R$"] = dados["Close"].values
        
        # Conversão aproximada: centavos USD/bushel para R$/tonelada
        taxa_cambio = 5.0
        df_soja["À vista R$"] = df_soja["À vista R$"] * 36.74 * taxa_cambio / 100
        
        df_soja = df_soja.sort_values("Data").reset_index(drop=True)
        return {"Soja Chicago": df_soja}, False
        
    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar dados da soja de Chicago: {str(e)}")
        st.info("📊 Usando dados de exemplo para demonstração")
        
        dates = pd.date_range(end=pd.Timestamp.now().date(), periods=30, freq='D')
        exemplo_precos = [1800 + i*5 + random.uniform(-50, 50) for i in range(30)]
        
        df_exemplo = pd.DataFrame({
            "Data": dates.date,
            "À vista R$": exemplo_precos
        })
        
        return {"Soja Chicago": df_exemplo}, True

def mapear_nome_arquivo(path_arquivo: str) -> str:
    """Usa o MAPEAMENTO_NOMES para encontrar um nome amigável para a aba."""
    nome_arquivo = Path(path_arquivo).name.lower()
    for chave, nome_aba in MAPEAMENTO_NOMES.items():
        if chave in nome_arquivo:
            return nome_aba
    return Path(path_arquivo).name

def listar_planilhas(dirpath: Path, recursivo: bool = False):
    if not dirpath.exists():
        return []
    pattern = "**/*" if recursivo else "*"
    return sorted([str(f) for f in dirpath.glob(pattern)
                   if f.is_file() and f.suffix.lower() == ".xls"])

def _normalize_numeric_series(s: pd.Series) -> pd.Series:
    if s.dtype == object:
        return pd.to_numeric(
            s.astype(str).str.replace(r"\.", "", regex=True).str.replace(",", ".", regex=False),
            errors="coerce"
        )
    return pd.to_numeric(s, errors="coerce")

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    header_idx = None
    for i, row in df.iterrows():
        if any(str(x).strip().lower() == "data" for x in row.values):
            header_idx = i
            break
    
    if header_idx is not None:
        df = df.iloc[header_idx + 1:].reset_index(drop=True)\
               .rename(columns={j: v for j, v in enumerate(df.iloc[header_idx].tolist())})
    
    df.columns = [str(c).strip() for c in df.columns]
    
    seen = {}
    new_cols = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}.{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df.columns = new_cols
    
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    
    for c in df.columns:
        if c != "Data":
            tmp = _normalize_numeric_series(df[c])
            if tmp.notna().sum() > 0:
                df[c] = tmp
    return df

def _read_all_sheets(path: str, engine=None) -> dict:
    raw = pd.read_excel(path, sheet_name=None, engine=engine, header=None)
    cleaned = {}
    for nome, df in raw.items():
        df = _clean_df(df.copy())
        cleaned[str(nome)] = df
    return cleaned

def _resalvar_com_excel(path_xls: str) -> str:
    from win32com.client import Dispatch
    xl = Dispatch("Excel.Application")
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(str(Path(path_xls).resolve()))
    novo = str(Path(path_xls).with_suffix(".reparado.xlsx"))
    wb.SaveAs(novo, FileFormat=51)
    wb.Close(False); xl.Quit()
    return novo

@st.cache_data(show_spinner=False)
def ler_planilha_robusta(caminho_arquivo: str) -> dict:
    try:
        return _read_all_sheets(caminho_arquivo, engine="xlrd")
    except Exception:
        try:
            return _read_all_sheets(caminho_arquivo, engine="calamine")
        except Exception:
            try:
                reparado = _resalvar_com_excel(caminho_arquivo)
                return _read_all_sheets(reparado, engine=None)
            except Exception as e3:
                return {"__ERRO__": pd.DataFrame({"erro": [str(e3)]})}

def colunas_numericas(df: pd.DataFrame):
    return list(df.select_dtypes(include="number").columns)

# ---------- app ----------
arquivos = listar_planilhas(PASTA_ARQUIVOS, INCLUIR_SUBPASTAS)

# Adiciona a soja de Chicago
dados_soja_chicago, usando_exemplo = buscar_dados_soja_chicago()
arquivos_completos = arquivos + ["soja-chicago"]

if not arquivos_completos:
    st.error(f"Nenhum arquivo encontrado em: {PASTA_ARQUIVOS}")
    st.stop()

# Cria as tabs
nomes_tabs = []
for arq in arquivos_completos:
    if arq == "soja-chicago":
        nome_tab = "Soja (Chicago)"
        if usando_exemplo:
            nome_tab += " 📊"
        nomes_tabs.append(nome_tab)
    else:
        nomes_tabs.append(mapear_nome_arquivo(arq))

tabs = st.tabs(nomes_tabs)

# Processa arquivos Excel
for idx, arq in enumerate(arquivos):
    with tabs[idx]:
        sheets = ler_planilha_robusta(arq)

        if "__ERRO__" in sheets:
            st.error(f"Falha ao ler: {Path(arq).name}")
            st.text(sheets["__ERRO__"].to_string(index=False))
            continue

        nomes_abas = list(sheets.keys())
        if not nomes_abas:
            st.warning("Arquivo sem abas legíveis.")
            continue

        df = sheets[nomes_abas[0]].copy()

        if df.empty:
            st.warning("A aba selecionada está vazia.")
            continue

        # APLICA CORREÇÃO DO ETANOL - DIVIDE POR 1000
        df = aplicar_correcao_etanol(df, arq)

        # Filtro de data
        if "Data" in df.columns and pd.api.types.is_datetime64_any_dtype(df["Data"]):
            min_date = df["Data"].min().date() if pd.notna(df["Data"].min()) else None
            max_date = df["Data"].max().date() if pd.notna(df["Data"].max()) else None
            
            if min_date and max_date:
                date_range = st.date_input(
                    "Período",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key=f"date_range_{idx}"
                )
                
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    df = df[(df["Data"].dt.date >= start_date) & (df["Data"].dt.date <= end_date)]
        
        # Layout em duas colunas
        col_grafico, col_tabela = st.columns([2, 1])
        
        with col_grafico:
            if "À vista R$" in df.columns:
                y_col = "À vista R$"
                x_col = "Data" if "Data" in df.columns else df.columns[0]
                
                # Adiciona nome do ativo e unidade no título
                nome_ativo = mapear_nome_arquivo(arq)
                unidade = obter_unidade_commodity(arq)
                titulo = f"{nome_ativo} - Preço À Vista ({unidade})" if unidade else f"{nome_ativo} - Preço À Vista"
                
                try:
                    fig = px.line(df, x=x_col, y=y_col, markers=True, title=titulo)
                    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Erro ao plotar: {e}")
            else:
                st.warning("Coluna 'À vista R$' não encontrada. Usando dados disponíveis.")
                cols_num = colunas_numericas(df)
                if cols_num:
                    y_col = cols_num[0]
                    x_col = "Data" if "Data" in df.columns else df.columns[0]
                    fig = px.line(df, x=x_col, y=y_col, markers=True)
                    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Não há colunas numéricas para plotar.")

        with col_tabela:
            cols_mostrar = ["Data", "À vista R$"] if "À vista R$" in df.columns else df.columns[:3]
            df_tab = df[cols_mostrar].copy()
            
            if "Data" in df_tab.columns and pd.api.types.is_datetime64_any_dtype(df_tab["Data"]):
                df_tab = df_tab.sort_values("Data", ascending=False).head(7)
            else:
                df_tab = df_tab.tail(6)
            
            # Formatar valores numéricos para 2 casas decimais
            if "À vista R$" in df_tab.columns:
                df_tab["À vista R$"] = df_tab["À vista R$"].round(2)
            
            st.dataframe(df_tab, use_container_width=True, height=400)

# Processa soja de Chicago
if len(arquivos_completos) > len(arquivos):
    with tabs[-1]:  # Última tab é a soja de Chicago
        df_soja = dados_soja_chicago["Soja Chicago"].copy()
        
        if not df_soja.empty:
            # Filtro de data para soja
            if "Data" in df_soja.columns:
                df_soja["Data"] = pd.to_datetime(df_soja["Data"])
                min_date = df_soja["Data"].min().date()
                max_date = df_soja["Data"].max().date()
                
                date_range = st.date_input(
                    "Período",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key="date_range_soja_chicago"
                )
                
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    df_soja = df_soja[(df_soja["Data"].dt.date >= start_date) & (df_soja["Data"].dt.date <= end_date)]
            
            col_grafico, col_tabela = st.columns([2, 1])
            
            with col_grafico:
                try:
                    fig = px.line(df_soja, x="Data", y="À vista R$", markers=True, 
                                title="Soja (Chicago) - Preço À Vista (tonelada)")
                    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Erro ao plotar soja de Chicago: {e}")
            
            with col_tabela:
                df_tab_soja = df_soja[["Data", "À vista R$"]].copy()
                df_tab_soja = df_tab_soja.sort_values("Data", ascending=False).head(7)
                
                # Formatar valores para 2 casas decimais
                df_tab_soja["À vista R$"] = df_tab_soja["À vista R$"].round(2)
                
                st.dataframe(df_tab_soja, use_container_width=True, height=400)
        else:
            st.warning("Não foi possível obter dados da soja de Chicago.")