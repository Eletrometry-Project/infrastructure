#!/usr/bin/env python3
"""Rejeita qualquer exclusao/substituicao no JSON de um plan. Nao executa apply."""
import argparse
import json
from pathlib import Path
import sys


def rejected_changes(plan):
    return [change["address"] for change in plan.get("resource_changes", [])
            if "delete" in change.get("change", {}).get("actions", [])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_json", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan_json.read_text(encoding="utf-8-sig"))
    if not isinstance(plan, dict) or "format_version" not in plan or "terraform_version" not in plan:
        print("Arquivo nao reconhecido como JSON de terraform show. Nenhum plano aprovado.")
        return 2
    failures = rejected_changes(plan)
    if failures:
        print("PARE: o plano inclui exclusao ou substituicao:")
        for address in failures:
            print(f"- {address}")
        return 1
    print("Sem exclusoes/substituicoes. Ainda revisar criacoes, regras de acesso, IAM e custos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
