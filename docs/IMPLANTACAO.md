# Implantacao — revisao 4

## Atualizar uma instalacao anterior

Use o procedimento do README: copie somente `lab.ps1` e `app-bundle.tar.gz` para a pasta
original que contem o state. Execute `atualizar`, `simular` e `status`.
Essa rota modifica a aplicacao na EC2 existente por SSM, mantem o banco e inicia o simulador continuo.
Nao exige novo apply. Uma breve pausa do consumidor durante a instalacao e esperada; a SQS mantem mensagens.
Atualizar nao redefine senhas nem cria tabelas. Se a instalacao inicial nao terminou, consulte logs primeiro.
A API de atualizacao permite comandos no servidor usando as permissoes ja fornecidas pelo Lab.

## Instalacao nova

Execute `lab.ps1 subir`. Revise conta e plano. O bootstrap usa commits fixos, instala dependencias,
configura schema/usuario e inicia consumidor e simulador. Aguarde e execute `status` e `simular`.
SSM precisa ficar Online; o instance profile e a conectividade de saida sao pre-requisitos.
Nao copie state de outra conta nem use um state vazio para recursos ja existentes.

## Erros

| Sintoma | Proximo passo |
|---|---|
| EC2 nao Online no SSM | Inicie Lab e EC2; confira credenciais, agente e profile. |
| ExpiredToken | Atualize access key, secret key e session token no perfil local. |
| AccessDenied | Envie acao/recurso do erro. Nao e corrigido criando IAM no Lab. |
| Simulador ativo, tabela vazia | Rode `testar`, `simular` e `logs`; confira host impresso em `status`. |
| Teste IoT aceito, eventos faltando no banco | Confira SQS/DLQ e logs do consumidor; nao marque como sucesso. |
| `lab_remote.py` ausente | Execute `atualizar` na pasta original. |
| SSM Pending por muito tempo | Confira se a instancia continua Online. CommandId esta em `.lab-last-command.json`. |
| SSH timeout | Os comandos desta revisao usam SSM; nao abra mais portas para esses testes. |
| Script bloqueado | Unblock-File lab.ps1 e politica RemoteSigned no escopo Process, conforme README. |
| Nenhum dado novo apos 120 s | `simular` e finito. `iniciar` habilita o servico continuo. |
| RDS indisponivel apos retomada do Lab | Inicie o banco e aguarde available; consumidor tenta reiniciar. |

Os fontes Terraform desta revisao alteram user-data: aplicar sobre a EC2 antiga pode substitui-la.
A atualizacao por SSM nao atualiza user-data no state. Para adotar o bootstrap novo em uma futura recriacao,
revise o plano e mantenha os arquivos/state da infraestrutura original. Dados locais da EC2 podem ser perdidos
nessa recriacao; o RDS e separado. Nao altere o banco existente para testar uma revisao da aplicacao.
