# Manual — transpilador com Terraform

O transpilador agora faz parte do Terraform em `infra/`. Um único apply cria o S3, a Lambda Python 3.12, a permissão de invocação, o gatilho, o grupo de logs e a fila de falhas. O próprio Terraform monta o ZIP a partir do código deste checkout. Não é necessário baixar um ZIP no Actions nem criar a função pelo console.

A implantação é código pronto para aplicar; os testes no Actions usam AWS simulada. A validação na conta real deve ser feita após o apply.

## 1. O que você precisa configurar

| Item | Configuração |
|---|---|
| Conta/credenciais | Inicie o AWS Academy e atualize access key, secret key e session token do perfil local `eletrometry-lab`. Não envie esses valores no chat ou Git. |
| Terraform | Versão >= 1.11 e < 2; executar na pasta original, preservando o state. |
| AWS CLI | Necessária para os comandos do laboratório e os exemplos abaixo. |
| Conta de destino | Confira `aws_account_id` em `infra/terraform.tfvars`; não reutilize o ID de outra pessoa. |
| Role da Lambda | Por padrão usa `arn:aws:iam::<conta>:role/LabRole`. A existência do nome NÃO garante que esteja autorizada. |
| GitHub Actions | Para os testes, apenas Actions habilitado no repositório. Não precisa de secrets AWS. |
| Python + boto3 | Opcionais para o teste automático real; não necessários para o Terraform empacotar a Lambda. |

Se seu laboratório fornecer outra role, acrescente ao seu arquivo de variáveis existente:

```hcl
transpiler_lambda_role_arn = "arn:aws:iam::123456789012:role/ROLE_AUTORIZADA"
```

Troque o ID e o nome pelo ARN real. Não use `LabInstanceProfile`: ele é o perfil das EC2, não o ARN de uma role.

### Permissões: dois papéis diferentes

**Quem executa Terraform:** precisa criar/atualizar os recursos AWS já usados pelo projeto e os novos recursos S3, Lambda, CloudWatch Logs e SQS, além de `iam:PassRole` para a role escolhida. Este código não cria nem altera roles ou suas políticas.

**Role de execução da Lambda:** deve confiar no serviço `lambda.amazonaws.com` (`sts:AssumeRole`) e permitir:

- `s3:GetObjectVersion` em `<bucket>/entrada/*`.
- `s3:PutObject` em `<bucket>/saida/*` e `<bucket>/erros/*`.
- `logs:CreateLogStream` e `logs:PutLogEvents` no grupo da função.
- `sqs:SendMessage` na fila `eletrometry-<ambiente>-elt-failures`.

O output `transpiler.role_policy_example` fornece o JSON com os ARNs após o apply, útil para um administrador autorizado. No Academy, não tente modificar LabRole sem permissão: se o laboratório bloquear a role, é necessário usar uma role permitida/solicitar suporte ao professor. Actions não contorna restrições do Academy.

## 2. Atualizar o código preservando o ambiente

A implementação está na branch `feat/elt-transpiler-v1` até o PR ser integrado.

Na pasta do repositório que você já usa:

```powershell
git status
git fetch origin
git switch feat/elt-transpiler-v1
git pull --ff-only origin feat/elt-transpiler-v1
aws sts get-caller-identity --profile eletrometry-lab
```

Se há alterações locais, preserve-as antes de trocar de branch. Se o Git avisar que substituiria arquivos, pare e resolva o conflito; não use reset/clean para contornar. Se sua infraestrutura foi criada a partir de um ZIP em outra pasta, copie o código atualizado para a pasta original, preservando `infra/terraform.tfstate`, backups, variáveis e chaves. Não execute apply num clone novo sem o state que administra seus recursos.

## 3. Subir junto com o restante

Para o fluxo completo já existente, na raiz:

```powershell
.\lab.ps1 subir
```

Ele executa init/plan/apply e completa as etapas existentes de dashboards e portal via SSM. O módulo novo entra automaticamente nesse plano; não é necessário alterar o script.

Para usar só Terraform, na raiz:

```powershell
terraform -chdir=infra init
terraform -chdir=infra validate
terraform -chdir=infra plan -out=integrado.tfplan
terraform -chdir=infra apply integrado.tfplan
terraform -chdir=infra output -json transpiler
```

O novo provider `hashicorp/archive` é instalado no init. Revise o plano: esta mudança acrescenta o módulo `module.transpiler`; não exige destruir RDS ou EC2. Outros recursos podem apresentar mudanças devido a drift ou configurações anteriores: confira antes de aplicar.

O ZIP `infra/elt-lambda.zip` é produzido durante o plan. Preserve o ZIP e o plano até o apply, na mesma máquina. Não compartilhe o plano: ele pode conter segredos do ambiente existente. Após aplicar, pode apagar `infra/integrado.tfplan`; o próximo plan recria o ZIP. O hash do ZIP faz alterações em compiler.py, lambda_handler.py ou cabines.json atualizarem a Lambda no próximo apply.

Terraform direto provisiona o transpilador inteiro. Para concluir a instalação/atualização do portal e dashboards existentes, siga o fluxo já documentado no README (`lab.ps1 subir` ou os comandos específicos).

## 4. Testar o fluxo real automaticamente

Na raiz, usando o mesmo código do último apply:

```powershell
python -m pip install boto3
python scripts/test_transpiler_aws.py
```

O teste lê somente o output `transpiler` do state, usa seu perfil/região, confirma conta e versionamento, envia uma regra válida e uma inválida e aguarda os resultados correspondentes às versões enviadas.

Resultado esperado: `OK compiled`, `OK invalid` e a mensagem final de validação. A regra válida precisa gerar SQL e manifesto; a inválida precisa gerar um erro semântico. O teste grava pequenos arquivos no S3 e os preserva para inspeção, sem executar SQL no RDS. Tempo padrão: até 180 segundos por arquivo; ajuste com `--timeout 300`.

O usuário do teste precisa de STS GetCallerIdentity, Lambda GetFunctionConfiguration, S3 GetBucketVersioning, PutObject em entrada/, GetObject em saida/ e erros/ e ListBucket. ListBucket permite distinguir chave ainda ausente (404) de falta de acesso (403).

No primeiro uso de versionamento de um bucket, a AWS recomenda aguardar até 15 minutos antes de começar PUT/DELETE para propagação. Não automatizamos um upload de exemplo no apply. Se o primeiro teste falhar por propagação, aguarde e execute de novo.

## 5. Enviar seus próprios arquivos sem entrar no console

No PowerShell, na raiz:

```powershell
$elt = terraform -chdir=infra output -json transpiler | ConvertFrom-Json
$awsArgs = @('--region', $elt.region)
if ($elt.profile) { $awsArgs += @('--profile', $elt.profile) }
aws s3 cp transpiler/examples/temperatura.elt "$($elt.input_uri)temperatura.elt" @awsArgs
aws s3 ls $elt.output_uri --recursive @awsArgs
aws s3 ls $elt.errors_uri --recursive @awsArgs
```

Para enviar outro arquivo, troque o caminho local e mantenha a extensão minúscula `.elt`. Use UTF-8, até 64 KiB. O destino precisa estar em `entrada/`. Cada envio cria uma versão; não é necessário criar pastas previamente.

No console, a alternativa é S3 → bucket indicado no output → upload com prefixo `entrada/`. O analista ainda não tem tela de upload no portal nesta versão.

## 6. Entender os resultados

| Caminho | Conteúdo |
|---|---|
| `entrada/*.elt` | Código da linguagem enviado pelo analista. |
| `saida/<id>/regra-001.sql` | SQL de uma regra válida. |
| `saida/<id>/compilacao.json` | Manifesto, tokens, AST, consultas e versão da origem. Escrito por último. |
| `erros/<id>/relatorio.json` | Erro de linguagem com etapa e localização. |
| CloudWatch / fila SQS de falhas | Falhas operacionais, como acesso S3 negado. |

O ID considera bucket, chave, VersionId, versão do compilador e cadastro de cabines. Eventos repetidos usam a mesma chave lógica; não há ponteiro de “última regra ativa”. SQL salvo no S3 não muda as dashboards automaticamente.

A Lambda compila; não acessa o RDS e não precisa de VPC/NAT. O gatilho usa somente `entrada/` + `.elt`, evitando recursão por gravações em saida/erros/. Erros de linguagem geram relatório; falhas operacionais são tentadas novamente (até duas tentativas adicionais, idade máxima de uma hora) e podem ir para SQS. A entrega à fila também depende das permissões da role.

## 7. GitHub Actions: o que configurar

O workflow **Transpiler ELT**, em `.github/workflows/transpiler.yml`, roda em push/PR com mudanças relevantes. Ele testa o compilador, executa SQL em MySQL descartável, valida Terraform e testa o módulo com AWS simulada. Não faz `terraform apply` na sua conta.

1. No GitHub, abra **Actions** e habilite workflows caso o repositório peça.
2. Confira a execução correspondente ao commit da branch.
3. Veja os jobs `compiler` e `terraform`.
4. Os artefatos contêm o exemplo compilado e o ZIP gerado no teste do Terraform. Para implantar, o Terraform local já gera seu próprio ZIP.

**Não há secrets obrigatórios para esse workflow.** Para executar apply pelo Actions futuramente, será necessário preparar backend remoto com locking, migrar o state existente, configurar autenticação AWS e variáveis do ambiente e controlar a aplicação do plano. O state atual é local; um runner novo não o possui e poderia tentar duplicar os recursos. Também seria preciso definir os IPs de acesso explicitamente para não usar o IP temporário do runner. Por isso, esta entrega automatiza a implantação no Terraform local que você já utiliza.

## 8. Diagnóstico

| Erro/sintoma | Conferir |
|---|---|
| ExpiredToken | Reinicie/atualize as três credenciais temporárias do Lab. |
| Conta incorreta | STS e `aws_account_id`; não remova a proteção do provider. |
| iam:PassRole / role cannot be assumed | Permissão de quem executa Terraform e trust da role para Lambda. |
| AccessDenied em S3, logs ou SQS | Permissões da role de execução; erro de linguagem é diferente de falha operacional. |
| Unable to validate destination | Permissão S3 → Lambda, região e restrições do Lab. O Terraform já ordena a criação antes do gatilho. |
| Teste sem resultado | Logs, fila de falhas, extensão/prefixo, versão da origem e código local igual ao último apply. |
| BucketNotEmpty no destroy | Proteção intencional: há objetos/versões. Faça backup e avalie a exclusão completa antes de esvaziar. Não apagamos regras automaticamente. |

Para logs, reutilize `$elt` e `$awsArgs` da seção 5:

```powershell
aws logs tail $elt.log_group --since 10m @awsArgs
aws sqs get-queue-attributes --queue-url $elt.failure_queue_url --attribute-names ApproximateNumberOfMessages @awsArgs
```

S3 mantém versões até exclusão explícita; CloudWatch retém logs por 14 dias e SQS retém registros por 14 dias. Há cobrança conforme armazenamento, requisições e execução. Um `terraform destroy` pode apagar outros recursos antes de falhar no bucket não vazio: essa proteção NÃO torna o destroy do laboratório seguro.

## 9. Próximas integrações

Este apply entrega: arquivo → S3 → Lambda/transpilador → SQL ou erro no S3.
Upload autenticado no portal, execução de teste no RDS e publicação de consultas nas dashboards continuam pendentes.

Fontes oficiais:
- [Eventos S3 e Lambda](https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html)
- [Permissões de invocação](https://docs.aws.amazon.com/AmazonS3/latest/userguide/grant-destinations-permissions-to-s3.html)
- [Destinos de falha assíncrona](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-retain-records.html)
- [Versionamento e propagação inicial](https://docs.aws.amazon.com/AmazonS3/latest/userguide/manage-versioning-examples.html)
- [Archive provider](https://registry.terraform.io/providers/hashicorp/archive/latest/docs/data-sources/archive_file)
