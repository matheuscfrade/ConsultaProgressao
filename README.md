# Consulta de progressão

Relatório de progressão por campus. Cada uso recebe um arquivo de servidores do SUAP e os afastamentos. Os afastamentos podem trazer todos os campi. O cruzamento é pela matrícula.

A página publicada calcula no navegador. As planilhas não são enviadas para nenhum servidor externo.

## Neste computador

```text
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

No Windows, `run.bat` faz o mesmo. A página que calcula no navegador abre em `http://127.0.0.1:8000/local/`.

Planilhas, CSV e o notebook com resultados de execução ficam de fora do Git. Eles não devem ser enviados ao repositório.
