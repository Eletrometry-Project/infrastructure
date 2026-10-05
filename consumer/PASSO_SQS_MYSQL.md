# Eletrometry: da fila SQS ao RDS MySQL

O RDS já tem o banco `eletrometry` e a tabela `leituras`. A EC2 Ubuntu já alcança o RDS. O simulador continua publicando **via HTTPS** no IoT Core; a regra entrega à fila existente. Este pacote adiciona o consumidor `consumidor_sqs_mysql.py` na EC2.

## Instalação na EC2

Copie `consumidor_sqs_mysql.py` e `requirements_consumidor.txt` para a EC2. No diretório dos arquivos:

```bash
sudo apt update
sudo apt install -y python3-venv curl
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements_consumidor.txt
curl -fsSLo global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
```

O `global-bundle.pem` é a CA pública do RDS. O consumidor verifica o certificado e o hostname do banco. A senha do MySQL será solicitada na execução; nunca a grave no Git nem coloque em argumento de comando.

## Primeiro teste: um lote

Use a URL real da fila e o endpoint real do RDS (somente hostname, sem `:3306`). O `--db-user` é o nome do usuário MySQL. **Não informe `--profile` na EC2 se ela tem instance profile com permissão para SQS**.

```bash
.venv/bin/python consumidor_sqs_mysql.py \
  --queue-url https://sqs.us-east-1.amazonaws.com/ID_CONTA/eletrometry-demo \
  --db-host SEU_ENDPOINT.rds.amazonaws.com \
  --db-user SEU_USUARIO \
  --ca-file global-bundle.pem \
  --lotes 1
```

Abra outra sessão MySQL na EC2 e confirme:

```sql
SELECT COUNT(*) AS mensagens, MIN(coletado_em), MAX(coletado_em)
FROM eletrometry.leituras;
SELECT cabine_id, tipo, coletado_em, fase_a, fase_b, fase_c
FROM eletrometry.leituras ORDER BY coletado_em DESC LIMIT 10;
```

Cada linha corresponde a uma mensagem de três fases. A chave `event_id` impede que reentregas do SQS dupliquem a leitura. O processo faz **INSERT → COMMIT → DeleteMessage**. Se não houver mensagens, aguarda dez segundos e encerra sem alterar a fila. Para mais lotes, use `--lotes 10`; para execução contínua, `--lotes 0`.

## Se aparecer erro

- `NoCredentialsError` ou `AccessDenied` para SQS: a EC2 precisa de instance profile autorizado para `sqs:ReceiveMessage` e `sqs:DeleteMessage`; IAM do Learner Lab pode limitar isso. Use `aws sts get-caller-identity` para conferir a identidade, sem compartilhar credenciais.
- Timeout no SQS: a EC2 precisa de saída para a API regional do SQS via internet ou VPC endpoint; alcançar o RDS na VPC não garante acesso ao SQS.
- Acesso negado no MySQL: confira usuário e senha do banco e privilégios de INSERT/SELECT na tabela.
- Mensagem inválida: o script para e não apaga a mensagem. Confira se a fila contém mensagens antigas do teste `painel-001` ou outro contrato; configure uma DLQ antes de rodar continuamente.
- Os dois consumidores `consumidor_sqs_mysql.py` e `consumidor_sqs_s3.py` **não devem usar a mesma fila simultaneamente**: em uma fila SQS, consumidores competem pelas mensagens. A cópia histórica para S3 precisa de um fluxo próprio após estabilizar o banco.

O arquivo `esquema_mysql.sql` reproduz a estrutura já criada; execute apenas se precisar preparar outro banco vazio.
