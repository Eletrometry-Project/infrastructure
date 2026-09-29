import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location("adapter", Path(__file__).parents[1] / "deploy/run_service.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class ServiceAdapterTests(unittest.TestCase):
    def test_credential_tls_and_continuous_consumption(self):
        config = {"db_host": "mock.rds.amazonaws.com", "db_user": "eletrometry_consumer",
                  "ca_file": "/mock/ca.pem", "aws_region": "us-east-1",
                  "queue_url": "https://mock/queue", "repo_path": "/mock/repo"}
        upstream = types.ModuleType("consumidor_sqs_mysql")
        upstream.consume = MagicMock(return_value=0)
        database = MagicMock()
        session = MagicMock()
        def read_text(path, *args, **kwargs):
            return json.dumps(config) if path.name == "runtime.json" else " synthetic-password-with-spaces "
        with patch.dict(sys.modules, {"consumidor_sqs_mysql": upstream}), \
             patch.dict(adapter.os.environ, {"CREDENTIALS_DIRECTORY": "/run/credentials/mock"}), \
             patch.object(Path, "read_text", read_text), \
             patch.object(adapter.mysql.connector, "connect", return_value=database) as connect, \
             patch.object(adapter.boto3, "Session", return_value=session):
            try:
                self.assertEqual(adapter.main(), 0)
            finally:
                sys.path.remove("/mock/repo")
        self.assertTrue(connect.call_args.kwargs["ssl_verify_cert"])
        self.assertTrue(connect.call_args.kwargs["ssl_verify_identity"])
        self.assertEqual(connect.call_args.kwargs["password"], " synthetic-password-with-spaces ")
        upstream.consume.assert_called_once_with(session.client.return_value, database, config["queue_url"], 0)
        database.close.assert_called_once()

    def test_password_file_is_atomic_and_private(self):
        import tempfile
        setup_spec = importlib.util.spec_from_file_location("setup", Path(__file__).parents[1] / "deploy/setup_database.py")
        setup = importlib.util.module_from_spec(setup_spec)
        setup_spec.loader.exec_module(setup)
        with tempfile.TemporaryDirectory() as temporary:
            secret = Path(temporary) / "password"
            setup.write_password(secret, "synthetic-one")
            self.assertEqual(secret.stat().st_mode & 0o777, 0o600)
            setup.write_password(secret, "synthetic-two")
            self.assertEqual(secret.read_text(), "synthetic-two")
            self.assertEqual(list(Path(temporary).iterdir()), [secret])
