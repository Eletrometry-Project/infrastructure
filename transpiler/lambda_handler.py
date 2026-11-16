"""S3 versioned entrada/*.elt -> saida/ or erros/. Does not publish dashboards."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote_plus
from .compiler import compile_source, CompileError, MAX_BYTES, VERSION

REGISTRY = json.loads(Path(__file__).with_name("cabines.json").read_text(encoding="utf-8"))

def process_record(s3, record):
    if not record.get("eventName", "").startswith("ObjectCreated:"):
        return {"status": "ignored"}
    bucket = record["s3"]["bucket"]["name"]
    obj = record["s3"]["object"]
    key = unquote_plus(obj["key"])
    if not key.startswith("entrada/") or not key.endswith(".elt"):
        return {"status": "ignored"}
    version = obj.get("versionId")
    if not version or version == "null":
        raise ValueError("Ative o versionamento do bucket antes de enviar regras.")
    identity = json.dumps([bucket, key, version, VERSION, REGISTRY], ensure_ascii=True)
    job = hashlib.sha256(identity.encode()).hexdigest()
    metadata = {"source_key": key, "source_version": version, "compiler_version": VERSION}
    response = s3.get_object(Bucket=bucket, Key=key, VersionId=version)
    body = response["Body"]
    try:
        data = body.read(MAX_BYTES + 1)
    finally:
        body.close()
    try:
        if len(data) > MAX_BYTES:
            raise CompileError("lexico", "Arquivo excede 64 KiB.")
        source = data.decode("utf-8-sig")
        result = compile_source(source, REGISTRY)
    except (CompileError, UnicodeError) as exc:
        diagnostic = getattr(exc, "diagnostic", {"stage": "lexico", "message": "Use UTF-8.", "line": 1, "column": 1})
        output = f"erros/{job}/relatorio.json"
        s3.put_object(Bucket=bucket, Key=output, ContentType="application/json",
                      Body=json.dumps({**metadata, "status": "invalid", "error": diagnostic}, ensure_ascii=False).encode())
        return {"status": "invalid", "key": output}
    prefix = f"saida/{job}/"
    for i, query in enumerate(result["queries"], 1):
        s3.put_object(Bucket=bucket, Key=f"{prefix}regra-{i:03d}.sql",
                      ContentType="text/plain; charset=utf-8", Body=(query["sql"] + ";\n").encode())
    # Manifest is written last: consumers must only use complete manifests.
    output = prefix + "compilacao.json"
    s3.put_object(Bucket=bucket, Key=output, ContentType="application/json",
                  Body=json.dumps({**metadata, "status": "compiled", **result}, ensure_ascii=False).encode())
    return {"status": "compiled", "key": output}

def handler(event, context):
    import boto3
    s3 = boto3.client("s3")
    return {"results": [process_record(s3, r) for r in event.get("Records", [])]}
