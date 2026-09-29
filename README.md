# Eletrometry — etapa 1, criação do zero (revisão 2)

Atualizado em 29/09/2026 após confirmação do hard reset. O MD é a especificação do ambiente a reconstruir. **Não é necessário ter VPC, EC2, RDS, fila ou regra IoT criados previamente.** Não há importações nem modos adopt/existing da infraestrutura nesta revisão.

Extraia este ZIP em uma **pasta nova**. Não sobreponha à versão anterior: arquivos antigos de importação poderiam permanecer no diretório. Esta revisão destina-se ao cenário confirmado de infraestrutura ainda não aplicada; não use a troca de arquivos como migração de um state já implantado.

## O que o Terraform cria

| Parte | Recursos |
|---|---|
| Rede | VPC, duas subnets públicas, duas privadas de banco em duas AZs, internet gateway, tabelas de rotas e associações. |
| Segurança | SGs e regras: SSH só do IP administrativo /32; MySQL só do SG da EC2; RDS sem acesso público. |
| Ingestão | Fila SQS Standard eletrometry-demo, DLQ, política de redrive e regra IoT para eletrometry/demo/+/+. |
| IAM | Por padrão, roles EC2/IoT, políticas restritas à fila e instance profile. Há opção de referenciar roles autorizadas quando o Lab impede criação de IAM. |
| SSH | Registra na AWS a chave **pública** gerada no computador. A chave privada fica somente com o usuário. |
| Banco | RDS MySQL Single-AZ, db.t4g.micro, 20 GiB gp2 por padrão, criptografado, backup e proteção contra exclusão. |
| Processamento | EC2 Ubuntu x86_64, disco criptografado e IMDSv2. Cloud-init instala o consumidor, dependências, CA do RDS e unit systemd. |

Fluxo: **simulador HTTPS no PC → IoT Core → SQS → consumidor EC2 → RDS MySQL**. O simulador existente continua sendo executado no PC.

O `apply` cria a infraestrutura e dispara a instalação dos arquivos. **A tabela, o usuário MySQL e a senha da aplicação são preparados depois com o script interativo incluído**, para não colocar senhas em user-data/state. Só depois iniciamos e testamos o serviço. O estado do cloud-init deve ser conferido: EC2 criada não comprova instalação bem-sucedida.

## Por onde começar

1. Ler `docs/IMPLANTACAO.md`, voltado a PowerShell/Windows.
2. Gerar uma chave SSH local ou indicar uma chave de laboratório já disponível.
3. Copiar `infra/terraform.tfvars.example` para `infra/terraform.tfvars`; ajustar seu IP público. A conta informada no inventário já está no exemplo.
4. Conferir se o Lab permite criar IAM; se exigir roles próprias, configurar as opções documentadas. Terraform não altera as roles protegidas do Lab.
5. Executar init, validate e testes; gerar e revisar plan; só depois executar apply.
6. Seguir a preparação do banco/serviço e os testes de aceite.

Não é necessário rodar inventário antes. O script `scripts/inventory.py` continua disponível para diagnóstico **após** a criação. Não é uma etapa de provisionamento.

## Arquivos importantes

- `infra/terraform.tfvars.example`: única configuração de exemplo para a aplicação.
- `scripts/terraform.ps1`: pede a senha administrativa sem eco; separa ações Plan e Apply; não grava a senha no tfvars.
- `deploy/`: instalador, adaptador systemd e preparação do banco.
- `bootstrap-state/`: bucket de state opcional para operação em equipe, separado do futuro data lake.
- `docs/ARQUITETURA.md`, `docs/TESTES.md`, `docs/VALIDACAO.md`: decisões, aceite e limites da verificação.

**Load balancer: mantido no planejamento da etapa 2**, junto de site/Grafana; não é criado nesta etapa. As duas subnets públicas já permitem preparar essa evolução. Etapa 3: ingestão histórica S3, Glue/PySpark, Trusted e Athena. Bastion, Docker, servidores privados e saída de rede da aplicação serão definidos na etapa 2.

As permissões efetivas, tipos/versões permitidos e custos dependem da conta. Esta entrega não foi aplicada à AWS. O usuário precisa fornecer somente entradas do novo ambiente e recursos de IAM do Lab se a conta os exigir; nenhum ID da infraestrutura apagada é necessário.
