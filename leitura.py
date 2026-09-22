"""Leitura dos arquivos enviados. Não calcula carreira."""

from __future__ import annotations

import io
import re
import unicodedata

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

COLUNAS_OBRIGATORIAS = [
    "SERVIDOR",
    "MATRICULA",
    "SITUACAO",
    "CARGO EMPREGO",
    "CARGO CLASSE",
    "NIVEL PADRAO",
    "SETOR EXERCICIO",
]

COLUNAS_DATA = [
    "DATA POSSE NO CARGO",
    "DATA ULTIMA PROGRESSAO",
    "DATA DE NASCIMENTO",
    "CARGO EMPREGO DATA SAIDA",
]


class ErroEntrada(Exception):
    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


def ler_tabela(conteudo: bytes, nome_arquivo: str) -> pd.DataFrame:
    nome = (nome_arquivo or "").lower()
    if nome.endswith(".xlsx"):
        try:
            tabela = pd.read_excel(io.BytesIO(conteudo))
        except Exception as exc:
            raise ErroEntrada("Não consegui ler o arquivo.") from exc
    elif nome.endswith(".csv"):
        tabela = _ler_csv(conteudo)
    else:
        raise ErroEntrada("Envie um arquivo CSV ou XLSX.")
    return _ajustar_cabecalho(tabela)


def preparar_servidores(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    out.columns = [str(coluna).strip() for coluna in out.columns]
    faltando = [coluna for coluna in COLUNAS_OBRIGATORIAS if coluna not in out.columns]
    if faltando:
        raise ErroEntrada("Faltam colunas obrigatórias: " + ", ".join(faltando) + ".")

    if "SERVIDOR" in out.columns:
        out["SERVIDOR"] = out["SERVIDOR"].astype(str).str.strip()
    for coluna in COLUNAS_DATA:
        if coluna in out.columns and not is_datetime64_any_dtype(out[coluna]):
            out[coluna] = _converter_datas(out[coluna])
    out["MATRICULA_NORMALIZADA"] = out["MATRICULA"].map(_matricula_servidor)
    antes = len(out)
    out = out.drop_duplicates(subset=["MATRICULA_NORMALIZADA"], keep="last")
    avisos = []
    descartadas = antes - len(out)
    if descartadas:
        avisos.append(
            f"{descartadas} matrícula(s) repetida(s) ficaram com a última linha."
        )
    return out, avisos


def preparar_afastamentos(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        raise ErroEntrada("Envie o arquivo de afastamentos.")
    out = df.copy()
    out.columns = [str(coluna).strip().upper() for coluna in out.columns]
    if not any(coluna in out.columns for coluna in ("VÍNCULO SERVIDOR", "VINCULO SERVIDOR", "MATRICULA")):
        raise ErroEntrada("O arquivo de afastamentos não tem coluna de matrícula.")
    if _coluna(out, ["DIA INICIO AFASTAMENTO", "DATA INÍCIO", "DATA INICIO"]) is None:
        raise ErroEntrada("O arquivo de afastamentos não tem as datas de início e fim.")
    if _coluna(out, ["DIA FIM AFASTAMENTO", "DATA FIM"]) is None:
        raise ErroEntrada("O arquivo de afastamentos não tem as datas de início e fim.")
    return out


def _ajustar_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    if _linha_e_cabecalho(df.columns):
        return df
    limite = min(20, len(df))
    for indice in range(limite):
        if not _linha_e_cabecalho(df.iloc[indice].tolist()):
            continue
        novo = df.iloc[indice + 1 :].copy()
        novo.columns = ["" if pd.isna(valor) else str(valor).strip() for valor in df.iloc[indice].tolist()]
        return novo.reset_index(drop=True)
    return df


def _linha_e_cabecalho(valores) -> bool:
    rotulos = {_rotulo(valor) for valor in valores}
    rotulos.discard("")
    if "VINCULO SERVIDOR" in rotulos:
        return True
    if {"SERVIDOR", "MATRICULA", "CARGO CLASSE"} <= rotulos:
        return True
    return "MATRICULA" in rotulos and "DIA INICIO AFASTAMENTO" in rotulos


def _rotulo(valor) -> str:
    texto = unicodedata.normalize("NFD", str(valor or ""))
    texto = "".join(caractere for caractere in texto if unicodedata.category(caractere) != "Mn")
    return re.sub(r"\s+", " ", texto).strip().upper()


def _ler_csv(conteudo: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = conteudo.decode(encoding)
        except UnicodeDecodeError:
            continue
        amostra = texto[:4000]
        separador = ";" if amostra.count(";") >= amostra.count(",") else ","
        try:
            return pd.read_csv(io.StringIO(texto), sep=separador)
        except Exception:
            continue
    raise ErroEntrada("Não consegui ler o arquivo.")


def _matricula_servidor(valor) -> str:
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def _converter_datas(serie: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(serie, errors="coerce", dayfirst=True, format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(serie, errors="coerce", dayfirst=True)


def _coluna(df: pd.DataFrame, opcoes: list[str]) -> str | None:
    for opcao in opcoes:
        if opcao in df.columns:
            return opcao
    return None
