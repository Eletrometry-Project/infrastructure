# Transpilador Eletrometry — ELT v1

Implementação integrada ao Terraform em `infra/`, com compilação local também disponível. Traduz ELT para consultas de leitura MySQL 8. Não altera tabelas, não publica dashboards e não opera equipamentos. Limites de exemplo são provisórios.

## Comece em cinco minutos

Requer Python 3.12. Na raiz do repositório:

```powershell
python -m transpiler transpiler/examples/temperatura.elt --out gerado --explain
python -m unittest discover -s transpiler/tests -v
python -m transpiler transpiler/examples/erro-unidade.elt --out gerado-erro
```

O último comando deve falhar com erro semântico. Sem MySQL configurado, testes de integração são marcados como skipped. O workflow GitHub Actions executa também os testes SQL em MySQL 8 descartável.

Saídas: regra-001.sql (uma por regra) e compilacao.json (versão, tokens, AST e consultas). Use uma pasta de saída nova para cada compilação; arquivos de uma execução anterior não são apagados. Em caso de erro, nada novo é escrito, mas arquivos antigos podem permanecer.

O código de saída é 0 no sucesso e 1 no erro. Não é necessário instalar bibliotecas para compilar localmente.

## Linguagem

```text
REGRA "Temperatura crítica"
 CABINE "cabine-002"
 FASE QUALQUER
 QUANDO TEMPERATURA >= 90 C
 DURANTE 10 SEGUNDOS
 LACUNA_MAXIMA 5 SEGUNDOS
 CLASSIFICAR CRITICO
FIM
```

- Palavras-chave maiúsculas, sem acentos. Nomes entre aspas aceitam Unicode.
- Comentários começam com #; espaços e quebras de linha não mudam a regra.
- Grandezas: TEMPERATURA/C e CORRENTE/A.
- Fases: A, B, C, QUALQUER. QUALQUER avalia cada fase independentemente.
- Operadores: >, >=, <, <=, ==.
- Classificações: ATENCAO, MODERADO, CRITICO.
- Duração: inteiro de 0 a 86400 segundos; 0 permite uma amostra.
- Lacuna: inteiro de 1 a 3600 segundos. Deve corresponder à frequência de coleta.
- Limites não negativos e menores que 10 milhões, compatíveis com a ingestão atual.
- Cadastro permitido: cabines.json; CLI pode usar --registry outro.json.
- Um arquivo pode conter até 100 regras de nomes diferentes e no máximo 64 KiB.
- Todas as regras precisam ser válidas antes de gerar qualquer saída.
- Ainda não suporta E/OU entre condições, minutos, expressões matemáticas ou herança.

## Semântica dos eventos

Consulta considera [start, end) em UTC. Não inclui histórico anterior ao início da janela: uma ocorrência em andamento pode ter seu início truncado. A primeira leitura que comprova duração >= DURANTE confirma o evento.

Qualidade diferente de ok, valor nulo, condição falsa ou intervalo > LACUNA_MAXIMA interrompe a sequência. Lacuna exatamente igual ao limite é aceita. Cada fase tem sua própria sequência; fases não somam tempo. Leituras simultâneas conflitantes são tratadas conservadoramente: todas precisam satisfazer a condição naquele instante/fase.

O resultado é uma linha por sequência confirmada, com regra, cabine, grandeza, fase, severidade, início, confirmação, última leitura e duração observada. Não extrapola além da última leitura. Última leitura não significa encerramento confirmado. Ausência de resultado não significa equipamento saudável.

Regras são independentes: duas regras sobrepostas podem gerar duas linhas para a mesma condição. V1 não resolve prioridade nem deduplica entre regras. Não some resultados como um único indicador de incidentes sem definir essa política.

## SQL e Grafana

Os arquivos usam parâmetros %(start)s e %(end)s, para binding por mysql.connector. Nunca substitua esses parâmetros por texto recebido do usuário. Use datetimes UTC e conexão com time_zone='+00:00'.

O SQL referencia a tabela leituras já existente. Ele é uma consulta SELECT com CTEs; o transpilador não se conecta ao banco.

Para experimentar no Grafana, em um painel de tabela NOVO:
1. Compile o exemplo.
2. Copie a consulta.
3. Substitua o marcador literal %(start)s por FROM_UNIXTIME(${__from}/1000.0).
4. Substitua o marcador literal %(end)s por FROM_UNIXTIME(${__to}/1000.0).
5. Use o datasource MySQL de leitura e selecione um período com medições.
6. Compare o resultado com as leituras de cada fase.

Essa é uma validação manual. Não substitua as cinco dashboards automaticamente: seus indicadores atuais têm regras próprias, inclusive antecipação e agregações. Integração de publicação, atualização das cores/limites e portal de upload são etapas seguintes.

## AWS

Veja [o manual de implantação e Actions](AWS.md). O Terraform empacota e provisiona S3/Lambda no mesmo apply do laboratório. Handler fornecido: transpiler.lambda_handler.handler.
Recebe ObjectCreated do S3, lê a versão exata do arquivo e grava SQL/metadados ou relatório de erro. Não executa SQL. Somente entrada/*.elt é processado; não acompanha a ordem de chegada para publicar regras.

## Onde estudar

- compiler.py: Token, tokenize, Rule, Parser, validate, generate_sql, compile_source.
- __main__.py: interface de terminal e gravação dos artefatos.
- lambda_handler.py: adaptação do mesmo compilador ao S3.
- tests/test_compiler.py: lexer/parser/semântica e S3 simulado.
- tests/test_mysql.py: execução do SQL sobre cenários controlados.
- APRENDA.md: explicação progressiva e exercícios.
