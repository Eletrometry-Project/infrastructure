"""Testa state mv com estados ficticios locais, sem chamadas AWS."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PWSH=shutil.which('pwsh')
TERRAFORM=shutil.which('terraform')

def resource(kind,name,instances):
    return {'mode':'managed','type':kind,'name':name,'provider':'provider["registry.terraform.io/hashicorp/aws"]','instances':instances}

def instance(identifier,ip=None):
    r={'schema_version':0,'attributes':{'id':identifier},'sensitive_attributes':[]}
    if ip:
        r['index_key']=ip;r['attributes']['cidr_ipv4']=ip
    return r

@unittest.skipUnless(PWSH and TERRAFORM,'Requer pwsh e terraform no PATH')
class MigrationTests(unittest.TestCase):
    def fixture(self,path,extra=False):
        (path/'infra').mkdir();(path/'grafana/infra').mkdir(parents=True)
        common={'version':4,'terraform_version':'1.11.4','serial':1,'lineage':'new-lineage','outputs':{},'resources':[]}
        main=dict(common);main['outputs']={'lab':{'value':{'account_id':'123456789012'},'type':['object',{'account_id':'string'}]}}
        old=dict(common);old['lineage']='old-lineage';old['outputs']={'target_group_arn':{'value':'arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/test/123','type':'string'}}
        old['resources']=[resource('aws_security_group','alb',[instance('sg-test')]),resource('aws_vpc_security_group_ingress_rule','web',[instance('sgr-a','203.0.113.10/32'),instance('sgr-b','203.0.113.20/32')])]
        if extra:old['resources'].append(resource('aws_s3_bucket','unknown',[instance('unknown')]))
        (path/'infra/terraform.tfstate').write_text(json.dumps(main));(path/'grafana/infra/terraform.tfstate').write_text(json.dumps(old))

    def invoke(self,path):
        return subprocess.run([PWSH,'-NoLogo','-NoProfile','-File',str(ROOT/'scripts/migrate_grafana_state.ps1'),'-ProjectRoot',str(path)],capture_output=True,text=True)

    def test_complete_resource_move_and_repeat(self):
        with tempfile.TemporaryDirectory(prefix='migration-space ') as tmp:
            p=Path(tmp);self.fixture(p)
            result=self.invoke(p)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            main=json.loads((p/'infra/terraform.tfstate').read_text(encoding='utf-8-sig'))
            old=json.loads((p/'grafana/infra/terraform.tfstate').read_text(encoding='utf-8-sig'))
            self.assertEqual(len(main['resources']),2)
            self.assertEqual(len(main['resources'][1]['instances']),2)
            self.assertEqual(old['resources'],[])
            self.assertEqual(len(list(p.glob('.state-backup-integracao-*'))),1)
            repeated=self.invoke(p);self.assertEqual(repeated.returncode,0,repeated.stderr)
            cidrs=json.loads((p/'infra/observability.auto.tfvars.json').read_text())
            self.assertEqual(len(cidrs['ui_allowed_ipv4_cidrs']),2)

    def test_unknown_resource_aborts_without_state_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);self.fixture(p,extra=True)
            before=(p/'infra/terraform.tfstate').read_bytes()
            result=self.invoke(p)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((p/'infra/terraform.tfstate').read_bytes(),before)
            self.assertEqual(len(list(p.glob('.state-backup-integracao-*'))),0)

if __name__=='__main__':unittest.main()
