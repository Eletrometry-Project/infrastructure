# Atualizar as dashboards na EC2 existente

O Grafana já está funcionando: esta atualização não exige Terraform apply nem recriação de recursos.

Se o Defender ainda detectar este ZIP, mantenha-o bloqueado. Esta revisão do instalador não confirma falso positivo nem garante ausência de malware; consulte `REVISAO-INSTALADOR.md`.

1. Faça uma cópia de segurança da pasta original do projeto.
2. Extraia este ZIP em uma pasta temporária.
3. Copie o conteúdo de `eletrometry-terraform-etapa1` sobre a pasta original, substituindo os arquivos de código. Preserve `infra/terraform.tfstate`, backups, `terraform.tfvars`, arquivos `*.auto.tfvars*` e chaves locais.
4. Inicie o Academy Lab, confira as duas EC2 ligadas, o RDS disponível e as credenciais atuais do perfil `eletrometry-lab`.
5. No PowerShell, na raiz original do projeto, execute:

```powershell
.\lab.ps1 atualizar
.\lab.ps1 dashboards
```

O primeiro atualiza consumidor/simulador e reinicia esses serviços, passando temperatura e corrente para 1 segundo. Mantém as leituras do RDS. Caso use simulador externo, execute com `--temperatura-intervalo 1` e use `lab.ps1 parar` depois da atualização para não duplicar fontes.

O segundo envia os dois JSONs e o instalador Python em texto UTF-8 por SSM, verifica o SHA-256 de cada arquivo, testa as consultas no Grafana/MySQL antes de substituir os JSONs e cria backup local. Pode reiniciar apenas o Grafana para mudar a página inicial. Não usa SSH, não altera schema, não recria o Neo4j.

Ao concluir, o comando mostra a URL real da visão geral, terminada em:

```text
/d/eletrometry-visao-geral?theme=light
```

Use o mesmo login e senha do Grafana. `./lab.ps1 acesso` consulta os acessos existentes — não compartilhe a saída com senhas.

As dashboards são **Eletrometry • Visão geral das cabines** e **Eletrometry • Dashboard interna da cabine**. Clique no cartão para abrir a cabine mantendo o período. Use os seletores superiores de cabine, métrica, sensor e fase. Período padrão: últimas 24h; atualização: 30s.

As três cabines reais do simulador aparecem. Não são criadas leituras ou outras cabines apenas para imitar os seis cartões ilustrativos do protótipo. Aguarde um minuto para formar a nova série de temperatura; constância de sensor exige cinco minutos. Alertas em zero podem estar corretos se o simulador não ultrapassar os limites.

A transferência em texto gera mais comandos SSM e pode levar alguns minutos. As consultas SQL e o código ficam visíveis nos registros SSM; não inclua senhas nesses arquivos. O instalador usa as credenciais já existentes na EC2.

## Falhas e retorno

Se o preflight SQL falhar, os JSONs anteriores não são substituídos. Copie a mensagem sem credenciais. Confira RDS, Grafana e perfil AWS. Se os arquivos foram instalados, mas o carregamento ainda não foi confirmado, aguarde 30s e recarregue a página.

Na EC2 dos painéis:

```bash
sudo journalctl -u grafana-server -n 60 --no-pager
```

Backups: `/var/lib/eletrometry-observability/dashboard-backups/<timestamp>`. Para voltar, copie os JSONs do backup escolhido para `/var/lib/grafana/dashboards/`; se houver `grafana.ini`, restaure em `/etc/grafana/` e reinicie `grafana-server`. Não apague dados do RDS ou Neo4j para corrigir uma dashboard.

## Ambiente novo

`./lab.ps1 subir` continua provisionando tudo, com as duas dashboards e temperatura a cada segundo. Leia `REGRAS-DASHBOARDS.md` e `VALIDACAO-DASHBOARDS.md`.

Não houve implantação remota na sua AWS durante a preparação deste pacote. Ela ocorre quando você executa os comandos acima. O acabamento visual ainda deve ser conferido no seu Grafana.
