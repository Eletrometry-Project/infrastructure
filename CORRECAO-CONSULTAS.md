# Correção de consultas e investigação da ingestão

> Atualização de desempenho: consulte **MELHORIA-DESEMPENHO.md**. Esta revisão inclui ingestão em lotes e exige `lab.ps1 atualizar`, além de `lab.ps1 dashboards`.

O log de 02/11 mostra 720 publicações aceitas pelo IoT, sem pendências locais, e zero linhas do run_id no MySQL durante a verificação. Não comprova entrega ao SQS. Consumidor, permissões, regra IoT, backlog e RDS precisam ser examinados separadamente.

Primeiro feche as abas Grafana e execute:

```powershell
.\lab.ps1 parar
.\lab.ps1 logs
```

`parar` pausa o simulador contínuo; o consumidor permanece ativo para esvaziar a fila. Envie a saída de logs para diagnóstico. Não purgue filas, não apague dados e não recrie a infraestrutura.

Nesta correção:
- A exposição ao risco usa união ordenada de intervalos, substituindo a comparação correlacionada entre cada segmento e cada leitura. Preserva a união por cabine e a soma entre cabines.
- Atualização automática desativada nas cinco telas; atualize manualmente durante o diagnóstico.
- Telas operacionais abrem por padrão na última hora. URLs que trazem período explícito continuam preservando-o.
- SELECTs dos painéis recebem MAX_EXECUTION_TIME(15000): limite de execução no MySQL. Não limita espera por conexão nem garante resposta completa em 15 segundos. Estouro aparece como erro de consulta, não como zero.
- O preflight imprime o UID e o painel antes de cada consulta para identificar qual falhou.

Para instalar: preserve scripts/send_text_ssm.ps1 corrigido para Base64, copie a pasta observability e observability-bundle.tar.gz e execute lab.ps1 dashboards. Não requer atualizar a aplicação nem Terraform apply.

Validação local: nove testes existentes; união de intervalos testada com duplicatas, sobreposição, contiguidade, lacunas e cabines independentes em SQLite (funções de janela). Não equivale a benchmark ou teste completo em MySQL/RDS. O volume de dados ainda pode exigir incidentes persistidos e agregações; a correção não comprova nem resolve sozinha a causa das mensagens ausentes.

Depois que o fluxo estiver diagnosticado e o teste lab.ps1 testar confirmar a chegada no RDS, rode:

```powershell
.\lab.ps1 simular -Cenario criticidades -Duracao 240
```

Com simulador contínuo pausado, ele permanece pausado ao término. Use lab.ps1 iniciar se quiser retomá-lo. O comando sem -Cenario utiliza o cenário normal, não o de criticidades.
