"""Página local. Não calcula carreira por conta própria."""

from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from leitura import ErroEntrada, ler_tabela, preparar_afastamentos, preparar_servidores
from relatorio import Registro, gerar_relatorio, para_excel

app = FastAPI(title="Consulta de progressão")
RAIZ = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(RAIZ / "templates"))
_excels: dict[str, bytes] = {}
CODIGO_NAVEGADOR = ("leitura.py", "carreira.py", "relatorio.py", "navegador.py")


@app.get("/local")
@app.get("/local/")
def pagina_navegador():
    return FileResponse(RAIZ / "estatico" / "index.html")


@app.get("/local/codigo/{nome}")
def codigo_navegador(nome: str):
    if nome not in CODIGO_NAVEGADOR:
        raise HTTPException(status_code=404, detail="Arquivo não disponível.")
    return PlainTextResponse((RAIZ / nome).read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    hoje = date.today()
    return _pagina(request, hoje.month, hoje.year)


@app.post("/", response_class=HTMLResponse)
async def gerar(
    request: Request,
    mes: int = Form(...),
    ano: int = Form(...),
    servidores: UploadFile | None = File(None),
    afastamentos: UploadFile | None = File(None),
):
    if not _arquivo_enviado(servidores):
        return _pagina(request, mes, ano, erro="Envie o relatório de servidores do SUAP.")
    if not _arquivo_enviado(afastamentos):
        return _pagina(request, mes, ano, erro="Envie o arquivo de afastamentos.")
    if mes < 1 or mes > 12 or ano < 1990 or ano > 2100:
        return _pagina(request, mes, ano, erro="Informe um mês de 1 a 12 e um ano válido.")

    try:
        tabela_servidores, avisos, tabela_afastamentos = _ler_tabelas(
            await servidores.read(),
            servidores.filename or "",
            await afastamentos.read(),
            afastamentos.filename or "",
        )
        registros = gerar_relatorio(tabela_servidores, tabela_afastamentos, mes, ano)
    except ErroEntrada as exc:
        return _pagina(request, mes, ano, erro=exc.mensagem)

    token = secrets.token_urlsafe(16)
    _excels[token] = para_excel(registros)
    return _pagina(
        request,
        mes,
        ano,
        avisos=avisos,
        registros=registros,
        token=token,
    )


@app.get("/excel/{token}")
def baixar_excel(token: str):
    conteudo = _excels.pop(token, None)
    if conteudo is None:
        raise HTTPException(status_code=404, detail="Esse Excel já foi baixado ou não existe.")
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=relatorio_progressoes.xlsx"},
    )


def _pagina(
    request: Request,
    mes: int,
    ano: int,
    erro: str | None = None,
    avisos: list[str] | None = None,
    registros: list[Registro] | None = None,
    token: str | None = None,
):
    grupos = {"No mês": [], "Não calculado": []}
    if registros is not None:
        for registro in registros:
            grupos.setdefault(registro.grupo, []).append(registro)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "mes": mes,
            "ano": ano,
            "erro": erro,
            "avisos": avisos or [],
            "registros": registros,
            "no_mes": grupos["No mês"],
            "nao_calculado": grupos["Não calculado"],
            "token": token,
        },
    )


def _ler_tabelas(servidores: bytes, nome_servidores: str, afastamentos: bytes, nome_afastamentos: str):
    tabela_servidores = ler_tabela(servidores, nome_servidores)
    tabela_servidores, avisos = preparar_servidores(tabela_servidores)
    tabela_afastamentos = ler_tabela(afastamentos, nome_afastamentos)
    tabela_afastamentos = preparar_afastamentos(tabela_afastamentos)
    return tabela_servidores, avisos, tabela_afastamentos


def _arquivo_enviado(arquivo: UploadFile | None) -> bool:
    return arquivo is not None and bool(arquivo.filename)
