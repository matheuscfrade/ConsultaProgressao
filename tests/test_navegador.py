import json

from navegador import processar

SERVIDORES = """SERVIDOR,MATRICULA,SITUACAO,CARGO EMPREGO,CARGO CLASSE,NIVEL PADRAO,SETOR EXERCICIO,DATA ULTIMA PROGRESSAO,DATA POSSE NO CARGO,FUNCAO DISPLAY,CPF,TITULACAO
Ana Silva,100,ATIVO PERMANENTE - 01,PROFESSOR ENSINO BASICO TECNICO E TECNOLOGICO,B,2,Coordenação,15/11/2024,01/03/2010,,123.456.789-00,MESTRADO
"""

AFASTAMENTOS = """MATRICULA,DATA INÍCIO,DATA FIM,OCORRÊNCIA
100,01/01/2020,05/01/2020,Férias
"""


def test_processar_devolve_o_relatorio_sem_enviar_arquivo():
    saida = json.loads(processar(SERVIDORES.encode(), "servidores.csv", AFASTAMENTOS.encode(), "afastamentos.csv", 11, 2026))
    assert saida["ok"] is True
    assert saida["registros"][0]["servidor"] == "ANA SILVA"
    assert saida["excel_b64"]


def test_processar_recusa_coluna_ausente():
    saida = json.loads(processar(b"SERVIDOR,MATRICULA\nAna,1\n", "servidores.csv", AFASTAMENTOS.encode(), "afastamentos.csv", 11, 2026))
    assert saida["ok"] is False
    assert "CARGO CLASSE" in saida["erro"]
