> Revisão do instalador de dashboards: leia `REVISAO-INSTALADOR.md`. A detecção reportada no Defender ainda não foi reproduzida ou resolvida de forma confirmada.

# Eletrometry integrado — consumidor, Grafana e Neo4j

Agora há **um único Terraform**, na pasta `infra`, para provisionar todo o laboratório. Em um ambiente novo, `terraform apply` cria os recursos e entrega os instaladores no user-data das EC2; o cloud-init inicia os serviços automaticamente. Não é preciso executar o antigo instalador Grafana separadamente.

## Já tenho Grafana funcionando: dashboards

Siga `ATUALIZAR-DASHBOARDS.md`: copie o código sobre a pasta original preservando state/variáveis/chaves; execute `./lab.ps1 atualizar` e `./lab.ps1 dashboards`. Não exige Terraform apply. Fórmulas em `REGRAS-DASHBOARDS.md`; validação em `VALIDACAO-DASHBOARDS.md`.

## Onde cada coisa roda

| Local | Serviços/dados |
| --- | --- |
| EC2 `eletrometry-lab-consumer` — t3.micro | Simulador e consumidor SQS |
| RDS MySQL | Banco `eletrometry`, tabela `leituras` |
| EC2 `eletrometry-lab-paineis` — t3.medium, 4 GiB | Grafana e Neo4j Community em Docker |
| Application Load Balancer | Acesso HTTP ao Grafana |
| Elastic IP da EC2 dos painéis | Neo4j Browser na porta 7474 e Bolt na 7687 |

**Não existe um MySQL dentro da EC2.** O consumidor e o Grafana são clientes do MySQL que está no RDS. O Neo4j é outro banco, independente. Ele começa vazio; não há cópia ou sincronização automática da telemetria RDS para o Neo4j nesta entrega.

A EC2 extra evita colocar Java/Neo4j na t3.micro da coleta. Container limitado a 2304 MiB, heap Java máximo 768 MiB e page cache 512 MiB: configuração inicial de laboratório, não dimensionamento de produção.

## Já tenho a etapa 1 funcionando — como atualizar?

1. Faça uma cópia de segurança da pasta original do projeto inteiro. Ela inclui os states, variáveis e chaves locais.
2. Extraia este ZIP em uma pasta temporária.
3. Copie **o conteúdo** da pasta extraída `eletrometry-terraform-etapa1` para a **pasta original que você já usa**, aceitando substituir os arquivos de código.
4. Preserve seus arquivos `infra/terraform.tfstate`, backups, `terraform.tfvars`, arquivos `*.auto.tfvars*` e chaves. Este ZIP não inclui states ou credenciais reais.
5. Se já aplicou o Grafana separado, mantenha também `grafana/infra/terraform.tfstate` no local original. O novo script precisa dele para a migração.

No PowerShell, na raiz original do projeto:

```powershell
.\lab.ps1 subir
```

O comando inicializa Terraform, consolida o state antigo do Grafana se necessário, valida, mostra o plano, pede `yes` uma vez, aplica e aguarda os serviços por SSM. As instalações podem levar vários minutos depois de o Terraform criar a EC2.

**Confira o plano antes de confirmar:** o esperado é acrescentar a EC2 dos painéis, EIP, senhas e regras; criar o ALB ou reaproveitá-lo. Se havia Grafana separado, a troca do target do ALB e regras de SG é esperada. **Não é esperado destruir/substituir o RDS nem a EC2 do consumidor.** Se aparecer isso, pare e envie o plano sem credenciais. Datasources dinâmicos podem propor atualização de versão do RDS conforme variáveis já existentes; revise também isso.

A migração do state usa `terraform state mv`, cria backups `.state-backup-integracao-...` e preserva o mesmo ALB. Não exige destruir o ambiente nem reinserir dados. Não execute Terraform em outra janela durante a migração. Se interromper, preserve ambos os states e backups; o script consegue continuar movimentos já concluídos. Nunca restaure só um dos dois states no meio de uma migração.

Depois da consolidação, **use apenas `infra` e `lab.ps1`**. `grafana.ps1` agora é um atalho compatível para `lab.ps1`, não possui um fluxo de infraestrutura separado. Não execute `terraform apply/destroy` em `grafana/infra` antigo: o código antigo poderia recriar recursos que já foram transferidos.

Se o Grafana antigo estava na EC2 do consumidor, a nova instalação usa a EC2 dos painéis e o mesmo leitor reservado `eletrometry_grafana`. Após verificar o novo dashboard, você pode desligar o serviço antigo pelo Session Manager da EC2 **consumer**:

```bash
sudo systemctl disable --now grafana-server
```

Não execute esse comando na EC2 nova dos painéis. O instalador não remove automaticamente a instalação antiga para você poder conferir a transição; dashboards criados manualmente nela devem ser exportados/importados. O dashboard provisionado desta entrega já está na nova instalação.

## Vou começar do zero

Extraia o ZIP. Configure AWS CLI, credenciais atuais do perfil `eletrometry-lab` (incluindo session token), Terraform e os valores da sua conta em `infra/terraform.tfvars`, conforme `infra/terraform.tfvars.example`. Inicie o AWS Academy Lab.

Na raiz do projeto:

```powershell
.\lab.ps1 subir
```

Ou, usando Terraform diretamente, sem o acompanhamento automático via SSM:

```powershell
cd infra
terraform init
terraform plan -out=integrado.tfplan
terraform apply integrado.tfplan
cd ..
```

**`Apply complete` confirma a criação dos recursos, não a conclusão das instalações dentro das EC2.** Aguarde e use os comandos abaixo. Em uma atualização com state antigo do Grafana, prefira `lab.ps1 subir`, que faz a consolidação antes do plano.

Se o Windows bloquear scripts baixados, confira o pacote, desbloqueie os scripts e permita execução somente nesta janela:

```powershell
Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

## Abrir Grafana e Neo4j

```powershell
.\lab.ps1 acesso
.\lab.ps1 paineis
```

`acesso` mostra URLs e senhas iniciais geradas. Não compartilhe essa saída: ela também fica no histórico do SSM Run Command. Nenhuma senha MySQL é exibida.

**Grafana:** abra a URL do ALB com o login existente. Página inicial: `Eletrometry • Visão geral das cabines`. Clique em um cartão para abrir `Eletrometry • Dashboard interna da cabine`. Padrão: últimas 24h, atualização 30s. Simulador integrado: corrente e temperatura a cada segundo.

**Neo4j:** abra a URL `http://IP:7474/browser/`; em Connect URL use o endereço `bolt://IP:7687` exibido pelo script; usuário `neo4j`; senha exibida; banco padrão `neo4j`. Teste:

```cypher
RETURN 1 AS funcionando;
```

Esse teste não grava dados. Para contar os nós existentes:

```cypher
MATCH (n) RETURN count(n) AS total;
```

No início, zero nós é esperado. O serviço está pronto, mas o modelo de grafo e o carregamento de dados ainda precisam ser definidos.

`paineis` faz consultas reais pelo Grafana ao RDS e pelo cypher-shell ao Neo4j, além de conferir o target do ALB. `status` também verifica consumidor/simulador:

```powershell
.\lab.ps1 status
```

## O que inicia sozinho

- Nova EC2: cloud-init configura um serviço de bootstrap; ele instala/configura Grafana e Neo4j automaticamente e repete a tentativa em falhas transitórias.
- Reinicializar ou Stop/Start: `grafana-server`, `docker` e `eletrometry-neo4j` estão habilitados no systemd. O container tem `restart=always`.
- Fechar o PowerShell ou desligar o seu PC não para os serviços na AWS.
- Quando o Academy desliga as instâncias, os serviços ficam indisponíveis até elas serem ligadas. Se necessário, inicie as duas EC2 pelo console e confira se o RDS está `available`.

Os dados Neo4j ficam em `/var/lib/eletrometry-observability/neo4j-data` no EBS raiz da EC2, fora do container. **Recriar o container e Stop/Start preservam os dados. Terminar/substituir a EC2 ou `terraform destroy` apaga o volume e os dados.** Faça exportação/snapshot antes de apagar o ambiente; este pacote não implementa backup automático do grafo.

Para impedir substituição automática de EC2 por mudanças de AMI/user-data, essas duas propriedades são ignoradas em instâncias existentes. Isso não instala atualizações de código automaticamente: em atualizações posteriores, use `lab.ps1 atualizar` para consumidor/simulador e `lab.ps1 dashboards` para as dashboards; `lab.ps1 reparar-paineis` para reparação completa de Grafana/Neo4j. Mudança de AMI deve ser planejada com backup/migração.

## Imagem Docker do Neo4j

`observability/neo4j/Dockerfile` deriva de `neo4j:5.26.30-community` e acrescenta uma verificação autenticada de saúde. O bootstrap **constrói a imagem na EC2** como `eletrometry-neo4j:5.26.30` e inicia o container. Este ZIP contém o Dockerfile e scripts; não é uma AMI e não contém uma imagem Docker binária pré-construída. Nenhuma senha ou banco está dentro da imagem.

Autenticação por arquivo montado somente para leitura. Browser e Bolt são portas diferentes; o ALB do Grafana não transporta Bolt.

## Acesso, custos e permissões

O padrão permite os IPs administrativos individuais, não a internet inteira. Nesta configuração de laboratório, Grafana/Neo4j Browser usam HTTP e Bolt não usa TLS: utilize apenas as senhas aleatórias exclusivas do Lab. Para produção, configure TLS e acesso privado apropriado.

Se trocar de rede/celular:

```powershell
.\lab.ps1 liberar-ip
```

Esse comando acrescenta seu IP e mostra o plano antes de aplicar. Para autorizar colegas, edite `infra/observability.auto.tfvars.json` com uma lista de IPs públicos reais `/32`, ou defina `ui_allowed_ipv4_cidrs` em suas variáveis. Não mantenha definições conflitantes em vários arquivos. O arquivo de exemplo mostra o formato.

Há custo adicional por EC2 t3.medium, disco de 30 GB, ALB e IPv4 público/EIP. O EIP alocado e o ALB podem continuar cobrando com a EC2 parada. Monitore o orçamento/créditos do Academy.

Não são criadas roles IAM. As EC2 reutilizam `LabInstanceProfile`; a publicação IoT continua usando a role já configurada. Se o Academy impedir t3.medium, EIP ou ALB, envie a mensagem de permissão/cota sem credenciais; não reduza para t3.micro para tentar acomodar o Neo4j.

Credenciais geradas ficam no state e user-data (mesma premissa do pacote educacional anterior), e em arquivos restritos dentro da EC2. A senha administrativa MySQL é removida do arquivo local de bootstrap depois do provisionamento. Não publique states, backups, chaves ou arquivos locais de credenciais no Git.

## Diagnóstico e reparação

Na EC2 **paineis**, pelo Session Manager:

```bash
sudo journalctl -u eletrometry-bootstrap -n 80 --no-pager
sudo systemctl status grafana-server eletrometry-neo4j --no-pager
sudo docker ps
sudo docker logs --tail 60 eletrometry-neo4j
sudo /opt/eletrometry-observability/venv/bin/python /opt/eletrometry-observability/health.py
```

Se a instalação falhar, o bootstrap repete automaticamente após 60 segundos. Para tentar novamente ou atualizar os arquivos desta entrega pelo PC:

```powershell
.\lab.ps1 reparar-paineis
```

Isso reinstala a configuração e recria o container preservando o diretório de dados. Não apague esse diretório para corrigir autenticação. As senhas iniciais só se aplicam a bancos novos. Se mudar senhas nas interfaces, atualize de forma segura os arquivos locais correspondentes (Grafana: `grafana_password` em `runtime.json`; Neo4j: arquivo `neo4j_auth` e `neo4j_password` em `runtime.json`). O reparador não reseta a senha de bancos existentes.

Na EC2 consumer, continue usando o diagnóstico operacional:

```bash
sudo /opt/eletrometry/venv/bin/python /opt/eletrometry/lab_remote.py status
```

## Arquivos principais

- `infra/`: único conjunto Terraform; `observability.tf` e `alb.tf` acrescentam os painéis.
- `lab.ps1`: subir tudo, status, acessos, reparos e comandos operacionais.
- `observability/`: instalador, verificação, Dockerfile e dashboard.
- `scripts/migrate_grafana_state.ps1`: consolidação opcional do state anterior com backups.
- `SIMULADOR-OUTRO-PC.md`: execução do simulador externo, sem trocar o IP da EC2 no código.
- `VALIDACAO-INTEGRADO.md`: testes e limites da verificação desta entrega.
- `README-OPERACIONAL-ANTERIOR.md`: referência histórica da etapa 1. Para instalação atual, siga este README.

Fontes: [Neo4j Docker](https://neo4j.com/docs/operations-manual/current/docker/introduction/), [autenticação e persistência](https://neo4j.com/docs/operations-manual/current/docker/docker-compose-standalone/), [imagem oficial Neo4j](https://hub.docker.com/_/neo4j/), [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).
