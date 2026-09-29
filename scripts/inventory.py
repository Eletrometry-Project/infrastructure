#!/usr/bin/env python3
"""Inventario AWS somente leitura, com campos selecionados e sem buscar credenciais/senhas."""
import argparse
import json
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile")
    parser.add_argument("--instance-id")
    parser.add_argument("--db-id")
    parser.add_argument("--rule-name")
    parser.add_argument("--queue-name", default="eletrometry-demo")
    args = parser.parse_args()
    errors = []

    def aws(*arguments):
        command = ["aws", "--region", args.region, "--output", "json", "--no-cli-pager"]
        if args.profile:
            command += ["--profile", args.profile]
        result = subprocess.run(command + list(arguments), capture_output=True, text=True, timeout=60)
        if result.returncode:
            errors.append({"operation": " ".join(arguments[:2]), "error": result.stderr.strip()[-1200:]})
            return {}
        return json.loads(result.stdout or "{}")

    def pick(item, fields):
        return {key: item.get(key) for key in fields}

    identity = aws("sts", "get-caller-identity")
    ec2_arguments = ["ec2", "describe-instances"]
    if args.instance_id:
        ec2_arguments += ["--instance-ids", args.instance_id]
    else:
        ec2_arguments += ["--filters", "Name=instance-state-name,Values=running,stopped,pending,stopping"]
    ec2 = aws(*ec2_arguments)
    instances = [pick(i, ["InstanceId", "ImageId", "InstanceType", "KeyName", "SubnetId", "VpcId", "PublicIpAddress", "PrivateIpAddress", "IamInstanceProfile", "SecurityGroups", "BlockDeviceMappings", "MetadataOptions", "Tags"])
                 for reservation in ec2.get("Reservations", []) for i in reservation.get("Instances", [])]
    db_arguments = ["rds", "describe-db-instances"]
    if args.db_id:
        db_arguments += ["--db-instance-identifier", args.db_id]
    databases = [pick(db, ["DBInstanceIdentifier", "Engine", "EngineVersion", "DBInstanceClass", "DBName", "MasterUsername", "Endpoint", "AllocatedStorage", "MaxAllocatedStorage", "StorageType", "StorageEncrypted", "BackupRetentionPeriod", "PubliclyAccessible", "MultiAZ", "DBSubnetGroup", "VpcSecurityGroups", "AutoMinorVersionUpgrade", "DeletionProtection", "DBParameterGroups", "DBInstanceStatus"])
                 for db in aws(*db_arguments).get("DBInstances", [])]

    queue_url = aws("sqs", "get-queue-url", "--queue-name", args.queue_name).get("QueueUrl")
    queue = aws("sqs", "get-queue-attributes", "--queue-url", queue_url, "--attribute-names", "All").get("Attributes", {}) if queue_url else {}
    rule = aws("iot", "get-topic-rule", "--rule-name", args.rule_name) if args.rule_name else aws("iot", "list-topic-rules")
    sg_ids = sorted({sg["GroupId"] for i in instances for sg in i.get("SecurityGroups", [])} |
                    {sg["VpcSecurityGroupId"] for db in databases for sg in db.get("VpcSecurityGroups", [])})
    groups = aws("ec2", "describe-security-groups", "--group-ids", *sg_ids).get("SecurityGroups", []) if sg_ids else []
    volumes = sorted({mapping["Ebs"]["VolumeId"] for i in instances for mapping in i.get("BlockDeviceMappings", []) if "Ebs" in mapping})
    disks = aws("ec2", "describe-volumes", "--volume-ids", *volumes).get("Volumes", []) if volumes else []
    vpc_ids = sorted({i["VpcId"] for i in instances if i.get("VpcId")} |
                     {db["DBSubnetGroup"]["VpcId"] for db in databases if db.get("DBSubnetGroup")})
    routes = aws("ec2", "describe-route-tables", "--filters", "Name=vpc-id,Values=" + ",".join(vpc_ids)).get("RouteTables", []) if vpc_ids else []
    output = {"region": args.region, "identity": pick(identity, ["Account", "Arn"]),
              "instances": instances, "databases": databases,
              "queue": {"url": queue_url, "attributes": queue}, "iot": rule,
              "security_groups": groups, "volumes": disks, "route_tables": routes, "errors": errors}
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError:
        sys.exit("AWS CLI nao encontrado. Instale o AWS CLI v2 e configure as credenciais temporarias localmente.")
    except subprocess.TimeoutExpired:
        sys.exit("Tempo esgotado em uma consulta AWS; verificar rede e sessao do laboratorio.")
