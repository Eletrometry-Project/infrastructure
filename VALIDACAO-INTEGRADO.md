> Registro da versão integrada anterior. Para esta atualização, veja VALIDACAO-DASHBOARDS.md.

# Validação — pacote integrado, 05/10/2026

## Verificações concluídas

- **9 testes Python** de configuração e contrato: leitor MySQL SELECT/TLS, reutilização sem senha mestre, falha sem falso estado pronto, isolamento das credenciais do datasource, arquivo de autenticação Neo4j, filtro comum dos seis painéis, tamanho do user-data, erro SQL não escondido pelo HTTP e permissões dos arquivos.
- **2 testes com Terraform 1.11.4 e PowerShell 7.5 reais**, usando states fictícios locais: migração do recurso completo com duas instâncias `for_each`, criação de backups, preservação dos IPs, segunda execução sem duplicação e interrupção preventiva diante de recurso desconhecido. Nenhuma chamada AWS nesses testes.
- Parser PowerShell: `lab.ps1`, `grafana.ps1` e `migrate_grafana_state.ps1` sem erros. A execução no Windows PowerShell 5.1 ainda depende de teste no PC do usuário; os scripts usam sintaxe compatível.
- `terraform fmt -check` passou; arquivos HCL analisáveis. Não equivale a validar os schemas do provider ou planejar contra a conta real.
- Bash/sh sem erros de sintaxe; fontes Python compiladas.
- User-data representativo dos painéis: **12.143 bytes comprimidos**, abaixo dos 16.384 bytes permitidos pela EC2. O Terraform também contém uma precondição de tamanho para o payload real.
- Tag `neo4j:5.26.30-community` confirmada na API oficial do Docker Hub com arquitetura amd64.
- Dashboard e arquivos de reparação empacotados, sem states, credenciais reais, chaves privadas ou caches de providers.

## Limites

O ambiente de preparação bloqueia sockets Unix locais, necessários à execução dos providers Terraform. Por isso, não foi possível concluir `terraform validate`/`plan` com os providers aqui. `lab.ps1 subir` executa essa validação no PC antes da migração/aplicação e interrompe em erro.

Não há Docker disponível aqui para construir/iniciar o container nem acesso à conta AWS do usuário. A imagem personalizada será construída na EC2 a partir da imagem oficial; sua inicialização e as consultas reais serão verificadas no ambiente AWS pelo bootstrap e por `lab.ps1 paineis`.

Nenhuma infraestrutura foi aplicada e nenhum banco real foi alterado durante a preparação. Os testes locais não garantem permissões/cotas do AWS Academy, disponibilidade de downloads APT/Docker Hub, rede ou recursos suficientes para a carga futura.

## Aceite no ambiente AWS

1. `lab.ps1 subir`: validação e plano; verificar que RDS e consumidor não serão destruídos/recriados; aplicar.
2. `lab.ps1 status`: consumidor/simulador ativos; consulta Grafana → RDS bem-sucedida; Neo4j `RETURN 1` bem-sucedido; target ALB healthy.
3. Abrir o Grafana e alternar as cabines com leituras recentes.
4. Abrir Neo4j Browser e executar `RETURN 1 AS funcionando;`.
5. Para confirmar reinicialização, depois de salvar o trabalho, reiniciar a EC2 dos painéis pelo console; aguardar SSM e repetir `lab.ps1 paineis`. Não é necessário repetir apply ou reinstalar serviços.

Esta entrega deixa o Neo4j pronto, mas vazio. Importar/modelar/sincronizar telemetria nele é uma etapa posterior.
