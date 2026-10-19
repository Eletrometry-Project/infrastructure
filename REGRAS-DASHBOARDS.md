# Regras provisórias das dashboards — 07/10/2026

Os KPIs/gráficos seguem os protótipos do grupo. As definições abertas foram preenchidas provisoriamente, conforme autorização do Cauê. Não são parâmetros certificados ou validação elétrica em campo.

## Limites e coleta

- Cabines cadastradas: 001, 002 e 003; R=A=fase 1; S=B=fase 2; T=C=fase 3.
- Capacidade provisória: **600A por fase** em todas. Não representa a especificação do sensor físico ou a soma trifásica; conferir TC/escala/circuito antes de uso real.
- Ideal de corrente: **396A** (0,66×600). Atenção ≥455,4A; moderado ≥514,8A; crítico ≥574,2A, pelos percentuais exatos.
- Ideal de temperatura: **60°C**; atenção ≥70°C; moderado ≥80°C; crítico ≥90°C. Esses limites explícitos prevalecem sobre os percentuais.
- A igualdade pertence à faixa mais grave. Abaixo do primeiro limite é normal, embora possa estar acima do ideal.
- Simulador integrado: corrente e temperatura por segundo. Avulso: usar `--temperatura-intervalo 1`; sem a opção, permanece o padrão original de 30s.
- Corrente e temperatura não são diretamente proporcionais. O gráfico mostra relação/atraso térmico; não diagnostica defeito apenas porque as curvas não se acompanham.

## Eventos

Evento por **cabine + tipo + fase**. Começa na primeira amostra em atenção ou pior, confirmado após 10 segundos contínuos. Elevar severidade não gera outro evento; sua classe final é a maior severidade observada.

Antecipação: aumento ≥20% sobre a média das amostras dos 10 segundos anteriores, com valor já em alerta e temperatura ≥70°C na mesma fase nos últimos 5s. Vale para corrente e temperatura. Sem referência anterior válida e positiva, não antecipa.

Termina ao voltar abaixo de atenção, receber qualidade inválida ou haver lacuna >5s. Sem histerese adicional. Fases diferentes geram eventos independentes.

Durações somam intervalos entre amostras válidas consecutivas, mantendo o valor da primeira até a seguinte. Lacunas >5s e tempo depois da última amostra não são contabilizados. Isso estima tempo observado, sem provar o estado entre medições.

Lê-se 60s antes do período para reconhecer eventos já em curso. Eventos mais antigos têm início truncado. Não há tabela persistente de incidentes; para continuidade histórica exata será necessária materialização de eventos.

## Visão geral

| KPI | Regra |
| --- | --- |
| Quantidade de Alertas Críticos | Eventos confirmados que atingiram crítico e têm amostras no período; não conta mensagens. |
| Cabine Mais Crítica | Maior soma de segundos críticos por fase. Desempate: quantidade de eventos críticos, total de eventos, identificador. Sem eventos: Nenhuma ocorrência. |
| Tipo de Alerta Com Mais Problema | Mais eventos confirmados; desempate por tempo crítico e nome. |
| % de cabines com ocorrências registradas | Cabines com ≥1 evento / cabines cadastradas ou observadas no período ×100. |
| Índice de cabines com reincidência de alertas | Cabines com ≥2 eventos / mesmo denominador ×100. Não exige mesma fase/tipo. |
| Visão das Cabines | Último valor por tipo/fase dentro do período. Estado instantâneo=pior faixa; cinza se faltar canal válido ou idade >60s. Clique mantém cabine e período. |
| Alertas das Cabines | Até 50 eventos confirmados mais recentes, com fase, máximo, unidade e confirmação. Um evento histórico pode já ter terminado. |

O denominador inclui as três cadastradas mesmo quando uma não envia. Zero alertas não comprova telemetria suficiente; confira saúde e cartões.

## Dashboard interna

| KPI/gráfico | Regra |
| --- | --- |
| Temperatura / Corrente da cabine | Maior valor válido entre fases no fim do período. Estado instantâneo, independente da confirmação de 10s. |
| Tempo total de Desvio | Tempo da maior fase acima do ideal, para a métrica selecionada; união das fases, sem triplicar segundos. |
| Desvio Atual | Maior valor atual − ideal; °C ou A conforme seleção. Pode ser negativo. |
| Em nível crítico | Tempo com a maior fase ≥ limite crítico, para a mesma métrica. |
| Margem até o crítico | 90°C − maior temperatura; negativo quando acima do crítico. |
| Taxa de Variação | Maior temperatura atual − média da maior temperatura entre 55 e 65s antes do fim do período, em °C/min. Sem referência: Sem dados. |
| Tendência | Alta >+0,05°C/min; queda <−0,05; estável no intervalo intermediário. |
| Corrente e Temperatura por Fase | Seis séries A/B/C. Temperatura contínua, corrente tracejada, cor por fase; dois eixos com unidades próprias; média por intervalo visual. |
| Desequilíbrio entre fases | 100×máximo de \|fase−média\|/média. Sem três correntes válidas ou com média zero, não calcula. Ideal≤5%; atenção>5%; moderado≥10%; crítico≥20%. |
| R/S/T e desvios | Corrente, diferença absoluta e percentual em relação à média. Maior fase = maior corrente; empates priorizam R, depois S. |
| Média das fases | Média aritmética das três correntes válidas. |
| Carregamento da cabine | Média das três correntes por amostra; exige três valores válidos. Curva agregada por intervalo visual. |
| Pico do dia | Maior média trifásica das últimas 24h até o fim do período, limitada aos dados selecionados. Primeiro horário do máximo. |
| Duração no pico | Soma de intervalos com média ≥95% desse pico, nessa mesma janela. |
| Padrão calculado | Média das médias trifásicas válidas do período. Referência estatística, distinta do ideal de 396A. |
| Saúde da Telemetria | Tipo/fase selecionável, medição, faixa, idade e estado; correntes R/S/T individuais. Atrasado≥15s; sem atualização≥60s. Idade usa coleta relativa ao fim do período. |
| Possível valor travado | Valor igual por aproximadamente 5min, ≥250 amostras válidas e amplitude temporal ≥295s. Mostra Valor constante; não afirma defeito. |

## Ausência, filtros e limites

Só qualidade `ok` entra como valor. Inválidos/nulos não viram zero. Mostradores podem exibir a última medição antiga, acompanhada de idade/estado. Em períodos históricos, atual significa o fim do período.

Período padrão 24h; atalhos dia/semana/mês e início/fim nativos. O gráfico por fase tem atalhos minuto/hora/24h. Atalhos alteram o período da dashboard, mantendo comparabilidade. Atualização visual a cada 30s.

Temperatura antiga a cada 30s não comprova eventos de 10s: essas lacunas não entram nas durações. Os gráficos continuam mostrando as amostras disponíveis.

Consultas somente SELECT via leitor TLS, sem alteração de schema, e-mail ou regra de notificação. Resultados são compartilhados entre painéis. Semana/mês com milhões de leituras podem ficar lentos no RDS pequeno; a evolução é agregação incremental/eventos persistidos, preservando KPIs.

Parâmetros: `observability/analysis_rules.json`; fórmulas: `dashboard_sql.py`; apresentação: `build_dashboard.py`. Ao alterar, execute `python scripts/build_observability_bundle.py` e depois `./lab.ps1 dashboards`. O ZIP já vem gerado; Python não é necessário para apenas instalar.

Os medidores visuais desta versão pressupõem capacidade igual em todas as cabines. Para capacidades diferentes, ajustar também os medidores; não basta mudar as capacidades nas consultas.

Canvas, Stat, Bar gauge, Time series e Table são nativos. Navegação, seletores, lista e espaçamentos seguem o Grafana; não é reprodução pixel a pixel da barra lateral de um site separado.
