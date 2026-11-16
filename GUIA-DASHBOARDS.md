# Eletrometry — guia das cinco dashboards e simulação

Versão 5 · 02/11/2026

## Instalação no laboratório existente

Faça backup do projeto original. Extraia o ZIP separadamente. Copie `lab.ps1`, `scripts`, `observability`, `deploy`, `telemetry`, `app-bundle.tar.gz` e `observability-bundle.tar.gz` para o projeto original, substituindo o código. Preserve a pasta `infra` com seus estados, variáveis e credenciais.

Se você corrigiu localmente `scripts/send_text_ssm.ps1` para resolver o erro SHA-256, preserve sua correção. A lista de destinos permitidos agora deve incluir `eletrometry|visao-geral|historico|gestor|tendencias`. Não remova a conferência SHA-256.

No PowerShell, com o Academy Lab iniciado e as credenciais AWS válidas:

```powershell
Unblock-File .\lab.ps1
Unblock-File .\scripts\send_text_ssm.ps1
.\lab.ps1 atualizar
.\lab.ps1 dashboards
```

`atualizar` instala o código da aplicação e reinicia o consumidor, preservando o RDS e o estado anterior do simulador (parado continua parado). `dashboards` valida e publica os cinco JSONs. Não requer Terraform apply. Para instalações novas, depois de `subir`, execute também `dashboards`: o bootstrap inicial gera as três telas base; as cinco são instaladas pelo comando de atualização.

Use os links Analista, Gestor e Tendências. O histórico abre pelo link Histórico da cabine; dele é possível abrir o detalhe operacional. A cabine e o período são preservados quando aplicáveis. Para tendências, selecione manualmente 90 dias ou mais: navegar com um intervalo curto preserva esse intervalo.

## 1. Analista — visão geral

**Pergunta de negócio:** qual cabine precisa ser investigada?

| Indicador | Como funciona |
| --- | --- |
| Alertas críticos | Eventos confirmados que atingiram a faixa crítica no período observado. |
| Cabine mais crítica | Maior soma de tempo crítico por fase; desempate por número de eventos. |
| Tipo com mais ocorrências | Temperatura ou corrente com maior quantidade de eventos confirmados. |
| Cabines com ocorrências | Cabines com pelo menos um evento / inventário cadastrado ou observado. |
| Reincidência | Cabines com dois ou mais eventos / mesmo inventário. Não exige repetição da mesma causa. |
| Tabelas das cabines | Últimas medições das fases R/S/T e pior estado observado, considerando dados ausentes ou antigos. |
| Ocorrências confirmadas | Até 50 eventos recentes; não significa que todos continuem ativos. |

Zero alertas não comprova cobertura de telemetria. A ausência deve ser investigada na saúde dos sensores.

## 2. Analista — detalhe operacional

**Pergunta:** o que está acontecendo e em qual fase?

- Temperatura e corrente: maior leitura válida entre as fases. A última leitura pode estar antiga; confira estado e idade.
- Tempo acima do ideal: união do tempo entre fases para a métrica escolhida, sem triplicar segundos.
- Desvio atual: maior leitura menos o ideal; negativo indica abaixo do ideal.
- Tempo crítico: duração observada acima do limite crítico; lacunas acima de 5 segundos não contam.
- Margem térmica: 90 °C menos a maior temperatura atual. Negativa significa limite ultrapassado.
- Taxa: temperatura atual menos a média entre 55 e 65 segundos atrás, expressa em °C/min; sem referência, não se calcula.
- Tendência: alta acima de +0,05 °C/min, queda abaixo de −0,05 e estável entre os dois.
- Curvas por fase: seis séries, corrente tracejada e temperatura contínua, eixos A e °C separados. O formato permite investigar coincidências; não prova causalidade.
- Carregamento: média das três correntes válidas. Não é energia, potência ou demanda contratada.
- Pico: maior média trifásica das últimas 24h contidas no período; tempo no pico usa ≥95% desse máximo.
- Desequilíbrio: 100 × maior distância absoluta de uma fase à média / média. Requer três correntes válidas e média positiva.
- Saúde: atraso ≥15s, sem atualização ≥60s; constância por aproximadamente cinco minutos é indício, não diagnóstico de sensor defeituoso.

## 3. Gestor — histórico da cabine

**Pergunta:** quais episódios ocorreram e como se relacionam às medições?

Contagens de eventos totais, críticos, moderados e em atenção; curvas por fase; distribuição por hora de confirmação; tabela filtrável de até 500 ocorrências. A tabela informa tipo, fase, máximo, unidade, início observado, confirmação e última leitura. Não existem registros de reconhecimento ou reparo.

O evento é definido por cabine + tipo + fase. Elevações de severidade dentro do mesmo evento não geram nova ocorrência; a classificação final é a maior observada. O gráfico horário considera confirmações dentro do período, enquanto os KPIs também podem incluir eventos confirmados antes e ainda observados no intervalo. Isso pode produzir totais diferentes.

## 4. Gestor — visão da planta

**Pergunta:** onde concentrar inspeção e manutenção?

| Painel | Interpretação |
| --- | --- |
| Eventos críticos | Quantidade de eventos confirmados classificados como críticos. |
| Estado da planta | Pior faixa das últimas leituras. A falta de canais recentes produz Dados incompletos. |
| Exposição | Soma de horas-cabine em atenção ou pior. Dentro de cada cabine, intervalos sobrepostos de fases/tipos são unidos. Entre cabines, são somados. |
| Cabines cadastradas | Quantidade configurada em analysis_rules.json, atualmente três. |
| Eventos por tipo/severidade | Barras empilhadas para temperatura e corrente. |
| Ranking de eventos | Cabines com maior número de eventos no período. |
| Ranking de exposição | Cabines com maior duração observada em risco. |
| Mapa tabular de cabines | Estado por cor e máximos de corrente/temperatura; acesso ao histórico. |

Duas cabines em risco durante uma hora representam **2 horas-cabine**, não duas horas cronológicas de risco da planta. As durações usam intervalos entre leituras válidas e não extrapolam após a última amostra.

**Ativas/desativadas e disponibilidade:** os painéis mostram falta de registro operacional. O schema recebido só armazena leituras; não permite distinguir cabine desligada, indisponível, desativada ou sem comunicação. Esses indicadores precisam de cadastro de estado e registros de operação antes de produzir valores ou donut fiel ao protótipo.

## 5. Gestor — tendências

**Pergunta:** como o comportamento mudou e qual referência simples temos para os próximos meses?

| Painel | Método desta entrega |
| --- | --- |
| Corrente média e variação | Média das três fases válidas; comparação percentual com janela imediatamente anterior de mesma duração. Denominador ausente/zero gera sem dados. |
| Temperatura média e variação | Mesmo cálculo para temperatura; painel separado mostra a média da planta como referência. |
| Exposição | União temporal por cabine, para a cabine selecionada. |
| Principal risco | Tipo mais frequente no histórico; referência de priorização, não previsão causal. |
| Cobertura do modelo | Pelo menos três meses observados, cada mês com pelo menos 20 dias contendo leituras válidas. Dias observados não significam 24h completas de cobertura. |
| Alertas: histórico + projeção | Totais mensais e projeção constante para três meses, usando a média mensal histórica. |
| Corrente: histórico + projeção | Média mensal histórica repetida nos próximos três meses. |
| Criticidade prevista | Médias mensais de atenção, moderado e crítico, repetidas por horizonte. São contagens esperadas e podem ser fracionárias. |
| Probabilidade de evento | Hipótese Poisson: 100 × (1 − exp(−90 × eventos/dias observados)), exigindo ao menos 60 dias observados. Estima ao menos um evento de temperatura/corrente em 90 dias sob taxa constante. |

Esta é uma **projeção demonstrativa de referência**, não um modelo treinado ou validado de manutenção preditiva. Ela não captura tendência crescente, sazonalidade, mudanças de carga, correlação entre eventos ou condições físicas. Períodos parciais e cobertura irregular afetam o resultado. Probabilidade de alerta não equivale a probabilidade de falha física.

A probabilidade de desequilíbrio permanece sem cálculo: o pipeline atual não materializa eventos desse tipo. A disponibilidade operacional também permanece sem cálculo. As setas comparativas para exposição/disponibilidade e uma probabilidade calibrada de falha exigem evolução adicional. Não foram substituídas por valores simulados silenciosamente.

## Limites de referência

- Temperatura ideal 60 °C; atenção ≥70, moderado ≥80 e crítico ≥90 °C.
- Corrente máxima provisória 600 A por fase. Ideal 396 A; atenção ≥455,4, moderado ≥514,8 e crítico ≥574,2 A.
- Desequilíbrio: normal ≤5%, atenção >5%, moderado ≥10%, crítico ≥20%.
- Eventos: confirmação após 10 segundos contínuos em alerta, com a regra de antecipação já documentada em REGRAS-DASHBOARDS.md.
- Leituras de qualidade inválida não viram zero. Lacunas >5s quebram continuidade.
- O início de eventos antigos pode ser truncado: as consultas leem apenas 60s anteriores ao período. Não existe tabela persistente de incidentes nesta entrega.

## Simular criticidades para a demonstração

Depois de instalar a aplicação atualizada:

```powershell
.\lab.ps1 simular -Cenario criticidades -Duracao 240
```

O modo normal continua disponível:

```powershell
.\lab.ps1 simular -Cenario normal -Duracao 120
```

O cenário criticidades publica seis mensagens por segundo (três cabines × corrente/temperatura), via IoT → SQS → consumidor → RDS. Os registros têm run_id iniciado por `demo-criticidades-` e são dados sintéticos, não medições físicas. As dashboards agregam esses dados junto com as demais leituras no período.

| Segundos | Cabine 001: fase R | Objetivo |
| --- | --- | --- |
| 0–29 | 240 A / 45 °C | Normal |
| 30–59 | 470 A / 74 °C | Atenção |
| 60–89 | 240 A / 45 °C | Recuperação, separa eventos |
| 90–119 | 530 A / 84 °C | Moderado |
| 120–149 | 240 A / 45 °C | Recuperação |
| 150–179 | 590 A / 95 °C | Crítico |
| 180–209 | 240 A / 45 °C | Recuperação |
| 210–239 | 590 A / 95 °C | Reincidência crítica |

Cabine 002 introduz desequilíbrio e concentra aquecimento na fase R. Cabine 003 apresenta aquecimento sem elevar a corrente para a faixa de sobrecarga. Esses patamares determinísticos testam as dashboards; não pretendem reproduzir a dinâmica física térmica.

O ciclo repete a cada 240s. O comando aceita até 600s. Uma execução curta não alcança todas as etapas. O simulador contínuo da EC2 é pausado durante o cenário e retomado ao final se estava ativo; falhas tratadas também executam a retomada. Interrupção abrupta da máquina/processo pode exigir `lab.ps1 iniciar`. Pare simuladores externos durante a demonstração para não intercalar leituras da mesma cabine.

Ao concluir, o comando verifica os event_ids no RDS. O ACK do IoT sozinho não é considerado sucesso de ponta a ponta. Observe a dashboard em 10 min e aguarde atualização visual de 30s. Após a retomada normal, o estado atual pode voltar a verde enquanto os históricos preservam as ocorrências.

A simulação de quatro minutos popula visão geral, histórico, rankings e exposição. **Ela não fabrica três meses de histórico** e, portanto, não habilita as previsões. Sem cobertura, esses gráficos continuam sem valores projetados.

## Validação e limites da entrega

JSONs gerados, verificação estrutural de painéis e execução dos testes locais disponíveis. As consultas novas não foram executadas contra seu RDS e a aparência não foi inspecionada em um Grafana local. O instalador executa preflight SQL antes de publicar os cinco arquivos.

As consultas de eventos e especialmente de união temporal podem ficar caras com meses de dados a cada segundo. O preflight dos últimos cinco minutos não comprova desempenho em 90 dias. A evolução recomendada é materializar incidentes e agregados diários/mensais com cobertura de telemetria, antes de usar as projeções em escala.

Não houve aplicação remota na AWS nesta preparação. O documento descreve o código entregue e suas limitações; os guias v3/v4 são registros das entregas anteriores.
