"""Testa codigo REAL do repo revisado; AWS/MySQL simulados, sem chamadas externas."""
import importlib.util
import json
import os
from pathlib import Path
import unittest

import mysql.connector


repo_path = Path(os.environ.get("CONSUMER_REPO_PATH", Path(__file__).parents[1] / "consumer"))
spec = importlib.util.spec_from_file_location("upstream_consumer", repo_path / "consumidor_sqs_mysql.py")
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


def message(event_id="test:event:1"):
    return {
        "MessageId": "test-message", "ReceiptHandle": "test-receipt",
        "Body": json.dumps({
            "schema_version": 1, "event_id": event_id, "run_id": "test-run",
            "cabine_id": "cabine-001", "tipo": "corrente", "sequence": 1,
            "timestamp": "2026-09-28T23:00:00Z", "valores": {"A": 100, "B": 101, "C": 102},
            "qualidade": {"A": "ok", "B": "ok", "C": "ok"},
        }),
    }


class FakeDB:
    def __init__(self, events, fail=False, rowcount=1):
        self.events, self.fail, self.rowcount = events, fail, rowcount

    def cursor(self): return self
    def executemany(self, sql, rows):
        self.rows = rows
        self.events.append("insert")
        if self.fail:
            raise mysql.connector.Error("synthetic failure")
    def commit(self): self.events.append("commit")
    def rollback(self): self.events.append("rollback")
    def close(self): pass


class FakeSQS:
    def __init__(self, events, messages):
        self.events, self.messages = events, messages
    def receive_message(self, **kwargs):
        return {"Messages": self.messages}
    def delete_message_batch(self, **kwargs):
        self.entries = kwargs["Entries"]
        self.events.append("delete")
        return {"Successful": [{"Id": item["Id"]} for item in self.entries]}


class ConsumerContractTests(unittest.TestCase):
    def test_delete_happens_after_commit(self):
        events = []
        result = consumer.consume(FakeSQS(events, [message()]), FakeDB(events), "mock-url", 1)
        self.assertEqual(result, 0)
        self.assertEqual(events, ["insert", "commit", "delete"])

    def test_database_error_keeps_message(self):
        events = []
        result = consumer.consume(FakeSQS(events, [message()]), FakeDB(events, fail=True), "mock-url", 1)
        self.assertEqual(result, 1)
        self.assertEqual(events, ["insert", "rollback"])

    def test_invalid_message_kept_and_valid_message_processed(self):
        events = []
        invalid = message()
        invalid["Body"] = '{"old_contract": true}'
        result = consumer.consume(FakeSQS(events, [invalid, message()]), FakeDB(events), "mock-url", 1)
        self.assertEqual(result, 0)
        self.assertEqual(events, ["insert", "commit", "delete"])

    def test_duplicate_is_committed_and_acknowledged(self):
        events = []
        result = consumer.consume(FakeSQS(events, [message()]), FakeDB(events, rowcount=0), "mock-url", 1)
        self.assertEqual(result, 0)
        self.assertEqual(events, ["insert", "commit", "delete"])

    def test_ten_messages_use_one_transaction_and_one_ack(self):
        events = []
        db = FakeDB(events)
        sqs = FakeSQS(events, [message(str(i)) for i in range(10)])
        self.assertEqual(consumer.consume(sqs, db, 'mock-url', 1), 0)
        self.assertEqual(events, ['insert', 'commit', 'delete'])
        self.assertEqual(len(db.rows), 10)
        self.assertEqual(len(sqs.entries), 10)

    def test_commit_failure_keeps_entire_batch(self):
        events = []
        db = FakeDB(events)
        def fail():
            events.append('commit')
            raise mysql.connector.Error('commit failed')
        db.commit = fail
        self.assertEqual(consumer.consume(FakeSQS(events, [message('1'), message('2')]), db, 'mock', 1), 1)
        self.assertEqual(events, ['insert', 'commit', 'rollback'])

    def test_partial_ack_is_not_reported_as_complete(self):
        events = []
        sqs = FakeSQS(events, [message('1'), message('2')])
        sqs.delete_message_batch = lambda **kw: {'Successful': [{'Id':'0'}], 'Failed':[{'Id':'1','Code':'InternalError'}]}
        self.assertEqual(consumer.consume(sqs, FakeDB(events), 'mock', 1), 1)
        self.assertEqual(events, ['insert', 'commit'])

    def test_invalid_message_is_excluded_from_ack_batch(self):
        events = []
        invalid = message('bad'); invalid['Body'] = '{}'
        sqs = FakeSQS(events, [invalid, message('valid')]); db = FakeDB(events)
        self.assertEqual(consumer.consume(sqs, db, 'mock', 1), 0)
        self.assertEqual([row[0] for row in db.rows], ['valid'])
        self.assertEqual(len(sqs.entries), 1)

    def test_quality_null_contract(self):
        payload = json.loads(message()["Body"])
        payload["valores"]["B"] = None
        payload["qualidade"]["B"] = "sem_leitura"
        row = consumer.row_from_body(json.dumps(payload))
        self.assertIsNone(row[7])
        payload["qualidade"]["B"] = "ok"
        with self.assertRaises(ValueError):
            consumer.row_from_body(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
