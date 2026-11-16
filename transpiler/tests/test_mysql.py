"""Execute generated SQL on a disposable MySQL 8, never on the production database."""
from datetime import datetime, timedelta
import os
from pathlib import Path
import unittest
from transpiler.compiler import compile_source

@unittest.skipUnless(os.environ.get("ELT_TEST_MYSQL") == "1", "MySQL integration disabled")
class MySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import mysql.connector
        cls.db = mysql.connector.connect(host="127.0.0.1", user="root",
                                         password="test-only", database="elt_test")
        cur = cls.db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS leituras(
            event_id VARCHAR(160) PRIMARY KEY, cabine_id VARCHAR(32), tipo VARCHAR(20),
            coletado_em DATETIME(3), fase_a DECIMAL(9,2), fase_b DECIMAL(9,2),
            fase_c DECIMAL(9,2), qualidade_a VARCHAR(20),
            qualidade_b VARCHAR(20), qualidade_c VARCHAR(20))""")
        cur.close()
        cls.start = datetime(2026, 1, 1)
        cls.source = (Path(__file__).parents[1] / "examples/temperatura.elt").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        cur = self.db.cursor()
        cur.execute("DELETE FROM leituras")
        self.db.commit()
        cur.close()

    def insert(self, seconds, a=95, b=40, c=40, quality="ok"):
        cur = self.db.cursor()
        cur.execute("INSERT INTO leituras VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (str(seconds), "cabine-002", "temperatura", self.start + timedelta(seconds=seconds),
                     a, b, c, quality, "ok", "ok"))
        self.db.commit()
        cur.close()

    def query(self, source=None):
        sql = compile_source(source or self.source, ["cabine-002"])["queries"][0]["sql"]
        cur = self.db.cursor(dictionary=True)
        cur.execute(sql, {"start": self.start, "end": self.start + timedelta(seconds=100)})
        rows = cur.fetchall()
        cur.close()
        return rows

    def test_persistent_condition(self):
        for second in [0, 5, 10, 15]:
            self.insert(second)
        result = self.query()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["fase"], "A")
        self.assertEqual(result[0]["confirmado_em"], self.start + timedelta(seconds=10))

    def test_boundary_equality(self):
        for second in [0, 5, 10]:
            self.insert(second, a=90)
        self.assertEqual(len(self.query()), 1)
        self.assertEqual(self.query(self.source.replace(">=", ">")), [])

    def test_gap_interrupts(self):
        for second in [0, 5, 11, 16]:
            self.insert(second)
        self.assertEqual(self.query(), [])

    def test_invalid_quality_interrupts(self):
        self.insert(0)
        self.insert(5, quality="sem_leitura", a=None)
        self.insert(10)
        self.assertEqual(self.query(), [])

    def test_below_threshold_interrupts(self):
        for second, value in [(0,95), (5,40), (10,95)]:
            self.insert(second, a=value)
        self.assertEqual(self.query(), [])

    def test_phases_do_not_share_duration(self):
        self.insert(0, a=95)
        self.insert(5, a=40, b=95)
        self.insert(10, a=40, b=95)
        self.assertEqual(self.query(), [])

    def test_empty_data(self):
        self.assertEqual(self.query(), [])

    def test_short_spike(self):
        self.insert(0)
        self.assertEqual(self.query(), [])

    def test_zero_duration_and_specific_phase(self):
        self.insert(0, a=95, b=95)
        rule = self.source.replace("DURANTE 10", "DURANTE 0").replace("FASE QUALQUER", "FASE B")
        result = self.query(rule)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["fase"], "B")

if __name__ == "__main__":
    unittest.main()
