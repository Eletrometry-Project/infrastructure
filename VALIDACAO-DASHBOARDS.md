# Validação das dashboards — 07/10/2026

Na etapa anterior desta implementação foram executados:

- MySQL Community 8.4.6 real, inicialização offline e banco descartável: 21 consultas em oito cenários (normal, crítico antecipado, alerta curto, reincidência, lacuna, qualidade inválida, desequilíbrio e banco vazio), com verificação dos valores retornados e seletores.
- Nove testes de integração dos painéis, sete de telemetria, dois do adaptador e cinco de bootstrap.
- Equivalência e idempotência do patch do simulador para bootstrap novo e atualização existente.
- Parser PowerShell 7.5.0 em três arquivos; sintaxe Python/Bash/HCL e Terraform fmt.
- Expressão real de user-data Terraform com configuração fictícia representativa: abaixo de 16.384 bytes. A precondição no Terraform valida os valores reais.

Na retomada final, os ajustes de empacotamento foram recuperados dos passos já executados e os bundles foram regenerados. O resultado não foi aplicado na AWS do usuário.

A inspeção visual em navegador/Grafana não foi concluída neste ambiente. Conferir acabamento na instância após instalar. Não houve teste de carga do RDS. O JSON usa componentes nativos, sem plugin visual adicional.

`lab.ps1 dashboards` testa as consultas pelo Grafana/MySQL real da EC2 nos últimos cinco minutos antes de publicar os JSONs. Isso verifica conexão e compatibilidade SQL; não comprova desempenho de um mês inteiro nem aparência no navegador.

Esta versão não persiste incidentes nem envia notificações. As fórmulas provisórias estão em REGRAS-DASHBOARDS.md.
