import json

from navegador import processar


def test_afastamentos_de_todos_os_campi_cruzam_pela_matricula():
    servidores = (
        "SERVIDOR,MATRICULA,SITUACAO,CARGO EMPREGO,CARGO CLASSE,NIVEL PADRAO,"
        "SETOR EXERCICIO,CAMPUS EXERCICIO SIAPE,DATA ULTIMA PROGRESSAO,DATA POSSE NO CARGO,CPF,TITULACAO\n"
        "Ana,100,ATIVO PERMANENTE - 01,PROFESSOR EBTT,B,2,CFO-DE,Formiga,15/11/2024,01/03/2010,12345678900,MESTRADO\n"
    ).encode()
    afastamentos = (
        "VÍNCULO SERVIDOR,UORG,COD AFASTAMENTO,DIA INICIO AFASTAMENTO,DIA FIM AFASTAMENTO\n"
        "26409-0000100,CFO-DE,Licença,01/01/2020,05/01/2020\n"
        "26409-0000200,COP-DE,Férias,01/01/2020,05/01/2020\n"
        "26409-0000100,RE-SECAP,Capacitação,02/01/2025,04/01/2025\n"
    ).encode()
    saida = json.loads(processar(servidores, "servidores.csv", afastamentos, "afastamentos.csv", 11, 2026))
    assert saida["ok"] is True
    assert [item["servidor"] for item in saida["registros"]] == ["ANA"]
    assert "Capacitação" in saida["registros"][0]["afastamentos_periodo"]
