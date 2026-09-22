"""Monta a lista do mês a partir das tabelas já lidas."""

from __future__ import annotations

import io
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from openpyxl.styles import Alignment

from carreira import avaliar

SITUACOES_CHEFIA = ("ATIVO PERMANENTE - 01", "COLAB PCCTAE E MAGIS - 41")
SITUACAO_SUBSTITUTO = "CONT.PROF.SUBSTITUTO - 52"
SITUACOES_EXCLUIDAS_PARES = {
    "APOSENTADO - 02",
    "CONT.PROF.SUBSTITUTO - 52",
    "CONT.PROF.TEMPORARIO - 54",
    "INSTITUIDOR PENSAO - 15",
    "ESTAGIARIO - 66",
    "CONTR.PROF.VISITANTE - 53",
}
ORDEM_GRUPO = {"No mês": 0, "Não calculado": 1}


@dataclass(frozen=True)
class Registro:
    grupo: str
    servidor: str
    siape: str
    situacao: str
    cargo: str
    intersticio: str
    posicao_atual: str
    proximo: str
    carreira: str
    efeitos_financeiros: str
    data_efeito: str
    observacao: str
    setor: str
    chefias: str
    pares: str
    funcao_cd: str
    senha: str
    afastamentos_periodo: str
    outros_afastamentos: str
    motivo: str


def gerar_relatorio(df_servidores: pd.DataFrame, df_afastamentos: pd.DataFrame, mes: int, ano: int) -> list[Registro]:
    df = _normalizar_servidores(df_servidores)
    df["_JA_SAIU"] = [_ja_saiu(row, mes, ano) for _, row in df.iterrows()]
    indice_setores = _indice_setores(df.loc[~df["_JA_SAIU"]].copy())
    indice_afast = _indice_afastamentos(df_afastamentos)
    registros = []

    for _, row in df.iterrows():
        if row["_JA_SAIU"]:
            continue

        resultado = avaliar(
            classe=row.get("CARGO CLASSE", ""),
            padrao=row.get("NIVEL PADRAO", ""),
            cargo=row.get("CARGO EMPREGO", ""),
            titulacao=row.get("TITULACAO", ""),
            data_ultima_progressao=_data(row.get("DATA ULTIMA PROGRESSAO")),
            data_posse=_data(row.get("DATA POSSE NO CARGO")),
            mes=mes,
            ano=ano,
        )
        if resultado.grupo == "Fora":
            continue

        matricula = _chave_matricula(row.get("MATRICULA_NORMALIZADA", row.get("MATRICULA", "")))
        afast_periodo, afast_outros = _afastamentos_da_pessoa(
            matricula,
            resultado.intersticio_inicio,
            resultado.intersticio_fim,
            resultado.paragrafo_7,
            indice_afast,
        )
        chefias, pares = _chefia_e_pares(row.get("SETOR EXERCICIO"), indice_setores, row.get("SERVIDOR"))
        proximo = resultado.proximo or ""
        registros.append(
            Registro(
                grupo=resultado.grupo,
                servidor=str(row.get("SERVIDOR", "")).strip().upper(),
                siape=_siape(row.get("MATRICULA")),
                situacao=str(row.get("SITUACAO", "") or "").strip(),
                cargo=str(row.get("CARGO EMPREGO", "") or ""),
                intersticio=_texto_intersticio(resultado),
                posicao_atual=resultado.posicao_atual,
                proximo=proximo,
                carreira=f"{resultado.posicao_atual} → {proximo}" if proximo else resultado.posicao_atual,
                efeitos_financeiros=resultado.efeitos_financeiros,
                data_efeito=_fmt(resultado.data_devida) if resultado.efeitos_financeiros == "Sim" else "",
                observacao=resultado.observacao,
                setor=str(row.get("SETOR EXERCICIO", "") or "N/A"),
                chefias=chefias,
                pares=pares,
                funcao_cd=_funcao_cd(row.get("FUNCAO DISPLAY")),
                senha=_senha(row.get("CPF")),
                afastamentos_periodo=afast_periodo,
                outros_afastamentos=afast_outros,
                motivo=resultado.motivo,
            )
        )

    registros.sort(key=lambda item: (ORDEM_GRUPO.get(item.grupo, 9), item.setor, item.servidor))
    return registros


def para_excel(registros: list[Registro]) -> bytes:
    colunas = [
        "grupo",
        "servidor",
        "siape",
        "situacao",
        "cargo",
        "intersticio",
        "pos_atual",
        "pos_nova",
        "efeitos_financeiros",
        "data_efeito",
        "observacao",
        "setor",
        "chefias",
        "pares",
        "exerce_cd",
        "senha",
        "afastamentos_periodo",
        "outros_afastamentos",
        "motivo",
    ]
    linhas = [
        {
            "grupo": item.grupo,
            "servidor": item.servidor,
            "siape": item.siape,
            "situacao": item.situacao,
            "cargo": item.cargo,
            "intersticio": item.intersticio,
            "pos_atual": item.posicao_atual,
            "pos_nova": item.proximo,
            "efeitos_financeiros": item.efeitos_financeiros,
            "data_efeito": item.data_efeito,
            "observacao": item.observacao,
            "setor": item.setor,
            "chefias": item.chefias,
            "pares": item.pares,
            "exerce_cd": item.funcao_cd,
            "senha": item.senha,
            "afastamentos_periodo": item.afastamentos_periodo,
            "outros_afastamentos": item.outros_afastamentos,
            "motivo": item.motivo,
        }
        for item in registros
    ]
    buffer = io.BytesIO()
    frame = pd.DataFrame(linhas, columns=colunas)
    with pd.ExcelWriter(buffer, engine="openpyxl") as escritor:
        frame.to_excel(escritor, index=False)
        planilha = escritor.book.active
        quebra = Alignment(wrap_text=True, vertical="top")
        colunas_quebra = {
            celula.column
            for celula in planilha[1]
            if celula.value in {"afastamentos_periodo", "outros_afastamentos"}
        }
        for linha in planilha.iter_rows(min_row=2):
            linhas_texto = 1
            for celula in linha:
                if celula.column not in colunas_quebra or not isinstance(celula.value, str):
                    continue
                celula.alignment = quebra
                linhas_texto = max(linhas_texto, celula.value.count("\n") + 1)
            planilha.row_dimensions[linha[0].row].height = 15 * linhas_texto
    return buffer.getvalue()


_OCORRENCIA = re.compile(r"(INCLUSAO|EXCLUSAO): .*? - (\d{2}/\d{2}/\d{4})")


def _ja_saiu(row, mes: int, ano: int) -> bool:
    if not _situacao_ativa(row.get("SITUACAO", "")):
        return True
    limite = _fim_do_mes(mes, ano)
    saida = _data(row.get("CARGO EMPREGO DATA SAIDA"))
    if saida is not None and saida <= limite:
        return True
    exclusao = _ultima_exclusao(row.get("OCORRENCIAS DISPLAY"))
    return exclusao is not None and exclusao <= limite


def _ultima_exclusao(texto) -> date | None:
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None
    inclusoes: list[date] = []
    exclusoes: list[date] = []
    for tipo, bruto in _OCORRENCIA.findall(str(texto)):
        data = _data(bruto)
        if data is None:
            continue
        if tipo == "EXCLUSAO":
            exclusoes.append(data)
        else:
            inclusoes.append(data)
    if not exclusoes:
        return None
    ultima = max(exclusoes)
    if any(inclusao > ultima for inclusao in inclusoes):
        return None
    return ultima


def _situacao_ativa(situacao) -> bool:
    texto = _sem_acento(str(situacao)).upper()
    if "ATIVO PERMANENTE" in texto:
        return True
    return "COLAB" in texto and ("PCCTAE" in texto or "MAGIS" in texto or "41" in texto)


def _fim_do_mes(mes: int, ano: int) -> date:
    if mes == 12:
        return date(ano, 12, 31)
    return date(ano, mes + 1, 1) - timedelta(days=1)


def _sem_acento(texto: str) -> str:
    return "".join(
        caractere for caractere in unicodedata.normalize("NFD", texto) if unicodedata.category(caractere) != "Mn"
    )


def _normalizar_servidores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(coluna).strip() for coluna in out.columns]
    if "MATRICULA" in out.columns and "MATRICULA_NORMALIZADA" not in out.columns:
        out["MATRICULA_NORMALIZADA"] = out["MATRICULA"].map(_matricula)
    if "SETOR EXERCICIO" in out.columns:
        out["SETOR_NORM"] = out["SETOR EXERCICIO"].astype(str).str.strip().str.upper()
    else:
        out["SETOR_NORM"] = ""
    return out


def _indice_setores(df: pd.DataFrame) -> dict:
    indice = {}
    for setor, grupo in df.groupby("SETOR_NORM", dropna=False):
        if not setor or str(setor).upper() in {"NAN", "NONE"}:
            continue
        indice[str(setor)] = grupo.copy()
    return indice


def _chefia_e_pares(setor, indice, servidor_atual) -> tuple[str, str]:
    if setor is None or str(setor).strip() == "" or str(setor).lower() == "nan":
        return "N/A", "Nenhum"
    df_setor = indice.get(str(setor).strip().upper())
    if df_setor is None or df_setor.empty:
        return "N/A", "Nenhum"

    funcao = df_setor["FUNCAO DISPLAY"] if "FUNCAO DISPLAY" in df_setor.columns else pd.Series("", index=df_setor.index)
    valida = funcao.astype(str).str.upper().str.startswith(("FG", "CD"), na=False)
    situacao = (
        df_setor["SITUACAO"] if "SITUACAO" in df_setor.columns else pd.Series("", index=df_setor.index)
    ).astype(str).str.strip().str.upper()

    chefes = df_setor[valida & situacao.isin(SITUACOES_CHEFIA)]
    substitutos = df_setor[valida & (situacao == SITUACAO_SUBSTITUTO)]
    nomes_chefes = sorted({
        f"{str(linha['SERVIDOR']).strip().upper()} ({_formatar_funcao(linha.get('FUNCAO DISPLAY'))})"
        for _, linha in chefes.iterrows()
    })
    nomes_substitutos = sorted({
        f"{str(linha['SERVIDOR']).strip().upper()} ({_formatar_funcao(linha.get('FUNCAO DISPLAY'))})"
        for _, linha in substitutos.iterrows()
    })
    partes = []
    if nomes_chefes:
        partes.append(", ".join(nomes_chefes))
    if nomes_substitutos:
        partes.append("Substitutos: " + ", ".join(nomes_substitutos))
    chefia = "; ".join(partes) if partes else "N/A"

    pares = df_setor[(~valida) & (~situacao.isin(SITUACOES_EXCLUIDAS_PARES))]
    if servidor_atual is not None:
        pares = pares[pares["SERVIDOR"].astype(str).str.upper() != str(servidor_atual).upper()]
    nomes = sorted(pares["SERVIDOR"].dropna().astype(str).str.strip().str.upper().unique().tolist())
    return chefia, ", ".join(nomes) if nomes else "Nenhum"


def _funcao_cd(funcao) -> str:
    """Sim se a pessoa ocupa CD na data do arquivo. Não há histórico no período."""
    if funcao is None or (isinstance(funcao, float) and pd.isna(funcao)):
        return "Não"
    bruto = str(funcao).split(" - ")[0].strip().upper()
    if bruto in {"", "-", "NAN", "NONE"} or not bruto.startswith("CD"):
        return "Não"
    return "Sim"


def _formatar_funcao(funcao) -> str:
    if funcao is None or (isinstance(funcao, float) and pd.isna(funcao)):
        return ""
    trecho = str(funcao).split(" - ")[0].strip().upper()
    encontrado = re.match(r"([A-Z]+)(\d+)", trecho)
    if encontrado:
        return f"{encontrado.group(1)}-{int(encontrado.group(2))}"
    return trecho


def _indice_afastamentos(df: pd.DataFrame) -> dict:
    indice = defaultdict(list)
    if df is None or df.empty:
        return indice
    tabela = df.copy()
    tabela.columns = [str(coluna).strip().upper() for coluna in tabela.columns]
    coluna_matricula = "VÍNCULO SERVIDOR" if "VÍNCULO SERVIDOR" in tabela.columns else None
    if coluna_matricula is None and "VINCULO SERVIDOR" in tabela.columns:
        coluna_matricula = "VINCULO SERVIDOR"
    coluna_tipo = _primeira(tabela, ["COD AFASTAMENTO", "OCORRÊNCIA", "OCORRENCIA"])
    coluna_inicio = _primeira(tabela, ["DIA INICIO AFASTAMENTO", "DATA INÍCIO", "DATA INICIO"])
    coluna_fim = _primeira(tabela, ["DIA FIM AFASTAMENTO", "DATA FIM"])
    if coluna_inicio is None or coluna_fim is None:
        return indice

    for _, linha in tabela.iterrows():
        if coluna_matricula:
            matricula = _chave_matricula(_matricula_afastamento(linha.get(coluna_matricula)))
        else:
            matricula = _chave_matricula(linha.get("MATRICULA", ""))
        if not matricula:
            continue
        indice[matricula].append({
            "tipo": str(linha.get(coluna_tipo) if coluna_tipo else "Ocorrência").strip() or "Ocorrência",
            "inicio": _data(linha.get(coluna_inicio)),
            "fim": _data(linha.get(coluna_fim)),
        })
    return indice


def _afastamentos_da_pessoa(matricula, inicio, fim, paragrafo_7, indice) -> tuple[str, str]:
    itens = indice.get(str(matricula).strip(), [])
    if not itens:
        if paragrafo_7:
            return "Nenhum", "Não se separam neste caso"
        return "Nenhum", "Nenhum"

    if paragrafo_7:
        textos = [
            f"{item['tipo']} ({_fmt(item['inicio'])} a {_fmt(item['fim'])})"
            for item in itens
            if item["inicio"] and item["fim"]
        ]
        return ("\n".join(textos) if textos else "Nenhum"), "Não se separam neste caso"

    no_periodo, outros = [], []
    for item in itens:
        if item["inicio"] is None or item["fim"] is None or inicio is None or fim is None:
            continue
        dias = (min(fim, item["fim"]) - max(inicio, item["inicio"])).days + 1
        texto = f"{item['tipo']} ({_fmt(item['inicio'])} a {_fmt(item['fim'])}"
        if dias > 0:
            no_periodo.append(f"{texto} | {dias} dias no interstício)")
        else:
            outros.append(f"{texto})")
    return (
        "\n".join(no_periodo) if no_periodo else "Nenhum",
        "\n".join(outros) if outros else "Nenhum",
    )


def _texto_intersticio(resultado) -> str:
    if resultado.paragrafo_7:
        return "Considerado cumprido em 01/01/2025 (art. 14, § 7º)."
    if resultado.intersticio_inicio and resultado.intersticio_fim:
        return f"{_fmt(resultado.intersticio_inicio)} a {_fmt(resultado.intersticio_fim)}"
    return ""


def _senha(cpf) -> str:
    if cpf is None or (isinstance(cpf, float) and pd.isna(cpf)):
        return "000"
    digitos = re.sub(r"\D", "", str(cpf))
    return digitos[:3] or "000"


def _siape(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    texto = str(valor).strip()
    return texto[:-2] if texto.endswith(".0") else texto


def _matricula(valor) -> str:
    return _siape(valor)


def _matricula_afastamento(valor) -> str:
    texto = _siape(valor)
    if "-" in texto:
        return texto.split("-")[-1].strip()
    return texto


def _chave_matricula(valor) -> str:
    texto = _matricula_afastamento(valor)
    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return texto
    return digitos.lstrip("0") or "0"


def _data(valor) -> date | None:
    if _vazio(valor):
        return None
    if isinstance(valor, datetime):
        try:
            valor = valor.date()
        except (ValueError, OSError):
            return None
    if isinstance(valor, date):
        mes = getattr(valor, "month", None)
        dia = getattr(valor, "day", None)
        if type(mes) is not int or type(dia) is not int or not 1 <= mes <= 12:
            return None
        return valor
    texto = str(valor).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", texto):
        convertido = pd.to_datetime(texto, errors="coerce", dayfirst=False)
    else:
        convertido = pd.to_datetime(valor, errors="coerce", dayfirst=True)
    if _vazio(convertido):
        return None
    return convertido.date()


def _vazio(valor) -> bool:
    if valor is None:
        return True
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def _fmt(valor: date | None) -> str:
    if valor is None:
        return ""
    return valor.strftime("%d/%m/%Y")


def _primeira(df: pd.DataFrame, opcoes: list[str]) -> str | None:
    for opcao in opcoes:
        if opcao in df.columns:
            return opcao
    return None
