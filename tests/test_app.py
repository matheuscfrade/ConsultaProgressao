import re

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

SERVIDORES = """SERVIDOR,MATRICULA,SITUACAO,CARGO EMPREGO,CARGO CLASSE,NIVEL PADRAO,SETOR EXERCICIO,DATA ULTIMA PROGRESSAO,DATA POSSE NO CARGO,FUNCAO DISPLAY,CPF,TITULACAO
Ana Silva,100,ATIVO PERMANENTE - 01,PROFESSOR ENSINO BASICO TECNICO E TECNOLOGICO,B,2,Coordenação,15/11/2024,01/03/2010,,123.456.789-00,MESTRADO
"""

AFASTAMENTOS = """MATRICULA,DATA INÍCIO,DATA FIM,OCORRÊNCIA
100,01/01/2020,05/01/2020,Férias
"""


def test_pagina_do_navegador_nao_recebe_planilha():
    pagina = client.get("/local/")
    assert pagina.status_code == 200
    assert "neste navegador" in pagina.text
    assert "method=\"post\"" not in pagina.text
    codigo = client.get("/local/codigo/navegador.py")
    assert codigo.status_code == 200
    assert "def processar" in codigo.text
    assert client.get("/local/codigo/report_cfo_suap.xlsx").status_code == 404


def test_pagina_inicial_pede_os_dois_arquivos():
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "Servidores" in resposta.text
    assert "Afastamentos" in resposta.text


def test_sem_arquivo_nao_gera_relatorio():
    resposta = client.post("/", data={"mes": "11", "ano": "2026"})
    assert resposta.status_code == 200
    assert "servidores" in resposta.text.lower()
    assert "Ana Silva" not in resposta.text


def test_coluna_ausente_explica_o_nome():
    resposta = client.post(
        "/",
        data={"mes": "11", "ano": "2026"},
        files={
            "servidores": ("servidores.csv", "SERVIDOR,MATRICULA\nAna,1\n", "text/csv"),
            "afastamentos": ("afastamentos.csv", AFASTAMENTOS, "text/csv"),
        },
    )
    assert "CARGO CLASSE" in resposta.text
    assert "B-2" not in resposta.text


def test_gera_relatorio_e_baixa_excel():
    resposta = client.post(
        "/",
        data={"mes": "11", "ano": "2026"},
        files={
            "servidores": ("servidores.csv", SERVIDORES, "text/csv"),
            "afastamentos": ("afastamentos.csv", AFASTAMENTOS, "text/csv"),
        },
    )
    assert resposta.status_code == 200
    assert "ANA SILVA" in resposta.text
    assert "B-2" in resposta.text
    encontrado = re.search(r"/excel/([A-Za-z0-9_\-]+)", resposta.text)
    assert encontrado
    excel = client.get(f"/excel/{encontrado.group(1)}")
    assert excel.status_code == 200
    assert excel.content.startswith(b"PK")
    assert client.get(f"/excel/{encontrado.group(1)}").status_code == 404
