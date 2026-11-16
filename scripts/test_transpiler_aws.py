"""Teste opt-in S3 -> Lambda -> S3; nao executa SQL nem altera dashboards."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transpiler.compiler import VERSION
from transpiler.lambda_handler import REGISTRY


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout deve ser positivo")

    import boto3
    from botocore.exceptions import ClientError

    output = subprocess.run(
        ["terraform", f"-chdir={ROOT / 'infra'}", "output", "-json", "transpiler"],
        check=True, capture_output=True, text=True,
    )
    cfg = json.loads(output.stdout)
    session = boto3.Session(profile_name=cfg.get("profile"), region_name=cfg["region"])
    account = session.client("sts").get_caller_identity()["Account"]
    if account != cfg["account_id"]:
        raise RuntimeError("Credenciais pertencem a outra conta AWS.")
    s3 = session.client("s3")
    bucket = cfg["bucket_name"]
    if s3.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
        raise RuntimeError("Versionamento S3 nao esta habilitado.")
    function = session.client("lambda").get_function_configuration(FunctionName=cfg["function_name"])
    if function["State"] != "Active" or function.get("LastUpdateStatus") == "Failed":
        raise RuntimeError("Lambda nao esta ativa ou sua atualizacao falhou.")

    for filename, expected in [("temperatura.elt", "compiled"), ("erro-unidade.elt", "invalid")]:
        key = f"entrada/smoke-{uuid.uuid4().hex}-{filename}"
        upload = s3.put_object(
            Bucket=bucket, Key=key,
            Body=(ROOT / "transpiler" / "examples" / filename).read_bytes(),
            ContentType="text/plain; charset=utf-8",
        )
        version = upload.get("VersionId")
        if not version or version == "null":
            raise RuntimeError("Upload nao retornou VersionId.")
        identity = json.dumps([bucket, key, version, VERSION, REGISTRY], ensure_ascii=True)
        job = hashlib.sha256(identity.encode()).hexdigest()
        candidates = [f"saida/{job}/compilacao.json", f"erros/{job}/relatorio.json"]
        print(f"Enviado: s3://{bucket}/{key} (versao {version})", flush=True)
        deadline = time.monotonic() + args.timeout
        found = None
        while time.monotonic() < deadline and found is None:
            for result_key in candidates:
                try:
                    response = s3.get_object(Bucket=bucket, Key=result_key)
                except ClientError as exc:
                    if exc.response["Error"]["Code"] in {"NoSuchKey", "404"}:
                        continue
                    raise
                with response["Body"] as body:
                    found = (result_key, json.loads(body.read()))
                break
            if found is None:
                time.sleep(3)
        if found is None:
            raise RuntimeError(
                f"Sem resposta em {args.timeout}s. Consulte {cfg['log_group']} e a fila "
                f"{cfg['failure_queue_url']}. Confira se codigo local/cabines.json "
                "correspondem ao ultimo apply. Preserve os objetos para diagnostico."
            )
        result_key, report = found
        if report.get("source_version") != version or report.get("source_key") != key:
            raise RuntimeError("Relatorio nao corresponde ao upload.")
        if report.get("status") != expected:
            raise RuntimeError(f"Esperado {expected}; recebido: {report}")
        if expected == "compiled":
            sql_key = f"saida/{job}/regra-001.sql"
            response = s3.get_object(Bucket=bucket, Key=sql_key)
            with response["Body"] as body:
                sql = body.read().decode("utf-8")
            if "WITH" not in sql.upper() or "leituras" not in sql:
                raise RuntimeError("SQL gerado nao contem a consulta esperada.")
        elif report.get("error", {}).get("stage") != "semantico":
            raise RuntimeError("Esperado erro semantico de unidade.")
        print(f"OK {expected}: s3://{bucket}/{result_key}", flush=True)
    print("Fluxo real validado para regra valida e invalida. Objetos de teste preservados.")


if __name__ == "__main__":
    main()
