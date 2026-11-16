import assert from 'node:assert/strict';
import {mkdtemp, readFile, mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import http from 'node:http';
import https from 'node:https';
import {checkServerIdentity} from 'node:tls';
import {execFileSync,spawn} from 'node:child_process';
import {once} from 'node:events';
const dir=await mkdtemp(join(tmpdir(),'eletrometry-cloud-test-'));
execFileSync('openssl',['req','-x509','-nodes','-newkey','rsa:2048','-sha256','-days','1','-subj','/CN=192.0.2.8','-addext','subjectAltName=IP:192.0.2.8','-addext','basicConstraints=critical,CA:FALSE','-keyout',join(dir,'portal.key'),'-out',join(dir,'portal.crt')],{stdio:'ignore'});
const ca=await readFile(join(dir,'portal.crt'));
const users=new Set();
const upstream=http.createServer(async(req,res)=>{
 const name=req.headers['x-eletrometry-reader'];assert(['elt-portal-analista','elt-portal-gestor'].includes(name));users.add(name);
 assert(!req.headers.authorization&&!req.headers.cookie);
 if(req.url.startsWith('/d-solo/')){res.writeHead(200,{'content-type':'text/html','x-frame-options':'DENY','set-cookie':'grafana_session=upstream; Path=/'});return res.end('<html><body>Painel</body></html>')}
 const doc=req.url.startsWith('/api/dashboards/uid/')?{dashboard:{panels:[{id:5,targets:[{rawSql:'SELECT 1 WHERE ${__to} >= ${__from}'}]}]}}:{results:{A:{frames:[]}}};
 res.setHeader('content-type','application/json');res.end(JSON.stringify(doc))
}).listen(0,'127.0.0.1');await once(upstream,'listening');
const port=18643,env={...process.env,PORT:String(port),GRAFANA_URL:'http://127.0.0.1:'+upstream.address().port,PORTAL_DATA:join(dir,'data'),PORTAL_ORIGIN:'https://192.0.2.8',PORTAL_TLS_DIR:dir};
const run=(args)=>new Promise((yes,no)=>{let p=spawn(process.execPath,args,{env,stdio:['ignore','pipe','pipe']});let log='';p.stdout.on('data',b=>log+=b);p.stderr.on('data',b=>log+=b);p.on('close',c=>c?no(Error(log)):yes(log))});
const portal=spawn(process.execPath,['portal-react/server.mjs'],{env,stdio:['ignore','pipe','inherit']});
await once(portal.stdout,'data');
function request(path,body,cookie,extras={}){
 return new Promise((yes,no)=>{let req=https.request({hostname:'127.0.0.1',port,ca,checkServerIdentity:(_,cert)=>checkServerIdentity('192.0.2.8',cert),path,method:body?'POST':'GET',
 headers:{host:'192.0.2.8',origin:env.PORTAL_ORIGIN,'content-type':'application/json',cookie:cookie||'',...extras}},res=>{res.resume();res.on('end',()=>yes(res))});req.on('error',no);req.end(body?JSON.stringify(body):undefined)})
}
try{
 console.log((await run(['frontend/smoke.mjs'])).trim());
 const input={name:'Teste',email:'isolated@example.invalid',password:'synthetic-password'};
 const reg=await request('/portal-api/register',input);assert.equal(reg.statusCode,200);assert.match(reg.headers['set-cookie'][0],/Secure/);
 const cookie=reg.headers['set-cookie'][0].split(';')[0]+'; grafana_session=arbitrary';
 const forged={'X-Eletrometry-Reader':'admin',Authorization:'Bearer supplied'};
 const frame=await request('/d-solo/eletrometry-cabines/test?panelId=6',null,cookie,forged);
 assert.equal(frame.statusCode,200);assert(!frame.headers['set-cookie']);assert.deepEqual([...users],['elt-portal-analista']);
 assert.equal((await request('/api/user',null,null,forged)).statusCode,401);
 assert.equal((await request('/portal-api/register',input,'',{origin:'https://wrong.invalid'})).statusCode,403);
 await run(['portal-react/server.mjs','--role',input.email,'Gestor']);
 const login=await request('/portal-api/login',input);const elevated=login.headers['set-cookie'][0].split(';')[0];
 assert.equal((await request('/api/dashboards/uid/eletrometry-gestor',null,elevated)).statusCode,200);
 assert(users.has('elt-portal-gestor'));console.log('OK: HTTPS pelo IP, sessao Secure e papeis aplicados pelo servidor. Upstream simulado.')
}finally{portal.kill();upstream.close()}
