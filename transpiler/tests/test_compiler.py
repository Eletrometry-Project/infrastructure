import io
import json
from pathlib import Path
import unittest
from transpiler.compiler import compile_source, CompileError
from transpiler.lambda_handler import process_record

ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / "examples/temperatura.elt").read_text(encoding="utf-8")
CABINS = ["cabine-001", "cabine-002", "cabine-003"]

class CompilerTests(unittest.TestCase):
    def test_pipeline(self):
        result = compile_source(SOURCE, CABINS)
        self.assertEqual(result["ast"][0]["phase"], "QUALQUER")
        self.assertEqual(result["tokens"][0]["value"], "REGRA")
        self.assertIn("qualidade_c = 'ok'", result["queries"][0]["sql"])
        self.assertIn("%(start)s", result["queries"][0]["sql"])

    def test_errors(self):
        cases = [
            (SOURCE.replace(">=", "!"), "lexico"),
            (SOURCE.replace("FIM", ""), "sintatico"),
            (SOURCE.replace("90 C", "90 A"), "semantico"),
            (SOURCE.replace("cabine-002", "cabine-999"), "semantico"),
            (SOURCE.replace("10 SEGUNDOS", "1.5 SEGUNDOS"), "semantico"),
            (SOURCE.replace("QUALQUER", "D"), "semantico"),
            (SOURCE + SOURCE, "semantico"),
            ("# vazio", "sintatico"),
        ]
        for source, stage in cases:
            with self.subTest(stage=stage, source=source):
                with self.assertRaises(CompileError) as cm:
                    compile_source(source, CABINS)
                self.assertEqual(cm.exception.diagnostic["stage"], stage)
                self.assertGreater(cm.exception.diagnostic["line"], 0)

    def test_multiple_rules_and_operators(self):
        for op in [">", ">=", "<", "<=", "=="]:
            source = SOURCE.replace(">=", op)
            result = compile_source(source, CABINS)
            self.assertEqual(len(result["queries"]), 1)
        other = (ROOT / "examples/corrente.elt").read_text(encoding="utf-8")
        self.assertEqual(len(compile_source(SOURCE + other, CABINS)["queries"]), 2)

    def test_name_is_encoded_not_interpolated(self):
        source = SOURCE.replace("Temperatura crítica", "x'; DROP TABLE leituras; --")
        sql = compile_source(source, CABINS)["queries"][0]["sql"]
        self.assertNotIn("DROP TABLE", sql)
        self.assertIn("CONVERT(X'", sql)

    def test_size_limit(self):
        with self.assertRaises(CompileError):
            compile_source("#" + "a" * 65536, CABINS)

class FakeS3:
    def __init__(self, data):
        self.data, self.writes, self.reads = data, [], []
    def get_object(self, **kwargs):
        self.reads.append(kwargs)
        return {"Body": io.BytesIO(self.data)}
    def put_object(self, **kwargs):
        self.writes.append(kwargs)

def record(key="entrada/teste.elt"):
    return {"eventName": "ObjectCreated:Put", "s3": {
        "bucket": {"name": "test"}, "object": {"key": key, "versionId": "v1"}}}

class LambdaTests(unittest.TestCase):
    def test_success_uses_exact_version_and_manifest_last(self):
        s3 = FakeS3(SOURCE.encode())
        result = process_record(s3, record())
        self.assertEqual(result["status"], "compiled")
        self.assertEqual(s3.reads[0]["VersionId"], "v1")
        self.assertTrue(s3.writes[-1]["Key"].endswith("compilacao.json"))
        self.assertEqual(json.loads(s3.writes[-1]["Body"])["status"], "compiled")

    def test_invalid_writes_only_report(self):
        s3 = FakeS3(SOURCE.replace("90 C", "90 A").encode())
        self.assertEqual(process_record(s3, record())["status"], "invalid")
        self.assertEqual(len(s3.writes), 1)
        self.assertTrue(s3.writes[0]["Key"].startswith("erros/"))

    def test_ignore_output_prevents_recursion(self):
        s3 = FakeS3(b"")
        self.assertEqual(process_record(s3, record("saida/teste.elt"))["status"], "ignored")
        self.assertEqual(s3.reads, [])

    def test_replay_is_deterministic(self):
        s3 = FakeS3(SOURCE.encode())
        a = process_record(s3, record())
        b = process_record(s3, record())
        self.assertEqual(a, b)

    def test_version_required(self):
        event = record()
        del event["s3"]["object"]["versionId"]
        with self.assertRaises(ValueError):
            process_record(FakeS3(b""), event)

if __name__ == "__main__":
    unittest.main()
