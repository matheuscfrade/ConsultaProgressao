"""Entrada usada pela página que roda no navegador. Não envia arquivo a lugar nenhum."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict

from leitura import ErroEntrada, ler_tabela, preparar_afastamentos, preparar_servidores
from relatorio import gerar_relatorio, para_excel


def processar(servidores, nome_servidores: str, afastamentos, nome_afastamentos: str, mes: int, ano: int) -> str:
    try:
        mes = int(mes)
        ano = int(ano)
        if mes < 1 or mes > 12 or ano < 1990 or ano > 2100:
            raise ErroEntrada("Informe um mês de 1 a 12 e um ano válido.")
        tabela_servidores, avisos, tabela_afastamentos = _tabelas(
            servidores, nome_servidores, afastamentos, nome_afastamentos
        )
        registros = gerar_relatorio(tabela_servidores, tabela_afastamentos, mes, ano)
    except ErroEntrada as exc:
        return json.dumps({"ok": False, "erro": exc.mensagem}, ensure_ascii=False)

    excel = para_excel(registros)
    return json.dumps(
        {
            "ok": True,
            "erro": "",
            "avisos": avisos,
            "registros": [asdict(registro) for registro in registros],
            "excel_b64": base64.b64encode(excel).decode("ascii"),
        },
        ensure_ascii=False,
    )


def _tabelas(servidores, nome_servidores, afastamentos, nome_afastamentos):
    tabela_servidores = ler_tabela(_como_bytes(servidores), nome_servidores or "")
    tabela_servidores, avisos = preparar_servidores(tabela_servidores)
    tabela_afastamentos = ler_tabela(_como_bytes(afastamentos), nome_afastamentos or "")
    tabela_afastamentos = preparar_afastamentos(tabela_afastamentos)
    return tabela_servidores, avisos, tabela_afastamentos


def _como_bytes(valor) -> bytes:
    if isinstance(valor, (bytes, bytearray)):
        return bytes(valor)
    if isinstance(valor, memoryview):
        return valor.tobytes()
    converter = getattr(valor, "to_py", None)
    if converter is not None:
        valor = converter()
        if isinstance(valor, memoryview):
            return valor.tobytes()
        return bytes(valor)
    return bytes(valor)
