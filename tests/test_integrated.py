import base64
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch
import yaml

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

c=load('panels_configure',ROOT/'observability/configure.py')
h=load('panels_health',ROOT/'observability/health.py')

class IntegratedTests(unittest.TestCase):
    def test_reader_tls_and_only_select(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c,'ROOT',Path(tmp)),patch.object(c.mysql.connector,'connect') as connect:
            config={'db_host':'example.rds','db_name':'eletrometry','admin_user':'admin','admin_password':'test-admin','mysql_password':'test-reader'}
            c.reader(config)
            calls=connect.return_value.cursor.return_value.execute.call_args_list
            grants=[call.args[0] for call in calls if call.args[0].startswith('GRANT ')]
            self.assertEqual(grants,["GRANT SELECT ON eletrometry.leituras TO 'eletrometry_grafana'@'%'"])
            self.assertTrue(connect.call_args.kwargs['ssl_verify_identity'])
            self.assertTrue((Path(tmp)/'reader-ready').exists())
            self.assertFalse(any('test-admin' in call.args[0] or 'test-reader' in call.args[0] for call in calls))

    def test_repeat_uses_reader_without_admin_secret(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'ROOT',Path(tmp)),patch.object(c.mysql.connector,'connect') as connect:
            (Path(tmp)/'reader-ready').touch()
            c.reader({'db_host':'example.rds','db_name':'eletrometry','mysql_password':'test-reader'})
            self.assertEqual(connect.call_args.kwargs['user'],'eletrometry_grafana')
            self.assertEqual(connect.return_value.cursor.return_value.execute.call_count,1)

    def test_failed_database_does_not_mark_reader_ready(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'ROOT',Path(tmp)),patch.object(c.mysql.connector,'connect',side_effect=c.mysql.connector.Error(errno=1045)):
            with self.assertRaises(c.mysql.connector.Error):
                c.reader({'db_host':'example.rds','db_name':'eletrometry','admin_user':'admin','admin_password':'test-admin','mysql_password':'test-reader'})
            self.assertFalse((Path(tmp)/'reader-ready').exists())

    def test_datasource_does_not_contain_admin_or_graph_password(self):
        config={'db_host':'rds.example','db_name':'eletrometry','mysql_password':'reader-test','admin_password':'master-test','neo4j_password':'graph-test'}
        d=c.datasource(config,'ca-test');serialized=json.dumps(d)
        self.assertNotIn('master-test',serialized);self.assertNotIn('graph-test',serialized)
        self.assertTrue(d['datasources'][0]['jsonData']['tlsAuthWithCACert'])
        self.assertFalse(d['datasources'][0]['jsonData']['tlsSkipVerify'])

    def test_graph_secret_not_in_environment_configuration(self):
        env=c.neo4j_env({'public_ip':'203.0.113.10','neo4j_password':'graph-test'})
        self.assertNotIn('graph-test',env)
        self.assertIn('NEO4J_AUTH_FILE=',env)
        self.assertIn('203.0.113.10:7687',env)
        self.assertIn('heap_max__size=768m',env)

    def test_dashboard_all_panels_share_filter(self):
        dashboard=json.loads((ROOT/'observability/dashboards/eletrometry.json').read_text())
        self.assertEqual(dashboard['uid'],'eletrometry-cabines')
        for panel in dashboard['panels']:
            target=panel.get('targets',[{}])[0]
            if 'rawSql' in target:
                self.assertIn('${cabine:sqlstring}',target['rawSql'])
            else:
                self.assertEqual(target.get('panelId'),1)

    def test_cloudinit_size_and_decodable_payload(self):
        # Mesmo conjunto de arquivos e estrutura do Terraform; valores ficticios de tamanho realista.
        paths=['install.sh','configure.py','health.py','build_dashboard.py','dashboard_sql.py','analysis_rules.json','eletrometry-bootstrap.service',
               'neo4j/Dockerfile','neo4j/health.sh','neo4j/eletrometry-neo4j.service']
        files=[{'path':'/opt/eletrometry-observability/'+n,'permissions':'0644','owner':'root:root',
                'content':(ROOT/'observability'/n).read_text()} for n in paths]
        config={'db_host':'eletrometry-lab.cfwcj9fejx5w.us-east-1.rds.amazonaws.com','db_name':'eletrometry','admin_user':'eletrometry_admin',
            'admin_password':'A'*24,'mysql_password':'B'*32,'grafana_password':'C'*32,'neo4j_password':'D'*32,
            'grafana_url':'http://elgraf20261005180000000000000001-1234567890.us-east-1.elb.amazonaws.com','public_ip':'203.0.113.123'}
        files.append({'path':'/etc/eletrometry-observability/bootstrap.json','permissions':'0600','owner':'root:root','content':json.dumps(config)})
        raw=('#cloud-config\n'+json.dumps({'write_files':files,'runcmd':[['cp','/opt/eletrometry-observability/eletrometry-bootstrap.service','/etc/systemd/system/eletrometry-bootstrap.service'],['systemctl','daemon-reload'],['systemctl','enable','--now','--no-block','eletrometry-bootstrap.service']]})).encode()
        compressed=gzip.compress(raw)
        self.assertLess(len(compressed),16000) # folga para senhas aleatorias e diferencas de yamlencode
        restored=yaml.safe_load(gzip.decompress(compressed))
        self.assertEqual(len(restored['write_files']),11)
        print('User-data representativo comprimido:',len(compressed),'bytes (limite EC2: 16384)')

    @patch.object(h.Path,'read_text',return_value='{"grafana_password":"test"}')
    @patch.object(h.urllib.request,'urlopen')
    @patch.object(h.subprocess,'run')
    def test_health_does_not_hide_sql_errors(self,run,urlopen,_):
        responses=[]
        for body in [{},{'status':'OK'},{'results':{'A':{'status':500,'error':'failed'}}}]:
            response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(body);responses.append(response)
        urlopen.side_effect=responses
        with self.assertRaisesRegex(SystemExit,'MySQL pelo Grafana falhou'):h.main()
        run.assert_not_called()

    def test_writer_restricts_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'runtime.json';c.write(p,'test')
            self.assertEqual(p.stat().st_mode & 0o777,0o600)

if __name__=='__main__':unittest.main()
