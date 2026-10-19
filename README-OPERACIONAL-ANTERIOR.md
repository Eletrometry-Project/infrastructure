# Eletrometry — etapa 1 integrada (revisao 4)

Simulador de tres cabines na EC2 → IoT Core → SQS → consumidor na EC2 → RDS MySQL.
O ZIP inclui o codigo original do simulador em `telemetry/` e do consumidor em `consumer/`.
Administracao, publicacao de teste e verificacao usam SSM (HTTPS); SSH nao e obrigatorio.
Load balancer, site e Grafana continuam na etapa 2; S3/Glue/Athena na etapa 3.

## Ja tem a infraestrutura funcionando? Comece aqui

1. Inicie o Learner Lab e atualize as credenciais do perfil `eletrometry-lab` no computador.
2. Extraia o ZIP em uma pasta separada. Copie **somente `lab.ps1` e `app-bundle.tar.gz`**
   para a raiz da pasta ANTIGA onde voce aplicou o Terraform. Substitua os dois arquivos.
   Mantenha `infra/terraform.tfstate`, `terraform.tfvars`, `.terraform` e `access` no lugar.
3. Abra o PowerShell nessa pasta antiga e execute:

```powershell
Unblock-File .\lab.ps1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
.\lab.ps1 atualizar
.\lab.ps1 simular
.\lab.ps1 status
```

`atualizar` transfere o codigo incluido neste ZIP para a EC2 e inicia a telemetria continua.
Mantem o banco, o schema, as senhas e os dados existentes. Nao executa Terraform apply.
`simular` leva cerca de 2–4 minutos e exige a chegada dos 372 eventos daquela execucao no MySQL.
`status` mostra o endpoint consultado, banco/tabela, servicos, total e ultimas leituras.
Os comandos acima sao para executar. Mensagens como `OK` sao resultados, nao comandos.
Se qualquer comando der erro, pare e envie a saida; nao repita `atualizar`/`simular` indiscriminadamente.

## Comandos de uso

| Comando | Efeito |
|---|---|
| `.\lab.ps1 atualizar` | Instala esta revisao na EC2 atual e inicia simulador/consumidor. |
| `.\lab.ps1 status` | Confere servicos, acesso ao MySQL, ultimas leituras e filas. |
| `.\lab.ps1 testar` | Publica um evento IoT na EC2 e exige 1 linha com A=100/B=101/C=102 no banco. |
| `.\lab.ps1 simular` | Executa 3 cabines por 120 s e confere os IDs de todos os 372 eventos no MySQL. |
| `.\lab.ps1 iniciar` | Habilita e inicia a telemetria continua; nao cria processos duplicados. |
| `.\lab.ps1 parar` | Para e desabilita apenas o simulador continuo; consumidor continua drenando a fila. |
| `.\lab.ps1 logs` | Mostra logs recentes dos dois servicos e estado do cloud-init. |
| `.\lab.ps1 entrar` | Sessao SSM opcional; exige Session Manager Plugin no PC. |
| `.\lab.ps1 subir` | Terraform init, validate e apply; para ambientes novos ou mudancas de infraestrutura revisadas. |

A telemetria continua permanece ativa apos `simular`: esse comando executa um teste adicional isolado
por `run_id`. Para encerrar a geracao, use `parar`. O servico habilitado reinicia com a EC2,
mas depende de o Lab, EC2 e RDS estarem ligados e das permissoes do instance profile.
A contagem total do banco pode exceder 372 porque inclui outras execucoes.
O simulador mantem arquivos locais e pendencias; em uso prolongado acompanhe espaco em disco.
Arquivos de simulacao ficam em `/var/lib/eletrometry-simulator/`; o relatorio do ultimo teste
aprovado fica em `latest-check.json`. Pendencias de uma execucao interrompida devem ser reenviadas
com o subcomando `reenviar` do simulador (consulte `telemetry/README.md`).

## Conta vazia: criacao do zero

Requisitos: AWS CLI v2, Terraform >=1.11 e <2, PowerShell 5.1 ou 7 e credenciais temporarias do Lab.
Copie `infra/terraform.tfvars.example` para `infra/terraform.tfvars` e ajuste conta/perfil quando necessario.
Execute `lab.ps1 subir`, revise o plano e aguarde o bootstrap; depois `status`, `testar` e `simular`.
O bootstrap baixa os commits fixados dos dois repositorios, instala o banco e inicia ambos os servicos.
O ZIP tambem contem essas mesmas fontes para revisao e atualizacao via SSM, sem git na EC2 atual.
O acesso a GitHub, repositorios Ubuntu e PyPI e necessario no primeiro bootstrap.

Nao aplique um state vazio sobre recursos antigos com os mesmos nomes. Nao apague o state.
Copiar a nova pasta `infra` sobre uma instalacao anterior altera o user-data e pode RECRIAR a EC2;
por isso, a atualizacao da aplicacao usa apenas os dois arquivos indicados acima.

## Permissoes e escolhas do Lab

- Nenhuma role/policy IAM e criada: usa LabInstanceProfile e uma role existente na regra IoT.
- O nome LabRole sozinho nao garante permissao. IoT precisa entregar na SQS; EC2 precisa publicar IoT,
  consumir SQS e estar Online no SSM. O perfil local precisa consultar e executar comandos SSM.
- Endpoint IoT e descoberto na conta, sem hostname fixo. O teste nunca pula IoT enviando direto a SQS.
- RDS privado, TLS, SSH restrito e senhas geradas continuam. State/user-data contem segredos do Lab;
  nao envie state, chave privada ou planos ao GitHub.
- Sem NAT Gateway, bastion, Secrets Manager ou IAM adicionais obrigatorios.
- Terraform destroy apaga o banco sem snapshot final nesta configuracao de laboratorio.

Analise e limites: [docs/ANALISE_TELEMETRIA.md](docs/ANALISE_TELEMETRIA.md).
Testes realizados: [docs/VALIDACAO.md](docs/VALIDACAO.md).
