export const views={
 analista:{title:'Prioridades de operação',role:'Analista',uid:'eletrometry-visao-geral',lead:'Veja quais cabines precisam de uma avaliação agora.',panels:[5,4,6,22,23,24,25,1,2,3]},
 investigar:{title:'Investigação da cabine',role:'Analista',uid:'eletrometry-cabines',lead:'Compare as fases e acompanhe a margem até o limite crítico.',panels:[6,8,1,2,3,4,13,14,5,15,16,9,7,30,31,32,10,11,17,12]},
 gestor:{title:'Panorama da planta',role:'Gestor',uid:'eletrometry-gestor',lead:'Compare a exposição ao risco e decida onde concentrar a manutenção.',panels:[6,7,5,8,1,2,3,4,9,10]},
 historico:{title:'Histórico da cabine',role:'Gestor',uid:'eletrometry-historico',lead:'Reconstrua a sequência de ocorrências no período selecionado.',panels:[7,8,6,1,2,3,4]},
 tendencias:{title:'Tendências e projeções',role:'Gestor',uid:'eletrometry-tendencias',lead:'Acompanhe a evolução mensal e a cobertura do histórico.',panels:[8,9,10,11,7,1,2,3,4,5,6]}
};
export function target(view,cab,range,panel){let v=views[view];let q=new URLSearchParams({from:'now-'+range,to:'now',theme:'light','var-cabine':cab,'var-fase':'A','var-sensor':'temperatura','var-metrica':'temperatura'});if(panel)q.set('panelId',panel);return (panel?'/d-solo/':'/d/')+v.uid+'/cabines?'+q}
export const cabins=[
 {id:'cabine-001',label:'Cabine 001',state:'Normal',temp:44.8,amp:241,exposure:0},
 {id:'cabine-002',label:'Cabine 002',state:'Crítico',temp:95,amp:590,exposure:118},
 {id:'cabine-003',label:'Cabine 003',state:'Atenção',temp:74,amp:246,exposure:64}
];
export const periods=[['10m','10 min'],['1h','1 hora'],['24h','24 horas'],['7d','7 dias'],['30d','30 dias'],['90d','90 dias']];
export const rangeMinutes={ '10m':10,'1h':60,'24h':1440,'7d':10080,'30d':43200,'90d':129600 };
export const events=[
 [2,'cabine-002','Temperatura','Crítico','95 °C'],[4,'cabine-003','Temperatura','Atenção','74 °C'],[7,'cabine-002','Corrente','Crítico','590 A'],[32,'cabine-002','Temperatura','Moderado','84 °C'],[64,'cabine-003','Temperatura','Atenção','72 °C'],[200,'cabine-001','Corrente','Atenção','470 A'],[1600,'cabine-002','Temperatura','Crítico','92 °C']
];
