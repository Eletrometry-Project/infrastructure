"""Gera visoes gerenciais; executar depois de build_dashboard.py."""
import json
from pathlib import Path
import build_dashboard as b
import dashboard_sql as s


def rawstat(pid,title,query,pos,unit='short'):
 p=b.panel(pid,title,'stat',pos,query);p['options']={'reduceOptions':{'calcs':['lastNotNull'],'fields':'/.*/','values':False},'textMode':'value','colorMode':'none','graphMode':'none','text':{'valueSize':26}}
 p['fieldConfig']['defaults'].update(unit=unit,decimals=1)
 return p


def table(pid,title,query,pos):
 p=b.panel(pid,title,'table',pos,query);p['options']={'showHeader':True,'cellHeight':'sm','enablePagination':True};return p


def bars(pid,title,query,pos,unit='short'):
 p=table(pid,title,query,pos);p['type']='barchart';p['options']={'orientation':'horizontal','showValue':'auto','legend':{'showLegend':True,'placement':'bottom'},'tooltip':{'mode':'multi'},'stacking':'normal'};p['fieldConfig']['defaults']['unit']=unit;return p


def risk(scope='1=1'):
 # Merge sorted risk intervals once, rather than testing every pair of intervals.
 return s.base(scope)+f""", risk_intervals AS (
 SELECT DISTINCT cabine_id,GREATEST(ts,UNIX_TIMESTAMP({s.START})) a,
 LEAST(next_ts,UNIX_TIMESTAMP({s.END})) z
 FROM flags WHERE severity>0 AND dt>0
 ), previous_end AS (
 SELECT *,MAX(z) OVER(PARTITION BY cabine_id ORDER BY a,z
 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) prev_end FROM risk_intervals
 ), islands AS (
 SELECT *,SUM(CASE WHEN prev_end IS NULL OR a>prev_end THEN 1 ELSE 0 END)
 OVER(PARTITION BY cabine_id ORDER BY a,z ROWS UNBOUNDED PRECEDING) island FROM previous_end
 ), merged AS (
 SELECT cabine_id,island,MAX(z)-MIN(a) seconds FROM islands GROUP BY cabine_id,island
 ), exposure AS (SELECT cabine_id,SUM(seconds) seconds FROM merged GROUP BY cabine_id)
 """


def manager():
 base=s.base()
 panels=[rawstat(1,'Eventos críticos',base+'SELECT COUNT(*) valor FROM events WHERE severity=3',(0,0,6,4)),
 rawstat(2,'Estado observado da planta',base+'''SELECT CASE WHEN COUNT(valor)<18 OR MAX(UNIX_TIMESTAMP('''+s.END+''')-ts)>60 THEN 'Dados incompletos' WHEN MAX(severity)=3 THEN 'Crítico' WHEN MAX(severity)=2 THEN 'Moderado' WHEN MAX(severity)=1 THEN 'Atenção' ELSE 'Normal' END Estado FROM latest''',(6,0,6,4),'none'),
 rawstat(3,'Exposição · horas-cabine',risk()+'SELECT SUM(seconds)/3600 valor FROM exposure',(12,0,6,4),'suffix:h-cabine'),
 rawstat(4,'Cabines cadastradas',f'SELECT {len(b.R["cabines"])} valor',(18,0,6,4))]
 panels[2]['description']='União temporal entre fases e tipos em alerta, por cabine; soma entre cabines. Não equivale à duração de risco da planta nem a indisponibilidade.'
 panels.append(bars(5,'Eventos por tipo e severidade',base+"SELECT tipo Tipo,SUM(severity=1) Atencao,SUM(severity=2) Moderado,SUM(severity=3) Critico FROM events GROUP BY tipo",(0,4,8,9)))
 panels.append(bars(6,'Ranking · total de eventos',base+'SELECT cabine_id Cabine,COUNT(*) Eventos FROM events GROUP BY cabine_id ORDER BY Eventos DESC',(8,4,8,9)))
 panels.append(bars(7,'Ranking · exposição ao risco',risk()+'SELECT cabine_id Cabine,seconds/3600 Horas FROM exposure ORDER BY seconds DESC',(16,4,8,9),'h'))
 panels.append(table(8,'Mapa de cabines · estado observado',base+'''SELECT cabine_id Cabine,
 CASE WHEN COUNT(valor)<6 OR MAX(UNIX_TIMESTAMP('''+s.END+''')-ts)>60 THEN 'Sem dados recentes' WHEN MAX(severity)=3 THEN 'Crítico' WHEN MAX(severity)=2 THEN 'Moderado' WHEN MAX(severity)=1 THEN 'Atenção' ELSE 'Normal' END Estado,
 MAX(CASE WHEN tipo='corrente' THEN valor END) Corrente_A,
 MAX(CASE WHEN tipo='temperatura' THEN valor END) Temperatura_C
 FROM latest GROUP BY cabine_id ORDER BY MAX(severity) DESC''',(0,13,24,9)))
 for f in ['Estado']:
  b.override(panels[-1],f,mappings=[{'type':'value','options':{k:{'text':k,'color':v} for k,v in [('Normal','green'),('Atenção','yellow'),('Moderado','orange'),('Crítico','red'),('Sem dados recentes','gray')]}}],**{'custom.cellOptions':{'type':'color-background'}})
 b.override(panels[-1],'Cabine',links=[{'title':'Histórico','url':'/d/eletrometry-historico?var-cabine=${__value.raw}&${__url_time_range}'}])
 panels.append(rawstat(9,'Ativas / desativadas · cadastro pendente',"SELECT 'Sem registro operacional' Estado",(0,22,12,4),'none'))
 panels.append(rawstat(10,'Disponibilidade operacional',"SELECT 'Sem registro de operação' Estado",(12,22,12,4),'none'))
 return b.base('eletrometry-gestor','Eletrometry • Gestor — visão da planta',panels)


def monthly():
 return s.base(s.CF)+''', months AS (
 SELECT DATE_FORMAT(coletado_em,'%Y-%m-01') mes,AVG(CASE WHEN tipo='corrente' THEN (fase_a+fase_b+fase_c)/3 END) corrente,
 COUNT(DISTINCT DATE(coletado_em)) dias FROM raw WHERE qualidade_a='ok' AND qualidade_b='ok' AND qualidade_c='ok'
 AND coletado_em>='''+s.START+''' GROUP BY 1), counts AS (
 SELECT DATE_FORMAT(FROM_UNIXTIME(confirmed_ts),'%Y-%m-01') mes,COUNT(*) n,
 SUM(severity=1) a,SUM(severity=2) m,SUM(severity=3) c FROM events
 WHERE confirmed_ts>=UNIX_TIMESTAMP('''+s.START+''') GROUP BY 1), history AS (
 SELECT x.*,COALESCE(n,0) n,COALESCE(a,0) a,COALESCE(m,0) m,COALESCE(c,0) c FROM months x LEFT JOIN counts y USING(mes)),
 model AS (SELECT CASE WHEN COUNT(*)>=3 AND MIN(dias)>=20 THEN 1 ELSE 0 END pronto,
 AVG(n) n,AVG(a) a,AVG(m) m,AVG(c) c,AVG(corrente) corrente,MAX(mes) ultimo FROM history),
 horizons AS (SELECT 1 h UNION ALL SELECT 2 UNION ALL SELECT 3)
 '''


def trend():
 panels=[]
 q=s.base(s.CF)
 # comparisons are adjacent equal-duration windows, matching selected period.
 for pid,title,kind,unit,x in [(1,'Corrente média · período','corrente','amp',0),(2,'Temperatura média · período','temperatura','celsius',6)]:
  query=f'''SELECT AVG(CASE WHEN coletado_em>={s.START} THEN (fase_a+fase_b+fase_c)/3 END) Atual,
 100*(AVG(CASE WHEN coletado_em>={s.START} THEN (fase_a+fase_b+fase_c)/3 END)-AVG(CASE WHEN coletado_em<{s.START} THEN (fase_a+fase_b+fase_c)/3 END))/NULLIF(AVG(CASE WHEN coletado_em<{s.START} THEN (fase_a+fase_b+fase_c)/3 END),0) Variacao_percentual
 FROM leituras WHERE {s.CF} AND tipo='{kind}' AND qualidade_a='ok' AND qualidade_b='ok' AND qualidade_c='ok' AND coletado_em BETWEEN DATE_SUB({s.START},INTERVAL TIMESTAMPDIFF(SECOND,{s.START},{s.END}) SECOND) AND {s.END}'''
  p=rawstat(pid,title,query,(x,0,6,5),unit);p['options']['textMode']='value_and_name';b.override(p,'Variacao_percentual',unit='percent');panels.append(p)
 panels.append(rawstat(3,'Exposição ao risco · período',risk(s.CF)+'SELECT SUM(seconds)/3600 Horas FROM exposure',(12,0,6,5),'h'))
 panels.append(rawstat(4,'Disponibilidade operacional',"SELECT 'Sem registro operacional' Estado",(18,0,6,5),'none'))
 panels.append(rawstat(5,'Principal risco · frequência histórica',q+"SELECT tipo Tipo FROM events GROUP BY tipo ORDER BY COUNT(*) DESC LIMIT 1",(0,5,8,4),'none'))
 panels.append(rawstat(6,'Temperatura média da planta',f"SELECT AVG((fase_a+fase_b+fase_c)/3) valor FROM leituras WHERE tipo='temperatura' AND qualidade_a='ok' AND qualidade_b='ok' AND qualidade_c='ok' AND coletado_em BETWEEN {s.START} AND {s.END}",(8,5,8,4),'celsius'))
 panels.append(rawstat(7,'Modelo de referência · cobertura',monthly()+"SELECT CASE WHEN pronto=1 THEN 'Baseline disponível' ELSE 'Histórico insuficiente' END Estado FROM model",(16,5,8,4),'none'))
 for pid,title,column,y in [(8,'Alertas · histórico e projeção de referência','n',9),(9,'Corrente · histórico e projeção de referência','corrente',18)]:
  query=monthly()+f'''SELECT UNIX_TIMESTAMP(mes) time,{column} Historico,NULL Projecao FROM history UNION ALL
 SELECT UNIX_TIMESTAMP(DATE_ADD(ultimo,INTERVAL h MONTH)),NULL,CASE WHEN pronto=1 THEN {column} END FROM model CROSS JOIN horizons ORDER BY time'''
  p=b.panel(pid,title,'timeseries',(0,y,24,9),query);p['targets'][0]['format']='time_series';p['fieldConfig']['defaults'].update(unit='amp' if column=='corrente' else 'short',custom={'drawStyle':'line','showPoints':'always','lineWidth':2});b.override(p,'Projecao',**{'custom.lineStyle':{'fill':'dash','dash':[6,4]}});panels.append(p)
 panels.append(bars(10,'Criticidade prevista · próximos três meses',monthly()+'''SELECT DATE_FORMAT(DATE_ADD(ultimo,INTERVAL h MONTH),'%Y-%m') Mes,
 CASE WHEN pronto=1 THEN a END Atencao,CASE WHEN pronto=1 THEN m END Moderado,CASE WHEN pronto=1 THEN c END Critico FROM model CROSS JOIN horizons''',(0,27,12,9)))
 panels.append(table(11,'Probabilidade de evento · próximos 90 dias',q+''', coverage AS (SELECT COUNT(DISTINCT DATE(coletado_em)) dias FROM raw WHERE coletado_em>='''+s.START+'''), types AS (SELECT 'temperatura' tipo UNION ALL SELECT 'corrente')
 SELECT t.tipo Tipo,CASE WHEN dias>=60 THEN 100*(1-EXP(-90.0*COUNT(e.tipo)/NULLIF(dias,0))) END Probabilidade_percentual
 FROM types t CROSS JOIN coverage LEFT JOIN events e ON e.tipo=t.tipo GROUP BY t.tipo,dias
 UNION ALL SELECT 'desequilibrio — sem eventos persistidos',NULL''',(12,27,12,9)))
 d=b.base('eletrometry-tendencias','Eletrometry • Gestor — tendências',panels,[b.variables()[0]])
 d['time']={'from':'now-90d','to':'now'}
 for p in panels:p['description']='Projeção demonstrativa por média mensal constante, não modelo treinado. Requer 3 meses com ≥20 dias observados por mês. Probabilidade: hipótese Poisson, ≥60 dias observados. Consulte GUIA-DASHBOARDS.md; não representa probabilidade de falha física.'
 return d


def intro(pid,title,content,y=0):
 return {'id':pid,'title':title,'type':'text','gridPos':{'x':0,'y':y,'w':24,'h':3},'options':{'mode':'markdown','content':content},'transparent':True}


def current_cte():
 # Seis buscas indexadas: ultima leitura por cabine/tipo. O estado atual nao
 # precisa reconstruir eventos nem ordenar todo o historico de cada fase.
 inventory=' UNION '.join('SELECT '+s.quote(k)+' cabine_id' for k in b.R['cabines'])
 raw=' UNION ALL '.join(
  "SELECT * FROM (SELECT * FROM leituras WHERE cabine_id="+s.quote(cab)+
  " AND tipo="+s.quote(kind)+" AND coletado_em BETWEEN "+s.START+" AND "+s.END+
  " ORDER BY coletado_em DESC,event_id DESC LIMIT 1) r"+str(i)
  for i,(cab,kind) in enumerate((cab,kind) for cab in b.R['cabines'] for kind in ['corrente','temperatura']))
 phases=' UNION ALL '.join("SELECT cabine_id,tipo,coletado_em,CASE WHEN qualidade_"+p+"='ok' THEN fase_"+p+" END valor FROM raw" for p in 'abc')
 limits=[]
 for severity in [3,2,1]:
  idx=severity-1
  limits.append("WHEN valor >= CASE WHEN tipo='temperatura' THEN "+str(b.R['temperature_thresholds_c'][idx])+" ELSE ("+s.capacity()+")*"+str(b.R['ideal_current_fraction']*b.R['current_alert_multipliers'][idx])+" END THEN "+str(severity))
 return "WITH raw AS ("+raw+"), phases AS ("+phases+"), latest AS (SELECT *,UNIX_TIMESTAMP(coletado_em) ts,CASE WHEN valor IS NULL THEN NULL "+' '.join(limits)+" ELSE 0 END severity FROM phases), inventory AS ("+inventory+"""), current_state AS (
 SELECT i.cabine_id,CASE WHEN COUNT(l.valor)<6 OR MAX(UNIX_TIMESTAMP("""+s.END+""")-l.ts)>60 THEN -1 ELSE MAX(l.severity) END estado,
 MAX(CASE WHEN tipo='corrente' THEN valor END) corrente,
 MAX(CASE WHEN tipo='temperatura' THEN valor END) temperatura
 FROM inventory i LEFT JOIN latest l ON l.cabine_id=i.cabine_id GROUP BY i.cabine_id)
 """


def simple_overview():
 q=current_cte()
 panels=[intro(90,'Onde preciso olhar primeiro?','**1.** Veja quantas cabines precisam de atenção. **2.** Consulte a lista de prioridades. **3.** Clique na cabine para investigar.\n\nEstado = última leitura do período selecionado. Alertas = ocorrências durante todo o período.')]
 for pid,title,query,x,color in [
 (1,'Cabines em alerta','SELECT SUM(estado>0) valor FROM current_state',0,'orange'),
 (2,'Cabines em estado crítico','SELECT SUM(estado=3) valor FROM current_state',6,'red'),
 (3,'Cabines sem dados recentes','SELECT SUM(estado=-1) valor FROM current_state',12,'gray'),
 (4,'Alertas críticos no período','SELECT COUNT(*) valor FROM events WHERE severity=3',18,'red')]:
  p=rawstat(pid,title,(s.overview() if pid==4 else q+query),(x,3,6,4));p['fieldConfig']['defaults'].update(decimals=0,color={'mode':'fixed','fixedColor':color});p['options']['colorMode']='value';panels.append(p)
  if pid==4: p['transformations']=[{'id':'filterFieldsByName','options':{'include':{'names':['alertas_criticos']}}}]
 query=q+"""SELECT cabine_id Cabine,
 CASE estado WHEN -1 THEN 'Sem dados recentes' WHEN 0 THEN 'Normal' WHEN 1 THEN 'Atenção' WHEN 2 THEN 'Moderado' ELSE 'Crítico' END Situacao,
 CASE WHEN estado=-1 THEN 'Verificar comunicação dos sensores' WHEN estado=0 THEN 'Acompanhar normalmente' WHEN estado=1 THEN 'Investigar o aumento das leituras' ELSE 'Priorizar avaliação técnica' END Proximo_passo,
 temperatura Temperatura,corrente Corrente FROM current_state
 ORDER BY CASE WHEN estado=-1 THEN 4 ELSE estado END DESC,cabine_id"""
 p=table(5,'Prioridades · clique na cabine para abrir os detalhes',query,(0,7,24,8));p['options']['cellHeight']='lg'
 b.override(p,'Temperatura',unit='celsius');b.override(p,'Corrente',unit='amp')
 b.override(p,'Cabine',links=[{'title':'Investigar cabine','url':'/d/'+b.DETAIL+'?var-cabine=${__value.raw}&${__url_time_range}'}])
 b.override(p,'Situacao',mappings=[{'type':'value','options':{k:{'text':k,'color':v} for k,v in [('Normal','green'),('Atenção','yellow'),('Moderado','orange'),('Crítico','red'),('Sem dados recentes','gray')]}}],**{'custom.cellOptions':{'type':'color-background'}})
 panels.append(p)
 old=b.overview()
 for pid,x in [(2,0),(3,6),(4,12),(5,18)]:
  p=next(p for p in old['panels'] if p['id']==pid);p['id']=20+pid;p['gridPos']=dict(x=x,y=15,w=6,h=4)
  p['datasource']=b.SHARED;p['targets']=[{'refId':'A','datasource':b.SHARED,'panelId':4,'withTransforms':False}];panels.append(p)
 alerts=next(p for p in old['panels'] if p['id']==6);alerts['gridPos']=dict(x=0,y=19,w=24,h=9);alerts['datasource']=b.SHARED;alerts['targets']=[{'refId':'A','datasource':b.SHARED,'panelId':4,'withTransforms':False}];panels.append(alerts)
 return b.base(b.OVERVIEW,'01 · Analista — resumo e prioridades',panels)


def simplify_manager(d):
 titles={1:'Alertas críticos no período',2:'Como está a planta?',3:'Tempo acumulado em risco',4:'Cabines monitoradas',5:'Quais problemas ocorreram?',6:'Onde houve mais alertas?',7:'Onde o risco durou mais?',8:'Situação das cabines · abrir histórico'}
 for p in d['panels']:
  p['title']=titles.get(p['id'],p['title']);p['gridPos']['y']+=3
  if p['id'] in [1,4]:p['fieldConfig']['defaults']['decimals']=0
 d['panels'].insert(0,intro(90,'Resumo para decidir prioridades','**Estado atual:** verifique a situação da planta. **Período:** compare quais cabines tiveram mais alertas e mais tempo em risco.\n\nTempo acumulado soma a duração de cada cabine: duas cabines em risco por 1 hora = 2 horas-cabine. Clique em uma cabine para abrir seu histórico.'))
 # Evita classificar uma planta sem inventário completo como normal.
 p=next(p for p in d['panels'] if p['id']==2)
 p['targets'][0]['rawSql']=current_cte()+"SELECT CASE WHEN SUM(estado=-1)>0 THEN 'Dados incompletos' WHEN MAX(estado)=3 THEN 'Crítico' WHEN MAX(estado)=2 THEN 'Moderado' WHEN MAX(estado)=1 THEN 'Atenção' ELSE 'Normal' END Estado FROM current_state"
 return d


def main():
 folder=Path(__file__).parent/'dashboards'
 for name,d in [('visao-geral',simple_overview()),('gestor',simplify_manager(manager())),('tendencias',trend())]:
  (folder/(name+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2))
 for path in folder.glob('*.json'):
  d=json.loads(path.read_text());d['tags']=['eletrometry','entrega-v6','ingestao-lotes'];d['refresh']='';d['version']=6;d['description']='Entrega v6 — cinco dashboards. '+d.get('description','');d['links']=[{'title':title,'type':'link','url':'/d/'+uid+'?${__url_time_range}'+('&${cabine:queryparam}' if any(v['name']=='cabine' for v in d['templating']['list']) else '')} for title,uid in [('Analista','eletrometry-visao-geral'),('Gestor','eletrometry-gestor'),('Tendências','eletrometry-tendencias')]]+d['links'];
  names={'eletrometry-cabines':'02 · Analista — investigar cabine','eletrometry-gestor':'03 · Gestor — resumo da planta','eletrometry-historico':'04 · Gestor — histórico da cabine','eletrometry-tendencias':'05 · Gestor — tendências e projeções'}
  d['title']=names.get(d['uid'],d['title'])
  if d['uid']!='eletrometry-tendencias':d['time']={'from':'now-1h','to':'now'}
  for panel in d['panels']:
   for target in panel.get('targets',[]):
    if target.get('rawSql'):
     suffix=' ORDER BY `time`' if target.get('format')=='time_series' else ''
     target['rawSql']='SELECT /*+ MAX_EXECUTION_TIME(15000) */ * FROM ('+target['rawSql']+') bounded_query'+suffix
  path.write_text(json.dumps(d,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
