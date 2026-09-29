# Evidências e limites da validação

Revisão 2: 29/09/2026. Criação do zero, sem importação de infraestrutura. Nenhuma credencial da conta do grupo foi usada.

| Verificação | Resultado |
|---|---|
| Repositório do consumidor | Acessado e revisado no commit `038b257430c7fbad19cf0d42d7353a4f795eb5d3`. Confirmados contrato, TLS, ordem INSERT/COMMIT/DeleteMessage e tratamento de duplicatas. |
| Terraform CLI | 1.13.5, arquivo conferido pelo SHA-256 do manifesto oficial. |
| `terraform init -backend=false` em `infra/` | Concluído. Provider oficial AWS 6.66.0 instalado; lockfile incluído. |
| `terraform fmt -check -recursive` | Concluído sem diferenças; sintaxe aceita pelo formatador HCL. |
| `bash -n deploy/install.sh` | Concluído. |
| Compilação Python (`compileall`) | Concluída para scripts, adaptador e testes. |
| Testes Python | **9 testes passaram** usando o código real do consumidor com AWS/MySQL simulados. |
| `terraform validate` | **Não concluído.** O provider não consegue iniciar o canal local de comunicação neste ambiente: `listen unix ...: socket: operation not permitted`. |
| `terraform test` | **Não concluído pelo mesmo bloqueio de comunicação com o provider.** Há sete cenários preparados em `infra/tests/security.tftest.hcl`. |
| Plan/apply com AWS real | Não executados. Dependem de credenciais locais do laboratório e configuração do novo ambiente e permissões do Lab. |
| Conexão TLS, migrations MySQL, reboot e ingestão real | Pendentes de execução na EC2/conta do grupo. |

Os testes Python cobrem confirmação somente após commit, preservação em falha MySQL, continuidade após mensagem inválida, confirmação de duplicata reportada pelo banco, consistência qualidade/NULL, bloqueio de planos destrutivos, entrega da credencial ao adaptador com TLS e gravação atômica do arquivo com modo 0600. O teste de duplicata usa rowcount simulado; a garantia real da chave primária deve ser conferida no MySQL com republicação do evento.

A formatação e os testes Python não substituem validação de schema do provider, plan ou aceite AWS. Antes de aplicar, executar `terraform validate` e `terraform test` em um ambiente onde o provider possa iniciar. O subprojeto de backend S3 foi formatado, mas também requer seu próprio init/validate/plan na máquina do operador.

O script PowerShell foi revisado, mas não executado neste ambiente Linux; sua execução permanece pendente no Windows do operador.

## Reproduzir os testes locais

Na raiz do pacote, com Python 3.12 recomendado e Bash/WSL:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r deploy/requirements.lock.txt
git clone https://github.com/Eletrometry-Project/sqs-consumer.git ../sqs-consumer-tests
git -C ../sqs-consumer-tests checkout --detach 038b257430c7fbad19cf0d42d7353a4f795eb5d3
CONSUMER_REPO_PATH="$(realpath ../sqs-consumer-tests)" .venv/bin/python -m unittest discover -s tests -v
cd infra
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform test
```

Os logs `synthetic failure` e `mensagem ... invalida` nos testes Python são falhas propositalmente simuladas; a linha final deve indicar nove testes e `OK`. Os testes Terraform usam mock provider explicitamente, sem credenciais AWS. A verificação real de permissões da conta acontece no plan/implantação e nos testes de aceite.
