# Executar o simulador em outro computador ou pasta

O simulador envia para o **AWS IoT Core da sua conta**, não diretamente para o IP da EC2. A regra do IoT encaminha para a SQS `eletrometry-demo`; o consumidor na EC2 grava no RDS; o Grafana lê o RDS. Mudar de pasta ou computador não exige mudar EC2, banco ou dashboard.

## O que precisa corresponder

| Item | Valor neste laboratório |
| --- | --- |
| Conta | A mesma conta em que o Terraform criou IoT/SQS/EC2/RDS |
| Região | `us-east-1` |
| Perfil AWS local | `eletrometry-lab`, com credenciais atuais do Lab e token de sessão |
| Destino | `--destino iot` (o padrão do simulador é arquivo!) |
| Prefixo de tópico | `eletrometry/demo` |
| Cabines | `cabine-001` a `cabine-003` com `--cabines 3 --primeira-cabine 1` |
| Endpoint | Descoberto na conta/região pelo SDK; `--endpoint` opcional usa somente o hostname |

A credencial precisa autorizar `iot:DescribeEndpoint` e `iot:Publish` nos tópicos do laboratório. Não use a senha do banco como credencial AWS. Se rodar na EC2 com instance profile, omita `--profile`; em outro PC, configure o perfil local.

## Windows: exemplo completo

Instale Python 3.11 ou mais recente, Git e AWS CLI. No PowerShell, em uma pasta da sua escolha:

```powershell
git clone https://github.com/Eletrometry-Project/telemetry-simulator.git
cd telemetry-simulator
# Versao compativel com o consumidor e o pacote desta entrega:
git checkout 866a56ea07f48e18773d27288cc20ed97f90f4f1
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Configure/atualize o perfil **localmente** com as credenciais fornecidas pelo Lab. A chave, segredo e `aws_session_token` expiram e podem mudar a cada sessão. Não salve essas credenciais dentro do projeto e não as envie no chat ou no Git.

Confira o destino antes de publicar:

```powershell
aws sts get-caller-identity --profile eletrometry-lab --region us-east-1 --no-cli-pager
aws iot describe-endpoint --endpoint-type iot:Data-ATS --profile eletrometry-lab --region us-east-1 --no-cli-pager
```

A conta deve ser a mesma do projeto (compare com `terraform -chdir=infra output -json lab` na pasta original da etapa 1). Em vez de colar o endpoint antigo das mensagens, deixe o simulador descobrir o endpoint atual.

Execute por dois minutos:

```powershell
.\.venv\Scripts\python.exe .\simulador_eletrometry.py simular --config .\config_industrial.json --cabines 3 --primeira-cabine 1 --executor pc-caue --duracao 120 --modo tempo-real --destino iot --regiao us-east-1 --profile eletrometry-lab
```

Para continuar até Ctrl+C, substitua `--duracao 120` por `--continuo`. A janela precisa permanecer aberta. Os argumentos ficam na linha de comando; não é necessário editar o código nem colocar o IP da EC2 no simulador.

## Evitar duas fontes para a mesma cabine

Seu simulador da EC2 já está ligado. Para substituir temporariamente as três cabines por dados do seu PC, primeiro, **na pasta original do Terraform**:

```powershell
.\lab.ps1 parar
```

Depois rode o comando de simulação no PC. No fim, pare o simulador do PC e volte à pasta original para:

```powershell
.\lab.ps1 iniciar
```

`parar` não desliga o consumidor nem o RDS. `--executor pc-caue` distingue a execução, mas o dashboard agrupa por `cabine_id`: dois simuladores na mesma cabine misturam as curvas. Se a ideia for adicionar outra cabine ao mesmo tempo, use `--cabines 1 --primeira-cabine 4 --executor pc-colega`; recarregue o dashboard para aparecer `cabine-004` no filtro.

## Se não chegar nada

1. Confirme `--destino iot`; sem isso os dados ficam em arquivo local.
2. Confira conta, região, credenciais temporárias, token de sessão e prefixo de tópico.
3. Observe erros no terminal. No seu teste anterior, a publicação do PC falhou por conexão ao endpoint, enquanto o envio pela EC2 funcionou. Isso não prova bloqueio da operadora, mas torna útil testar outra rede se o problema repetir.
4. Veja `lab.ps1 status` e o período do Grafana. Use relógio correto e `tempo-real`; não use uma data antiga em `--inicio`.
5. Em falha de envio, o simulador guarda pendências locais e informa o comando de reenvio. Reenvie com o mesmo perfil/região; não considere arquivos gerados como confirmação de publicação.

Não abra MySQL ou SSH para permitir que o PC simule: a comunicação de publicação é HTTPS com o endpoint IoT.


## Dashboards com eventos de 10 segundos

Use o simulador deste pacote com `--temperatura-intervalo 1`. Sem a opção, temperatura segue a cadência original de 30s e não permite confirmar eventos térmicos de 10s.
