# Abrir o Eletrometry pelo IP da EC2
O portal React, a API de cadastro e o proxy dos painéis rodam na terceira EC2, dentro da imagem Docker eletrometry/portal. O navegador acessa https://IP-PUBLICO-DO-FRONTEND. Para cada iframe, o mesmo servidor encaminha a requisição para http://IP-PRIVADO-DOS-PAINEIS:3000. O Grafana consulta o RDS como antes.

## Atualizar uma instalação existente
Faça backup da pasta em que você já executa o Terraform. Extraia o ZIP em outra pasta e copie o **conteúdo da pasta eletrometry-terraform-etapa1 extraída** para a raiz do projeto existente, mesclando diretórios. Assim o Terraform encontra o novo frontend, os scripts de instalação e os arquivos de bootstrap da mesma revisão. Se você editou código próprio, compare as alterações antes da cópia.

Mantenha na pasta original o estado do Terraform (incluindo infra/terraform.tfstate quando o backend é local), os seus tfvars e as chaves do lab. O pacote contém os arquivos de exemplo e o build do portal. O cadastro desta instalação fica na EC2. Se você tinha contas em portal-react/data no computador, preserve esse diretório para consulta. A instalação não migra os cadastros locais automaticamente.

Na pasta original do lab, com o perfil da AWS ativo:

    Unblock-File .\lab.ps1
    Get-ChildItem .\scripts -Filter *.ps1 | Unblock-File
    .\lab.ps1 subir

Revise o plano. Ele acrescenta uma EC2 t3.micro, disco gp3 de 16 GiB, Elastic IP e regras de rede. Eles têm custos da AWS. A EC2 usa a subnet pública do lab e o instance profile existente. O portal aceita HTTPS na porta 443 de qualquer IPv4 por padrão. Para voltar a restringir o portal aos IPs do laboratório, defina portal_publico = false no infra/terraform.tfvars e aplique o plano. A porta 3000 do Grafana aceita conexões do grupo do frontend pela rede privada. Não é necessária porta SSH no frontend.

Após o apply, o script aguarda as EC2, instala as cinco dashboards, configura o acesso dos leitores, transfere o pacote compilado via SSM com SHA-256, constrói a imagem **na própria EC2 de frontend**, inicia o contêiner e testa a integração. A estação Windows pode ser desligada depois da instalação. O contêiner tem restart unless-stopped. O Docker e o Node locais não são pré-requisitos.

## Primeiro acesso HTTPS
Ao terminar, procure a linha **Portal React na AWS**. Para consultar o mesmo endereço:

    terraform -chdir=infra output -raw portal_url

Para o lab com acesso direto por IP, a instalação gera um certificado autoassinado específico daquele IPv4. A chave privada fica na EC2. O script copia o certificado público portal-lab.cer para o computador usando o SSM autenticado. No Windows, se você confia na instalação que acabou de executar, importe **essa cópia** para seu usuário antes de abrir o endereço em Edge ou Chrome:

    Import-Certificate -FilePath .\portal-lab.cer -CertStoreLocation Cert:\CurrentUser\Root

Abra o endereço HTTPS exibido. Cadastre uma conta. O perfil inicial é Analista e a fonte padrão da instalação AWS é o Grafana do laboratório. O portal escolhe o leitor correto no servidor, sem que o visitante forneça endereço ou credenciais do Grafana. Os visitantes podem entrar de outras redes. Para acesso sem aviso do navegador, cada computador precisa confiar no certificado do laboratório. Para uso público em produção, use um domínio e um certificado de confiança pública.

Para promover uma conta existente (e encerrar suas sessões anteriores):

    .\lab.ps1 perfil-portal -Email 'usuario@empresa.com' -Papel Gestor

Use Analista para revogar a promoção. O administrador precisa da permissão SSM da conta AWS para executar esse comando. Os cadastros e contatos ficam no SQLite persistente em /var/lib/eletrometry-frontend/data na EC2. Atualizações do contêiner preservam esse diretório. Faça backup antes de substituir ou destruir a instância.

## Verificação e recuperação
O instalador verifica, a partir da EC2 de frontend, as duas identidades nativas de leitura, permissão nas cinco dashboards, resposta HTTPS do app, cadastro temporário, acesso ao iframe e consulta real do resumo via Grafana/RDS. Exclui a conta temporária após o teste. Quando os leitores ou a configuração do proxy mudam, o Grafana reinicia para aplicar as permissões. A verificação aguarda até 60 segundos por uma permissão de leitura recém-concedida e interrompe a publicação se encontrar acesso adicional. Uma consulta válida pode retornar zero leituras quando a simulação está parada. Para gerar dados no período exibido:

    .\lab.ps1 simular -Cenario criticidades -Duracao 240

Se o Terraform já terminou e houve erro nas dashboards, rode .\lab.ps1 dashboards, depois .\lab.ps1 portal. Se só a publicação do contêiner falhou, repita .\lab.ps1 portal. O comando portal agora instala/atualiza na AWS e exibe a URL remota. Se usar terraform apply diretamente, finalize com esses dois comandos SSM. Após reparar o Grafana, execute a mesma sequência para restabelecer as ACLs e os leitores.

Se a página nem abrir, confira HTTPS, o certificado, a regra HTTPS do frontend e o estado da instância. Se a página abrir e apenas o painel falhar, confira o erro de consulta e a saída de .\lab.ps1 portal. Pelo Console AWS → EC2 → frontend → Connect → Session Manager, use sudo docker ps e sudo docker logs --tail 60 eletrometry-portal. O host precisa de saída para os repositórios Ubuntu e para obter a imagem base oficial do Node. O frontend usa auth.proxy no Grafana restrito ao seu IP privado e identidades Viewer dedicadas às equipes; cabeçalhos de identidade e cookies enviados por visitantes não são usados para autenticar a chamada ao Grafana.

A demonstração hospedada anteriormente é um ambiente separado. Para a apresentação com a telemetria AWS, use a URL https://IP-DO-FRONTEND fornecida pelo Terraform.

Para verificar o contêiner, a consulta do resumo e a porta 443 a partir do computador, execute `.\lab.ps1 verificar-portal`. Em uma instalação antiga com três dashboards, execute primeiro `.\lab.ps1 dashboards` e aguarde a confirmação 5/5. Depois execute `.\lab.ps1 portal`. Se o state ainda não tiver frontend, use `.\lab.ps1 subir`.
