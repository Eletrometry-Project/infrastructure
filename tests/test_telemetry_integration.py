"""Contrato real simulador -> consumidor e verificador de entrega. Sem chamadas AWS."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


remote = load('lab_remote', ROOT / 'deploy/lab_remote.py')
consumer = load('bundled_consumer', ROOT / 'consumer/consumidor_sqs_mysql.py')


class TelemetryIntegrationTests(unittest.TestCase):
    def test_actual_simulator_372_messages_accepted_by_actual_consumer(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, str(ROOT / 'telemetry/simulador_eletrometry.py'),
                       'simular', '--config', str(ROOT / 'telemetry/config_industrial.json'),
                       '--cabines', '3', '--duracao', '120', '--modo', 'acelerado',
                       '--inicio', '2026-10-04T12:00:00Z', '--saida', directory]
            subprocess.run(command, check=True, capture_output=True)
            folder = next(Path(directory).glob('*/manifesto.json')).parent
            events = remote.expected_events(folder)
            self.assertEqual(len(events), 372)
            counts = Counter()
            import gzip
            for path in folder.glob('telemetria/**/*.jsonl.gz'):
                with gzip.open(path, 'rt') as stream:
                    for line in stream:
                        row = consumer.row_from_body(line)
                        counts[(row[2], row[3])] += 1
            self.assertEqual(counts, Counter({(f'cabine-{i:03d}', kind): count
                             for i in range(1, 4) for kind, count in [('corrente', 120), ('temperatura', 4)]}))

    def test_equal_count_but_wrong_events_is_not_success(self):
        expected = {'id1': ('cabine-001', 'corrente')}
        self.assertFalse(remote.compare_events(expected, [('other', 'cabine-001', 'corrente')]))
        self.assertFalse(remote.compare_events(expected, [('id1', 'cabine-001', 'temperatura')]))
        self.assertTrue(remote.compare_events(expected, [('id1', 'cabine-001', 'corrente')]))

    def test_missing_event_fails_and_query_is_scoped_to_run(self):
        db = MagicMock()
        with patch.object(remote, 'database', return_value=db), patch.object(remote, 'query', return_value=[]) as query:
            self.assertEqual(remote.verify_run({'db_host': 'test'}, 'new-run', {'id': ('cabine-001','corrente')}, wait=0), 1)
        self.assertEqual(query.call_args.args[2], ('new-run',))
        db.close.assert_called_once()

    def test_empty_expected_never_passes(self):
        with self.assertRaises(RuntimeError):
            remote.verify_run({}, 'empty', {})

    def test_success_report_uses_exact_run_and_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(remote, 'STATE', Path(directory)), patch.object(remote, 'database', return_value=MagicMock()), patch.object(remote, 'query', return_value=[('id','cabine-001','corrente')]):
                self.assertEqual(remote.verify_run({'db_host':'test'}, 'run1', {'id':('cabine-001','corrente')}, 0), 0)
            report = json.loads((Path(directory)/'latest-check.json').read_text())
            self.assertEqual(report['run_id'], 'run1')
            self.assertEqual(report['actual'], 1)

    def test_failed_publish_never_runs_database_success_check(self):
        fake_session = MagicMock()
        fake_session.client.return_value.publish.side_effect = RuntimeError('synthetic network failure')
        with patch.object(remote, 'service', return_value='active'), patch.object(remote, 'endpoint', return_value='example'), patch.object(remote, 'session', return_value=fake_session), patch.object(remote.subprocess, 'call') as call:
            with self.assertRaises(RuntimeError): remote.smoke({})
        call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
