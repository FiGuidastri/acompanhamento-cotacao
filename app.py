import os
from pathlib import Path
from datetime import timedelta
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Acompanhamento Cotação", layout="wide")

# >>> AJUSTES AQUI <<<
PASTA_ARQUIVOS = Path(os.getenv("XLS_DIR", r"./data")).resolve()
INCLUIR_SUBPASTAS = False

# MAPEAMENTO DE NOMES PARA AS ABAS:
# Adicione ou altere as "traduções" aqui.
# O código vai procurar o texto da esquerda no nome do arquivo
# e usar o texto da direita como nome da aba.
MAPEAMENTO_NOMES = {
    "açucar-cristal": "Açúcar Branco (Mercado Externo)",
    "açucar-santos": "Açúcar (Santos)",
    "açucar-vhp": "Açúcar VHP (Mercado Externo)",
    "café-arabica": "Café Arábica",
    "dolar": "Dólar",
    "milho": "Milho",
    "robusta": "Café Robusta",
    "soja-paranagua": "Soja (Paranaguá)",
}

st.title("Acompanhamento Cotações - CEPEA/ESALQ")


# ---------- utilidades ----------
def mapear_nome_arquivo(path_arquivo: str) -> str:
    """Usa o MAPEAMENTO_NOMES para encontrar um nome amigável para a aba."""
    nome_arquivo = Path(path_arquivo).name.lower()
    for chave, nome_aba in MAPEAMENTO_NOMES.items():
        if chave in nome_arquivo:
            return nome_aba
    return Path(path_arquivo).name  # Retorna o nome original se não encontrar


def listar_planilhas(dirpath: Path, recursivo: bool = False):
    if not dirpath.exists():
        return []
    pattern = "**/*" if recursivo else "*"
    return sorted([str(f) for f in dirpath.glob(pattern)
                   if f.is_file() and f.suffix.lower() == ".xls"])

def _normalize_numeric_series(s: pd.Series) -> pd.Series:
    # normaliza números estilo BR: "1.234,56" -> 1234.56
    if s.dtype == object:
        return pd.to_numeric(
            s.astype(str).str.replace(r"\.", "", regex=True).str.replace(",", ".", regex=False),
            errors="coerce"
        )
    return pd.to_numeric(s, errors="coerce")

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    # tenta achar a linha de cabeçalho (procura "Data")
    header_idx = None
    for i, row in df.iterrows():
        if any(str(x).strip().lower() == "data" for x in row.values):
            header_idx = i
            break
    # se encontrar, reatribui cabeçalho
    if header_idx is not None:
        df = df.iloc[header_idx + 1:].reset_index(drop=True)\
               .rename(columns={j: v for j, v in enumerate(df.iloc[header_idx].tolist())})
    # strip e dedup de colunas
    df.columns = [str(c).strip() for c in df.columns]
    # remove duplicatas de colunas adicionando sufixo
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
    # parse de data (se existir coluna "Data")
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    # normaliza numéricos
    for c in df.columns:
        if c != "Data":
            tmp = _normalize_numeric_series(df[c])
            # só troca se ganhou valores numéricos de verdade
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
    wb.SaveAs(novo, FileFormat=51)  # .xlsx
    wb.Close(False); xl.Quit()
    return novo

@st.cache_data(show_spinner=False)
def ler_planilha_robusta(caminho_arquivo: str) -> dict:
    p = Path(caminho_arquivo)
    # Para arquivos .xls, tenta primeiro o xlrd, depois calamine, depois Excel COM
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

def sugestao_eixos(df: pd.DataFrame):
    x = "Data" if "Data" in df.columns else (df.columns[0] if len(df.columns) else None)
    # Prioriza coluna "À vista R$" se existir
    if "À vista R$" in df.columns:
        return x, ["À vista R$"]
    ys = colunas_numericas(df)
    return x, (ys[:1] if len(ys) >= 1 else ys)


# ---------- app ----------
arquivos = listar_planilhas(PASTA_ARQUIVOS, INCLUIR_SUBPASTAS)
if not arquivos:
    st.error(f"Nenhum .xls encontrado em: {PASTA_ARQUIVOS}")
    st.stop()

# >>> LINHA ALTERADA PARA USAR O MAPEAMENTO <<<
tabs = st.tabs([mapear_nome_arquivo(a) for a in arquivos])

for idx, arq in enumerate(arquivos):
    with tabs[idx]:
        sheets = ler_planilha_robusta(arq)

        if "__ERRO__" in sheets:
            st.error(f"Falha ao ler: {Path(arq).name}")
            st.text(sheets["__ERRO__"].to_string(index=False))
            continue

        nomes_abas = list(sheets.keys())
        if not nomes_abas:
            st.warning("Arquivo sem abas legíveis."); continue

        # Usa a primeira aba automaticamente
        df = sheets[nomes_abas[0]].copy()

        if df.empty:
            st.warning("A aba selecionada está vazia."); continue


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
        
        # Layout em duas colunas: gráfico e tabela
        col_grafico, col_tabela = st.columns([2, 1])
        
        with col_grafico:
            # Usa apenas "À vista R$" se disponível
            if "À vista R$" in df.columns:
                y_col = "À vista R$"
                x_col = "Data" if "Data" in df.columns else df.columns[0]
                
                try:
                    fig = px.line(df, x=x_col, y=y_col, markers=True, title="Preço À Vista")
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
            # Mostra apenas colunas relevantes na tabela - últimos 7 dias
            cols_mostrar = ["Data", "À vista R$"] if "À vista R$" in df.columns else df.columns[:3]
            df_tab = df[cols_mostrar].copy()
            
            # Filtra os últimos 7 dias
            if "Data" in df_tab.columns and pd.api.types.is_datetime64_any_dtype(df_tab["Data"]):
                df_tab = df_tab.sort_values("Data", ascending=False).head(7)
            else:
                df_tab = df_tab.tail(6)
            
            st.dataframe(df_tab, use_container_width=True, height=400)