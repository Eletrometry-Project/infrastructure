# Eletrometry — atualização visual v3

Revisão de 02/11/2026, baseada nos prints do Grafana, protótipos, PDF de métricas e arquivo metricas-dashboards Eletrometry.excalidraw.

## Instalar na AWS existente

1. Faça backup da pasta atual do projeto.
2. Extraia o ZIP em uma pasta separada.
3. Copie a pasta `observability` e o arquivo `observability-bundle.tar.gz` do ZIP para a raiz do seu projeto original, substituindo os arquivos correspondentes. Não é preciso copiar `infra` nem substituir estado Terraform, variáveis ou credenciais. O gerador continua no mesmo arquivo e o comando de empacotamento existente funciona.
4. Com o Academy Lab iniciado, perfil AWS `eletrometry-lab` atualizado, EC2 dos painéis ligada e RDS disponível, abra PowerShell na raiz do projeto original e execute:

```powershell
.\lab.ps1 dashboards
```

5. Abra a URL apresentada pelo comando e recarregue com Ctrl+F5. Use tema claro. Para coleta iniciada há pouco, selecione **10 min** ou **1 hora**. Os links e UIDs existentes foram preservados.

Esta revisão só requer o comando de dashboards. Não execute `subir`, `terraform apply` nem `atualizar` para aplicar apenas o visual. As consultas e as regras de negócio são as mesmas do pacote anterior. O instalador existente valida as consultas pelo Grafana antes de substituir os JSONs e guarda backup na EC2.

## O que mudou

- Todos os blocos Canvas foram substituídos por Stat, Bar gauge, Table e Time series. O conteúdo passa a usar o layout nativo dos painéis em vez das coordenadas absolutas que aparecem cortadas nos prints.
- Visão geral: cinco KPIs compactos; três cartões por linha, com estado, corrente e temperatura de cada fase; tabela de ocorrências ao lado, com paginação, filtros e colunas menores.
- Detalhe: estado, duas barras finas, seis indicadores, gráfico de seis séries à esquerda e carregamento à direita; desequilíbrio e valores por fase; saúde da telemetria na linha inferior.
- Fontes explícitas, azul-marinho e cores de severidade. Os cartões conservam fundo azul-marinho nas medições, e o estado tem sua própria cor.
- Atalhos de 10 minutos e 1 hora, além de dia, semana e mês.
- Pontos automáticos nos gráficos, tornando amostras isoladas visíveis. Não se preenchem lacunas com zero e não se ligam trechos sem dados.
- As consultas compartilhadas continuam centralizadas no painel 1. Não foram multiplicadas consultas históricas para cada indicador.

A organização foi adaptada ao Grafana, sem plugins adicionais, HTML com scripts ou alterações globais de CSS. A barra lateral e os filtros continuam sendo os do Grafana. A tela interna pode exigir rolagem, conforme a resolução e o zoom; os painéis deixam de depender de um canvas de tamanho fixo.

## Métricas e decisões preservadas

- Ideal de temperatura: 60 °C; atenção 70 °C; moderado 80 °C; crítico 90 °C.
- Capacidade provisória: 600 A por fase, três cabines. Ideal 396 A; atenção 455,4 A; moderado 514,8 A; crítico 574,2 A.
- Desequilíbrio: maior desvio absoluto relativo à média das três correntes válidas. Ideal até 5%; atenção acima de 5%; moderado a partir de 10%; crítico a partir de 20%.
- Regras de evento, antecipação, qualidade, duração e ausência de dados continuam em `REGRAS-DASHBOARDS.md`.
- Zero ocorrências é um resultado possível; não foram adicionados eventos fictícios para preencher a tela.
- O carregamento permanece em amperes. Ele não representa kWh, mAh, kVA ou potência.

## Leitura do Excalidraw: itens para a próxima etapa

O quadro reúne rascunhos e revisões conflitantes. Esta versão utiliza o PDF e as regras já presentes no código, sem promover todas as ideias do quadro a requisitos definitivos.

| Item do quadro | Situação / decisão necessária |
| --- | --- |
| Visão geral e detalhe do analista | Atualização visual entregue neste pacote. |
| Gestor: rankings, mapa de cabines, histórico e exposição | Próxima entrega; definir tempo de risco da planta como união temporal ou soma de horas-cabine. Os dois valores têm sentidos diferentes. |
| Ativas / desativadas e disponibilidade operacional | Precisam de cadastro ou eventos operacionais. Sensor sem atualização não comprova cabine desativada. |
| IMR em escala 0–100 | A fórmula 100 × (0,4F + 0,3T + 0,3I) não limita o resultado a 100; F=T=I=2 produz 200. Falta normalização e definição coerente do sentido do componente de intervalo. |
| Estabilidade operacional | Há faixas concorrentes de 0–3/4–10/>10 transições e 0–5/6–15/>15 por dia. Definir uma unidade e uma regra antes de implementar. |
| Índices ponderados de degradação TMD/TMDE | Podem ser indicadores convencionados pelo grupo, mas os fatores propostos não demonstram percentual físico de desgaste. O quadro tem limites diferentes dos adotados nas telas. |
| Temperatura/corrente e ΔT/A | A razão proposta está marcada para reavaliação. Tratar como hipótese; não aplicar limiares antigos sobre regras novas. |
| Probabilidade de falha | A expressão exponencial é uma hipótese de modelo, não uma probabilidade validada só por existir uma extrapolação até o crítico. Precisa de tratamento de taxa nula/negativa, histórico e avaliação. |
| Intervalo entre alertas críticos | Pode ser medido, mas não equivale automaticamente a tempo até falha física. Eventos por fase/tipo também precisam ser agrupados por incidente se essa for a unidade pretendida. |
| Antecipação de três meses | Requer histórico e processo de geração das previsões. Não há modelo de previsão implementado nesta revisão. |
| Tempo até ação / reparo | Requer registrar intervenções; retorno da leitura à faixa normal não comprova reparo. |

## Conferência após instalar

- Visão geral tem 9 painéis; detalhe tem 20. Não há Canvas.
- Cada cartão apresenta as três fases e permite abrir o detalhe mantendo o período.
- Fonte menor para textos como “Sem ocorrências”; as medições conservam unidades.
- Troque a cabine e verifique os valores. Troque Desvio para Corrente e confirme a interpretação em A.
- Se o gráfico continuar vazio com leituras recentes, abra **Inspect → Data** e **Inspect → Query**. Os prints não permitem afirmar se existe também erro de consulta, intervalo sem amostras ou problema de renderização. O visual não altera a coleta.
- “Sem dados” na telemetria não deve ser confundido com estado Normal. Examine idade e estado da leitura.
- Verifique que os horários seguem o fuso do navegador e que o intervalo escolhido contém leituras.

## Voltar à versão anterior

O instalador mantém backups em `/var/lib/eletrometry-observability/dashboard-backups/<timestamp>`. Restaure os dois JSONs do backup para `/var/lib/grafana/dashboards/`. Alternativamente, restaure a pasta `observability` do seu backup local e execute `lab.ps1 dashboards` novamente. Não apague dados do RDS.

## Limites da validação

Validação local de JSON, referências compartilhadas, IDs, grade sem sobreposições, regeneração do pacote e testes automatizados descritos em `VALIDACAO-DASHBOARDS.md`. Não foi feita implantação na sua AWS nem inspeção desta versão renderizada dentro do Grafana. O acabamento precisa ser conferido na instância após instalar; não se apresenta mockup externo como captura de Grafana.
