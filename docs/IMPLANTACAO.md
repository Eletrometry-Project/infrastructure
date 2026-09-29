# Implantar do zero — PowerShell/Windows

Revisão 2, 29/09/2026. Começar em uma pasta nova com o ZIP atualizado. Usar o perfil local `eletrometry-lab` já configurado, incluindo session token temporário. Nunca colocar essas credenciais em arquivos Terraform.

## 1. Confirmar ferramentas e conta

Na pasta extraída:

```powershell
terraform version
aws --version
py --version
aws sts get-caller-identity --profile eletrometry-lab
```

Requer Terraform >=1.11 e <2, AWS CLI v2, Python 3 e OpenSSH. Terraform 1.13.5 foi usado na preparação, provider AWS 6.66.0 fixado no lockfile. A conta informada pelo usuário foi `831154260318`. Conferir se continua sendo a conta alvo ao renovar a sessão.

## 2. Preparar chave SSH

Isso cria um arquivo no seu computador; o Terraform registra a parte pública na AWS:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\eletrometry"
```

Escolher uma passphrase para a chave e guardá-la. Se esse arquivo já existir, não sobrescrever: reutilizar seu `.pub` se você ainda tiver a chave privada, ou escolher outro nome e atualizar `ssh_public_key_path`. Se preferir uma key pair já fornecida pelo Lab, definir `existing_key_pair_name` no tfvars e dispensar o registro de chave nova. Ter o nome da key pair não basta: você precisa da chave privada correspondente para SSH/WinSCP.

## 3. Preencher a configuração única

```powershell
Copy-Item infra/terraform.tfvars.example infra/terraform.tfvars
```

Editar `infra/terraform.tfvars`. Substituir `SEU_IP_PUBLICO/32` pelo IPv4 público da conexão administrativa, mantendo `/32`. Confirmar conta, perfil e caminho `.pub`. Não preencher IDs de VPC/subnet/EC2/RDS antigos.

As duas opções `create_consumer_iam` e `create_iot_iam` são `true`: criam IAM dedicado ao projeto. Se a documentação/permissões do Learner Lab exigirem roles fornecidas, configurar somente a opção correspondente:

```hcl
create_consumer_iam = false
instance_profile_name = "NOME_REAL_DO_INSTANCE_PROFILE"

create_iot_iam = false
iot_sqs_role_arn = "ARN_REAL_DA_ROLE_AUTORIZADA_PARA_IOT"
```

Não inventar ARN nem assumir que `LabRole` serve ao IoT. A role IoT precisa confiar em `iot.amazonaws.com` e permitir `sqs:SendMessage` na fila; o perfil EC2 precisa das permissões de consumo. Nesse modo Terraform **referencia**, não altera esses objetos. Se não houver role apropriada e a criação for negada, será necessário resolver a permissão com o responsável pelo laboratório. Um `plan` válido não comprova autorização para criar IAM; conferir isso antes do apply. Um apply que falhar pode já ter criado outros recursos: manter o state, corrigir a causa e revisar um novo plan; não apagar o state para repetir.

## 4. Inicializar e validar

```powershell
Set-Location infra
terraform init
terraform fmt -check -recursive
terraform validate
terraform test
Set-Location ..
```

Os testes Terraform usam provider simulado e não criam recursos na conta. Eles usam entradas próprias, sem pedir a senha real. O primeiro init baixa o provider; não atualizar o lockfile sem necessidade.

## 5. Gerar o plano

Na raiz do pacote:

```powershell
& .\scripts\terraform.ps1 -Action Plan
```

O script solicita a senha administrativa por `Read-Host -AsSecureString`, passa temporariamente em `TF_VAR_db_master_password`, executa o plan e restaura a variável ao sair. Use senha de 16 a 41 caracteres ASCII, sem espaço, barra `/`, aspas duplas ou `@`, guardada em seu gerenciador de senhas. O Terraform usa variável efêmera + `password_wo`; o segredo não é gravado no plano/state. Não usar senha da aplicação como senha administrativa.

Se o PowerShell impedir executar scripts, não é necessário alterar a política do sistema. Podemos executar os comandos equivalentes interativamente. A senha não deve ser colocada em argumento literal, arquivo tfvars ou screenshot.

O plano inicial pesquisa uma AMI oficial Ubuntu 24.04 x86_64 da Canonical e uma versão disponível padrão da família MySQL 8.4. O MD não fixava a versão MySQL. Conferir suporte dessa versão e de `db.t4g.micro` no Lab. Copiar os valores de `selected_versions` para `consumer_ami_id` e `db_engine_version` no tfvars e executar o Plan novamente. Isso fixa as versões antes da criação e evita pesquisa móvel nos próximos planos. É possível informar explicitamente outra versão suportada antes do plano.

O plano fica em `infra/reviewed.tfplan` e a versão JSON em `infra/plan.json`. O script confere se há exclusões/substituições. A revisão humana também deve conferir criações, IAM, IP do SSH, banco privado, tamanhos, custos e crédito do Lab. No primeiro plano os recursos devem ser criações, sem importação ou exclusão.

## 6. Aplicar somente o plano revisado

```powershell
& .\scripts\terraform.ps1 -Action Apply
```

Essa ação executa o plano salvo: rodar o comando significa aplicá-lo. Digitar **a mesma senha usada no Plan**, pois o valor efêmero precisa ser fornecido novamente e não está armazenado no plano. Não mudar senha, configuração, conta ou sessão-alvo entre revisão e aplicação; se precisar, gerar outro plano.

O script exporta `runtime.json` sem segredos. A senha da aplicação ainda não foi fornecida, portanto o consumidor ainda não deve estar processando. Não repetir a criação em outra pasta/state para corrigir um erro.

## 7. Conferir instalação e preparar banco

Obter o IPv4 da EC2 nos outputs. Conectar substituindo `IP_DA_EC2`:

```powershell
ssh -i "$env:USERPROFILE\.ssh\eletrometry" ubuntu@IP_DA_EC2
```

Dentro da EC2 Ubuntu:

```bash
sudo cloud-init status --wait
sudo /opt/eletrometry/venv/bin/python /opt/eletrometry/setup_database.py
```

O setup solicita `eletrometry_admin` e a senha definida no Plan/Apply, depois uma nova senha para o usuário `eletrometry_consumer`. Ele cria a tabela `leituras` se ausente, prepara esse usuário exigindo TLS e concede SELECT, INSERT e UPDATE(event_id). A senha da aplicação é gravada em arquivo root:root 0600 e entregue ao serviço por `LoadCredential`; a senha administrativa não é salva. A rotação dessa credencial local é manual. Não confundir esse procedimento com Secrets Manager automático.

Se cloud-init falhar, conferir `/var/log/cloud-init-output.log`. A instalação pode ser repetida na EC2 com `sudo bash /opt/eletrometry-package/deploy/install.sh /opt/eletrometry-package/runtime.json`, após resolver o erro. O checkout é fixado no commit revisado. O instalador não inicia nem reinicia o serviço por conta própria.

```bash
sudo systemctl start eletrometry-consumer
sudo systemctl status eletrometry-consumer --no-pager
sudo journalctl -u eletrometry-consumer -n 60 --no-pager
```

Agora executar o simulador no PC e seguir `docs/TESTES.md`. Evitar outro consumidor concorrendo na mesma fila, especialmente o antigo SQS→S3. Depois de alterações de banco pendentes terminarem, um novo plan deve ficar sem alterações inesperadas.

## State em equipe e encerramento

O padrão é state local protegido e fora do Git, operado por uma pessoa. Para trabalho em equipe, preparar o backend S3 antes de compartilhar a operação. O subprojeto `bootstrap-state/` cria um bucket próprio, criptografado, versionado, com bloqueio de acesso público e exigência de TLS. Não é o data lake.

No PowerShell definir `$env:AWS_PROFILE = 'eletrometry-lab'` para o bootstrap/backend, executar init/validate/plan no subprojeto com as variáveis `aws_account_id` e `bucket_name`, revisar e aplicar. Depois copiar `infra/backend.tf.example` para `infra/backend.tf`, e `backend.hcl.example` para `backend.hcl`, preenchendo o bucket. Usar `terraform init -backend-config=backend.hcl`; se já houver state local, usar `-migrate-state` e conferir a migração. O state do próprio bootstrap também deve ser guardado. O backend precisa permitir operações do state e do arquivo `.tflock`.

Não há destroy automático: EC2, filas e RDS têm proteção contra exclusão/substituição, e o RDS exige snapshot final. A desativação depois da faculdade deve ser planejada para não manter cobranças. A proteção não elimina custos. Se um snapshot final com o mesmo nome já existir, definir um nome único antes do encerramento deliberado.
