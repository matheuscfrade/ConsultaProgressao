"""Regra de próximo nível. Não lê arquivo e não sabe o que é o relatório do mês."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

PCCTAE_PADRAO_MAX = 19
CORTE_PARAGRAFO_7 = date(2021, 12, 31)
DATA_PARAGRAFO_7 = date(2025, 1, 1)


@dataclass(frozen=True)
class ResultadoCarreira:
    grupo: str
    posicao_atual: str
    proximo: str | None
    data_devida: date | None
    efeitos_financeiros: str
    observacao: str
    motivo: str
    intersticio_inicio: date | None = None
    intersticio_fim: date | None = None
    paragrafo_7: bool = False


@dataclass(frozen=True)
class _Leitura:
    reconhecido: bool
    malha_antiga: bool
    rotulo_antigo: str | None
    nivel_antigo: int | None
    classe: str
    nivel: int | None
    no_topo: bool
    aviso: str
    bruto: str


def avaliar(
    classe,
    padrao,
    cargo,
    titulacao,
    data_ultima_progressao,
    data_posse,
    mes: int,
    ano: int,
) -> ResultadoCarreira:
    if _eh_professor(cargo):
        return _avaliar_ebtt(
            classe, padrao, titulacao, data_ultima_progressao, data_posse, mes, ano
        )
    return _avaliar_pcctae(classe, padrao, data_ultima_progressao, data_posse, mes, ano)


def _eh_professor(cargo) -> bool:
    return "PROFESSOR" in str(cargo or "").upper()


def _avaliar_ebtt(classe, padrao, titulacao, ultima, posse, mes, ano) -> ResultadoCarreira:
    leitura = _ler_ebtt(classe, padrao)
    if not leitura.reconhecido:
        return _nao_calculado(leitura.bruto, leitura.aviso or "Classe não reconhecida.")

    atual, proximo = _exibir_ebtt(leitura)
    if leitura.classe == "A":
        data_posse = _como_data(posse)
        if data_posse is None:
            return _nao_calculado(
                atual,
                "Sem data de posse para calcular a passagem da Classe A para a B.",
                aviso=leitura.aviso,
            )
        if data_posse <= CORTE_PARAGRAFO_7:
            return _fechar(
                leitura=leitura,
                atual=atual,
                proximo=proximo,
                data_devida=DATA_PARAGRAFO_7,
                mes=mes,
                ano=ano,
                ancora=data_posse,
                ciclo=None,
                paragrafo_7=True,
                promocao_titular=False,
                titulacao=titulacao,
            )
        return _fechar(
            leitura=leitura,
            atual=atual,
            proximo=proximo,
            data_devida=_somar_meses(data_posse, 36),
            mes=mes,
            ano=ano,
            ancora=data_posse,
            ciclo=36,
            paragrafo_7=False,
            promocao_titular=False,
            titulacao=titulacao,
        )

    ancora = _como_data(ultima) or _como_data(posse)
    if ancora is None:
        return _nao_calculado(atual, "Sem data de última progressão e sem data de posse.", aviso=leitura.aviso)

    return _fechar(
        leitura=leitura,
        atual=atual,
        proximo=proximo,
        data_devida=_somar_meses(ancora, 24),
        mes=mes,
        ano=ano,
        ancora=ancora,
        ciclo=24,
        paragrafo_7=False,
        promocao_titular=proximo == "Titular" and not leitura.no_topo,
        titulacao=titulacao,
    )


def _avaliar_pcctae(classe, padrao, ultima, posse, mes, ano) -> ResultadoCarreira:
    leitura = _ler_pcctae(classe, padrao)
    if not leitura.reconhecido:
        return _nao_calculado(leitura.bruto, leitura.aviso or "Classe ou padrão não reconhecido.")

    atual = f"{leitura.classe}-{leitura.nivel}"
    proximo = f"{leitura.classe}-{PCCTAE_PADRAO_MAX if leitura.no_topo else leitura.nivel + 1}"
    ancora = _como_data(ultima) or _como_data(posse)
    if ancora is None:
        return _nao_calculado(atual, "Sem data de última progressão e sem data de posse.")

    return _fechar(
        leitura=leitura,
        atual=atual,
        proximo=proximo,
        data_devida=_somar_meses(ancora, 12),
        mes=mes,
        ano=ano,
        ancora=ancora,
        ciclo=12,
        paragrafo_7=False,
        promocao_titular=False,
        titulacao="",
    )


def _fechar(
    leitura: _Leitura,
    atual: str,
    proximo: str,
    data_devida: date,
    mes: int,
    ano: int,
    ancora: date,
    ciclo: int | None,
    paragrafo_7: bool,
    promocao_titular: bool,
    titulacao,
) -> ResultadoCarreira:
    if paragrafo_7:
        grupo = "No mês" if data_devida.month == mes and data_devida.year == ano else "Fora"
    elif _eh_aniversario(ancora, mes, ano, ciclo or 24):
        grupo = "No mês"
    else:
        grupo = "Fora"

    inicio, fim = _janela(data_devida, mes, ano, ancora, ciclo, paragrafo_7, leitura.no_topo, grupo)
    observacao = _observacao(
        grupo, data_devida, leitura, paragrafo_7, ancora, promocao_titular, titulacao, proximo
    )
    if leitura.no_topo or promocao_titular:
        efeitos = "Não"
    else:
        efeitos = "Sim"

    return ResultadoCarreira(
        grupo=grupo,
        posicao_atual=atual,
        proximo=proximo,
        data_devida=data_devida if not leitura.no_topo else (_aniversario_no_ano(ancora, ano) if grupo == "No mês" else data_devida),
        efeitos_financeiros=efeitos,
        observacao=observacao,
        motivo="",
        intersticio_inicio=inicio,
        intersticio_fim=fim,
        paragrafo_7=paragrafo_7,
    )


def _eh_aniversario(ancora: date, mes: int, ano: int, ciclo: int) -> bool:
    if ancora.month != mes:
        return False
    meses = (ano - ancora.year) * 12
    return meses >= ciclo and meses % ciclo == 0


def _janela(data_devida, mes, ano, ancora, ciclo, paragrafo_7, no_topo, grupo):
    if paragrafo_7 or ciclo is None:
        return None, None
    if no_topo:
        if grupo != "No mês":
            return None, None
        fim_ciclo = _aniversario_no_ano(ancora, ano)
        return _somar_meses(fim_ciclo, -ciclo), fim_ciclo - timedelta(days=1)
    return _somar_meses(data_devida, -ciclo), data_devida - timedelta(days=1)


def _observacao(grupo, data_devida, leitura, paragrafo_7, ancora, promocao_titular, titulacao, proximo) -> str:
    partes: list[str] = []
    if paragrafo_7:
        partes.append(
            "Interstício para a Classe B considerado cumprido em 01/01/2025 (art. 14, § 7º). "
            f"Estágio probatório presumido pela posse em {_fmt(ancora)}."
        )
    if leitura.aviso:
        partes.append(leitura.aviso)
    if leitura.no_topo:
        partes.append("Somente avaliação de desempenho. Sem efeitos financeiros — final de carreira.")
    elif promocao_titular:
        faltas = []
        if not _tem_doutorado(titulacao):
            faltas.append("o título de doutor")
        faltas.append("aprovação de memorial ou defesa de tese inédita")
        partes.append("Promoção a Titular sem efeitos financeiros neste relatório. Falta " + " e ".join(faltas) + ".")
    elif proximo:
        partes.append(_frase_movimento(leitura, proximo))
    return " ".join(partes)


def _frase_movimento(leitura: _Leitura, proximo: str) -> str:
    promocao = leitura.classe == "A" or not proximo.startswith(f"{leitura.classe}-")
    nome = "Promoção" if promocao else "Progressão"
    return f"{nome} com efeitos financeiros quando a avaliação de desempenho for aprovada."


def _exibir_ebtt(leitura: _Leitura) -> tuple[str, str]:
    if leitura.no_topo:
        return "Titular", "Titular"
    if leitura.malha_antiga:
        if leitura.classe == "A":
            canonico = "A-1"
        else:
            canonico = f"{leitura.classe}-{leitura.nivel}"
        atual = f"{leitura.rotulo_antigo}-{leitura.nivel_antigo} (equivale a {canonico})"
    else:
        atual = f"{leitura.classe}-{leitura.nivel}"
    return atual, _proximo_ebtt(leitura)


def _proximo_ebtt(leitura: _Leitura) -> str:
    if leitura.classe == "A":
        return "B-1"
    if leitura.classe == "B":
        return {1: "B-2", 2: "B-3", 3: "B-4", 4: "C-1"}[leitura.nivel]
    return {1: "C-2", 2: "C-3", 3: "C-4", 4: "Titular"}[leitura.nivel]


def _ler_ebtt(classe, padrao) -> _Leitura:
    texto = _normalizar_classe(classe)
    bruto = texto or _bruto(classe)
    vazio = _Leitura(False, False, None, None, "", None, False, "", bruto)

    if "TITULAR" in texto or texto in {"T", "DV", "D V"}:
        return _Leitura(True, False, None, None, "TITULAR", None, True, "", bruto)

    antiga = _malha_antiga(texto)
    if antiga is not None:
        rotulo, classe_nova = antiga
        if classe_nova == "A":
            nivel = _extrair_nivel(padrao, 2)
            if nivel is None:
                return vazio
            return _Leitura(True, True, rotulo, nivel, "A", 1, False, "", bruto)
        nivel = _extrair_nivel(padrao, 4)
        if nivel is None:
            return vazio
        return _Leitura(True, True, rotulo, nivel, classe_nova, nivel, False, "", bruto)

    if texto in {"A", "B", "C"}:
        if texto == "A":
            nivel = _extrair_nivel(padrao, 4)
            if nivel is None:
                return vazio
            aviso = ""
            if nivel != 1:
                aviso = "O nível informado foi ajustado para A-1, único nível da Classe A."
            return _Leitura(True, False, None, None, "A", 1, False, aviso, bruto)
        nivel = _extrair_nivel(padrao, 4)
        if nivel is None:
            return vazio
        return _Leitura(True, False, None, None, texto, nivel, False, "", bruto)

    if texto == "D":
        return _Leitura(
            True,
            False,
            None,
            None,
            "TITULAR",
            None,
            True,
            "A planilha trouxe apenas a classe D, sem algarismo. Tratei como Titular. Confira.",
            bruto,
        )
    return vazio


def _malha_antiga(texto: str) -> tuple[str, str] | None:
    if "DIV" in texto or "D IV" in texto:
        return "DIV", "C"
    if "DIII" in texto or "D III" in texto:
        return "DIII", "B"
    if "DII" in texto or "D II" in texto:
        return "DII", "A"
    if "DI" in texto or "D I" in texto:
        return "DI", "A"
    return None


def _ler_pcctae(classe, padrao) -> _Leitura:
    texto = _normalizar_classe(classe)
    bruto = texto or _bruto(classe)
    partes = [p for p in texto.split() if p]
    codigo = partes[-1] if partes else ""
    nivel = _extrair_nivel(padrao, PCCTAE_PADRAO_MAX)
    if not re.fullmatch(r"[A-E]", codigo) or nivel is None:
        aviso = "Nível não reconhecido." if codigo else "Classe não reconhecida."
        if codigo and nivel is None:
            aviso = "Nível não reconhecido."
        elif not re.fullmatch(r"[A-E]", codigo or ""):
            aviso = "Classe não reconhecida."
        return _Leitura(False, False, None, None, codigo, nivel, False, aviso, bruto)
    return _Leitura(True, False, None, None, codigo, nivel, nivel >= PCCTAE_PADRAO_MAX, "", bruto)


def _nao_calculado(posicao: str, motivo: str, aviso: str = "") -> ResultadoCarreira:
    observacao = " ".join(p for p in (aviso, motivo) if p)
    return ResultadoCarreira(
        grupo="Não calculado",
        posicao_atual=posicao,
        proximo=None,
        data_devida=None,
        efeitos_financeiros="",
        observacao=observacao,
        motivo=motivo,
    )


def _normalizar_classe(classe) -> str:
    if classe is None:
        return ""
    texto = str(classe).strip().upper()
    if texto in {"", "NAN", "NONE", "NAT"}:
        return ""
    texto = texto.replace("CLASSE", " ").replace("-", " ")
    return re.sub(r"\s+", " ", texto).strip()


def _bruto(classe) -> str:
    if classe is None:
        return ""
    return str(classe).strip()


def _extrair_nivel(valor, maximo: int) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, float):
        if valor != valor:
            return None
        if valor.is_integer():
            valor = int(valor)
    texto = str(valor).strip()
    if texto.upper() in {"", "NAN", "NONE", "NAT"}:
        return None
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".", 1)[0]
    digitos = "".join(ch for ch in texto if ch.isdigit())
    if not digitos:
        return None
    candidatos = [int(digitos)]
    if len(digitos) >= 2:
        candidatos.append(int(digitos[-2:]))
    candidatos.append(int(digitos[-1]))
    for candidato in candidatos:
        if 1 <= candidato <= maximo:
            return candidato
    return None


def _tem_doutorado(titulacao) -> bool:
    texto = str(titulacao or "").strip().upper()
    if texto in {"", "NAN", "NONE"}:
        return False
    return any(chave in texto for chave in ("DOUTORADO", "DOUTOR", "DR.", "DR ", "PHD", "PH.D", "PH. D"))


def _como_data(valor) -> date | None:
    if valor is None:
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
    return None


def _somar_meses(base: date, meses: int) -> date:
    return base + relativedelta(months=meses)


def _aniversario_no_ano(ancora: date, ano: int) -> date:
    try:
        return date(ano, ancora.month, ancora.day)
    except ValueError:
        return date(ano, ancora.month, 28)


def _fmt(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")
