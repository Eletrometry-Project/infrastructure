import argparse
import json
from pathlib import Path
from .compiler import compile_source, CompileError

def main():
    parser = argparse.ArgumentParser(description="Transpila regras ELT para MySQL 8.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("cabines.json"))
    parser.add_argument("--out", type=Path, default=Path("gerado"))
    parser.add_argument("--explain", action="store_true", help="Mostra tokens e árvore sintática.")
    args = parser.parse_args()
    try:
        result = compile_source(args.source.read_text(encoding="utf-8-sig"),
                                json.loads(args.registry.read_text(encoding="utf-8")))
    except (CompileError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps(getattr(exc, "diagnostic", {"message": str(exc)}), ensure_ascii=False))
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for i, query in enumerate(result["queries"], 1):
        (args.out / f"regra-{i:03d}.sql").write_text(query["sql"] + ";\n", encoding="utf-8")
    (args.out / "compilacao.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.explain:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"{len(result['queries'])} regra(s) compilada(s) em {args.out}. Nenhuma consulta executada.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
