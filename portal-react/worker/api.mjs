import {allowed} from '../policy.mjs';
const json=(value,status=200)=>Response.json(value,{status,headers:{'cache-control':'no-store'}});
export async function handle(request,env){
 const url=new URL(request.url),op=url.pathname.slice('/portal-api/'.length);
 const id=request.headers.get('oai-authenticated-user-id'),email=request.headers.get('oai-authenticated-user-email');
 if(!id||!email)return json({error:'Entre com sua conta para continuar.'},401);
 const manager=(env.MANAGER_EMAILS||'').toLowerCase().split(',').map(v=>v.trim()).includes(email.toLowerCase());
 const row=await env.DB.prepare('SELECT name,active FROM profiles WHERE identity=?').bind(id).first();
 const signedOut=(request.headers.get('cookie')||'').split(';').some(c=>c.trim()==='elt_out=1');
 const profile=row?{name:row.name,email,role:manager?'Gestor':'Analista'}:null;
 if(request.method==='GET'){
  if(op==='config')return json({portal:true,hosted:true,grafana:false,user:row&&!signedOut?profile:null});
  if(op.startsWith('view/'))return (!row||signedOut)?json({error:'Entre para continuar.'},401):allowed(profile.role,op.slice(5))?json({ok:true}):json({error:'Visão exclusiva do gestor.'},403);
  return json({error:'Recurso indisponível.'},404);
 }
 if(request.method!=='POST'||request.headers.get('origin')!==url.origin||!request.headers.get('content-type')?.startsWith('application/json'))return json({error:'Solicitação inválida.'},403);
 const raw=await request.text();if(raw.length>12000)return json({error:'Conteúdo muito longo.'},413);
 const d=JSON.parse(raw);if(d.role&&d.role!=='Analista')return json({error:'O perfil é atribuído pelo administrador.'},403);
 if(op==='register'){
  const name=String(d.name||'').trim();if(!name||name.length>80)return json({error:'Informe seu nome.'},400);
  let saved=await env.DB.prepare('INSERT INTO profiles(identity,name,active) VALUES(?,?,1) ON CONFLICT(identity) DO NOTHING').bind(id,name).run();
  if(!saved.meta.changes)return json({error:'Perfil já cadastrado. Use Login.'},409);
  const response=json({user:{name,email,role:manager?'Gestor':'Analista'}},201);response.headers.set('Set-Cookie','elt_out=0; Path=/; Secure; HttpOnly; SameSite=Strict');return response;
 }
 if(op==='login'||op==='logout'){
  if(!row)return json({error:'Clique em Registre-se para concluir seu cadastro.'},404);
  const response=json({user:op==='login'?profile:null});response.headers.set('Set-Cookie','elt_out='+ (op==='login'?'0':'1')+'; Path=/; Secure; HttpOnly; SameSite=Strict');return response;
 }
 if(op==='contact'){const name=String(d.name||'').trim(),message=String(d.message||'').trim(),reply=String(d.email||'').trim();if(!name||name.length>80||!message||message.length>2500||!/^\S+@\S+\.\S+$/.test(reply)||reply.length>160)return json({error:'Confira os campos de contato.'},400);const key=crypto.randomUUID();await env.DB.prepare('INSERT INTO messages VALUES(?,?,?,?)').bind(key,name,reply,message).run();return json({id:key},201)}
 return json({error:'Recurso indisponível.'},404)
}
