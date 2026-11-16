# Revisão v4 — analista

Inclui visão geral, detalhe operacional e nova dashboard Histórico da cabine.
Histórico: contagens por severidade, seis séries de corrente/temperatura, eventos por hora e tabela filtrável de até 500 eventos. Usa as mesmas regras provisórias e consultas SELECT; não cria tabela de incidentes. Eventos são reconstruídos e podem ter início truncado. Não inclui ainda painel gestor nem previsões.

Correções: contraste adaptado ao tema, campos textuais incluídos explicitamente nos Stats (o seletor vazio mostrava apenas campos numéricos), cartões substituídos por tabelas de largura inteira, altura maior das referências de carregamento, navegação sem forçar tema claro.

Instalação: faça backup. Copie lab.ps1, scripts/send_text_ssm.ps1, toda a pasta observability e observability-bundle.tar.gz deste ZIP para o projeto original. Preserve infra e credenciais. No PowerShell, na raiz original:

```powershell
Unblock-File .\lab.ps1
Unblock-File .\scripts\send_text_ssm.ps1
.\lab.ps1 dashboards
```

O instalador envia agora três JSONs. Abra Histórico da cabine pelo link superior. Use 10 min ou 1 hora se a coleta começou recentemente. Não precisa de Terraform apply.

O usuário informou que resolveu o envio SSM; o mecanismo de transporte foi preservado, com ampliação da lista de destinos para historico.json. Se você alterou esse helper localmente para resolver o SHA-256, preserve sua correção e acrescente historico à lista permitida de dashboards.

Validação: testes locais de integração e geração dos JSONs. Sem conexão ao RDS real, sem aplicação AWS e sem inspeção visual renderizada no Grafana. Conferir após instalar. Documentos v3 descrevem a entrega anterior.
