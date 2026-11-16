import assert from 'node:assert/strict';
import {spawn,execFileSync} from 'node:child_process';
import {mkdtemp,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {once} from 'node:events';
import {DatabaseSync} from 'node:sqlite';
import {handle} from '../worker/api.mjs';
import {allowed,grafanaRoute,dashboards} from '../policy.mjs';
const db=new DatabaseSync(':memory:');db.exec(await readFile('drizzle/0000_profiles.sql','utf8'));
const DB={prepare(sql){return {bind(...params){let q=db.prepare(sql);return {first:()=>q.get(...params),run:()=>({meta:q.run(...params)})}}}}};
const env={DB,MANAGER_EMAILS:'owner@example.org'};
async function hosted(id,op,data,cookie=''){
 const headers={'origin':'https://test.local','content-type':'application/json',cookie};
 if(id){headers['oai-authenticated-user-id']=id;headers['oai-authenticated-user-email']=id+'@example.org'}
 return handle(new Request('https://test.local/portal-api/'+op,{headers,method:data?'POST':'GET',body:data?JSON.stringify(data):undefined}),env)
}
assert.equal((await hosted(null,'config')).status,401);
assert.equal((await hosted('reader','view/gestor')).status,401);
assert.equal((await hosted('reader','register',{name:'Reader',role:'Gestor'})).status,403);
for(const [id,role] of [['reader','Analista'],['owner','Gestor']]){
 let r=await hosted(id,'register',{name:id});assert.equal((await r.json()).user.role,role);
 for(const v of Object.keys(dashboards))assert.equal((await hosted(id,'view/'+v)).status,allowed(role,v)?200:403);
 assert.equal((await hosted(id,'login',{})).status,200);
 assert.equal((await hosted(id,'view/analista',undefined,'elt_out=1')).status,401)
}
assert.equal((await hosted('reader','register',{name:'Duplicate'})).status,409);
for(const k of ['gestor','historico','tendencias']){
 for(const path of ['/d/','/d-solo/','/api/dashboards/uid/','/apis/dashboard.grafana.app/v1/namespaces/default/dashboards/']){
  assert(!grafanaRoute('Analista',path+dashboards[k],'GET'));assert(grafanaRoute('Gestor',path+dashboards[k],'GET'))
 }
}
const dir=await mkdtemp(tmpdir()+'/elt-role-'),opts={...process.env,PORT:'18526',PORTAL_DATA:dir,GRAFANA_URL:''};
const proc=spawn(process.execPath,['server.mjs'],{env:opts,stdio:['ignore','pipe','inherit']});await once(proc.stdout,'data');
async function local(path,body,cookie=''){return fetch('http://localhost:18526'+path,{method:body?'POST':'GET',headers:{'content-type':'application/json',cookie},body:body?JSON.stringify(body):undefined})}
try{
 const d={name:'Local',password:'long-test-password',email:'local@example.org'};
 assert.equal((await local('/d/eletrometry-gestor/')).status,401);
 assert.equal((await local('/portal-api/register',{...d,role:'Gestor'})).status,403);
 let r=await local('/portal-api/register',d);assert.equal(r.status,200);let c=r.headers.get('set-cookie').split(';')[0];
 assert.equal((await local('/portal-api/view/gestor',null,c)).status,403);
 assert.equal((await local('/portal-api/view/analista',null,c)).status,200);
 assert.equal((await local('/api/dashboards/uid/eletrometry-gestor',null,c)).status,403);
 execFileSync(process.execPath,['server.mjs','--role',d.email,'Gestor'],{env:opts});
 assert.equal((await local('/portal-api/view/analista',null,c)).status,401);
 r=await local('/portal-api/login',d);c=r.headers.get('set-cookie').split(';')[0];
 for(const k of Object.keys(dashboards))assert.equal((await local('/portal-api/view/'+k,null,c)).status,200);
 await local('/portal-api/logout',{},c);assert.equal((await local('/portal-api/snapshot',null,c)).status,401);
 console.log('OK · cadastro, promoção, logout, 5 rotas por papel e bloqueios de proxy.')
}finally{proc.kill();db.close()}
