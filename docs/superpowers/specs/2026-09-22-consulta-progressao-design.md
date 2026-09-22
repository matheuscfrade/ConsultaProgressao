# Consulta de progressão — desenho

Data: 2026-09-22

Aplicativo local, aberto no navegador, que substitui o notebook Colab `analise_pessoas_cfo_v2` para o uso do dia a dia. Cada uso é um campus: um relatório de servidores exportado do SUAP e o arquivo de afastamentos desse mesmo campus. O resultado é a lista de quem está no prazo no mês escolhido e de quem já passou do prazo, com o próximo nível da carreira e um Excel.

O que se roda é o aplicativo novo. O rascunho antigo do Colab não entra no repositório.

## Fora deste desenho

- Publicar na internet e criar login. O programa já nasce separado para isso, mas esta entrega só escuta em `127.0.0.1`.
- API do SIAPE. Quando existir, entra como outra forma de obter as mesmas tabelas. A regra de carreira e a montagem do relatório não mudam.
- Gravar os arquivos enviados. Eles são lidos na memória e descartados.
- Descontar afastamento do interstício, julgar avaliação de desempenho, memorial ou tese. O afastamento só aparece no card.

## Peças

Três partes, cada uma com uma responsabilidade.

| Peça | Faz | Não faz |
|---|---|---|
| Regra de carreira | Lê classe, nível, cargo e datas. Devolve posição exibida, próximo nível, data devida e o tipo de movimento. | Não lê arquivo e não sabe o que é "relatório do mês". |
| Relatório | Recebe as duas tabelas já lidas, o mês e o ano. Aplica a regra, chefia, pares, afastamentos e o campo de CD. | Não abre navegador e não conhece o nome do campus. |
| Página | Recebe os dois arquivos, o mês e o ano. Mostra a lista e o botão do Excel. | Não calcula carreira por conta própria. |

Rodar no Windows, a partir da pasta do projeto:

```text
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

A página abre em `http://127.0.0.1:8000`. Um `run.bat` executa esse comando. Um README curto repete só isso.

## Entrada

Um uso, um campus. Não há Formiga nem Polo fixos no código.

- Arquivo de servidores, obrigatório. CSV ou XLSX.
- Arquivo de afastamentos, obrigatório. CSV ou XLSX.
- Mês e ano de referência, obrigatórios.

CSV: tentar UTF-8 e, se falhar, Latin-1. Aceitar separador vírgula ou ponto e vírgula. Datas em dia/mês/ano.

Colunas obrigatórias do relatório de servidores:

- `SERVIDOR`
- `MATRICULA`
- `SITUACAO`
- `CARGO EMPREGO`
- `CARGO CLASSE`
- `NIVEL PADRAO`
- `SETOR EXERCICIO`

Colunas usadas quando existirem: `DATA ULTIMA PROGRESSAO`, `DATA POSSE NO CARGO`, `FUNCAO DISPLAY`, `CPF`, `TITULACAO`.

Matrícula repetida no mesmo arquivo: fica a última ocorrência e a página avisa quantas foram descartadas.

Afastamentos: localizar matrícula em `VÍNCULO SERVIDOR` (trecho depois do último hífen) ou em `MATRICULA`. Localizar início e fim entre os nomes já aceitos pelo script atual (`DIA INICIO AFASTAMENTO`, `DATA INÍCIO`, `DATA INICIO`, `DIA FIM AFASTAMENTO`, `DATA FIM`). Localizar o tipo em `COD AFASTAMENTO`, `OCORRÊNCIA` ou `OCORRENCIA`.

Quem tem a situação contendo `APOSENTADO`, `SUBSTITUTO` ou `TEMPORARIO` não entra em lista nenhuma.

## Carreira EBTT

Professor é quem tem `PROFESSOR` no cargo. A conta do próximo nível usa sempre a malha vigente desde 1º de janeiro de 2025 (Lei nº 12.772/2012, art. 14, com a redação da Lei nº 15.141/2025 e da Lei nº 15.367/2026).

A posição **exibida** é a da planilha quando ela ainda está na malha antiga. O **próximo nível** já sai na malha nova. A equivalência vai entre parênteses.

| Planilha | Equivale a | Próximo nível |
|---|---|---|
| DI-1, DI-2, DII-1, DII-2 | A-1 | B-1 |
| DIII-1 a DIII-3 | B-1 a B-3 | B-2 a B-4 |
| DIII-4 | B-4 | C-1 |
| DIV-1 a DIV-3 | C-1 a C-3 | C-2 a C-4 |
| DIV-4 | C-4 | Titular |
| A-1 | A-1 | B-1 |
| B-1 a B-3 | a própria | sobe um nível |
| B-4 | B-4 | C-1 |
| C-1 a C-3 | a própria | sobe um nível |
| C-4 | C-4 | Titular |
| Titular | Titular | permanece |

Exemplos do card: `DIV-3 (equivale a C-3) → C-4`. Quem já vem como `B-2` aparece `B-2 → B-3`, sem parênteses.

A classe é normalizada antes da leitura: maiúsculas, sem a palavra `CLASSE`, hífen virando espaço, espaços repetidos virando um. A leitura segue esta ordem, para `DIII` não ser engolido por `DI` e `D IV` não ser engolido por `D V`:

- Contém `TITULAR`, ou o texto é `T`, `DV` ou `D V`: Titular.
- Contém `DIV` ou `D IV`: classe C, com o nível da planilha.
- Contém `DIII` ou `D III`: classe B, com o nível da planilha.
- Contém `DII` ou `D II`: A-1, qualquer que seja o nível 1 ou 2.
- Contém `DI` ou `D I`: A-1, qualquer que seja o nível 1 ou 2.
- O texto inteiro é `A`, `B` ou `C`: malha nova. `A` com nível diferente de 1 vira A-1 e a linha avisa que o nível foi ajustado.
- O texto inteiro é `D`: Titular, com aviso na linha para conferência.
- Qualquer outro texto, ou nível EBTT que não dê para ler: classe não reconhecida. Não inventar próximo nível.

Nível EBTT válido: 1 a 4, exceto A (só 1) e Titular (único). Valor composto no padrão, como `409`, usa a mesma extração de dígitos do script atual, limitada a esse máximo.

Não existe progressão A-1 → A-2. A aceleração por titulação está revogada. RSC não conta como doutorado (art. 19).

### Quando a pessoa entra na lista

A data âncora dos níveis B e C, inclusive B-4 → C-1 e C-4 → Titular, é `DATA ULTIMA PROGRESSAO`. Se ela estiver vazia, usa `DATA POSSE NO CARGO`. A primeira data devida é essa âncora mais 24 meses, no mesmo dia. Em 29 de fevereiro de ano não bissexto, usa 28 de fevereiro.

Classe A, vinda de A, DI ou DII, não usa a data da última progressão. Usa a posse:

- Posse em 31/12/2021 ou antes: a primeira data devida é 01/01/2025. O art. 14, § 7º, considera o interstício cumprido nessa data para quem estava em DI ou DII e já tinha estágio probatório. A planilha não informa a aprovação do estágio. A observação diz que isso foi presumido pela posse, e cita a data da posse.
- Posse depois de 31/12/2021: a primeira data devida é a posse mais 36 meses.
- Sem data de posse: não entra em "no mês" nem em "em atraso". Vai para "não calculado".

Classificação, sem repetir a pessoa:

- **No mês.** A primeira data devida cai no mês e no ano de referência.
- **Em atraso.** A primeira data devida é anterior ao mês de referência e a planilha ainda mostra o nível antigo. Aparece em todo relatório, até o arquivo mudar. O card marca `Em atraso desde dd/mm/aaaa`. Só um nível: a lei não acumula interstício para pular dois níveis de uma vez. Se o mês de referência também é um aniversário posterior, a pessoa fica só na lista de atraso.
- **Fora do relatório.** A primeira data devida é posterior ao mês de referência.

Titular já no topo não entra em atraso. Entra em "no mês" quando o aniversário de 24 meses da âncora cai no mês de referência e já se passaram pelo menos 24 meses. O card diz final de carreira, somente avaliação de desempenho, sem efeito financeiro.

O mesmo ano da âncora não conta como prazo cumprido. Quem progrediu em novembro de 2026 não reaparece no relatório de novembro de 2026.

### Efeito financeiro e Titular

"Efeito financeiro: sim" significa que o movimento produz efeito na data devida quando a avaliação de desempenho for aprovada. A ferramenta não verifica a avaliação.

- Progressão dentro de B ou C, promoção A → B e promoção B-4 → C: sim, na primeira data devida.
- C-4 → Titular: não. A observação sempre diz que falta memorial ou tese inédita. Se a titulação não for de doutorado, diz também que falta o título de doutor. RSC sozinho não satisfaz o doutorado. Doutorado na mesma célula, ainda que acompanhado de RSC, satisfaz.
- Já Titular: não.

Para o grupo do § 7º, o card não finge um interstício ainda em curso. Diz que o interstício foi considerado cumprido em 01/01/2025 e lista os afastamentos do arquivo como informação, sem separá-los em "dentro do interstício" e "fora".

Nos demais casos, o período mostrado é o ciclo que termina no dia anterior à primeira data devida: 24 meses, ou 36 meses na passagem A → B contada da posse. Afastamentos que cruzam esse período entram em "Afastamentos (período)", com a quantidade de dias sobrepostos. Os outros entram em "Outros afastamentos". Afastamento não muda a data devida.

## Técnico-administrativo

Quem não é professor permanece na regra atual. Sobe um padrão dentro da mesma classe, até 19 (Lei nº 15.141/2025). A primeira data devida é a âncora mais 12 meses. Quem ainda tem próximo padrão usa a mesma comparação de "no mês" e "em atraso" da carreira EBTT. No padrão 19, fica no topo: somente avaliação, sem efeito financeiro, e nunca entra em atraso. Padrão que não dê para ler vai para "não calculado".

## Chefia, pares e CD

Chefia e pares saem do mesmo arquivo de servidores, pelo setor de exercício.

- Chefia: pessoa do setor com situação `ATIVO PERMANENTE - 01` ou `COLAB PCCTAE E MAGIS - 41` e função exibida começando com `FG` ou `CD`.
- Substitutos de chefia: mesma função, situação `CONT.PROF.SUBSTITUTO - 52`, listados à parte.
- Pares: os demais do setor, exceto as situações já excluídas no script (`APOSENTADO - 02`, substituto, temporário, instituidor de pensão, estagiário, visitante) e exceto a própria pessoa.

O campo **Função/CD** é só da pessoa do card. Mostra o cargo se `FUNCAO DISPLAY` for de CD. Função gratificada e campo vazio viram `Não ocupou`. FG continua podendo aparecer na chefia do setor.

A senha continua sendo os três primeiros dígitos do CPF, ou `000` se o CPF estiver vazio. Ela só existe na resposta daquele uso. Não é gravada.

## Página e Excel

A página tem mês, ano e os dois arquivos. Depois de gerar:

1. Contagem de em atraso, no mês e não calculado.
2. Seção **Em atraso**, visualmente distinta, antes da outra.
3. Seção **No mês**.
4. Seção **Não calculado**, só se houver alguém. Motivos possíveis: classe não reconhecida, sem data de posse na Classe A, sem data de progressão e sem data de posse.

Cada card mantém os campos do relatório atual: servidor, SIAPE, cargo, interstício (ou a frase do § 7º), carreira, efeito financeiro, observação, setor, chefias, pares, Função/CD, senha e afastamentos.

O Excel tem as mesmas informações, em uma aba, com a coluna `grupo` (`Em atraso`, `No mês` ou `Não calculado`). Datas em `dd/mm/aaaa`. Afastamentos em texto, sem marcação HTML. O arquivo enviado pelo usuário não é salvo. O Excel gerado pode ir para um arquivo temporário só para o download e é apagado em seguida.

Ninguém no mês e ninguém em atraso é um resultado válido, não um erro. A página diz isso.

## Erros

A página não monta relatório pela metade.

- Falta um dos arquivos, ou o arquivo não é CSV nem XLSX: pede o arquivo de novo.
- Falta coluna obrigatória dos servidores: lista o nome das colunas e para.
- Afastamentos sem matrícula ou sem as duas datas: explica o que não foi encontrado e para.
- Arquivo ilegível: diz que não conseguiu ler e para.

## Testes

Testes automáticos da regra, sem navegador e sem planilha real:

- Cada linha da tabela de conversão, inclusive DI/DII nos dois níveis virando A-1 e o próximo sendo B-1.
- `DIII` não é lido como `DI`.
- `A` com nível 2 vira A-1, com aviso, e o próximo é B-1.
- `D` sozinho vira Titular, com aviso.
- Classe ilegível não ganha próximo nível.
- Posse em 31/12/2021, referência novembro de 2026: em atraso desde 01/01/2025, próximo B-1, observação da presunção.
- Posse em 01/01/2022, referência novembro de 2026: em atraso desde 01/01/2025, e não usa o texto do § 7º.
- Posse em 01/06/2024, referência novembro de 2026: fora do relatório. A data devida é 01/06/2027.
- Classe A sem posse: não calculado.
- B-2 com âncora em novembro de 2024 e referência em novembro de 2026: no mês, próximo B-3.
- B-2 com âncora em março de 2024 e referência em novembro de 2026: em atraso desde março de 2026, um nível só.
- Âncora no mesmo mês e ano da referência: fora do relatório.
- B-4 vai para C-1. C-4 com doutorado vai para Titular, sem efeito financeiro, pendente de memorial ou tese. C-4 sem doutorado aponta a falta do título. RSC-III sozinho não é doutorado. Doutorado e RSC na mesma célula contam como doutorado.
- Titular no aniversário de 24 meses: no mês, final de carreira, não entra em atraso.
- Padrão 18 do PCCTAE vai para 19 no ciclo de 12 meses. Padrão 19 é topo.
- Função da pessoa em FG vira `Não ocupou`. CD aparece. A chefia do setor ainda lista FG.
- Coluna obrigatória ausente não produz relatório.
- Matrícula repetida fica com a última linha.

Não há, nesta entrega, teste de navegador contra um SUAP real. A conferência visual fica para quando o aplicativo estiver no ar localmente.
