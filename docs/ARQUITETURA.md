# Arquitetura da revisao integrada

Etapa 1: simulador Python (3 cabines) na EC2 → publicacao HTTPS IoT Core → regra IoT
`eletrometry/demo/+/+` → SQS Standard + DLQ → consumidor na mesma EC2 → RDS MySQL privado.
Duas unidades systemd separadas: eletrometry-simulator e eletrometry-consumer.

PC → AWS Systems Manager → comandos na EC2. SSM usa HTTPS; administracao e testes nao exigem
conexao SSH direta. O IP publico/SSH existentes continuam no Terraform para uso opcional.
A EC2 publica usando o instance profile; a regra IoT usa a role autorizada pelo Lab para SQS.
Credenciais MySQL sao usadas apenas pelo consumidor e verificacoes; o simulador nao abre a senha.

O modo continuo coleta corrente a cada segundo e temperatura a cada 30 segundos por cabine.
Os valores sao sinteticos. O teste de 120 segundos cria um run_id proprio e mede entrega no banco.
O arquivo local de telemetria nao e ingestao historica em S3.

Etapa 2 prevista: ALB, site e Grafana. Etapa 3 prevista: S3 Raw, processamento Glue/PySpark,
Trusted e Athena. Esses servicos nao sao provisionados nesta entrega. Nao ha NAT Gateway.
