# Portal Eletrometry
O console tem duas dashboards de analista e três de gestor. Analistas acessam o resumo operacional e a investigação por cabine. Gestores acessam as cinco, incluindo o panorama da planta, histórico e tendências. A página de apresentação continua pública dentro da audiência do site.

## Site privado
Clique em Registre-se e informe seu nome usando sua identidade autenticada no Sites. O servidor vincula o cadastro persistente a essa identidade. Login recupera o cadastro. A lista administrativa MANAGER_EMAILS, configurada no ambiente do site, identifica os gestores pelo e-mail verificado da sessão. O formulário não concede permissões. A conta proprietária está configurada como gestora. Para outras pessoas usarem o site privado, conceda acesso ao site e só depois atribua o perfil, caso precisem ser gestoras. Os números identificados como demonstração são ilustrativos. O modo externo requer um Grafana HTTPS com sessão própria e permissões nativas configuradas.

## Instalação do laboratório na AWS
O portal roda em Docker na EC2 de frontend. Siga [PORTAL-AWS.md](../PORTAL-AWS.md) para publicar, abrir o IP por HTTPS, atribuir perfis e conferir os testes com o Grafana privado. O pacote de implantação usa o build compilado em dist e o servidor Node. Para reconstruí-lo, rode npm ci, npm run build e, a partir da raiz do projeto, python scripts/build_frontend_bundle.py.

## Desenvolvimento e verificação
    
    npm ci
    npm run build
    node tests/access.mjs
    
Para usar o servidor local sem Terraform, defina GRAFANA_URL com a origem do Grafana e execute node server.mjs. Para gerar o Worker da edição hospedada, execute node build-worker.mjs após o build. As rotas hospedadas usam a identidade do Sites e a base D1; as locais usam SQLite e sessões HttpOnly. A integração real com a AWS e o resultado visual no navegador precisam ser conferidos no ambiente de destino.
