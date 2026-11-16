# Menos atraso na ingestão e no resumo do analista

Esta revisão mantém as cinco dashboards, as regras de criticidade e o caminho IoT → SQS → consumidor → MySQL → Grafana. Não exige destruir ou recriar a infraestrutura. O atraso observado ainda precisa ser medido na AWS após a instalação: os logs antigos mostram ingestão posterior, mas não isolam a causa nem comprovam a entrega daquele run_id específico.

## Instalar na infraestrutura existente

1. Faça backup da pasta de projeto que você está usando no PowerShell.
2. Extraia este ZIP em outra pasta. Copie para sua pasta original os arquivos `lab.ps1`, `app-bundle.tar.gz`, `observability-bundle.tar.gz` e as pastas `scripts`, `observability`, `consumer`, `deploy`, `telemetry`, `tests`. Copie também este guia. Não substitua `infra`, arquivos `.tfstate`, variáveis nem credenciais.
3. Na pasta original, execute:

```powershell
Unblock-File .\lab.ps1
Get-ChildItem .\scripts -Filter *.ps1 | Unblock-File
.\lab.ps1 parar
.\lab.ps1 atualizar
.\lab.ps1 dashboards
.\lab.ps1 testar
```

`atualizar` deve terminar com **ELETROMETRY - ingestao em lotes instalada**. Ele preserva o estado anterior do simulador; como o roteiro o parou antes, continuará parado. O consumidor permanece ativo. `dashboards` deve confirmar **5/5** e as telas terão a tag `ingestao-lotes`. Copiar o ZIP sem rodar os dois comandos não instala as mudanças na EC2.

Se `testar` confirmar a leitura no MySQL, execute a demonstração completa:

```powershell
.\lab.ps1 simular -Cenario criticidades -Duracao 240
```

Esse comando dura aproximadamente quatro minutos porque gera quatro minutos de dados em tempo real. Esse tempo de geração é diferente do atraso de entrega. Não precisa executar `iniciar` antes. Normal, atenção, moderado, crítico e recuperação são gerados em patamares, e o último patamar é crítico. A verificação espera até 1.440 IDs únicos: três cabines × dois tipos × 240 segundos. A espera adicional por entrega continua limitada, não foi simplesmente aumentada.

No Grafana, abra **01 · Analista — resumo e prioridades**, selecione **10 min** e clique em **Refresh**. Depois abra o resumo do gestor. O período curto facilita enxergar a simulação; não altera os dados nem elimina métricas. As telas continuam com atualização automática desativada por padrão para evitar consultas sobrepostas durante a validação. Após encerrar a simulação, o estado atual pode passar a “Sem dados recentes”; os alertas históricos continuam no período selecionado.

Para voltar a gerar continuamente depois da apresentação, use `lab.ps1 iniciar`. Um teste finito pausa o simulador contínuo da EC2 se ele estava ativo e o retoma ao terminar, inclusive em falhas tratadas. Simuladores externos precisam ser pausados separadamente; encerrar abruptamente o processo remoto pode exigir retomada manual.

## O que mudou

| Parte | Antes | Agora |
|---|---|---|
| Gravação | Um INSERT e COMMIT por mensagem | `executemany` e um COMMIT para o lote recebido, até dez mensagens |
| Confirmação SQS | Uma chamada de exclusão por mensagem | Uma chamada por lote, verificando sucesso de cada item |
| Logs | Mensagem de log para cada leitura | Resumo a cada cinco segundos de atividade, com duração da gravação e idade da mensagem |
| Validação de simulação | Busca por run_id sem índice dedicado | Busca dos IDs esperados pela chave primária, consultando apenas os que faltam |
| Estado atual nos resumos | Processamento histórico com funções de janela | Última leitura de cada cabine/tipo, usando o índice existente |
| Histórico no resumo do analista | Seis consultas históricas separadas | Uma consulta compartilhada entre o contador, quatro indicadores e a lista de alertas |
| Atualização da aplicação | Iniciava o simulador mesmo se estava parado | Preserva o estado anterior |

Não se espera preencher dez mensagens: o lote recebido é gravado imediatamente. Um lote cheio passa de dez commits para um, mas isso **não comprova melhoria de dez vezes no tempo total**. Latência de rede, desempenho do RDS, volume histórico e concorrência continuam influenciando o resultado. As outras telas preservam os gráficos e indicadores existentes; as consultas de histórico/projeção ainda podem exigir agregações persistidas quando o volume crescer.

A confirmação na fila acontece somente depois do COMMIT. Falha no banco mantém o lote na fila. Mensagens inválidas ficam disponíveis para o fluxo de retentativas/DLQ. Se a exclusão SQS falhar parcialmente, os itens sem confirmação podem ser entregues de novo; a chave `event_id` impede uma segunda linha. Nenhuma fila é purgada e nenhum histórico é apagado por esta atualização.

## Como ler as medidas

- `testar` informa o tempo desde o início da publicação até a verificação no banco. Inclui inicialização do verificador e intervalo de consulta; é uma medida observada do teste, não apenas tempo de rede.
- `simular` imprime `coleta_ate_insert` com média, p95 e máximo em segundos. Mede `recebido_em - coletado_em` para os IDs desta execução, depois que suas transações ficaram visíveis. `recebido_em` é atribuído no INSERT, antes do COMMIT. Relógios desalinhados podem afetar a diferença; valores negativos são sinalizados.
- `lab.ps1 logs` mostra `MySQL+commit ... ms` e `SQS->commit max ... s` para o último lote no resumo periódico. O primeiro isola gravação/commit; o segundo inclui a idade desde a entrada no SQS, mas não o tempo anterior ao SQS.
- `status` chama a idade da última chegada pelo nome correto: segundos desde a última chegada, não latência. Com o simulador parado, esse número aumenta normalmente.

Se continuar lento, execute `lab.ps1 status` e `lab.ps1 logs` e guarde a saída do teste. Fila acumulada com `MySQL+commit` alto aponta para investigação do banco/concorrência; fila acumulada com banco rápido exige examinar consumo, retentativas e tráfego. Se o teste chega rápido e só os painéis demoram, investigue as consultas no Query Inspector do Grafana. São pistas, não diagnósticos conclusivos. Não rode várias simulações para tentar “destravar” uma fila atrasada.

## Validação desta revisão

39 testes locais passaram; dois testes de migração de estado foram ignorados por falta de PowerShell/Terraform neste ambiente. Foram verificados: transação única para dez mensagens, COMMIT antes da confirmação, rollback, duplicatas, mensagem inválida, confirmação SQS parcial, preservação do estado do simulador, comparação de IDs, contrato do simulador real e as cinco definições de dashboard. A consulta de estado atual foi exercitada em SQLite com funções equivalentes para cenários normal, crítico, ausente, inválido e leitura mais recente.

A sintaxe do instalador shell também foi verificada. Não houve implantação, benchmark no RDS nem validação visual no Grafana remoto. Os testes locais não comprovam disponibilidade da AWS nem um limite de latência em produção.

Referências técnicas: [inserções em lote no Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-executemany.html), [confirmação em lote no SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/example_sqs_DeleteMessageBatch_section.html) e [compartilhamento de consultas no Grafana](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/query-transform-data/share-query/).
