"""Duas dashboards Grafana nativas, com consultas reais ao MySQL e regras revisáveis."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import dashboard_sql as sql

DS={'type':'mysql','uid':'eletrometry-mysql'}
SHARED={'type':'datasource','uid':'-- Dashboard --'}
NAVY='#20234F';BLUE='#1264F5';MUTED='#77859F';WHITE='#FFFFFF'
COLORS=['#FF9800','#3486FF','#9865FF']
R=sql.R
IMAX=R['default_max_current_a']
IIDEAL=IMAX*R['ideal_current_fraction']
OVERVIEW='eletrometry-visao-geral';DETAIL='eletrometry-cabines'

def target(query,kind='table'):
    return {'refId':'A','datasource':DS,'rawSql':query,'format':kind,'editorMode':'code','rawQuery':True}

def panel(pid,title,kind,pos,query=None,source=None,description=''):
    p={'id':pid,'title':title,'type':kind,'gridPos':dict(zip(['x','y','w','h'],pos)),
       'description':description,'datasource':DS,'targets':[target(query)] if query else [],
       'fieldConfig':{'defaults':{'unit':'short','decimals':1,'noValue':'Sem dados','color':{'mode':'fixed','fixedColor':NAVY},'mappings':[]},'overrides':[]},
       'options':{},'pluginVersion':'12.2.0'}
    if source:
        p['datasource']=SHARED
        p['targets']=[{'refId':'A','datasource':SHARED,'panelId':source,'withTransforms':False}]
    return p

def override(p,field,**props):
    p['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':field},'properties':[{'id':k,'value':v} for k,v in props.items()]})

def thresholds(values):
    return {'mode':'absolute','steps':[{'value':None,'color':'green'}]+[{'value':v,'color':c} for v,c in zip(values,['yellow','orange','red'])]}

def state(p,field='estado'):
    override(p,field,color={'mode':'thresholds'},thresholds=thresholds([1,2,3]),mappings=[{'type':'value','options':{str(n):{'text':s,'color':c} for n,s,c in [(-1,'SEM DADOS RECENTES','gray'),(0,'NORMAL','green'),(1,'ATENÇÃO','yellow'),(2,'MODERADO','orange'),(3,'CRÍTICO','red')]}}])

def text(value,x,y,w,h=24,size=16,color=NAVY,field=False,background='transparent',link=None):
    e={'name':str(value)+'-'+str(x)+'-'+str(y),'type':'metric-value' if field else 'text',
       'placement':{'left':x,'top':y,'width':w,'height':h},
       'constraint':{'horizontal':'scale','vertical':'scale'},
       'background':{'color':{'fixed':background}},'border':{'radius':8,'width':0},
       'config':{'text':{'mode':'field','field':value,'fixed':''} if field else {'mode':'fixed','fixed':value},
                 'align':'left','valign':'middle','size':size,'color':{'field':value,'fixed':color} if field else {'fixed':color}}}
    if link:e['links']=[{'title':'Abrir cabine','url':link,'targetBlank':False,'oneClick':True}]
    return e

def canvas(p,elements,w,h,bg=WHITE):
    p['type']='canvas'
    p['options']={'inlineEditing':False,'panZoom':False,'zoomToContent':True,'showAdvancedTypes':False,
                  'tooltip':{'mode':'single','disableForOneClick':True},
                  'root':{'name':'Eletrometry','type':'frame','placement':{'left':0,'top':0,'width':w,'height':h},
                          'background':{'color':{'fixed':bg}},'elements':elements}}
    return p

def stat(pid,title,field,pos,source,unit='short',decimals=0):
    p=panel(pid,title,'stat',pos,source=source)
    p['options']={'reduceOptions':{'calcs':['lastNotNull'],'fields':field,'values':False},'colorMode':'value','graphMode':'none','textMode':'value','justifyMode':'center'}
    p['fieldConfig']['defaults'].update(unit=unit,decimals=decimals)
    p['transformations']=[{'id':'filterFieldsByName','options':{'include':{'names':[field]}}}]
    return p

def links(uid):
    return [{'title':name,'type':'link','url':f'/d/{uid}?from=now-{period}&to=now&${{cabine:queryparam}}&theme=light','targetBlank':False} for name,period in [('24 Horas','24h'),('1 Semana','7d'),('1 Mês','30d')]]

def base(uid,title,panels,variables=None):
    return {'id':None,'uid':uid,'title':title,'version':2,'schemaVersion':39,'editable':False,
            'tags':['eletrometry','protótipo','regras-provisórias'],'timezone':'browser','refresh':R['refresh'],
            'time':{'from':'now-24h','to':'now'},'timepicker':{'refresh_intervals':['30s','1m','5m'],'time_options':['1m','1h','24h','7d','30d']},
            'description':'Protótipo com dados reais do RDS e regras provisórias do grupo. Ver REGRAS-DASHBOARDS.md. Limites não certificados.',
            'annotations':{'list':[]},'links':links(uid),'panels':panels,'templating':{'list':variables or []}}

def overview():
    p=panel(1,'Quantidade de Alertas Críticos','stat',(0,2,8,4),sql.overview(),description='Eventos confirmados por cabine/tipo/fase. Regras provisórias: consulte REGRAS-DASHBOARDS.md.')
    p['options']={'reduceOptions':{'calcs':['lastNotNull'],'fields':'alertas_criticos','values':False},'colorMode':'value','graphMode':'none','textMode':'value','justifyMode':'center'}
    p['transformations']=[{'id':'filterFieldsByName','options':{'include':{'names':['alertas_criticos']}}}]
    p['fieldConfig']['defaults']['decimals']=0
    panels=[canvas(panel(90,'','canvas',(0,0,24,2)),[text('⚡ ELETROMETRY   /   VISÃO GERAL DAS CABINES',20,5,800,36,22),text('Dados reais · regras provisórias · período no seletor superior',840,5,680,36,15,MUTED)],1540,50),p,
            stat(2,'Cabine Mais Crítica','cabine_critica',(8,2,8,4),1,'none'),stat(3,'Tipo de Alerta Com Mais Problema','tipo_problema',(16,2,8,4),1,'none'),
            stat(4,'% de cabines com ocorrências registradas','pct_ocorrencias',(12,6,6,4),1,'percent',1),
            stat(5,'Índice de cabines com reincidência de alertas','pct_reincidencia',(18,6,6,4),1,'percent',1)]
    panels[2]['fieldConfig']['defaults']['noValue']='Nenhuma ocorrência'
    panels[3]['fieldConfig']['defaults']['noValue']='Nenhuma ocorrência'
    override(panels[3],'tipo_problema',mappings=[{'type':'value','options':{'temperatura':{'text':'Temperatura'},'corrente':{'text':'Corrente'}}}])
    panels.append(canvas(panel(91,'','canvas',(0,6,12,2)),[text('Visão das Cabines',14,4,650,34,24)],720,45))
    for i,cab in enumerate(R['cabines']):
        url=f'/d/{DETAIL}?var-cabine={cab}&${{__url_time_range}}&theme=light'
        card=panel(20+i,cab,'canvas',((i%3)*4,8+(i//3)*8,4,8),sql.card(cab),description='Clique no título ou nos valores para abrir a cabine, mantendo o período. R=A; S=B; T=C. Cinza: dados ausentes, inválidos ou antigos.')
        card['links']=[{'title':'Abrir dashboard da cabine','url':url,'targetBlank':False}]
        elements=[text(cab.replace('cabine-','Cabine '),16,8,232,35,23,WHITE,link=url),text('estado',16,49,232,25,14,field=True,link=url)]
        state(card)
        for j,phase in enumerate('abc'):
            y=94+j*45
            elements.extend([text(f'Fase {j+1}',16,y,64,30,14,WHITE,link=url),text('corrente_'+phase,84,y,88,30,17,WHITE,True,link=url),text('temperatura_'+phase,176,y,91,30,17,WHITE,True,link=url)])
            override(card,'corrente_'+phase,unit='amp',color={'mode':'fixed','fixedColor':WHITE})
            override(card,'temperatura_'+phase,unit='celsius',color={'mode':'fixed','fixedColor':WHITE})
        panels.append(canvas(card,elements,282,243,NAVY))
    alerts=panel(6,'Alertas das Cabines','table',(12,10,12,14),source=1,description='Últimas 50 ocorrências confirmadas no período. Valor = máximo do evento. Histórico, não necessariamente alertas ainda ativos.')
    alerts['transformations']=[{'id':'filterDataByValues','options':{'filters':[{'fieldName':'Cabine','config':{'id':'isNotNull','options':{}}}],'type':'include','match':'all'}},
        {'id':'filterFieldsByName','options':{'include':{'names':['Nivel','Alerta','Cabine','Fase','Valor','Unidade','Confirmado']}}}]
    alerts['options']={'showHeader':True,'cellHeight':'lg','sortBy':[{'displayName':'Confirmado','desc':True}]}
    override(alerts,'Nivel',mappings=[{'type':'value','options':{k:{'text':k,'color':v} for k,v in [('Crítico','red'),('Moderado','orange'),('Atenção','yellow')]}}],**{'custom.cellOptions':{'type':'color-background'}})
    override(alerts,'Confirmado',unit='dateTimeFromNow')
    panels.append(alerts)
    d=base(OVERVIEW,'Eletrometry • Visão geral das cabines',panels)
    # A visão geral não possui variável cabine.
    for link in d['links']:link['url']=link['url'].replace('&${cabine:queryparam}','')
    return d

def variables():
    cabines=' UNION '.join('SELECT '+sql.quote(k)+' AS cabine_id' for k in R['cabines'])
    q=f'SELECT cabine_id AS __text,cabine_id AS __value FROM ({cabines} UNION SELECT DISTINCT cabine_id FROM leituras) c ORDER BY cabine_id'
    result=[{'name':'cabine','label':'Cabine','type':'query','datasource':DS,'query':q,'definition':q,'refresh':1,'multi':False,'includeAll':False,'sort':1,'current':{'text':next(iter(R['cabines'])),'value':next(iter(R['cabines']))},'options':[]}]
    for name,label,opts in [('metrica','Tempo de desvio','Temperatura : temperatura,Corrente : corrente'),('sensor','Saúde · sensor','Temperatura : temperatura,Corrente : corrente'),('fase','Saúde · fase','R (A) : A,S (B) : B,T (C) : C')]:
        pairs=[item.split(' : ') for item in opts.split(',')]
        result.append({'name':name,'label':label,'type':'custom','query':opts,'multi':False,'includeAll':False,'current':{'text':pairs[0][0],'value':pairs[0][1]},'options':[{'text':k,'value':v,'selected':i==0} for i,(k,v) in enumerate(pairs)]})
    return result

def detail():
    head=panel(1,'Cabine ${cabine:text}','canvas',(0,0,24,2),sql.details(),description='Estado instantâneo = pior fase/tipo. Sem dados recentes se um canal estiver ausente ou com idade >60 s. Não confundir estado instantâneo com evento confirmado de 10 s.')
    state(head)
    panels=[canvas(head,[text('⚡ DASHBOARD — ANALISTA INTERNA',12,4,950,40,24),text('estado',1110,4,390,40,20,field=True)],1540,50)]
    for pid,name,field,x,unit,limits,maximum,ideal in [(2,'Temperatura da cabine','temperatura',0,'celsius',R['temperature_thresholds_c'],120,R['ideal_temperature_c']),(3,'Corrente da cabine','corrente',12,'amp',[IIDEAL*m for m in R['current_alert_multipliers']],IMAX,IIDEAL)]:
        p=stat(pid,f'{name} · ideal {ideal} '+('°C' if unit=='celsius' else 'A'),field,(x,2,12,4),1,unit,1)
        p['type']='bargauge';p['description']='Maior valor válido entre as três fases. Limites provisórios; capacidade inicial de 600 A por fase.'
        p['fieldConfig']['defaults'].update(min=0,max=maximum,color={'mode':'thresholds'},thresholds=thresholds(limits))
        p['options'].update(orientation='horizontal',displayMode='gradient',showUnfilled=True,minVizHeight=20,minVizWidth=0,sizing='auto',valueMode='color')
        panels.append(p)
    p=panel(4,'Tempo total de Desvio · ${metrica:text}','canvas',(0,6,8,6),source=1,description='Duração observada com a maior fase acima do ideal; união entre fases, sem triplicar segundos. Lacunas >5 s não são contabilizadas. Seletor de métrica acima.')
    for f in ['tempo_desvio','tempo_critico']:override(p,f,unit='dtdhms',decimals=0,color={'mode':'fixed','fixedColor':BLUE if f=='tempo_desvio' else 'red'})
    override(p,'desvio_atual',decimals=1,color={'mode':'fixed','fixedColor':BLUE})
    panels.append(canvas(p,[text('Desde o início do período',12,2,440,24,13,MUTED),text('Acima do ideal',12,39,240,22,15,BLUE),text('tempo_desvio',12,67,265,51,35,field=True),text('Desvio atual (°C ou A)',285,36,205,24,14),text('desvio_atual',285,62,205,40,29,field=True),text('Em nível crítico',285,113,205,24,14),text('tempo_critico',285,140,205,40,25,field=True)],510,190))
    p=panel(5,'Margem de Ação – Temperatura','canvas',(8,6,8,6),source=1,description='Margem=90°C−maior temperatura. Taxa=temperatura atual−média entre 55 e 65 s atrás, em °C/min. Tendência estável entre −0,05 e +0,05°C/min.')
    override(p,'margem',unit='celsius',color={'mode':'thresholds'},thresholds={'mode':'absolute','steps':[{'value':None,'color':'red'},{'value':0,'color':'green'}]})
    override(p,'taxa',unit='suffix:°C/min',color={'mode':'fixed','fixedColor':BLUE})
    override(p,'tendencia',unit='none',color={'mode':'fixed','fixedColor':BLUE})
    panels.append(canvas(p,[text('Margem até o crítico',12,22,235,28,16),text('margem',12,63,235,55,35,field=True),text('Taxa de Variação',265,22,230,28,16),text('taxa',265,63,230,55,30,field=True),text('Tendência',265,126,90,26,13,MUTED),text('tendencia',360,126,135,26,15,field=True)],510,190))
    p=panel(6,'Corrente e Temperatura por Fase','timeseries',(0,12,11,14),sql.phase_series(),description='Cheia=temperatura; tracejada=corrente; cor=fase. Selecione séries pela legenda. Fórmulas em REGRAS-DASHBOARDS.md.')
    p['targets'][0]['format']='time_series';p['maxDataPoints']=700;p['interval']='1s'
    p['options']={'legend':{'displayMode':'list','placement':'top','calcs':[]},'tooltip':{'mode':'multi','sort':'none'}}
    p['fieldConfig']['defaults'].update(unit='amp',color={'mode':'palette-classic'},custom={'drawStyle':'line','lineWidth':2,'fillOpacity':0,'spanNulls':False,'showPoints':'never'})
    for phase,color in zip('ABC',COLORS):
        for name,unit,axis,style in [('Temp','celsius','right','solid'),('Corr','amp','left','dash')]:
            override(p,name+' '+phase,unit=unit,color={'mode':'fixed','fixedColor':color},**{'custom.axisPlacement':axis,'custom.axisLabel':'Temperatura (°C)' if name=='Temp' else 'Corrente (A)','custom.lineStyle':{'fill':style,'dash':[8,5]}})
    p['links']=[{'title':n,'url':f'/d/{DETAIL}?${{cabine:queryparam}}&from=now-{r}&to=now&theme=light'} for n,r in [('Minuto','1m'),('1 Hora','1h'),('24h','24h')]]
    panels.append(p)
    p=panel(7,'Desequilíbrio entre fases','canvas',(11,12,5,14),source=1,description='100×máximo desvio absoluto em relação à média / média das três correntes. R=A; S=B; T=C. Ideal≤5%; atenção>5%; moderado≥10%; crítico≥20%. Sem três fases válidas, sem cálculo.')
    override(p,'desequilibrio',unit='percent',color={'mode':'thresholds'},thresholds=thresholds([5.000001,10,20]))
    els=[text('desequilibrio',12,8,282,65,42,field=True),text('Desvio máximo em relação',12,78,282,24,14,MUTED),text('à média das fases',12,99,282,24,14,MUTED),text('desequilibrio_status',12,121,282,23,13,field=True)]
    for j,(f,name) in enumerate(zip('abc','RST')):
        y=146+j*70
        els.extend([text('Fase '+name,12,y,75,32,16),text('corrente_'+f,90,y,110,32,21,field=True),text('delta_'+f,206,y,90,32,15,field=True),text('delta_pct_'+f,206,y+29,90,22,12,field=True)])
        override(p,'delta_pct_'+f,unit='percent',decimals=1);override(p,'corrente_'+f,unit='amp');override(p,'delta_'+f,unit='amp',color={'mode':'fixed','fixedColor':MUTED})
    els.extend([text('Média das fases',12,367,280,25,16),text('media_fases',12,397,280,40,26,field=True),text('Faixa ideal ≤ 5%',12,443,280,32,18)])
    override(p,'media_fases',unit='amp')
    els.extend([text('Maior fase',12,485,130,25,14),text('maior_fase',156,485,140,25,17,field=True)])
    panels.append(canvas(p,els,310,525))
    p=panel(8,'Carregamento da cabine','timeseries',(16,6,8,9),sql.load_series(),description='Média das três correntes válidas ao longo do período. Padrão calculado=média das amostras do período. Não estima energia ou demanda contratada.')
    p['targets'][0]['format']='time_series';p['interval']='1s';p['maxDataPoints']=400
    p['fieldConfig']['defaults'].update(unit='amp',custom={'drawStyle':'line','lineWidth':2,'fillOpacity':10,'spanNulls':False,'showPoints':'never'},color={'mode':'fixed','fixedColor':'orange'})
    override(p,'Padrão calculado',color={'mode':'fixed','fixedColor':MUTED},**{'custom.lineStyle':{'fill':'dash','dash':[8,5]},'custom.fillOpacity':0})
    p['options']={'legend':{'displayMode':'list','placement':'bottom','calcs':[]},'tooltip':{'mode':'multi','sort':'none'}}
    p['links']=links(DETAIL)
    panels.append(p)
    p=panel(9,'','canvas',(16,15,8,3),source=1,description='Pico do dia=máxima média trifásica nas últimas 24h dentro do período. Duração no pico=soma dos intervalos com carga ≥95% desse pico; não só o instante máximo.')
    for f in ['pico','padrao']:override(p,f,unit='amp')
    override(p,'duracao_pico',unit='dtdhms',decimals=0);override(p,'pico_hora',unit='time:HH:mm')
    panels.append(canvas(p,[text('Pico do dia',8,0,160,22,13,MUTED),text('pico',8,28,160,30,22,field=True),text('pico_hora',8,60,160,20,13,field=True),text('Duração no pico',178,0,170,22,13,MUTED),text('duracao_pico',178,29,170,32,22,field=True),text('Padrão calculado',354,0,150,22,13,MUTED),text('padrao',354,29,150,32,22,field=True)],515,85))
    p=panel(10,'Saúde da Telemetria · ${sensor:text} / ${fase:text}','canvas',(16,18,8,4),source=1,description='Seletores acima. Atrasado≥15s; sem atualização≥60s; constante≥5min é indício. Idade de coleta relativa ao fim do período.')
    override(p,'sensor_estado',unit='none');override(p,'sensor_idade',unit='s',decimals=0);override(p,'sensor_valor',decimals=1)
    state(p,'sensor_severity')
    els=[text('sensor_estado',12,4,490,35,22,field=True),text('sensor_severity',12,45,265,30,16,field=True),text('Tempo sem atualização',12,86,315,25,14,MUTED),text('sensor_idade',343,85,160,27,18,field=True)]
    panels.append(canvas(p,els,520,120))
    p=stat(11,'Medição · ${sensor:text} / ${fase:text}','sensor_valor',(16,22,8,2),1,'short',1)
    p['type']='bargauge'
    p['options'].update(orientation='horizontal',displayMode='gradient',showUnfilled=True,valueMode='color')
    p['transformations']=[{'id':'configFromData','options':{'configRefId':'A','applyTo':{'id':'byName','options':'sensor_valor'},'mappings':[{'fieldName':'sensor_max','handlerKey':'max','reducerId':'lastNotNull'},{'fieldName':'sensor_unit','handlerKey':'unit','reducerId':'lastNotNull'}]}},{'id':'filterFieldsByName','options':{'include':{'names':['sensor_valor']}}}]
    p['fieldConfig']['defaults'].update(min=0,color={'mode':'fixed','fixedColor':BLUE})
    panels.append(p)
    p=panel(12,'Correntes · atualização por fase','canvas',(16,24,8,4),source=1)
    els=[]
    for j,f in enumerate('abc'):
        x=12+j*168
        els.extend([text('Fase '+'RST'[j],x,3,160,24,14),text('corrente_'+f,x,30,160,32,22,field=True),text('saude_'+f,x,68,160,24,12,field=True),text('idade_'+f,x,96,160,24,13,field=True)])
        override(p,'corrente_'+f,unit='amp');override(p,'idade_'+f,unit='s',decimals=0,color={'mode':'thresholds'},thresholds=thresholds([15,30,60]))
        override(p,'saude_'+f,unit='none')
    panels.append(canvas(p,els,520,130))
    d=base(DETAIL,'Eletrometry • Dashboard interna da cabine',panels,variables())
    d['links'].insert(0,{'title':'← Visão geral','type':'link','url':f'/d/{OVERVIEW}?${{__url_time_range}}&theme=light','targetBlank':False})
    return d

def main():
    folder=Path(__file__).resolve().parent/'dashboards';folder.mkdir(exist_ok=True)
    for filename,data in [('visao-geral.json',overview()),('eletrometry.json',detail())]:
        (folder/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(filename,len(data['panels']),'painéis')

if __name__=='__main__':main()
