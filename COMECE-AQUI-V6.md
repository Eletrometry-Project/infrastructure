# Correção v6: cinco telas, resumos e confirmação de instalação

> Atualização de desempenho: consulte **MELHORIA-DESEMPENHO.md**. Esta revisão inclui ingestão em lotes e exige `lab.ps1 atualizar`, além de `lab.ps1 dashboards`.

O print recebido mostrava três dashboards. O pacote anterior tinha cinco JSONs, mas o bootstrap copiava explicitamente só três. Não foi possível verificar qual comando/versão rodou na AWS. Nesta entrega, o provisionador copia todos os JSONs disponíveis, e `lab.ps1 subir` chama o instalador das cinco ao terminar. `lab.ps1 dashboards` continua sendo o caminho para atualizar a instância existente.

## Instalar na instância existente

1. Faça uma cópia de segurança da pasta original.
2. Extraia este ZIP em uma pasta separada.
3. Copie `lab.ps1`, `observability`, `observability-bundle.tar.gz` e `scripts` para o projeto original. Preserve `infra`, estado, variáveis e credenciais.
4. Se você fez uma correção local no transporte SHA-256, preserve-a no helper `scripts/send_text_ssm.ps1`, incluindo os cinco nomes na lista permitida.
5. Abra PowerShell na pasta original e execute:

```powershell
Unblock-File .\lab.ps1
Unblock-File .\scripts\send_text_ssm.ps1
.\lab.ps1 dashboards
```

O início deve mostrar `ELETROMETRY v6 - instalacao de CINCO dashboards`. Se não mostrar, o arquivo lab.ps1 executado ainda é outro.

Só considere a implantação confirmada quando terminar com:

```text
CONFIRMADO: 5/5 dashboards da entrega v6 carregadas no Grafana.
```

A confirmação consulta individualmente os cinco UIDs na API, verifica títulos, tags e configurações fornecidas dos painéis (aceitando propriedades padrão adicionadas pelo Grafana). O comando também imprime os cinco caminhos. Não basta copiar os arquivos ou contar três dashboards antigas.

No Grafana, recarregue a pasta Eletrometry. Devem existir:

1. 01 · Analista — resumo e prioridades
2. 02 · Analista — investigar cabine
3. 03 · Gestor — resumo da planta
4. 04 · Gestor — histórico da cabine
5. 05 · Gestor — tendências e projeções

Todas terão a tag `entrega-v6`. Se falhar, envie a saída completa a partir da mensagem ELETROMETRY v6, sem senhas. Não rode Terraform apply para tentar corrigir a exibição.

## Organização para leitura

O resumo do analista apresenta quantas cabines estão em alerta, críticas ou sem dados, seguido de uma tabela de prioridades com situação, próximo passo e link para investigação. Os indicadores históricos planejados ficam abaixo. Não há seis curvas competindo pela atenção na entrada.

O resumo do gestor apresenta estado da planta, alertas críticos, tempo acumulado de risco e quantidade de cabines. Os gráficos respondem: quais problemas ocorreram, onde houve mais alertas e onde o risco durou mais. O mapa permite abrir o histórico.

As medições por fase, taxa térmica, desvios, saúde e curvas técnicas ficam na investigação. O detalhe passa a abrir por padrão em uma hora; links com um período explícito preservam esse período. Se só houver alguns minutos de coleta, escolha 10 min para não comprimir todas as curvas na borda de um gráfico de 24h.

O guia `GUIA-DASHBOARDS.md` continua detalhando fórmulas, limites e simulação. A v6 não transforma projeções demonstrativas em previsões validadas, nem preenche disponibilidade operacional com valores inventados.

## Validação

Nove testes de integração existentes aprovados. Verificação estrutural de cinco JSONs e teste do instalador com API simulada, incluindo confirmação dos cinco UIDs. Sem implantação remota, teste SQL no seu RDS ou conferência visual no Grafana. A nova mensagem de confirmação deverá ser obtida na sua instalação.
