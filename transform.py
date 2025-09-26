import os
import time
import gc
from pathlib import Path
from win32com.client import Dispatch


def _resalvar_com_excel(path_xls: str, pasta_destino: str) -> str:
    xl = Dispatch("Excel.Application")
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(str(Path(path_xls).resolve()))

    for ws in wb.Worksheets:
        ws.Rows("1:3").Delete()  # Exclui as 3 primeiras linhas em cada planilha

    nome_arquivo = Path(path_xls).stem + ".reparado.xlsx"
    novo = Path(pasta_destino) / nome_arquivo
    novo = novo.resolve()  # Garante o caminho absoluto

    wb.SaveAs(Filename=str(novo), FileFormat=51)
    wb.Close(False)
    xl.Quit()
    del wb
    del xl
    gc.collect()
    time.sleep(1)

    return str(novo)


def salvar_todos_arquivos(origem, destino):
    origem = Path(origem)
    destino = Path(destino)
    destino.mkdir(exist_ok=True)
    arquivos = list(origem.glob("*.xls"))
    for arquivo in arquivos:
        try:
            novo_arquivo = _resalvar_com_excel(str(arquivo), str(destino))
            print(f"Arquivo {arquivo.name} reparado salvo em: {novo_arquivo}")
        except Exception as e:
            print(f"Erro ao processar {arquivo.name}: {e}")

# Exemplo de uso:
pasta_origem = r"data/raw"
pasta_destino = r"data/processed"
salvar_todos_arquivos(pasta_origem, pasta_destino)
