import io
from datetime import date

import pandas as pd
import pytest

from leitura import ErroEntrada, ler_tabela, preparar_afastamentos, preparar_servidores
from relatorio import gerar_relatorio, para_excel


def servidores(linhas):
    return pd.DataFrame(linhas)


def base(**kwargs):
    linha = {
        "SERVIDOR": "Ana Silva",
        "MATRICULA": "100",
        "SITUACAO": "ATIVO PERMANENTE - 01",
        "CARGO EMPREGO": "PROFESSOR ENSINO BASICO TECNICO E TECNOLOGICO",
        "CARGO CLASSE": "B",
        "NIVEL PADRAO": "2",
        "SETOR EXERCICIO": "Coordenação",
        "DATA ULTIMA PROGRESSAO": "15/11/2024",
        "DATA POSSE NO CARGO": "01/03/2010",
        "FUNCAO DISPLAY": "",
        "CPF": "123.456.789-00",
        "TITULACAO": "MESTRADO",
    }
    linha.update(kwargs)
    return linha


def test_funcao_fg_nao_ocupa_cd_e_chefia_ainda_lista_fg():
    df = servidores([
        base(SERVIDOR="Ana Silva", MATRICULA="100", **{"FUNCAO DISPLAY": "FG1 - COORDENACAO"}),
        base(
            SERVIDOR="Bruno Costa",
            MATRICULA="200",
            **{"CARGO CLASSE": "C", "NIVEL PADRAO": "1", "FUNCAO DISPLAY": "CD3 - DIRETOR"},
        ),
    ])
    registros = gerar_relatorio(df, pd.DataFrame(), 11, 2026)
    ana = next(r for r in registros if r.servidor == "ANA SILVA")
    bruno = next(r for r in registros if r.servidor == "BRUNO COSTA")
    assert ana.funcao_cd == "Não"
    assert bruno.funcao_cd == "Sim"
    assert "BRUNO COSTA (CD-3)" in ana.chefias
    assert "ANA SILVA (FG-1)" in bruno.chefias


def test_coluna_obrigatoria_ausente_nao_produz_relatorio():
    df = pd.DataFrame([{"SERVIDOR": "Ana", "MATRICULA": "1"}])
    with pytest.raises(ErroEntrada) as erro:
        preparar_servidores(df)
    assert "CARGO CLASSE" in erro.value.mensagem


def test_matricula_repetida_fica_com_a_ultima_linha():
    df = servidores([
        base(**{"CARGO CLASSE": "C", "NIVEL PADRAO": "1", "SERVIDOR": "Ana Antiga"}),
        base(**{"CARGO CLASSE": "B", "NIVEL PADRAO": "2", "SERVIDOR": "Ana Atual"}),
    ])
    preparado, avisos = preparar_servidores(df)
    registros = gerar_relatorio(preparado, pd.DataFrame(), 11, 2026)
    assert len(registros) == 1
    assert registros[0].servidor == "ANA ATUAL"
    assert registros[0].posicao_atual == "B-2"
    assert avisos


def test_afastamento_automatico_com_titulo_e_matricula_com_zeros():
    buffer = io.BytesIO()
    quadro = pd.DataFrame([
        ["Afastamentos", None, None, None, None],
        [None, None, None, None, None],
        ["VÍNCULO SERVIDOR", "NOME SERVIDOR", "COD AFASTAMENTO", "DIA INICIO AFASTAMENTO", "DIA FIM AFASTAMENTO"],
        ["26409-0000100", "Alguem", "Licença", "2025-03-06", "2025-03-15"],
    ])
    quadro.to_excel(buffer, index=False, header=False)
    afast = ler_tabela(buffer.getvalue(), "afastamentos.xlsx")
    afast = preparar_afastamentos(afast)
    registros = gerar_relatorio(servidores([base()]), afast, 11, 2026)
    assert "Licença" in registros[0].afastamentos_periodo
    assert "10 dias" in registros[0].afastamentos_periodo


def test_afastamento_no_periodo_e_fora_dele():
    df = servidores([base()])
    afast = pd.DataFrame([
        {
            "VÍNCULO SERVIDOR": "Ana Silva - 100",
            "COD AFASTAMENTO": "Licença",
            "DIA INICIO AFASTAMENTO": "01/12/2024",
            "DIA FIM AFASTAMENTO": "10/12/2024",
        },
        {
            "VÍNCULO SERVIDOR": "Ana Silva - 100",
            "COD AFASTAMENTO": "Capacitação",
            "DIA INICIO AFASTAMENTO": "02/01/2025",
            "DIA FIM AFASTAMENTO": "04/01/2025",
        },
        {
            "VÍNCULO SERVIDOR": "Ana Silva - 100",
            "COD AFASTAMENTO": "Férias",
            "DIA INICIO AFASTAMENTO": "01/01/2020",
            "DIA FIM AFASTAMENTO": "10/01/2020",
        },
        {
            "VÍNCULO SERVIDOR": "Ana Silva - 100",
            "COD AFASTAMENTO": "Recesso",
            "DIA INICIO AFASTAMENTO": "01/02/2020",
            "DIA FIM AFASTAMENTO": "05/02/2020",
        },
    ])
    registros = gerar_relatorio(df, afast, 11, 2026)
    assert registros[0].afastamentos_periodo.splitlines() == [
        "Licença (01/12/2024 a 10/12/2024 | 10 dias no interstício)",
        "Capacitação (02/01/2025 a 04/01/2025 | 3 dias no interstício)",
    ]
    assert registros[0].outros_afastamentos.splitlines() == [
        "Férias (01/01/2020 a 10/01/2020)",
        "Recesso (01/02/2020 a 05/02/2020)",
    ]


def test_paragrafo_7_nao_separa_afastamento_em_periodo():
    df = servidores([
        base(
            **{
                "CARGO CLASSE": "DI",
                "NIVEL PADRAO": "1",
                "DATA POSSE NO CARGO": "15/03/2018",
                "DATA ULTIMA PROGRESSAO": "01/05/2024",
            }
        )
    ])
    afast = pd.DataFrame([
        {
            "MATRICULA": "100",
            "OCORRÊNCIA": "Capacitação",
            "DATA INÍCIO": "01/02/2024",
            "DATA FIM": "05/02/2024",
        }
    ])
    registros = gerar_relatorio(df, afast, 1, 2025)
    assert registros[0].grupo == "No mês"
    assert "01/01/2025" in registros[0].intersticio
    assert "Capacitação" in registros[0].afastamentos_periodo
    assert "dias no interstício" not in registros[0].afastamentos_periodo


def test_aposentado_nao_entra():
    df = servidores([base(**{"SITUACAO": "APOSENTADO - 02"})])
    assert gerar_relatorio(df, pd.DataFrame(), 11, 2026) == []


def test_so_entra_quem_ainda_esta_ativo():
    df = servidores([
        base(**{"SERVIDOR": "Ativo", "MATRICULA": "100"}),
        base(**{
            "SERVIDOR": "Colaborador",
            "MATRICULA": "150",
            "SITUACAO": "COLAB PCCTAE E MAGIS - 41",
        }),
        base(**{"SERVIDOR": "Aposentada", "MATRICULA": "200", "SITUACAO": "APOSENTADA - 02"}),
        base(**{"SERVIDOR": "Cedido", "MATRICULA": "300", "SITUACAO": "CEDIDO - 08"}),
        base(**{"SERVIDOR": "Provisorio", "MATRICULA": "400", "SITUACAO": "EXERCICIO PROVISORIO - 19"}),
    ])
    nomes = [item.servidor for item in gerar_relatorio(df, pd.DataFrame(), 11, 2026)]
    assert nomes == ["ATIVO", "COLABORADOR"]


def test_ultima_ocorrencia_de_exclusao_tira_do_relatorio():
    df = servidores([
        base(**{
            "SERVIDOR": "Redistribuido",
            "MATRICULA": "100",
            "DATA ULTIMA PROGRESSAO": "15/10/2024",
            "OCORRENCIAS DISPLAY": (
                "EXCLUSAO: REDISTRIBUICAO / ART. 37, LEI 8.112/90 - 03/04/2017"
                "<br>INCLUSAO: ADMISSAO POR CONCURSO PUBLICO - 23/12/2008"
            ),
        }),
        base(**{
            "SERVIDOR": "Voltou",
            "MATRICULA": "200",
            "DATA ULTIMA PROGRESSAO": "15/10/2024",
            "OCORRENCIAS DISPLAY": (
                "INCLUSAO: NOMEACAO CARATER EFETIVO - 01/02/2024"
                "<br>EXCLUSAO: REDISTRIBUICAO / ART. 37, LEI 8.112/90 - 03/04/2017"
            ),
        }),
        base(**{
            "SERVIDOR": "Sai Depois",
            "MATRICULA": "300",
            "DATA ULTIMA PROGRESSAO": "15/10/2024",
            "OCORRENCIAS DISPLAY": "EXCLUSAO: REDISTRIBUICAO / ART. 37, LEI 8.112/90 - 01/12/2026",
        }),
    ])
    nomes = [item.servidor for item in gerar_relatorio(df, pd.DataFrame(), 10, 2026)]
    assert "REDISTRIBUIDO" not in nomes
    assert "VOLTOU" in nomes
    assert "SAI DEPOIS" in nomes


def test_quem_saiu_ate_o_mes_nao_entra_nem_como_par():
    df = servidores([
        base(**{
            "SERVIDOR": "Saiu Antes",
            "MATRICULA": "100",
            "CARGO EMPREGO DATA SAIDA": "01/10/2026",
        }),
        base(**{"SERVIDOR": "Fica No Campus", "MATRICULA": "200"}),
        base(**{
            "SERVIDOR": "Sai Depois",
            "MATRICULA": "300",
            "CARGO EMPREGO DATA SAIDA": "01/12/2026",
        }),
        base(**{
            "SERVIDOR": "Exonerado",
            "MATRICULA": "400",
            "SITUACAO": "EXONERADO - 07",
        }),
    ])
    registros = gerar_relatorio(df, pd.DataFrame(), 11, 2026)
    nomes = [item.servidor for item in registros]
    assert "SAIU ANTES" not in nomes
    assert "EXONERADO" not in nomes
    assert "FICA NO CAMPUS" in nomes
    assert "SAI DEPOIS" in nomes
    fica = next(item for item in registros if item.servidor == "FICA NO CAMPUS")
    assert "SAIU ANTES" not in fica.pares
    assert "EXONERADO" not in fica.pares


def test_csv_com_ponto_e_virgula_e_latin1():
    conteudo = "SERVIDOR;MATRICULA\nJosé;10\n".encode("latin-1")
    df = ler_tabela(conteudo, "servidores.csv")
    assert list(df.columns) == ["SERVIDOR", "MATRICULA"]
    assert df.iloc[0]["SERVIDOR"] == "José"


def test_afastamento_sem_data_e_rejeitado():
    df = pd.DataFrame([{"MATRICULA": "1", "COD AFASTAMENTO": "Licença"}])
    with pytest.raises(ErroEntrada) as erro:
        preparar_afastamentos(df)
    assert "data" in erro.value.mensagem.lower()


def test_colunas_extras_e_data_vazia_nao_derrubam_o_relatorio():
    linha = base(
        **{
            "CARGO EMPREGO": "ADMINISTRADOR",
            "CARGO CLASSE": "E",
            "NIVEL PADRAO": "10",
            "DATA ULTIMA PROGRESSAO": pd.NaT,
            "DATA POSSE NO CARGO": pd.Timestamp("2010-03-01"),
            "EMAIL": "ana@example.com",
            "LOTACAO SIAPE": "IFMG",
        }
    )
    df = pd.DataFrame([linha])
    preparado, avisos = preparar_servidores(df)
    assert "EMAIL" in preparado.columns
    assert avisos == []
    registros = gerar_relatorio(preparado, pd.DataFrame(), 3, 2011)
    assert len(registros) == 1
    assert registros[0].grupo == "No mês"
    assert registros[0].proximo == "E-11"


def test_excel_traz_a_coluna_grupo():
    df = servidores([base()])
    registros = gerar_relatorio(df, pd.DataFrame(), 11, 2026)
    planilha = pd.read_excel(io.BytesIO(para_excel(registros)))
    assert planilha.loc[0, "grupo"] == "No mês"
    assert planilha.loc[0, "pos_atual"] == "B-2"
