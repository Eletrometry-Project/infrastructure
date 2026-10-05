"""Bootstrap automatico e verificacao final, sem AWS/MySQL reais."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import mysql.connector


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'deploy' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


setup = module('setup_database')
check = module('check_database')


class BootstrapTests(unittest.TestCase):
    def test_retries_transient_rds_startup_with_tls(self):
        db = MagicMock()
        with patch.object(setup.mysql.connector, 'connect', side_effect=[mysql.connector.Error(errno=2003), db]) as connect, patch.object(setup.time, 'sleep') as sleep:
            result = setup.connect_admin({'db_host': 'test', 'ca_file': '/ca'}, {'admin_user': 'admin', 'admin_password': 'synthetic'}, attempts=2)
        self.assertIs(result, db)
        self.assertTrue(connect.call_args.kwargs['ssl_verify_identity'])
        sleep.assert_called_once_with(5)

    def test_does_not_retry_invalid_password(self):
        with patch.object(setup.mysql.connector, 'connect', side_effect=mysql.connector.Error(errno=1045)) as connect, patch.object(setup.time, 'sleep') as sleep:
            with self.assertRaises(mysql.connector.Error):
                setup.connect_admin({'db_host': 'test', 'ca_file': '/ca'}, {'admin_user': 'admin', 'admin_password': 'synthetic'})
        self.assertEqual(connect.call_count, 1)
        sleep.assert_not_called()

    def test_bootstrap_keeps_secrets_on_failure_and_cleans_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config'; config.write_text('{}')
            secrets = root / 'secrets'; secrets.write_text('{"app_password":"synthetic"}')
            password = root / 'password'
            with patch.object(setup, 'CONFIG', config), patch.object(setup, 'SECRETS', secrets), patch.object(setup, 'PASSWORD', password), patch.object(setup.os, 'geteuid', return_value=0), patch.object(setup, 'connect_admin', side_effect=mysql.connector.Error(errno=1045)):
                with self.assertRaises(SystemExit): setup.main()
            self.assertTrue(secrets.exists())
            self.assertFalse(password.exists())
            db = MagicMock()
            # Only schema read is simulated, while secret/config files remain real.
            original = Path.read_text
            def read(path, *args, **kwargs):
                return 'CREATE TABLE example(id int);' if path.name == '001-schema.sql' else original(path, *args, **kwargs)
            with patch.object(setup, 'CONFIG', config), patch.object(setup, 'SECRETS', secrets), patch.object(setup, 'PASSWORD', password), patch.object(setup.os, 'geteuid', return_value=0), patch.object(setup, 'connect_admin', return_value=db), patch.object(Path, 'read_text', read):
                setup.main()
            self.assertFalse(secrets.exists())
            self.assertEqual(password.read_text(), 'synthetic')
            db.close.assert_called_once()

    def test_e2e_requires_expected_values(self):
        db = MagicMock()
        db.cursor.return_value.fetchone.return_value = (1, 100, 101, 102)
        self.assertEqual(check.wait_for_event(db, 'unique-id', 0), 0)
        db.cursor.return_value.fetchone.return_value = (1, 0, 0, 0)
        self.assertEqual(check.wait_for_event(db, 'unique-id', 0), 1)

    def test_e2e_missing_message_is_failure(self):
        db = MagicMock()
        db.cursor.return_value.fetchone.return_value = (0, None, None, None)
        self.assertEqual(check.wait_for_event(db, 'unique-id', 0), 1)
        db.cursor.return_value.execute.assert_called_once()
        self.assertEqual(db.cursor.return_value.execute.call_args.args[1], ('unique-id',))


if __name__ == '__main__':
    unittest.main()
