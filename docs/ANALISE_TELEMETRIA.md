# Analise da integracao — 04/10/2026

## Comprovado no historico do laboratorio

- Em 30/09, SSM confirmou cloud-init concluido, consumidor ativo e acesso a `eletrometry.leituras`.
- A publicacao do computador falhou por conectividade ao endpoint IoT.
- Um teste publicado de dentro da EC2 terminou com sucesso: um event_id encontrado no MySQL,
  exatamente uma linha, A=100/B=101/C=102. Isso comprova o caminho basico naquele momento.
- A rota, grupo de seguranca e ACL verificados estavam coerentes. SSH continuou com timeout.
  O uso de dados moveis e uma hipotese para a conectividade, nao causa comprovada.
- Nao foi fornecido resultado da execucao de 120 segundos do repositorio original.
  Nao ha evidencia de que essas 372 mensagens tenham sido geradas/publicadas/gravadas.

## Lacunas confirmadas no codigo anterior

1. Terraform instalava somente consumidor; nao havia produtor continuo de telemetria.
   Consumidor ativo com tabela vazia e possivel: ele apenas aguarda mensagens.
2. `lab.ps1` dependia de SSH para status/consulta e publicava IoT a partir do PC. Ambos falharam
   na conexao observada, impedindo a verificacao mesmo com a aplicacao acessivel via SSM.
3. O simulador original tem `--destino arquivo` como padrao. Executar sem `--destino iot`
   apenas arquiva localmente; nao envia dados para a AWS.
4. `--duracao 120` encerra a geracao apos dois minutos. Para gerar sempre, precisa `--continuo`.
5. A leitura vazia observada nao confirma defeito no schema. Pode ser outro host/banco,
   recursos recriados apos reset, ausencia de publicacao ou falha posterior. Sem consultas atuais
   a AWS nao e possivel atribuir a causa exata da tabela vazia relatada em 04/10.

## Contrato verificado localmente

Gerados 120 segundos acelerados com o simulador original, tres cabines e perfil industrial.
As 372 mensagens passaram pela funcao real `row_from_body` do consumidor original:
120 correntes e 4 temperaturas para cada cabine. Schema v1, IDs, timestamps com fuso,
campos valores/qualidade e agrupamento A/B/C sao compativeis nesse cenario.
Este teste local nao comprova permissoes AWS nem escrita real no RDS.

## Correcao incluida

- Fontes originais incluidas no ZIP; commits identificados em `FONTES.md`.
- Simulador continuo em systemd, na mesma EC2, com instance profile existente.
- SSM como caminho padrao para administrar e publicar testes de dentro da EC2.
- Atualizacao da aplicacao sem alterar RDS, senha ou state.
- Teste finito compara os event_ids arquivados pelo simulador com as linhas MySQL do mesmo run_id;
  aceita somente igualdade exata, agrupada por cabine/tipo. Aceite IoT sozinho nao e sucesso.
- Teste de uma mensagem publica 1 evento e verifica tambem valores A/B/C.
- Status imprime host efetivo, schema, tabela, ultimas leituras, servicos e estado aproximado SQS/DLQ.

Para investigar uma falha atual, envie as saidas de `lab.ps1 status`, `lab.ps1 simular` e,
se necessario, `lab.ps1 logs`. Nao envie senhas, state nem credenciais AWS.
