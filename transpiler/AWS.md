# Execução na AWS — preparação, sem implantação automática

Este pacote não adiciona recursos ao Terraform atual. O fluxo S3/Lambda precisa ser configurado e validado na conta de laboratório. Permissões do AWS Academy podem impedir a criação ou uso de roles; confirme uma role permitida antes de configurar recursos.

## Pacote e configuração

1. O workflow gera elt-lambda.zip como artefato após os testes. Alternativa local, na raiz: python -m zipfile -c elt-lambda.zip transpiler
2. Crie um bucket privado dedicado, com versionamento habilitado.
3. Crie uma Lambda Python 3.12 e envie o ZIP. Handler: transpiler.lambda_handler.handler.
4. Configuração inicial de laboratório: 256 MB, timeout 30 segundos. Ajustar após medições.
5. Configure evento S3 ObjectCreated com prefixo entrada/ e sufixo .elt. Autorize o bucket a invocar a função, restringindo SourceArn e SourceAccount.
6. Role da função: logs no CloudWatch, s3:GetObjectVersion apenas em entrada/* e s3:PutObject em saida/* e erros/*. Se usar SSE-KMS, configurar também as permissões da chave.
7. A Lambda não precisa acessar RDS nem ficar na VPC: só compila e acessa S3.
8. Envie examples/temperatura.elt em entrada/. Procure saida/<identificador>/compilacao.json e regra-001.sql.
9. Envie examples/erro-unidade.elt. Procure erros/<identificador>/relatorio.json.

cabines.json deve refletir o cadastro autorizado antes de empacotar. Upload pelo portal ainda não está implementado: usar console ou AWS CLI para este teste técnico.

## Confiabilidade

S3 pode entregar eventos repetidos ou fora de ordem. A função lê VersionId e gera uma chave determinística considerando arquivo, versão, compilador e cadastro. Repetições gravam o mesmo conteúdo lógico, embora o versionamento possa criar versões físicas adicionais.

Não existe ponteiro automático para “a última regra ativa”. Compilar uma versão não publica nem substitui a regra em produção.

compilacao.json é escrito por último; só considere uma saída completa quando esse manifesto existir com status compiled. Falhas operacionais de S3 sobem como exceção para permitir retry; erros de linguagem viram relatório. Configure destino de falha/retenção dos eventos assíncronos conforme o laboratório; não confunda erros operacionais com erros do aluno.

## Roteiro de validação

- Regra válida produz SQL e manifesto com source_version.
- Unidade incorreta produz somente relatório naquela compilação.
- Reenvio/evento repetido resulta na mesma chave lógica.
- Envio em saida/ não dispara o transpilador.
- Bucket sem versionamento causa falha explícita.
- Nenhuma dashboard existente é modificada.

Próxima entrega: portal autenticado para upload, acompanhamento dos relatórios, teste de consultas e publicação explícita da versão aprovada. Reusar autenticação do portal e scripts de observabilidade, mantendo os perfis.
