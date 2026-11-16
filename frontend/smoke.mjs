// Exercita o portal HTTPS real depois de cada instalação; remove apenas a sua conta de teste.
import https from 'node:https';
import {checkServerIdentity} from 'node:tls';
import {readFile} from 'node:fs/promises';
import {DatabaseSync} from 'node:sqlite';
import {randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
const base=new URL(process.env.PORTAL_ORIGIN),port=Number(process.env.PORT||8443);
const email='smoke-'+randomUUID()+'@eletrometry.invalid',ca=await readFile((process.env.PORTAL_TLS_DIR||'/run/portal-tls')+'/portal.crt');
let cookie='';
function request(path,body){
 return new Promise((accept,reject)=>{
  const req=https.request({hostname:'127.0.0.1',port,path,ca,checkServerIdentity:(_,cert)=>checkServerIdentity(base.hostname,cert),
   method:body?'POST':'GET',headers:{host:base.host,origin:base.origin,cookie,'content-type':'application/json'}},res=>{
    let chunks=[];res.on('data',d=>chunks.push(d));res.on('error',reject);res.on('end',()=>accept({status:res.statusCode,headers:res.headers,text:Buffer.concat(chunks).toString()}))
  });
  req.on('error',reject);req.setTimeout(35000,()=>req.destroy(Error('Tempo esgotado: '+path)));req.end(body?JSON.stringify(body):undefined)
 })
}
const db=new DatabaseSync(process.env.PORTAL_DATA+'/portal.sqlite');
try{
 const reg=await request('/portal-api/register',{name:'Verificação de implantação',email,password:randomUUID()});
 assert.equal(reg.status,200,'Cadastro HTTPS');cookie=reg.headers['set-cookie'][0].split(';')[0];
 const route='/d-solo/eletrometry-cabines/cabines?panelId=6&var-cabine=cabine-001&from=now-10m&to=now';
 const frame=await request(route);assert.equal(frame.status,200,'Iframe do analista');assert.equal(frame.headers['x-frame-options'],'SAMEORIGIN');
 assert.match(frame.headers['content-type'],/text\/html/);
 assert.equal((await request('/d/eletrometry-gestor/planta')).status,403,'Bloqueio de painel gerencial');
 const result=await request('/portal-api/snapshot?range=10m');assert.equal(result.status,200,'Consulta ao RDS pelo proxy do portal');assert(Array.isArray(JSON.parse(result.text).rows));
 console.log('OK: HTTPS, sessão do portal, iframe autorizado, bloqueio por perfil e consulta Grafana/RDS.');
}finally{
 db.exec('BEGIN');db.prepare('DELETE FROM sessions WHERE user=(SELECT id FROM users WHERE email=?)').run(email);
 db.prepare('DELETE FROM users WHERE email=?').run(email);db.exec('COMMIT');db.close()
}
