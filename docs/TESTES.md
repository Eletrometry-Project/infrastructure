# Testes no Lab

Na pasta original do Terraform, com credenciais renovadas e a EC2 Online:

```powershell
.\lab.ps1 status
.\lab.ps1 testar
.\lab.ps1 simular
```

- `status` consulta o destino configurado no consumidor: host, `eletrometry.leituras`, total,
  ultimas leituras e filas. Servico ativo nao basta para comprovar fluxo.
- `testar` publica um evento via IoT, aguarda MySQL e confere event_id unico e valores 100/101/102.
- `simular` chama o simulador original durante 120 segundos em tempo real. Confere que 372 eventos
  foram gerados e aceitos pelo IoT, sem pendencias. Depois compara TODOS os IDs/tipos/cabines
  arquivados com o banco usando somente o run_id novo, aguardando ate 90 segundos pela entrega.
  Esperado por cabine: 120 correntes e 4 temperaturas. Um evento faltante reprova o teste.

Sucesso no teste finito nao comprova comportamento por horas, tolerancia a todas as falhas ou desempenho
sob carga maior. Nao deixe outro consumidor da mesma fila competindo pela entrega para outro destino.

```powershell
.\lab.ps1 iniciar
.\lab.ps1 status
.\lab.ps1 parar
```

`iniciar` e idempotente: habilita o servico, sem abrir outro processo se ja estiver ativo.
`parar` encerra apenas a geracao continua; registros anteriores permanecem e a fila pode continuar drenando.
Verifique novamente status apos alguns segundos para observar novas leituras quando ligado.

Para diagnostico, envie `logs` e a saida do teste, incluindo Status, Saida e Erro se estiver usando SSM
manualmente. Nao envie state, chaves, senhas ou o user-data com segredos.
