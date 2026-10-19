"""SQL MySQL 8 de leitura. Regras provisórias, sem criar tabelas ou alterar RDS."""
import json
from pathlib import Path

R = json.loads(Path(__file__).with_name('analysis_rules.json').read_text())
START = 'FROM_UNIXTIME(${__from}/1000.0)'
END = 'LEAST(FROM_UNIXTIME(${__to}/1000.0), UTC_TIMESTAMP(3))'
CF = 'cabine_id = ${cabine:sqlstring}'

def quote(s):
    return "'" + s.replace("'", "''") + "'"

def capacity(column='cabine_id'):
    return 'CASE ' + column + ' ' + ' '.join(f'WHEN {quote(k)} THEN {float(v)}' for k,v in R['cabines'].items()) + f" ELSE {float(R['default_max_current_a'])} END"

def base(scope='1=1', recent=False):
    ideal=R['ideal_current_fraction']; ta,tm,tc=R['temperature_thresholds_c']
    a,m,c=R['current_alert_multipliers']; gap=R['max_gap_seconds']; sec=R['event_min_seconds']; win=R['variation_window_seconds']
    phases=' UNION ALL '.join(f"SELECT event_id,cabine_id,tipo,coletado_em,recebido_em,'{p.upper()}' fase,CASE WHEN qualidade_{p}='ok' THEN fase_{p} END valor FROM raw" for p in 'abc')
    raw=f"SELECT * FROM leituras WHERE {scope} AND coletado_em >= {START} - INTERVAL 60 SECOND AND coletado_em <= {END}"
    if recent:
        raw=' UNION ALL '.join(f"SELECT * FROM ({raw} AND tipo='{kind}' ORDER BY coletado_em DESC,event_id DESC LIMIT 1) t_{kind}" for kind in ['corrente','temperatura'])
    return f"""WITH
raw AS ({raw}),
phases AS ({phases}),
limits AS (
 SELECT *,UNIX_TIMESTAMP(coletado_em) ts,
 CASE WHEN tipo='temperatura' THEN {R['ideal_temperature_c']} ELSE ({capacity()})*{ideal} END ideal,
 CASE WHEN tipo='temperatura' THEN {ta} ELSE ({capacity()})*{ideal*a} END lim1,
 CASE WHEN tipo='temperatura' THEN {tm} ELSE ({capacity()})*{ideal*m} END lim2,
 CASE WHEN tipo='temperatura' THEN {tc} ELSE ({capacity()})*{ideal*c} END lim3
 FROM phases
),
levels AS (
 SELECT *,CASE WHEN valor IS NULL THEN NULL WHEN valor>=lim3 THEN 3 WHEN valor>=lim2 THEN 2 WHEN valor>=lim1 THEN 1 ELSE 0 END severity,
 AVG(valor) OVER (PARTITION BY cabine_id,tipo,fase ORDER BY ts RANGE BETWEEN {win} PRECEDING AND 1 PRECEDING) baseline,
 MAX(CASE WHEN tipo='temperatura' THEN valor END) OVER (PARTITION BY cabine_id,fase ORDER BY ts RANGE BETWEEN {gap} PRECEDING AND CURRENT ROW) temp_recent,
 LAG(ts) OVER w prev_ts,LEAD(ts) OVER w next_ts,
 LEAD(valor) OVER w next_val,
 ROW_NUMBER() OVER (PARTITION BY cabine_id,tipo,fase ORDER BY ts DESC,event_id DESC) rn
 FROM limits WINDOW w AS (PARTITION BY cabine_id,tipo,fase ORDER BY ts,event_id)
),
flags AS (
 SELECT *,LAG(severity) OVER (PARTITION BY cabine_id,tipo,fase ORDER BY ts,event_id) prev_severity,
 CASE WHEN next_val IS NOT NULL AND valor IS NOT NULL AND next_ts-ts<={gap}
 THEN GREATEST(0,LEAST(next_ts,UNIX_TIMESTAMP({END}))-GREATEST(ts,UNIX_TIMESTAMP({START}))) ELSE 0 END dt
 FROM levels
),
groups_ AS (
 SELECT *,SUM(CASE WHEN severity>0 AND (COALESCE(prev_severity,0)=0 OR ts-prev_ts>{gap}) THEN 1 ELSE 0 END)
 OVER (PARTITION BY cabine_id,tipo,fase ORDER BY ts,event_id) grp
 FROM flags
),
marked AS (
 SELECT *,MIN(CASE WHEN severity>0 THEN ts END) OVER (PARTITION BY cabine_id,tipo,fase,grp) event_start
 FROM groups_
),
event_groups AS (
 SELECT cabine_id,tipo,fase,grp,MIN(ts) first_ts,MAX(ts) last_ts,MAX(severity) severity,
 MAX(valor) peak,
 MIN(CASE WHEN ts-event_start>={sec} OR (baseline>0 AND valor>=baseline*{1+R['variation_fraction']} AND temp_recent>={ta}) THEN ts END) confirmed_ts,
 SUM(CASE WHEN severity=3 THEN dt ELSE 0 END) critical_seconds
 FROM marked WHERE severity>0 GROUP BY cabine_id,tipo,fase,grp
),
events AS (
 SELECT * FROM event_groups WHERE confirmed_ts IS NOT NULL AND last_ts>=UNIX_TIMESTAMP({START})
),
latest AS (SELECT * FROM levels WHERE rn=1 AND coletado_em>={START})
"""

def overview():
    # Uma consulta compartilhada entre KPIs e lista de alertas.
    registered=' UNION '.join(f'SELECT {quote(k)} cabine_id' for k in R['cabines'])
    return base()+f""",
inventory AS ({registered} UNION SELECT DISTINCT cabine_id FROM raw WHERE coletado_em>={START}),
counts AS (SELECT cabine_id,COUNT(*) n,SUM(critical_seconds) critical_seconds,SUM(severity=3) critical_count FROM events GROUP BY cabine_id),
summary AS (
 SELECT (SELECT COUNT(*) FROM events WHERE severity=3) alertas_criticos,
 (SELECT cabine_id FROM counts ORDER BY critical_seconds DESC,critical_count DESC,n DESC,cabine_id LIMIT 1) cabine_critica,
 (SELECT tipo FROM events GROUP BY tipo ORDER BY COUNT(*) DESC,SUM(critical_seconds) DESC,tipo LIMIT 1) tipo_problema,
 100.0*(SELECT COUNT(*) FROM counts)/NULLIF((SELECT COUNT(*) FROM inventory),0) pct_ocorrencias,
 100.0*COALESCE((SELECT SUM(n>=2) FROM counts),0)/NULLIF((SELECT COUNT(*) FROM inventory),0) pct_reincidencia,
 (SELECT COUNT(*) FROM raw WHERE coletado_em>={START}) amostras
),
recent_events AS (SELECT * FROM events ORDER BY confirmed_ts DESC LIMIT 50)
SELECT s.*,
 CASE e.severity WHEN 3 THEN 'Crítico' WHEN 2 THEN 'Moderado' WHEN 1 THEN 'Atenção' END Nivel,
 CASE WHEN e.tipo='temperatura' THEN 'Temperatura' WHEN e.tipo='corrente' THEN 'Sobrecarga' END Alerta,
 e.cabine_id Cabine,e.fase Fase,e.peak Valor,
 CASE WHEN e.tipo='temperatura' THEN '°C' WHEN e.tipo='corrente' THEN 'A' END Unidade,
 FROM_UNIXTIME(e.confirmed_ts) Confirmado,
 FROM_UNIXTIME(e.last_ts) Ultima_leitura
FROM summary s LEFT JOIN recent_events e ON 1=1 ORDER BY e.confirmed_ts DESC"""

def card(cabine):
    return base('cabine_id='+quote(cabine),recent=True)+"""
SELECT MAX(cabine_id) cabine,
 MAX(CASE WHEN tipo='corrente' AND fase='A' THEN valor END) corrente_a,
 MAX(CASE WHEN tipo='corrente' AND fase='B' THEN valor END) corrente_b,
 MAX(CASE WHEN tipo='corrente' AND fase='C' THEN valor END) corrente_c,
 MAX(CASE WHEN tipo='temperatura' AND fase='A' THEN valor END) temperatura_a,
 MAX(CASE WHEN tipo='temperatura' AND fase='B' THEN valor END) temperatura_b,
 MAX(CASE WHEN tipo='temperatura' AND fase='C' THEN valor END) temperatura_c,
 CASE WHEN COUNT(valor)<6 OR MAX(UNIX_TIMESTAMP("""+END+""")-ts)>60 THEN -1 ELSE MAX(severity) END estado
FROM latest"""

def details():
    return base(CF)+f""",
wide AS (
 SELECT tipo,ts,MAX(valor) valor,MAX(ideal) ideal,MAX(lim3) lim3,
 CASE WHEN COUNT(valor)=3 THEN AVG(valor) END mean_value
 FROM levels GROUP BY tipo,ts
),
wide_next AS (
 SELECT *,LEAD(ts) OVER w next_ts,LEAD(valor) OVER w next_val FROM wide WINDOW w AS (PARTITION BY tipo ORDER BY ts)
),
wide_time AS (
 SELECT *,CASE WHEN next_val IS NOT NULL AND valor IS NOT NULL AND next_ts-ts<={R['max_gap_seconds']}
 THEN GREATEST(0,LEAST(next_ts,UNIX_TIMESTAMP({END}))-GREATEST(ts,UNIX_TIMESTAMP({START}))) ELSE 0 END dt
 FROM wide_next
),
now_values AS (
 SELECT MAX(CASE WHEN tipo='temperatura' THEN valor END) temperatura,
 MAX(CASE WHEN tipo='corrente' THEN valor END) corrente,
 MAX(CASE WHEN tipo=${{metrica:sqlstring}} THEN valor END) valor_metrica,
 MAX(CASE WHEN tipo=${{metrica:sqlstring}} THEN ideal END) ideal_metrica,
 MAX(CASE WHEN tipo='corrente' AND fase='A' THEN valor END) corrente_a,
 MAX(CASE WHEN tipo='corrente' AND fase='B' THEN valor END) corrente_b,
 MAX(CASE WHEN tipo='corrente' AND fase='C' THEN valor END) corrente_c,
 MAX(CASE WHEN tipo='temperatura' AND fase='A' THEN valor END) temperatura_a,
 MAX(CASE WHEN tipo='temperatura' AND fase='B' THEN valor END) temperatura_b,
 MAX(CASE WHEN tipo='temperatura' AND fase='C' THEN valor END) temperatura_c,
 MAX(CASE WHEN tipo='corrente' AND fase='A' THEN UNIX_TIMESTAMP({END})-ts END) idade_a,
 MAX(CASE WHEN tipo='corrente' AND fase='B' THEN UNIX_TIMESTAMP({END})-ts END) idade_b,
 MAX(CASE WHEN tipo='corrente' AND fase='C' THEN UNIX_TIMESTAMP({END})-ts END) idade_c,
 MAX(CASE WHEN tipo=${{sensor:sqlstring}} AND fase=${{fase:sqlstring}} THEN valor END) sensor_valor,
 MAX(CASE WHEN tipo=${{sensor:sqlstring}} AND fase=${{fase:sqlstring}} THEN UNIX_TIMESTAMP({END})-ts END) sensor_idade,
 MAX(CASE WHEN tipo=${{sensor:sqlstring}} AND fase=${{fase:sqlstring}} THEN severity END) sensor_severity,
 CASE WHEN COUNT(valor)<6 OR MAX(UNIX_TIMESTAMP({END})-ts)>{R['offline_seconds']} THEN -1 ELSE MAX(severity) END estado,
 CASE WHEN COUNT(CASE WHEN tipo='corrente' THEN valor END)=3 THEN AVG(CASE WHEN tipo='corrente' THEN valor END) END media_fases
 FROM latest
),
durations AS (
 SELECT SUM(CASE WHEN tipo=${{metrica:sqlstring}} AND valor>ideal THEN dt ELSE 0 END) tempo_desvio,
 SUM(CASE WHEN tipo=${{metrica:sqlstring}} AND valor>=lim3 THEN dt ELSE 0 END) tempo_critico
 FROM wide_time WHERE ts>=UNIX_TIMESTAMP({START})-5
),
load_stats AS (
 SELECT MAX(CASE WHEN ts>=UNIX_TIMESTAMP({END})-86400 THEN mean_value END) pico,AVG(mean_value) padrao FROM wide_time
 WHERE tipo='corrente' AND ts>=UNIX_TIMESTAMP({START})
),
peak_stats AS (
 SELECT SUM(CASE WHEN w.mean_value>=l.pico*{R['peak_fraction']} THEN w.dt ELSE 0 END) duracao_pico,
 MIN(CASE WHEN w.mean_value=l.pico THEN w.ts END) pico_ts
 FROM wide_time w CROSS JOIN load_stats l WHERE w.tipo='corrente' AND w.ts>=GREATEST(UNIX_TIMESTAMP({START}),UNIX_TIMESTAMP({END})-86400)
),
trend AS (
 SELECT (MAX(CASE WHEN rn=1 THEN valor END)-AVG(CASE WHEN ts BETWEEN UNIX_TIMESTAMP({END})-65 AND UNIX_TIMESTAMP({END})-55 THEN valor END)) taxa
 FROM (SELECT *,ROW_NUMBER() OVER (ORDER BY ts DESC) rn FROM wide WHERE tipo='temperatura') x
),
stuck AS (
 SELECT tipo,fase,CASE WHEN COUNT(valor)>=250 AND MAX(ts)-MIN(ts)>={R['stuck_seconds']}-5 AND MAX(valor)=MIN(valor) THEN 1 ELSE 0 END travado
 FROM levels WHERE ts>=UNIX_TIMESTAMP({END})-{R['stuck_seconds']} GROUP BY tipo,fase
)
SELECT n.*,d.*,l.*,CASE WHEN ${{sensor:sqlstring}}='temperatura' THEN 120 ELSE {R['default_max_current_a']} END sensor_max,
 CASE WHEN ${{sensor:sqlstring}}='temperatura' THEN 'celsius' ELSE 'amp' END sensor_unit,p.duracao_pico,FROM_UNIXTIME(p.pico_ts) pico_hora,
 n.valor_metrica-n.ideal_metrica desvio_atual,
 {R['temperature_thresholds_c'][2]}-n.temperatura margem,
 CASE WHEN n.temperatura IS NULL THEN NULL ELSE t.taxa END taxa,
 CASE WHEN t.taxa>0.05 THEN 'Alta' WHEN t.taxa< -0.05 THEN 'Queda' WHEN t.taxa IS NOT NULL THEN 'Estável' END tendencia,
 100*GREATEST(ABS(n.corrente_a-n.media_fases),ABS(n.corrente_b-n.media_fases),ABS(n.corrente_c-n.media_fases))/NULLIF(n.media_fases,0) desequilibrio,
 CASE WHEN n.media_fases IS NULL OR n.media_fases=0 THEN NULL WHEN 100*GREATEST(ABS(n.corrente_a-n.media_fases),ABS(n.corrente_b-n.media_fases),ABS(n.corrente_c-n.media_fases))/NULLIF(n.media_fases,0)>=20 THEN 'CRÍTICO' WHEN 100*GREATEST(ABS(n.corrente_a-n.media_fases),ABS(n.corrente_b-n.media_fases),ABS(n.corrente_c-n.media_fases))/NULLIF(n.media_fases,0)>=10 THEN 'MODERADO' WHEN 100*GREATEST(ABS(n.corrente_a-n.media_fases),ABS(n.corrente_b-n.media_fases),ABS(n.corrente_c-n.media_fases))/NULLIF(n.media_fases,0)>5 THEN 'ATENÇÃO' ELSE 'NORMAL' END desequilibrio_status,
 n.corrente_a-n.media_fases delta_a,n.corrente_b-n.media_fases delta_b,n.corrente_c-n.media_fases delta_c,
 100*(n.corrente_a-n.media_fases)/NULLIF(n.media_fases,0) delta_pct_a,
 100*(n.corrente_b-n.media_fases)/NULLIF(n.media_fases,0) delta_pct_b,
 100*(n.corrente_c-n.media_fases)/NULLIF(n.media_fases,0) delta_pct_c,
 CASE WHEN n.media_fases IS NULL THEN NULL WHEN n.corrente_a>=GREATEST(n.corrente_b,n.corrente_c) THEN 'R (A)' WHEN n.corrente_b>=n.corrente_c THEN 'S (B)' ELSE 'T (C)' END maior_fase,
 CASE WHEN n.sensor_valor IS NULL THEN 'Sem dados' WHEN n.sensor_idade>={R['offline_seconds']} THEN 'Sem atualização' WHEN n.sensor_idade>={R['stale_seconds']} THEN 'Atrasado'
 WHEN (SELECT travado FROM stuck WHERE tipo=${{sensor:sqlstring}} AND fase=${{fase:sqlstring}})=1 THEN 'Valor constante ≥5 min' ELSE 'Atualizando' END sensor_estado
,
CASE WHEN n.corrente_a IS NULL THEN 'Sem dados' WHEN n.idade_a>=60 THEN 'Sem atualização' WHEN n.idade_a>=15 THEN 'Atrasado' WHEN (SELECT travado FROM stuck WHERE tipo='corrente' AND fase='A')=1 THEN 'Constante ≥5 min' ELSE 'Atualizando' END saude_a,
CASE WHEN n.corrente_b IS NULL THEN 'Sem dados' WHEN n.idade_b>=60 THEN 'Sem atualização' WHEN n.idade_b>=15 THEN 'Atrasado' WHEN (SELECT travado FROM stuck WHERE tipo='corrente' AND fase='B')=1 THEN 'Constante ≥5 min' ELSE 'Atualizando' END saude_b,
CASE WHEN n.corrente_c IS NULL THEN 'Sem dados' WHEN n.idade_c>=60 THEN 'Sem atualização' WHEN n.idade_c>=15 THEN 'Atrasado' WHEN (SELECT travado FROM stuck WHERE tipo='corrente' AND fase='C')=1 THEN 'Constante ≥5 min' ELSE 'Atualizando' END saude_c
FROM now_values n CROSS JOIN durations d CROSS JOIN load_stats l CROSS JOIN peak_stats p CROSS JOIN trend t
""".replace('$metrica', '${metrica}')

def phase_series():
    return f"""SELECT $__timeGroupAlias(coletado_em,'$__interval',NULL),
 AVG(CASE WHEN tipo='corrente' AND qualidade_a='ok' THEN fase_a END) `Corr A`,
 AVG(CASE WHEN tipo='corrente' AND qualidade_b='ok' THEN fase_b END) `Corr B`,
 AVG(CASE WHEN tipo='corrente' AND qualidade_c='ok' THEN fase_c END) `Corr C`,
 AVG(CASE WHEN tipo='temperatura' AND qualidade_a='ok' THEN fase_a END) `Temp A`,
 AVG(CASE WHEN tipo='temperatura' AND qualidade_b='ok' THEN fase_b END) `Temp B`,
 AVG(CASE WHEN tipo='temperatura' AND qualidade_c='ok' THEN fase_c END) `Temp C`
 FROM leituras WHERE {CF} AND $__timeFilter(coletado_em) GROUP BY 1 ORDER BY 1"""

def load_series():
    return f"""WITH readings AS (
 SELECT coletado_em,(fase_a+fase_b+fase_c)/3 valor FROM leituras
 WHERE {CF} AND tipo='corrente' AND $__timeFilter(coletado_em)
 AND qualidade_a='ok' AND qualidade_b='ok' AND qualidade_c='ok'
), baseline AS (SELECT AVG(valor) valor FROM readings)
SELECT $__timeGroupAlias(coletado_em,'$__interval',NULL),AVG(r.valor) Carregamento,MAX(b.valor) `Padrão calculado`
FROM readings r CROSS JOIN baseline b GROUP BY 1 ORDER BY 1"""
