# Revisão do instalador integrado — 18/10/2026

## Objetivo e limite

Preservar o provisionamento automático, as duas dashboards, seus KPIs e gráficos, e simplificar a atualização de dashboards. Esta é uma revisão funcional do instalador, não uma declaração de que o alerta Trojan:Win32/MalUri.A!cl foi corrigido. Não houve execução do Microsoft Defender neste ambiente nem implantação na AWS do usuário.

## Evidência do pacote recebido

ZIP recebido: eletrometry-terraform-etapa1(1).zip.
SHA-256 original: 877ab740bbdac818bdccb7c33fb4f8946a44320f277b2e500a34044486814b20.

O pacote corresponde ao entregue anteriormente. Os arquivos dos três tar.gz internos correspondem byte a byte aos fontes visíveis. A revisão dos caminhos do ZIP, dos scripts de instalação/atualização e dos endereços literais não identificou o componente responsável pela detecção. Essa revisão estática não substitui um antivírus e não examina os pacotes de terceiros baixados durante a instalação na EC2.

A comparação com a versão anterior mostrou que o transporte Base64 já existia antes das novas dashboards. Não há evidência suficiente para atribuir a detecção a esse mecanismo.

## Alterações verificáveis

- A ação `lab.ps1 dashboards` envia três arquivos de texto: o instalador Python e os dois JSONs. Não usa mais `dashboards-bundle.tar.gz`, Base64 ou extração de tar nessa ação.
- O transporte preserva UTF-8, limita os destinos a uma pasta temporária exclusiva e trata o conteúdo como texto literal do shell, inclusive aspas, crases e `$()`.
- Cada arquivo é conferido por SHA-256 antes de executar o instalador. SHA-256 detecta erro de transferência; não é assinatura nem atestado de segurança.
- Corrigida a gravação dos parâmetros SSM: UTF-8 sem BOM em vez de ASCII, evitando corromper acentos no novo envio de texto.
- Permanecem a validação SQL pelo Grafana antes de substituir dashboards, o backup local e a confirmação de carregamento.
- Os dois JSONs, regras, consultas, Terraform, simulador e consumidor não foram modificados nesta revisão.
- `atualizar` e `reparar-paineis` mantêm seus mecanismos anteriores. A instalação inicial por Terraform continua incluindo as duas dashboards.

## Uso

Se o download e a extração forem permitidos pelo Defender, siga `ATUALIZAR-DASHBOARDS.md` na pasta original, preservando state, variáveis e chaves. Não é necessário executar Terraform apply para atualizar um Grafana existente.

Se o alerta continuar, não restaure da quarentena e não adicione exclusões. Preserve o nome da detecção e encaminhe o mesmo arquivo para análise em https://www.microsoft.com/en-us/wdsi/filesubmission . Não renomeie ou recomprima o pacote com a finalidade de mudar o resultado do antivírus.

A nova transferência usa mais chamadas SSM e demora mais que a compactada. Nenhum novo bucket, perfil IAM, credencial ou abertura de porta é necessário.

## Validação desta revisão

PowerShell 7.5 em Linux: os três arquivos reais chegaram byte a byte iguais após transporte simulado (sem AWS), com SHA-256 correspondente. Um arquivo de teste com acentos, emoji, aspas, crases e substituição de comando chegou intacto, sem executar seu conteúdo. Destino fora da pasta temporária foi rejeitado. Foram 51 chamadas simuladas; todos os scripts PowerShell passaram pelo parser. Windows PowerShell 5.1 não foi executado neste ambiente.

A suíte integrada Python não pôde iniciar neste ambiente por ausência de `mysql.connector`. Os componentes de consulta, instalação na EC2 e geração das dashboards não foram alterados; não há uma nova validação de ponta a ponta na AWS nesta revisão.
