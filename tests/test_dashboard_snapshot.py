"""Estado atual e compartilhamento de resultados, sem Grafana/MySQL externos."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'observability'))
import build_management as dashboard
sys.path.pop(0)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('UNIX_TIMESTAMP', 1, float)
        self.db.execute('CREATE TABLE leituras(event_id TEXT, cabine_id TEXT, tipo TEXT, coletado_em REAL, '
                        'fase_a REAL,fase_b REAL,fase_c REAL,qualidade_a TEXT,qualidade_b TEXT,qualidade_c TEXT)')

    def tearDown(self):
        self.db.close()

    def add(self, cab, kind, when, value, quality='ok', event_id='1'):
        self.db.execute('INSERT INTO leituras VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (event_id,cab,kind,when,value,value,value,quality,quality,quality))

    def states(self):
        sql = dashboard.current_cte().replace(dashboard.s.START, '0').replace(dashboard.s.END, '100')
        return self.db.execute(sql+'SELECT cabine_id,estado FROM current_state ORDER BY cabine_id').fetchall()

    def test_normal_critical_and_missing_inventory(self):
        for kind, normal, critical in [('corrente',240,590),('temperatura',45,95)]:
            self.add('cabine-001',kind,99,normal)
            self.add('cabine-002',kind,99,critical)
        self.assertEqual(self.states(), [('cabine-001',0),('cabine-002',3),('cabine-003',-1)])

    def test_old_or_invalid_is_not_normal(self):
        for kind in ['corrente','temperatura']:
            self.add('cabine-001',kind,20,40)
            self.add('cabine-002',kind,99,None,'sem_leitura')
        self.assertTrue(all(state == -1 for _,state in self.states()))

    def test_latest_reading_wins_even_if_prior_reading_was_critical(self):
        for kind in ['corrente','temperatura']:
            self.add('cabine-001',kind,80,600,event_id='old')
            self.add('cabine-001',kind,99,40,event_id='new')
        self.assertEqual(self.states()[0], ('cabine-001',0))

    def test_five_dashboards_and_shared_sources_are_real_sql_panels(self):
        files = list((ROOT/'observability/dashboards').glob('*.json'))
        self.assertEqual(len(files),5)
        for path in files:
            data=json.loads(path.read_text()); panels={p['id']:p for p in data['panels']}
            for p in panels.values():
                for target in p.get('targets',[]):
                    if 'panelId' in target:
                        source=panels[target['panelId']]
                        self.assertTrue(any(t.get('rawSql') for t in source['targets']))
                        self.assertFalse(target['withTransforms'])
        data=json.loads((ROOT/'observability/dashboards/visao-geral.json').read_text())
        queries=[t['rawSql'] for p in data['panels'] for t in p.get('targets',[]) if t.get('rawSql')]
        self.assertEqual(sum('event_groups AS' in q for q in queries),1)
