// Portal do laboratório. HTTPS na EC2 e loopback no desenvolvimento.
import http from 'node:http';
import https from 'node:https';
import {isIP} from 'node:net';
import {allowed,grafanaRoute} from './policy.mjs';
import {DatabaseSync} from 'node:sqlite';
import {randomBytes,randomUUID,scrypt,timingSafeEqual,createHash} from 'node:crypto';
import {promisify} from 'node:util';
import {readFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const stretch=promisify(scrypt),root=fileURLToPath(new URL('.',import.meta.url)),dir=resolve(process.env.PORTAL_DATA||root+'/data');
await mkdir(dir,{recursive:true,mode:0o700});
const db=new DatabaseSync(dir+'/portal.sqlite');db.exec(`PRAGMA journal_mode=WAL;CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,name TEXT,role TEXT,salt TEXT,digest TEXT);CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user INTEGER,expires INTEGER);CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY,created TEXT,name TEXT,email TEXT,message TEXT)`);
if(!db.prepare('PRAGMA table_info(users)').all().some(c=>c.name==='role_approved')){
 db.exec("BEGIN; ALTER TABLE users ADD COLUMN role_approved INTEGER NOT NULL DEFAULT 0; UPDATE users SET role='Analista'; DELETE FROM sessions; COMMIT");
}
if(process.argv[2]==='--role'){
 const email=(process.argv[3]||'').toLowerCase(),role=process.argv[4];
 if(!['Gestor','Analista'].includes(role))throw Error('Uso: node server.mjs --role email Gestor|Analista');
 const result=db.prepare('UPDATE users SET role=?,role_approved=1 WHERE email=?').run(role,email);
 if(!result.changes)throw Error('Cadastre o e-mail primeiro.');
 db.prepare('DELETE FROM sessions WHERE user=(SELECT id FROM users WHERE email=?)').run(email);
 console.log('Perfil atualizado. Entre novamente.');db.close();process.exit(0)
}
if(process.argv.includes('--contacts')){console.table(db.prepare('SELECT * FROM contacts ORDER BY created DESC').all());db.close();process.exit(0)}
const upstream=process.env.GRAFANA_URL?new URL(process.env.GRAFANA_URL):null;
if(upstream&&(!['http:','https:'].includes(upstream.protocol)||upstream.username||upstream.password||upstream.pathname!=='/'||upstream.search||upstream.hash))throw Error('GRAFANA_URL deve ser a origem HTTP(S) do Grafana.');
const port=Number(process.env.PORT||4173),sha=s=>createHash('sha256').update(s).digest('hex');
const origin=process.env.PORTAL_ORIGIN ? new URL(process.env.PORTAL_ORIGIN) : null;
if(origin && (origin.protocol!=='https:' || !isIP(origin.hostname) || origin.pathname!=='/' || origin.search || origin.hash || origin.username || origin.password || !upstream))throw Error('Configure PORTAL_ORIGIN=https://IP e GRAFANA_URL.');
const canonical=process.env.GRAFANA_CANONICAL_URL?new URL(process.env.GRAFANA_CANONICAL_URL).origin:null;
const secureCookie=origin?'; Secure':'';
const budget=new Map();function limit(key,n){let now=Date.now(),b=budget.get(key);if(!b||b.t<now){b={t:now+60000,n:0};budget.set(key,b)}if(++b.n>n)fail(429,'Muitas tentativas. Aguarde um minuto.')}
function fail(status,message){throw Object.assign(new Error(message),{status})}
async function body(req,max=16000){let a=[],n=0;for await(const b of req){n+=b.length;if(n>max)fail(413,'Conteúdo muito longo.');a.push(b)}return Buffer.concat(a)}
const gCookies=req=>(req.headers.cookie||'').split(';').filter(s=>/^\s*(grafana_session(?:_expiry)?|redirect_to|oauth_state|grafana_sess)=/.test(s)).join(';');
const cookieHash=req=>sha((req.headers.cookie||'').match(/(?:^|;\s*)elt_portal=([0-9a-f]{64})(?:;|$)/)?.[1]||'');
const current=req=>db.prepare('SELECT u.name,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user WHERE s.hash=? AND s.expires>?').get(cookieHash(req),Date.now())||null;
function session(res,id){let val=randomBytes(32).toString('hex');db.prepare('DELETE FROM sessions WHERE expires<=?').run(Date.now());db.prepare('INSERT INTO sessions VALUES(?,?,?)').run(sha(val),id,Date.now()+8*3600000);res.setHeader('Set-Cookie','elt_portal='+val+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800'+secureCookie)}
async function gf(req,path,opts={}){if(!upstream)fail(503,'Configure GRAFANA_URL e reinicie o portal.');let u=new URL(upstream);let p=new URL(path,'http://portal.invalid');u.pathname=p.pathname;u.search=p.search;let identity;
 if(origin){
   const actor=current(req);
   if(!actor)fail(401,'Entre no portal.');
   if(!['Gestor','Analista'].includes(actor.role))fail(403,'Perfil indisponível.');
   identity={'X-Eletrometry-Reader':actor.role==='Gestor'?'elt-portal-gestor':'elt-portal-analista'};
 }else identity={cookie:gCookies(req)};
 return fetch(u,{redirect:'manual',signal:AbortSignal.timeout(30000),...opts,headers:{...opts.headers,...identity}})
}

const json=(res,data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data))};
async function snapshot(req,search){
 const periods={'10m':600,'1h':3600,'24h':86400,'7d':604800,'30d':2592000,'90d':7776000};let seconds=periods[search.get('range')]||600;
 // Use the provisioned priority table, under the current Grafana reader session.
 const meta=await gf(req,'/api/dashboards/uid/eletrometry-visao-geral');if(!meta.ok)fail(meta.status,'Entre no Grafana para ler as prioridades.');let dash=await meta.json(),t=dash.dashboard?.panels.find(p=>p.id===5)?.targets[0];if(!t?.rawSql)fail(409,'Instale a revisão das cinco dashboards.');
 let end=Date.now(),start=end-seconds*1000,rawSql=t.rawSql.replaceAll('${__from}',String(start)).replaceAll('${__to}',String(end));
 let result=await gf(req,'/api/ds/query',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({from:String(start),to:String(end),queries:[{...t,refId:'A',rawSql,intervalMs:1000,maxDataPoints:500}]})});if(!result.ok)fail(502,'Consulta indisponível.');let a=(await result.json()).results?.A;if(!a||a.error)fail(502,'Falha na leitura das cabines.');return (a.frames||[]).flatMap(f=>(f.data.values[0]||[]).map((_,i)=>Object.fromEntries(f.schema.fields.map((v,j)=>[v.name,f.data.values[j][i]]))))
}
async function serve(req,res){
 const host=req.headers.host;if(!(origin?[origin.host,origin.host+(!origin.port?':443':'')]:['127.0.0.1:'+port,'localhost:'+port]).includes(host))fail(403,'Host inválido.');
 if(!['GET','HEAD'].includes(req.method)&&req.headers.origin&&req.headers.origin!==(origin?.origin||'http://'+host))fail(403,'Origem inválida.');
 const u=new URL(req.url,'http://'+host),path=u.pathname;
 if(path.startsWith('/portal-api/')){
  let op=path.slice('/portal-api/'.length);
  if(req.method==='GET'&&op==='config')return json(res,{portal:true,grafana:!!upstream,aws:!!origin,user:current(req)});
  if(req.method==='GET'&&(op.startsWith('view/')||op==='snapshot')){
   const user=current(req);if(!user)fail(401,'Entre para acessar as dashboards.');
   if(op.startsWith('view/')){if(!allowed(user.role,op.slice(5)))fail(403,'Esta visão é exclusiva do gestor.');return json(res,{ok:true})}
  }
  if(req.method==='GET'&&op==='snapshot')return json(res,{rows:await snapshot(req,u.searchParams)});
  if(req.method!=='POST'||!['login','logout','register','contact'].includes(op))fail(404,'Rota indisponível.');
  if(!req.headers['content-type']?.startsWith('application/json'))fail(415,'Use JSON.');
  let d;try{d=JSON.parse(await body(req))}catch(e){if(e.status)throw e;fail(400,'JSON inválido.')}if(!d||typeof d!=='object')fail(400,'Dados inválidos.');
  if(op==='logout'){db.prepare('DELETE FROM sessions WHERE hash=?').run(cookieHash(req));res.setHeader('Set-Cookie','elt_portal=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'+secureCookie);return json(res,{ok:true})}
  limit(op,op==='login'?20:10);
  let email=String(d.email||'').trim().toLowerCase(),name=String(d.name||'').trim(),pw=String(d.password||'');if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||email.length>160)fail(400,'Informe um e-mail válido.');
  if(op!=='login'&&(!name||name.length>80))fail(400,'Informe o nome.');
  if(op==='contact'){let msg=String(d.message||'').trim();if(!msg||msg.length>2500)fail(400,'Informe sua mensagem.');let id=randomUUID();db.prepare('INSERT INTO contacts VALUES(?,?,?,?,?)').run(id,new Date().toISOString(),name,email,msg);return json(res,{id},201)}
  if(pw.length>128||!pw)fail(400,'Senha inválida.');
  let user=db.prepare('SELECT * FROM users WHERE email=?').get(email);
  if(op==='register'){if(d.role&&d.role!=='Analista')fail(403,'Somente o administrador concede acesso de gestor.');if(pw.length<10)fail(400,'Escolha uma visão e uma senha de pelo menos dez caracteres.');if(user)fail(409,'Este e-mail já possui um perfil.');let salt=randomBytes(16).toString('hex'),digest=(await stretch(pw,salt,64)).toString('hex');try{db.prepare('INSERT INTO users(email,name,role,salt,digest) VALUES(?,?,?,?,?)').run(email,name,'Analista',salt,digest)}catch{fail(409,'Não foi possível criar o perfil.')}user=db.prepare('SELECT * FROM users WHERE email=?').get(email)}
  else{const digest=await stretch(pw,user?.salt||'unused-salt',64);if(!user||!timingSafeEqual(Buffer.from(user.digest,'hex'),digest))fail(401,'E-mail ou senha incorretos.')}
  session(res,user.id);return json(res,{user:{name:user.name,role:user.role,email:user.email}})
 }
 const assets={'/':['index.html','text/html'],'/index.html':['index.html','text/html'],'/app.js':['app.js','text/javascript'],'/app.css':['app.css','text/css'],'/cabine.svg':['cabine.svg','image/svg+xml']};
 if(Object.hasOwn(assets,path)){if(req.method!=='GET'&&req.method!=='HEAD')fail(405,'Método inválido.');let [file,type]=assets[path];res.writeHead(200,{'Content-Type':type+'; charset=utf-8','X-Content-Type-Options':'nosniff'});return res.end(await readFile(root+'/dist/'+file))}
 // Forward native Grafana navigation, assets, API reads and login on the same origin.

 const actor=current(req);if(!actor)fail(401,'Entre no portal.');
 if(req.url.startsWith('//')||/%(?:2f|5c|25|2e)/i.test(path)||!grafanaRoute(actor.role,path,req.method))fail(403,'Acesso indisponível para este perfil.');
 const headers={};for(const k of ['accept','content-type','x-grafana-org-id','x-grafana-device-id','x-dashboard-uid','x-panel-id'])if(req.headers[k])headers[k]=req.headers[k];
 if(!upstream)fail(503,'Configure GRAFANA_URL.');
 if(origin && ['/login','/logout'].includes(path))fail(403,'Use o login do portal.');
 if(req.headers.origin)headers.origin=upstream.origin;
 const r=await gf(req,req.url,{method:req.method,headers,body:['GET','HEAD'].includes(req.method)?undefined:await body(req,2e6)});
 const h={};for(const k of ['content-type','cache-control','x-frame-options','content-security-policy','x-content-type-options'])if(r.headers.has(k))h[k]=r.headers.get(k);if(/^\/d(?:-solo)?\//.test(path))h['x-frame-options']='SAMEORIGIN';
 if(r.headers.has('location')){let dest=new URL(r.headers.get('location'),upstream);h.location=(dest.origin===upstream.origin||(origin&&dest.origin===canonical))?dest.pathname+dest.search+dest.hash:dest.href}
 const cookies=r.headers.getSetCookie().filter(c=>!c.startsWith('elt_portal=')).map(c=>c.replace(/;\s*Domain=[^;]+/ig,''));if(!origin&&cookies.length)h['set-cookie']=cookies;
 if(origin&&canonical&&/^\/d(?:-solo)?\//.test(path)&&h['content-type']?.includes('text/html')){
  const html=await r.text();
  res.writeHead(r.status,h);return res.end(html.replaceAll(canonical+'/',origin.origin+'/'));
 }
 res.writeHead(r.status,h);if(!r.body)return res.end();for await(const piece of r.body){if(res.destroyed)break;res.write(piece)}res.end()
}
const listener=(req,res)=>serve(req,res).catch(e=>{
 if(res.headersSent)return res.destroy();
 json(res,{error:e.status?e.message:'Serviço indisponível. Confira o acesso privado ao Grafana.'},e.status||502)
});
const tlsDir=process.env.PORTAL_TLS_DIR||'/run/portal-tls';
const server=origin?https.createServer({key:await readFile(tlsDir+'/portal.key'),cert:await readFile(tlsDir+'/portal.crt')},listener):http.createServer(listener);
server.listen(port,origin?'0.0.0.0':'127.0.0.1',()=>console.log('Eletrometry · '+(origin?.origin||'http://localhost:'+port)));
