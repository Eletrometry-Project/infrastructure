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
        import subprocess
        packed = (ROOT/'infra/panel-files.br').read_bytes()
        runtime = {'db_host':'example.us-east-1.rds.amazonaws.com','passwords':'A'*128}
        template = (ROOT/'infra/panel-bootstrap.tftpl').read_text()
        script = template.replace('${files}',base64.b64encode(packed).decode()).replace(
            '${runtime}',base64.b64encode(json.dumps(runtime).encode()).decode())
        compile(script, '<user-data>', 'exec')
        self.assertLessEqual(len(gzip.compress(script.encode())), 16384)
        decoded = subprocess.check_output(['node','-e',
            "process.stdout.write(require('node:zlib').brotliDecompressSync(require('node:fs').readFileSync(0)))"], input=packed)
        files = json.loads(decoded)
        dashboards = {name for name in files if name.startswith('dashboards/')}
        self.assertEqual(len(dashboards), 5)
        for name in dashboards:
            self.assertEqual(json.loads(files[name]), json.loads((ROOT/'observability'/name).read_text()))
        self.assertNotIn('build_dashboard.py', files['install.sh'])

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
