# Arquitetura — criação do zero, revisão 2

O hard reset removeu a infraestrutura anterior. O handoff define o fluxo a reconstruir; nenhum recurso de aplicação antigo é requerido.

## Fluxo e etapas

Etapa 1: simulador HTTPS → regra IoT → SQS Standard → consumidor Python EC2 → RDS MySQL. O consumidor confirma a mensagem somente depois do COMMIT; event_id impede duplicações. Cloud-init instala os componentes e systemd; a tabela/usuário/credencial são preparados com o script interativo posterior.

Etapa 2: site, Grafana e load balancer. A proposta de ALB atende HTTP/HTTPS e exige definir listeners, TLS, health checks e targets. Ele não integra o polling da fila nem o tráfego MySQL. Bastion, Docker e servidores privados continuam decisões da etapa 2. Etapa 3: S3 Raw, transformação Glue/PySpark, Trusted e Athena, com ingestão histórica própria. Não colocar consumidor SQS→S3 competindo pela mesma fila.

## Rede e recursos

VPC nova, duas subnets públicas para a evolução com ALB e duas privadas de banco em duas AZs. EC2 Ubuntu pública nesta etapa de laboratório, SSH somente do /32 administrativo. RDS privado, 3306 somente a partir do SG da EC2. Nenhuma entrada HTTP/HTTPS na EC2. Banco Single-AZ; subnets em duas zonas não significam dois bancos nem alta disponibilidade integral.

O gateway e a rota pública fornecem saída para SQS e downloads Git/PyPI/APT/CA. Subnets do RDS têm apenas rotas locais. Não há NAT, bastion ou endpoints nesta etapa. Para mover a aplicação para subnets privadas, definir sua saída na etapa 2: um endpoint SQS resolve apenas SQS; um bastion não fornece saída para downloads.

## IAM, versões e senha

Por padrão Terraform cria duas roles distintas: EC2 com consumo SQS, IoT com envio SQS. As políticas limitam ações à fila; a confiança IoT limita conta e ARN da regra. No modo de roles de laboratório, apenas referencia os objetos autorizados; não os modifica. Credenciais temporárias do computador continuam necessárias para executar Terraform. A EC2 usa instance profile, sem chaves estáticas.

A chave SSH é gerada no computador: só a pública é registrada pelo Terraform. AMI Ubuntu 24.04 oficial e MySQL 8.4 padrão disponível são consultados no primeiro plano quando não fixados; depois devem ser fixados no tfvars. A versão MySQL não estava definida no handoff; verificar disponibilidade/classe no Lab e compatibilidade antes de aplicar. Não assumir gratuidade.

Senha administrativa: write_only + variável efêmera por padrão; opção managed usa Secrets Manager do RDS caso permitido. Senha da aplicação: arquivo protegido na EC2, entregue ao systemd por LoadCredential; rotação manual. Nenhum segredo entra no user-data. O banco lógico é criado no RDS, mas a tabela e o usuário restrito são etapas SQL explícitas do pacote.

## Entrega e retenção

Regra SELECT * FROM 'eletrometry/demo/+/+', JSON sem Base64. Três correntes por mensagem a cada segundo, três temperaturas a cada 30 segundos, por cabine. Consumidor lê até dez mensagens por chamada, long polling 10 s e visibilidade 120 s. Fila principal: quatro dias; DLQ: 14 dias e cinco recebimentos malsucedidos. Não há purge ou redrive automático. Indisponibilidade prolongada do banco pode encaminhar mensagens válidas à DLQ; investigar antes de reenviar. Ordenar análises por coletado_em UTC.

Não há exclusão automática de leituras. Definir retenção/arquivamento antes de manter carga contínua longa; 20 GiB não representam dimensionamento de um ano. Custos precisam considerar EC2, RDS, IPv4, disco/backup e, depois, ALB, NAT/endpoints e serviços analíticos. Não foi determinado qual item será o mais caro. O bucket opcional de state é separado do futuro data lake.

## Referências oficiais

- [IoT para SQS](https://docs.aws.amazon.com/iot/latest/developerguide/sqs-rule-action.html)
- [RDS na VPC e grupos de subnets](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html)
- [SQS via endpoint VPC](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-internetwork-traffic-privacy.html)
- [Application Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html)
- [Senha write-only no Terraform](https://developer.hashicorp.com/terraform/language/manage-sensitive-data/write-only)
- [Integração RDS/Secrets Manager e permissões](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html)
- [Consumidor do grupo](https://github.com/Eletrometry-Project/sqs-consumer/tree/038b257430c7fbad19cf0d42d7353a4f795eb5d3)

- [Seleção de versão RDS](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/rds_engine_version)
- [Confiança e permissões da role IoT](https://docs.aws.amazon.com/iot/latest/developerguide/iot-create-role.html)
- [Imagens Ubuntu oficiais](https://documentation.ubuntu.com/aws/aws-how-to/instances/launch-ubuntu-ec2-instance/)
