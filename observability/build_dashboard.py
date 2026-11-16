"""Dashboards Eletrometry: layout nativo adaptável, sem coordenadas Canvas."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_sql as sql

DS = {'type': 'mysql', 'uid': 'eletrometry-mysql'}
SHARED = {'type': 'datasource', 'uid': '-- Dashboard --'}
NAVY = '#20234F'
BLUE = '#1264F5'
MUTED = '#77859F'
COLORS = ['#FF9800', '#3486FF', '#9865FF']
R = sql.R
IMAX = R['default_max_current_a']
IIDEAL = IMAX * R['ideal_current_fraction']
OVERVIEW = 'eletrometry-visao-geral'
DETAIL = 'eletrometry-cabines'


def panel(pid, title, kind, pos, query=None, source=None, description=''):
    p = {'id': pid, 'title': title, 'type': kind,
         'gridPos': dict(zip(['x', 'y', 'w', 'h'], pos)),
         'description': description, 'datasource': DS,
         'targets': [{'refId': 'A', 'datasource': DS, 'rawSql': query,
                      'format': 'table', 'editorMode': 'code', 'rawQuery': True}] if query else [],
         'fieldConfig': {'defaults': {'unit': 'short', 'decimals': 1, 'noValue': 'Sem dados',
                                      'color': {'mode': 'fixed', 'fixedColor': 'text'}, 'mappings': []},
                         'overrides': []}, 'options': {}, 'pluginVersion': '12.2.0'}
    if source is not None:
        p['datasource'] = SHARED
        p['targets'] = [{'refId': 'A', 'datasource': SHARED, 'panelId': source, 'withTransforms': False}]
    return p


def override(p, field, **props):
    p['fieldConfig']['overrides'].append({'matcher': {'id': 'byName', 'options': field},
                                         'properties': [{'id': k, 'value': v} for k, v in props.items()]})


def thresholds(values):
    return {'mode': 'absolute', 'steps': [{'value': None, 'color': 'green'}] +
            [{'value': v, 'color': c} for v, c in zip(values, ['yellow', 'orange', 'red'])]}


def state(p, field='estado'):
    override(p, field, unit='none', decimals=0, color={'mode': 'thresholds'},
             thresholds=thresholds([1, 2, 3]), mappings=[{'type': 'value', 'options': {
                 str(n): {'text': s, 'color': c} for n, s, c in [
                     (-1, 'Sem dados recentes', 'gray'), (0, 'Normal', 'green'),
                     (1, 'Atenção', 'yellow'), (2, 'Moderado', 'orange'), (3, 'Crítico', 'red')]}}])


def stats(p, fields, labels=None, size=26, orientation='horizontal', dark=False):
    """One shared result, explicit field selection, no absolute positioning."""
    p['type'] = 'stat'
    p['options'] = {'reduceOptions': {'calcs': ['lastNotNull'], 'fields': '/.*/', 'values': False},
                    'colorMode': 'background_solid' if dark else 'value', 'graphMode': 'none',
                    'textMode': 'value_and_name' if labels else 'value', 'justifyMode': 'center',
                    'orientation': 'auto', 'wideLayout': False,
                    'text': {'valueSize': size, 'titleSize': 12}}
    p['transformations'] = [{'id': 'filterFieldsByName', 'options': {'include': {'names': fields}}},
                            {'id': 'organize', 'options': {'indexByName': {f: i for i, f in enumerate(fields)}}}]
    for f, label in (labels or {}).items():
        override(p, f, displayName=label)
    return p


def metric(pid, title, field, pos, unit='short', decimals=1, size=28):
    p = stats(panel(pid, title, 'stat', pos, source=1), [field], size=size)
    p['fieldConfig']['defaults'].update(unit=unit, decimals=decimals)
    return p


def nav(uid):
    return [{'title': name, 'type': 'link',
             'url': f'/d/{uid}?from=now-{period}&to=now&${{cabine:queryparam}}',
             'targetBlank': False} for name, period in [('10 min', '10m'), ('1 hora', '1h'),
                                                       ('24 horas', '24h'), ('1 semana', '7d'), ('1 mês', '30d')]]


def base(uid, title, panels, variables=None):
    return {'id': None, 'uid': uid, 'title': title, 'version': 3, 'schemaVersion': 39,
            'editable': False, 'tags': ['eletrometry', 'layout-v3', 'regras-provisórias'],
            'timezone': 'browser', 'refresh': R['refresh'],
            'time': {'from': 'now-24h', 'to': 'now'},
            'timepicker': {'refresh_intervals': ['30s', '1m', '5m'],
                           'time_options': ['10m', '1h', '24h', '7d', '30d']},
            'description': 'Dados do RDS. Layout v3, painéis nativos. Regras provisórias em REGRAS-DASHBOARDS.md.',
            'annotations': {'list': []}, 'links': nav(uid), 'panels': panels,
            'templating': {'list': variables or []}}


def overview():
    p = stats(panel(1, 'Alertas críticos', 'stat', (0, 0, 4, 4), sql.overview(),
                    description=''),
              ['alertas_criticos'], size=38)
    p['fieldConfig']['defaults']['decimals'] = 0
    panels = [p]
    for pid, title, field, x, unit in [
        (2, 'Cabine mais crítica', 'cabine_critica', 4, 'none'),
        (3, 'Tipo com mais ocorrências', 'tipo_problema', 9, 'none'),
        (4, 'Cabines com ocorrências', 'pct_ocorrencias', 14, 'percent'),
        (5, 'Cabines com reincidência', 'pct_reincidencia', 19, 'percent')]:
        p = metric(pid, title, field, (x, 0, 5, 4), unit, 1, 23 if pid in (2, 3) else 34)
        if pid in (2, 3):
            p['fieldConfig']['defaults']['noValue'] = 'Sem ocorrências'
        if pid == 4:
            p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
        if pid == 5:
            p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
        panels.append(p)
    override(panels[2], 'tipo_problema', mappings=[{'type': 'value', 'options': {
        'temperatura': {'text': 'Temperatura'}, 'corrente': {'text': 'Corrente'}}}])
    for i, cab in enumerate(R['cabines']):
        url = f'/d/{DETAIL}?var-cabine={cab}&${{__url_time_range}}'
        p = panel(20+i, cab.replace('cabine-', 'Cabine '), 'stat',
                  ((i % 3)*5, 4+(i//3)*13, 5, 13), sql.card(cab),
                  description='')
        fields = ['estado'] + [f'{kind}_{f}' for f in 'abc' for kind in ['corrente', 'temperatura']]
        labels = {'estado': 'Estado da cabine'}
        for f, name in zip('abc', 'RST'):
            labels['corrente_'+f] = 'Fase '+name+' · corrente'
            labels['temperatura_'+f] = 'Fase '+name+' · temperatura'
            override(p, 'corrente_'+f, unit='amp')
            override(p, 'temperatura_'+f, unit='celsius')
        stats(p, fields, labels, size=20, orientation='vertical', dark=True)
        p['fieldConfig']['defaults']['links'] = [{'title': 'Abrir cabine', 'url': url, 'targetBlank': False}]
        state(p)
        p['links'] = [{'title': 'Abrir cabine', 'url': url, 'targetBlank': False}]
        panels.append(p)
    p = panel(6, 'Ocorrências confirmadas · últimas 50', 'table', (15, 4, 9, 13), source=1,
              description='')
    p['transformations'] = [
        {'id': 'filterDataByValues', 'options': {'filters': [{'fieldName': 'Cabine', 'config': {'id': 'isNotNull', 'options': {}}}], 'type': 'include', 'match': 'all'}},
        {'id': 'organize', 'options': {
            'excludeByName': {f: True for f in ['alertas_criticos', 'cabine_critica', 'tipo_problema', 'pct_ocorrencias', 'pct_reincidencia', 'amostras', 'Ultima_leitura']},
            'indexByName': {'Nivel': 0, 'Cabine': 1, 'Alerta': 2, 'Fase': 3, 'Valor': 4, 'Unidade': 5, 'Confirmado': 6},
            'renameByName': {'Nivel': 'Nível', 'Confirmado': 'Quando'}}}]
    p['options'] = {'showHeader': True, 'cellHeight': 'sm', 'sortBy': [{'displayName': 'Quando', 'desc': True}], 'enablePagination': True}
    p['fieldConfig']['defaults'].update(noValue='—', **{'custom': {'filterable': True, 'minWidth': 60}})
    for field, width in [('Nível', 85), ('Cabine', 100), ('Alerta', 105), ('Fase', 45), ('Valor', 65), ('Unidade', 45), ('Quando', 100)]:
        override(p, field, **{'custom.width': width})
    override(p, 'Nível', mappings=[{'type': 'value', 'options': {k: {'text': k, 'color': v} for k, v in [('Crítico', 'red'), ('Moderado', 'orange'), ('Atenção', 'yellow')]}}], **{'custom.cellOptions': {'type': 'color-background'}})
    override(p, 'Quando', unit='dateTimeFromNow')
    panels.append(p)
    d = base(OVERVIEW, 'Eletrometry • Visão geral das cabines', panels)
    for link in d['links']:
        link['url'] = link['url'].replace('&${cabine:queryparam}', '')
    return polish(d)


def variables():
    cabines = ' UNION '.join('SELECT '+sql.quote(k)+' AS cabine_id' for k in R['cabines'])
    q = f'SELECT cabine_id AS __text,cabine_id AS __value FROM ({cabines} UNION SELECT DISTINCT cabine_id FROM leituras) c ORDER BY cabine_id'
    result = [{'name': 'cabine', 'label': 'Cabine', 'type': 'query', 'datasource': DS, 'query': q, 'definition': q, 'refresh': 1, 'multi': False, 'includeAll': False, 'sort': 1, 'current': {'text': next(iter(R['cabines'])), 'value': next(iter(R['cabines']))}, 'options': []}]
    for name, label, opts in [('metrica', 'Desvio', 'Temperatura : temperatura,Corrente : corrente'), ('sensor', 'Sensor', 'Temperatura : temperatura,Corrente : corrente'), ('fase', 'Fase', 'R (A) : A,S (B) : B,T (C) : C')]:
        pairs = [item.split(' : ') for item in opts.split(',')]
        result.append({'name': name, 'label': label, 'type': 'custom', 'query': opts, 'multi': False, 'includeAll': False, 'current': {'text': pairs[0][0], 'value': pairs[0][1]}, 'options': [{'text': k, 'value': v, 'selected': i == 0} for i, (k, v) in enumerate(pairs)]})
    return result


def detail():
    p = stats(panel(1, '${cabine:text} · estado no fim do período', 'stat', (0, 0, 4, 3), sql.details(),
                    description=''), ['estado'], size=23)
    state(p)
    panels = [p]
    for pid, name, field, x, unit, limits, maximum, ideal in [
        (2, 'Temperatura', 'temperatura', 4, 'celsius', R['temperature_thresholds_c'], 120, R['ideal_temperature_c']),
        (3, 'Corrente', 'corrente', 14, 'amp', [IIDEAL*m for m in R['current_alert_multipliers']], IMAX, IIDEAL)]:
        p = metric(pid, f'{name} · maior fase · ideal {ideal:g} '+('°C' if unit == 'celsius' else 'A'), field, (x, 0, 10, 3), unit)
        p['type'] = 'bargauge'
        p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
        p['fieldConfig']['defaults'].update(min=0, max=maximum, color={'mode': 'thresholds'}, thresholds=thresholds(limits))
        p['options'] = {'reduceOptions': {'calcs': ['lastNotNull'], 'fields': '/.*/', 'values': False}, 'orientation': 'horizontal', 'displayMode': 'basic', 'showUnfilled': True, 'valueMode': 'color', 'namePlacement': 'hidden', 'sizing': 'manual', 'minVizHeight': 16, 'maxVizHeight': 22}
        panels.append(p)
    for pid, title, field, x, unit, color in [
        (4, 'Tempo acima do ideal · ${metrica:text}', 'tempo_desvio', 0, 'dtdhms', BLUE),
        (13, 'Desvio atual · ${metrica:text}', 'desvio_atual', 4, 'short', BLUE),
        (14, 'Tempo em crítico · ${metrica:text}', 'tempo_critico', 8, 'dtdhms', 'red'),
        (5, 'Margem até 90 °C', 'margem', 12, 'celsius', NAVY),
        (15, 'Variação de temperatura', 'taxa', 16, 'suffix:°C/min', BLUE),
        (16, 'Tendência térmica', 'tendencia', 20, 'none', BLUE)]:
        p = metric(pid, title, field, (x, 3, 4, 4), unit, 0 if unit == 'dtdhms' else 1, 24)
        p['fieldConfig']['defaults']['color'] = {'mode': 'fixed', 'fixedColor': color}
        if pid == 4 or pid == 14:
            p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
        if pid == 13:
            p['title'] += ' (°C / A)'
            p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
        if pid == 5:
            p['fieldConfig']['defaults'].update(color={'mode': 'thresholds'}, thresholds={'mode': 'absolute', 'steps': [{'value': None, 'color': 'red'}, {'value': 0, 'color': 'green'}]})
        if pid == 15:
            p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
        panels.append(p)
    for pid, title, pos, query in [
        (6, 'Corrente e temperatura por fase', (0, 7, 16, 11), sql.phase_series()),
        (8, 'Carregamento · média das três fases', (16, 7, 8, 8), sql.load_series())]:
        p = panel(pid, title, 'timeseries', pos, query)
        p['targets'][0]['format'] = 'time_series'
        p['maxDataPoints'] = 700 if pid == 6 else 400
        p['interval'] = '1s'
        p['options'] = {'legend': {'displayMode': 'list', 'placement': 'bottom', 'calcs': []}, 'tooltip': {'mode': 'multi', 'sort': 'none'}}
        p['fieldConfig']['defaults'].update(unit='amp', color={'mode': 'fixed', 'fixedColor': '#FF9800'}, custom={'drawStyle': 'line', 'lineWidth': 2, 'fillOpacity': 0 if pid == 6 else 12, 'spanNulls': False, 'showPoints': 'auto', 'pointSize': 4, 'axisBorderShow': False, 'axisCenteredZero': False})
        if pid == 6:
            p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
            for phase, color in zip('ABC', COLORS):
                for name, unit, axis, style in [('Temp', 'celsius', 'right', 'solid'), ('Corr', 'amp', 'left', 'dash')]:
                    override(p, name+' '+phase, unit=unit, color={'mode': 'fixed', 'fixedColor': color}, **{'custom.axisPlacement': axis, 'custom.axisLabel': 'Temperatura (°C)' if name == 'Temp' else 'Corrente (A)', 'custom.lineStyle': {'fill': style, 'dash': [8, 5]}})
        else:
            p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
            override(p, 'Padrão calculado', color={'mode': 'fixed', 'fixedColor': MUTED}, **{'custom.lineStyle': {'fill': 'dash', 'dash': [8, 5]}, 'custom.fillOpacity': 0})
        panels.append(p)
    p = stats(panel(9, 'Referências de carregamento', 'stat', (16, 15, 8, 3), source=1), ['pico', 'pico_hora', 'duracao_pico', 'padrao'], {'pico': 'Pico · 24h', 'pico_hora': 'Horário do pico', 'duracao_pico': 'Tempo no pico', 'padrao': 'Média do período'}, size=17)
    for f in ['pico', 'padrao']:
        override(p, f, unit='amp')
    override(p, 'duracao_pico', unit='dtdhms', decimals=0)
    override(p, 'pico_hora', unit='time:HH:mm')
    p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
    panels.append(p)
    p = stats(panel(7, 'Desequilíbrio · correntes', 'stat', (0, 18, 6, 5), source=1), ['desequilibrio', 'media_fases'], {'desequilibrio': 'Desvio máximo', 'media_fases': 'Média das fases'}, size=27)
    override(p, 'desequilibrio', unit='percent', color={'mode': 'thresholds'}, thresholds=thresholds([5.000001, 10, 20]))
    override(p, 'media_fases', unit='amp')
    p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
    panels.append(p)
    for j, f in enumerate('abc'):
        p = stats(panel(30+j, 'Fase '+'RST'[j]+' · corrente', 'stat', (6+j*6, 18, 6, 5), source=1), ['corrente_'+f, 'delta_'+f, 'delta_pct_'+f], {'corrente_'+f: 'Última leitura', 'delta_'+f: 'Desvio (A)', 'delta_pct_'+f: 'Desvio (%)'}, size=20)
        override(p, 'corrente_'+f, unit='amp')
        override(p, 'delta_pct_'+f, unit='percent')
        override(p, 'delta_'+f, unit='amp')
        panels.append(p)
    p = stats(panel(10, 'Telemetria · ${sensor:text} / ${fase:text}', 'stat', (0, 23, 8, 5), source=1), ['sensor_estado', 'sensor_idade'], {'sensor_estado': 'Comunicação', 'sensor_idade': 'Idade da leitura'}, size=20)
    override(p, 'sensor_estado', unit='none')
    override(p, 'sensor_idade', unit='s', decimals=0)
    p['description'] = 'Regras: REGRAS-DASHBOARDS.md'
    panels.append(p)
    p = metric(11, 'Medição · ${sensor:text} / ${fase:text}', 'sensor_valor', (8, 23, 4, 5), 'short')
    p['transformations'].insert(0, {'id': 'configFromData', 'options': {'configRefId': 'A', 'applyTo': {'id': 'byName', 'options': 'sensor_valor'}, 'mappings': [{'fieldName': 'sensor_unit', 'handlerKey': 'unit', 'reducerId': 'lastNotNull'}]}})
    panels.append(p)
    p = metric(17, 'Faixa da leitura selecionada', 'sensor_severity', (12, 23, 4, 5), 'none', 0, 20)
    state(p, 'sensor_severity')
    panels.append(p)
    p = stats(panel(12, 'Comunicação · correntes R / S / T', 'stat', (16, 23, 8, 5), source=1), ['saude_a', 'saude_b', 'saude_c'], {'saude_a': 'R', 'saude_b': 'S', 'saude_c': 'T'}, size=16)
    p['fieldConfig']['defaults']['unit'] = 'none'
    panels.append(p)
    d = base(DETAIL, 'Eletrometry • Dashboard interna da cabine', panels, variables())
    d['links'].insert(0, {'title': '← Visão geral', 'type': 'link', 'url': f'/d/{OVERVIEW}?${{__url_time_range}}', 'targetBlank': False})
    return polish(d)


def polish(d):
    d['version'] = 4
    for p in d['panels']:
        if p['type'] == 'stat':
            p['options']['colorMode'] = 'value'
            p['options']['text']['valueSize'] = 22
        if d['uid'] == OVERVIEW and 20 <= p['id'] < 30:
            p['type'] = 'table'
            p['gridPos'] = dict(x=0,y=4+(p['id']-20)*4,w=24,h=4)
            p['options'] = {'showHeader':True,'cellHeight':'sm'}
            p['fieldConfig']['defaults']['color'] = {'mode':'fixed','fixedColor':'text'}
        if d['uid'] == OVERVIEW and p['id'] == 6:
            p['gridPos'] = dict(x=0,y=16,w=24,h=10)
        if d['uid'] == DETAIL and p['id'] == 9:
            p['gridPos']['h'] = 5
        if d['uid'] == DETAIL and p['gridPos']['y'] >= 18:
            p['gridPos']['y'] += 2
    d['links'].insert(0, {'title':'Histórico da cabine','type':'link','url':'/d/eletrometry-historico?${cabine:queryparam}&${__url_time_range}'})
    if d['uid'] == OVERVIEW:
        d['links'][0]['url'] = '/d/eletrometry-historico?${__url_time_range}'
    return d


def history():
    summary = sql.base(sql.CF) + """
SELECT COUNT(*) total,COALESCE(SUM(severity=3),0) criticos,
 COALESCE(SUM(severity=2),0) moderados,COALESCE(SUM(severity=1),0) atencao
FROM events"""
    p = stats(panel(1,'Eventos confirmados','stat',(0,0,6,4),summary),['total'])
    p['fieldConfig']['defaults']['decimals']=0
    panels=[p]
    for pid,label,field,x in [(2,'Críticos','criticos',6),(3,'Moderados','moderados',12),(4,'Em atenção','atencao',18)]:
        panels.append(metric(pid,label,field,(x,0,6,4),'short',0))
    import copy
    chart=copy.deepcopy(next(p for p in detail()['panels'] if p['id']==6))
    chart['gridPos']=dict(x=0,y=4,w=24,h=11)
    panels.append(chart)
    q=sql.base(sql.CF)+"""
SELECT FROM_UNIXTIME(FLOOR(confirmed_ts/3600)*3600) time,
 SUM(severity=3) Criticos,SUM(severity=2) Moderados,SUM(severity=1) Atencao
FROM events WHERE confirmed_ts>=UNIX_TIMESTAMP("""+sql.START+""")
GROUP BY 1 ORDER BY 1"""
    p=panel(7,'Eventos confirmados por hora','timeseries',(0,15,24,8),q,
        description='Contagem por hora de confirmação. Cada evento pertence a cabine, tipo e fase; classe = maior severidade observada. Eventos confirmados antes do início não entram neste gráfico.')
    p['targets'][0]['format']='time_series'
    p['fieldConfig']['defaults'].update(decimals=0,custom={'drawStyle':'bars','fillOpacity':80,'lineWidth':0,'stacking':{'mode':'normal','group':'A'}})
    for name,color in [('Criticos','red'),('Moderados','orange'),('Atencao','yellow')]:
        override(p,name,color={'mode':'fixed','fixedColor':color})
    p['options']={'legend':{'displayMode':'list','placement':'bottom'},'tooltip':{'mode':'multi'}}
    panels.append(p)
    q=sql.base(sql.CF)+"""
SELECT FROM_UNIXTIME(confirmed_ts) Confirmado,tipo Tipo,fase Fase,
 CASE severity WHEN 3 THEN 'Crítico' WHEN 2 THEN 'Moderado' ELSE 'Atenção' END Nivel,
 peak Maximo,CASE tipo WHEN 'temperatura' THEN '°C' ELSE 'A' END Unidade,
 FROM_UNIXTIME(first_ts) Inicio_observado,FROM_UNIXTIME(last_ts) Ultima_leitura
FROM events ORDER BY confirmed_ts DESC LIMIT 500"""
    p=panel(8,'Histórico de ocorrências · até 500 eventos','table',(0,23,24,12),q,
        description='Eventos reconstruídos das leituras. Início pode estar truncado pelo período e sua margem de 60s. Última leitura não significa reparo ou fechamento. Use o seletor temporal para consultar períodos menores.')
    p['options']={'showHeader':True,'cellHeight':'sm','enablePagination':True}
    p['fieldConfig']['defaults'].update(decimals=1,custom={'filterable':True})
    for f in ['Confirmado','Inicio_observado','Ultima_leitura']: override(p,f,unit='dateTimeAsIso')
    panels.append(p)
    d=base('eletrometry-historico','Eletrometry • Histórico da cabine',panels,[variables()[0]])
    d['links'][:0]=[{'title':'Visão geral','type':'link','url':'/d/'+OVERVIEW+'?${__url_time_range}'},{'title':'Detalhe operacional','type':'link','url':'/d/'+DETAIL+'?${cabine:queryparam}&${__url_time_range}'}]
    return d


def main():
    folder = Path(__file__).resolve().parent/'dashboards'
    folder.mkdir(exist_ok=True)
    for filename, data in [('visao-geral.json', overview()), ('eletrometry.json', detail()), ('historico.json', history())]:
        (folder/filename).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(filename, len(data['panels']), 'painéis')


if __name__ == '__main__':
    main()
