import {build} from 'esbuild';
import {readFile,mkdir,writeFile,copyFile} from 'node:fs/promises';
const assets={};
for(const [name,type] of [['index.html','text/html'],['app.css','text/css'],['app.js','text/javascript'],['cabine.svg','image/svg+xml']])assets['/'+name]=[type,await readFile('dist/'+name,'utf8')];
await mkdir('dist/server',{recursive:true});await mkdir('dist/.openai',{recursive:true});
await build({stdin:{resolveDir:process.cwd(),contents:`import {handle} from './worker/api.mjs';const assets=${JSON.stringify(assets)};export default {async fetch(request,env){const path=new URL(request.url).pathname;if(path.startsWith('/portal-api/')){try{return await handle(request,env)}catch{return Response.json({error:'Serviço indisponível.'},{status:503})}}const item=assets[path==='/'?'/index.html':path];return Array.isArray(item)?new Response(item[1],{headers:{'content-type':item[0]+';charset=utf-8','x-content-type-options':'nosniff'}}):new Response('Não encontrado',{status:404})}}`},bundle:true,platform:'browser',format:'esm',outfile:'dist/server/index.js'});
await copyFile('.openai/hosting.json','dist/.openai/hosting.json');
