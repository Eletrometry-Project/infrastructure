export const dashboards = Object.freeze({
 analista:'eletrometry-visao-geral', investigar:'eletrometry-cabines', gestor:'eletrometry-gestor',
 historico:'eletrometry-historico', tendencias:'eletrometry-tendencias'
});
export function allowed(role,view){return Object.hasOwn(dashboards,view)&&(role==='Gestor'||(role==='Analista'&&['analista','investigar'].includes(view)))}
export function grafanaRoute(role,path,method){
 // Grafana supplies search, alternative dashboard APIs and edit routes. Only forward
 // the dashboard reads and supporting viewer requests that this portal needs.
 const dashboard=path.match(/^\/(?:d(?:-solo)?|api\/dashboards\/uid)\/([^/]+)(?:\/.*)?$/)
   ||path.match(/^\/apis\/dashboard\.grafana\.app\/v[\w]+\/namespaces\/[^/]+\/dashboards\/([^/]+)(?:\/dto)?$/);
 if(dashboard){const key=Object.keys(dashboards).find(v=>dashboards[v]===dashboard[1]);return method==='GET'&&allowed(role,key)}
 if(method==='POST')return ['/login','/api/ds/query','/api/frontend-metrics'].includes(path);
 if(method!=='GET'&&method!=='HEAD')return false;
 return /^(?:\/public\/|\/avatar\/|\/api\/plugins\/[^/]+\/settings$|\/api\/datasources\/uid\/[^/]+$)/.test(path)||
 ['/login','/logout','/favicon.ico','/robots.txt','/api/frontend/settings','/api/user','/api/user/preferences','/api/user/orgs','/api/org/preferences','/api/plugins','/api/datasources','/api/org','/api/annotations','/api/live/ws','/api/health','/api/access-control/user/permissions'].includes(path)
}
