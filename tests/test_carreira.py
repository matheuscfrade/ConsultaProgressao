from datetime import date

import pytest

from carreira import avaliar


def ebtt(**kwargs):
    dados = {
        "classe": "B",
        "padrao": "2",
        "cargo": "PROFESSOR ENSINO BASICO TECNICO E TECNOLOGICO",
        "titulacao": "MESTRADO",
        "data_ultima_progressao": date(2024, 11, 15),
        "data_posse": date(2010, 3, 1),
        "mes": 11,
        "ano": 2026,
    }
    dados.update(kwargs)
    return avaliar(**dados)


def test_di_e_dii_viram_a1_e_proximo_e_b1():
    for classe, nivel in (("DI", 1), ("DI", 2), ("DII", 1), ("DII", 2)):
        resultado = ebtt(
            classe=classe,
            padrao=nivel,
            data_posse=date(2018, 3, 15),
            data_ultima_progressao=date(2023, 3, 15),
            mes=1,
            ano=2025,
        )
        assert resultado.posicao_atual == f"{classe}-{nivel} (equivale a A-1)"
        assert resultado.proximo == "B-1"


def test_diii_nao_e_lido_como_di():
    resultado = ebtt(classe="D III", padrao=2, mes=11, ano=2026)
    assert resultado.posicao_atual == "DIII-2 (equivale a B-2)"
    assert resultado.proximo == "B-3"
    assert "A-1" not in resultado.posicao_atual


@pytest.mark.parametrize(
    ("classe", "nivel", "exibicao", "proximo"),
    [
        ("DIII", 1, "DIII-1 (equivale a B-1)", "B-2"),
        ("DIII", 3, "DIII-3 (equivale a B-3)", "B-4"),
        ("DIII", 4, "DIII-4 (equivale a B-4)", "C-1"),
        ("DIV", 1, "DIV-1 (equivale a C-1)", "C-2"),
        ("DIV", 3, "DIV-3 (equivale a C-3)", "C-4"),
        ("DIV", 4, "DIV-4 (equivale a C-4)", "Titular"),
        ("B", 1, "B-1", "B-2"),
        ("B", 3, "B-3", "B-4"),
        ("B", 4, "B-4", "C-1"),
        ("C", 1, "C-1", "C-2"),
        ("C", 3, "C-3", "C-4"),
    ],
)
def test_tabela_de_conversao(classe, nivel, exibicao, proximo):
    resultado = ebtt(classe=classe, padrao=nivel)
    assert resultado.posicao_atual == exibicao
    assert resultado.proximo == proximo


def test_a_com_nivel_2_ajusta_para_a1():
    resultado = ebtt(
        classe="A",
        padrao=2,
        data_posse=date(2024, 6, 1),
        data_ultima_progressao=None,
        mes=6,
        ano=2027,
    )
    assert resultado.posicao_atual == "A-1"
    assert resultado.proximo == "B-1"
    assert "ajustado" in resultado.observacao.lower()


def test_d_sozinho_vira_titular_com_aviso():
    resultado = ebtt(classe="D", padrao=1, data_ultima_progressao=date(2024, 11, 15))
    assert resultado.posicao_atual == "Titular"
    assert resultado.proximo == "Titular"
    assert "confira" in resultado.observacao.lower()


def test_classe_ilegivel_nao_inventa_proximo_nivel():
    resultado = ebtt(classe="XYZ", padrao=1)
    assert resultado.grupo == "Não calculado"
    assert resultado.proximo is None


def test_paragrafo_7_entra_somente_em_janeiro_de_2025():
    resultado = ebtt(
        classe="DI",
        padrao=2,
        data_posse=date(2021, 12, 31),
        data_ultima_progressao=date(2024, 5, 1),
        mes=1,
        ano=2025,
    )
    assert resultado.grupo == "No mês"
    assert resultado.data_devida == date(2025, 1, 1)
    assert resultado.proximo == "B-1"
    assert "§ 7" in resultado.observacao
    assert "31/12/2021" in resultado.observacao

    fora = ebtt(
        classe="DI",
        padrao=2,
        data_posse=date(2021, 12, 31),
        data_ultima_progressao=date(2024, 5, 1),
        mes=11,
        ano=2026,
    )
    assert fora.grupo == "Fora"


def test_posse_depois_de_2021_nao_usa_paragrafo_7():
    resultado = ebtt(
        classe="A",
        padrao=1,
        data_posse=date(2022, 1, 1),
        data_ultima_progressao=date(2023, 1, 1),
        mes=1,
        ano=2025,
    )
    assert resultado.grupo == "No mês"
    assert resultado.data_devida == date(2025, 1, 1)
    assert "§ 7" not in resultado.observacao
    assert resultado.efeitos_financeiros == "Sim"


def test_classe_a_com_36_meses_no_futuro_fica_de_fora():
    resultado = ebtt(
        classe="DI",
        padrao=1,
        data_posse=date(2024, 6, 1),
        data_ultima_progressao=None,
        mes=11,
        ano=2026,
    )
    assert resultado.grupo == "Fora"
    assert resultado.data_devida == date(2027, 6, 1)


def test_classe_a_sem_posse_nao_e_calculada():
    resultado = ebtt(classe="A", padrao=1, data_posse=None, data_ultima_progressao=date(2024, 1, 1))
    assert resultado.grupo == "Não calculado"
    assert "posse" in resultado.motivo.lower()


def test_b2_no_aniversario_de_24_meses():
    resultado = ebtt(classe="B", padrao=2, data_ultima_progressao=date(2024, 11, 15))
    assert resultado.grupo == "No mês"
    assert resultado.proximo == "B-3"
    assert resultado.data_devida == date(2026, 11, 15)
    assert resultado.efeitos_financeiros == "Sim"


def test_aniversario_de_outro_mes_fica_de_fora():
    resultado = ebtt(
        classe="B",
        padrao=2,
        data_ultima_progressao=date(2024, 3, 10),
        mes=11,
        ano=2026,
    )
    assert resultado.grupo == "Fora"
    assert resultado.proximo == "B-3"


def test_ancora_no_mesmo_mes_e_ano_fica_de_fora():
    resultado = ebtt(
        classe="B",
        padrao=2,
        data_ultima_progressao=date(2026, 11, 10),
        mes=11,
        ano=2026,
    )
    assert resultado.grupo == "Fora"
    assert resultado.data_devida == date(2028, 11, 10)


def test_promocao_a_titular_exige_memorial_e_doutorado():
    com_doutorado = ebtt(classe="C", padrao=4, titulacao="DOUTORADO E RSC-III")
    assert com_doutorado.proximo == "Titular"
    assert com_doutorado.efeitos_financeiros == "Não"
    assert "memorial" in com_doutorado.observacao.lower()
    assert "falta o título" not in com_doutorado.observacao.lower()

    sem_doutorado = ebtt(classe="C", padrao=4, titulacao="MESTRADO")
    assert "doutor" in sem_doutorado.observacao.lower()

    so_rsc = ebtt(classe="DIV", padrao=4, titulacao="RSC-III")
    assert so_rsc.proximo == "Titular"
    assert "doutor" in so_rsc.observacao.lower()


def test_titular_no_aniversario_nao_entra_em_atraso():
    no_prazo = ebtt(classe="TITULAR", padrao=1, data_ultima_progressao=date(2024, 11, 15))
    assert no_prazo.grupo == "No mês"
    assert no_prazo.efeitos_financeiros == "Não"
    assert "final de carreira" in no_prazo.observacao.lower()

    fora_do_aniversario = ebtt(
        classe="TITULAR",
        padrao=1,
        data_ultima_progressao=date(2024, 3, 15),
        mes=11,
        ano=2026,
    )
    assert fora_do_aniversario.grupo == "Fora"


def test_pcctae_sobe_um_padrao_e_para_em_19():
    sobe = avaliar(
        classe="E",
        padrao="18",
        cargo="ADMINISTRADOR",
        titulacao="",
        data_ultima_progressao=date(2025, 11, 2),
        data_posse=date(2015, 1, 1),
        mes=11,
        ano=2026,
    )
    assert sobe.grupo == "No mês"
    assert sobe.posicao_atual == "E-18"
    assert sobe.proximo == "E-19"
    assert sobe.data_devida == date(2026, 11, 2)

    topo = avaliar(
        classe="E",
        padrao="19",
        cargo="ADMINISTRADOR",
        titulacao="",
        data_ultima_progressao=date(2024, 11, 2),
        data_posse=date(2015, 1, 1),
        mes=11,
        ano=2026,
    )
    assert topo.grupo == "No mês"
    assert topo.proximo == "E-19"
    assert topo.efeitos_financeiros == "Não"
    assert "final de carreira" in topo.observacao.lower()

    topo_fora_do_mes = avaliar(
        classe="E",
        padrao="19",
        cargo="ADMINISTRADOR",
        titulacao="",
        data_ultima_progressao=date(2024, 3, 2),
        data_posse=date(2015, 1, 1),
        mes=11,
        ano=2026,
    )
    assert topo_fora_do_mes.grupo == "Fora"


def test_29_de_fevereiro_cai_no_dia_28():
    resultado = ebtt(classe="B", padrao=1, data_ultima_progressao=date(2024, 2, 29), mes=2, ano=2026)
    assert resultado.data_devida == date(2026, 2, 28)
    assert resultado.grupo == "No mês"
