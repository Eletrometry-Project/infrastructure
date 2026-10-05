# Validacao desta entrega — 04/10/2026

## Executado localmente

- 18 testes Python aprovados: bootstrap, TLS/credenciais, commit antes de apagar SQS,
  duplicatas, mensagens invalidas, falha no banco, teste de uma mensagem e verificacao por run_id.
- Teste novo executa o simulador REAL (120 segundos acelerados, 3 cabines) e passa as 372
  mensagens pela validacao REAL do consumidor. Resultado: 120 correntes + 4 temperaturas por cabine.
- Verificador recusa contagem correta com IDs errados, eventos ausentes e teste vazio.
- Falha de publicacao nao executa a etapa que poderia anunciar sucesso no MySQL.
- Fontes Python incluidas conferidas byte a byte por SHA256 com os dois commits upstream.
- PowerShell 7.4.6: sintaxe aprovada; execucoes simuladas de atualizar/status/simular,
  rejeicao de EC2 offline e comando SSM Failed. Upload em partes recomposto byte a byte,
  igual ao app-bundle.tar.gz, com endpoint correto. APIs AWS foram simuladas nesses testes.
  Sintaxe escrita para PowerShell 5.1, mas nao houve execucao em Windows real nesta entrega.
- bash -n nos instaladores; terraform fmt -check; todos os arquivos HCL parseados.
- Cloud-init equivalente com valores sinteticos: aproximadamente 13,3 KiB apos gzip,
  abaixo de 16 KiB. O tamanho exato depende dos valores reais.

## Limites

- Nao houve acesso a conta AWS do usuario, apply, execucao SSM real desta revisao ou consulta atual ao RDS.
- terraform init concluiu. terraform validate falhou por divergencia de checksum do provider AWS
  em cache neste ambiente. Nenhuma verificacao de checksum foi desabilitada.
  Terraform validate e terraform test completos continuam pendentes no computador do usuario.
- O teste real anterior de 1 mensagem via SSM foi bem-sucedido no Lab conforme saida enviada em 30/09.
  Isso nao valida automaticamente a nova execucao continua ou o teste de 372 eventos.
- Nao foi alterado nem publicado codigo nos repositorios GitHub. O ZIP inclui copias dos commits.

Para a instalacao existente, use a atualizacao da aplicacao via SSM; nao precisa de apply.
Conclua a verificacao remota com `lab.ps1 simular` e `lab.ps1 status`.
