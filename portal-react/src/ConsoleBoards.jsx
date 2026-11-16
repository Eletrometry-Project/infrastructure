import React,{useEffect,useRef,useState} from 'react';
import {cabins,events,rangeMinutes,views,target} from './data.js';
import catalog from './catalog.json';
const number=(v,d=1)=>v.toLocaleString('pt-BR',{maximumFractionDigits:d});
const colors=['#36376c','#e9a21a','#39a799'];
const labels=['Atenção','Moderado','Crítico'];
const color=s=>({'Crítico':'#e54c4e','Atenção':'#e7af19','Moderado':'#eb852f','Normal':'#26a65e'}[s]||'#8191a2');
function Card({title,value,note}){return <article className="metricBox"><span>{title}</span><strong>{value}</strong>{note&&<small>{note}</small>}</article>}
function Box({title,children,wide=false}){return <section className={'protoBox'+(wide?' wide':'')}><h3>{title}</h3>{children}</section>}
function Dot({state}){return <i className="statusDot" style={{background:color(state)}} title={state}/>}
function phases(c){return [{i:c.amp,t:c.temp},{i:c.amp*.98,t:c.temp-.6},{i:c.amp*.95,t:c.temp-1.2}]}
function Cards({manager,go}){
 return <div className={'stationList'+(manager?' stationMap':'')}>{[cabins[1],cabins[2],cabins[0]].map(c=>
   <button key={c.id} onClick={()=>go(c.id)} className="station" style={{'--severity':color(c.state)}}>
     <span className="stationGlyph" aria-hidden="true"><svg viewBox="0 0 28 36" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="4" y="2" width="20" height="31" rx="2"/><path d="M8 7h12v7H8zM8 24h8m-8 3h8m3-11v5M8 33v2m11-2v2"/><circle cx="10" cy="18" r="1"/></svg></span>
     <span className="stationName"><strong>{c.label}</strong><small><Dot state={c.state}/>{c.state}</small></span>
     {manager?<span className="stationReading">{number(c.amp)} A <small>{number(c.temp)} °C</small></span>:
       <span className="phaseList">{phases(c).map((phase,i)=><span key={i}><small>Fase {'RST'[i]}</small><b>{number(phase.i,0)} A</b><em>{number(phase.t)} °C</em></span>)}</span>}
     <svg className="stationArrow" aria-hidden="true" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 13 13 3M4 3h9v9"/></svg>
   </button>)}</div>
}
export function ReadingsComparison({rows}){
 const measures=[['Temperatura','°C','#c37338'],['Corrente','A','#327b76']];
 return <div className="readingsComparison">{measures.map(([field,unit,ink])=>{
   const valid=rows.filter(row=>typeof row[field]==='number'&&Number.isFinite(row[field]));
   if(!valid.length)return null;
   return <Box key={field} title={field+' por cabine'}><Bars unit={unit} items={valid.map(row=>[row.Cabine,row[field],ink])}/></Box>
 })}</div>
}
function Log({rows,go,compact=false}){return <div className={'protoLog '+(compact?'compact':'')}>{rows.length?rows.map(([m,id,kind,sev,val])=><button key={m} onClick={()=>go(id)} style={{borderLeftColor:color(sev)}}><b>{kind} · {sev}</b><span>{val} · {id}</span><small>−{m} min</small></button>):<p>Sem ocorrências neste período.</p>}</div>}
function Bars({items,unit=''}){const max=Math.max(1,...items.map(a=>a[1]));return <div className="bars">{items.map(([k,v,c])=><div key={k}><span>{k}</span><i><b style={{width:(100*v/max)+'%',background:c||colors[0]}}/></i><strong>{number(v)} {unit}</strong></div>)}</div>}
function Gauge({title,v,max,unit,ideal}){return <div className="protoGauge"><b>{title}</b><strong>{number(v)} {unit}</strong><div><i style={{left:Math.min(99,100*v/max)+'%'}}/></div><small>0 {unit}<span>Ideal · {ideal} {unit}</span>{max} {unit}</small></div>}
function Series({data,range,combo=false}){
 const host=useRef(null),[width,setWidth]=useState(520);
 useEffect(()=>{
   const observer=new ResizeObserver(([entry])=>setWidth(Math.max(220,Math.round(entry.contentRect.width))));
   observer.observe(host.current);return ()=>observer.disconnect();
 },[]);
 const maxima={};data.forEach(([,values,unit])=>{maxima[unit]=Math.max(maxima[unit]||1,...values)});
 const units=Object.keys(maxima),left=38,right=width-(units.length>1?43:15);
 const height=width>700?234:195,top=22,bottom=height-28;
 const x=(i,n)=>left+8+(right-left-16)*i/Math.max(1,n-1);
 const y=(v,u)=>bottom-v/maxima[u]*(bottom-top);
 const ink=(i)=>data.length===6?colors[Math.floor(i/2)]:colors[i%colors.length];
 return <div className="protoPlot" ref={host}><div className="plotLegend">{data.map(([name,,unit],i)=>
   <span key={name}><i style={{background:ink(i)}}/>{name} ({unit})</span>)}</div>
   <svg viewBox={'0 0 '+width+' '+height} role="img" aria-label={data.map(([name,,unit])=>name+' em '+unit).join(', ')}>
     <text x={left} y="12">{units[0]}</text>{units[1]&&<text x={right} y="12" textAnchor="end">{units[1]}</text>}
     {[0,1,2,3].map(i=>{const line=bottom-(bottom-top)*i/3;return <g key={i}>
       <path d={'M'+left+' '+line+'H'+right} stroke="#d9e2e4" strokeDasharray={i?'3 4':undefined}/>
       <text x={left-6} y={line+4} textAnchor="end">{number(i*maxima[units[0]]/3,0)}</text>
       {units[1]&&<text x={right+6} y={line+4}>{number(i*maxima[units[1]]/3,0)}</text>}</g>})}
     {data.map(([name,values,unit],i)=>combo&&i===0?values.map((v,j)=>{
       const w=Math.min(25,(right-left)/values.length*.56);return <rect key={j} x={x(j,values.length)-w/2} y={y(v,unit)} width={w} height={bottom-y(v,unit)} rx="2" fill={ink(i)}/>
     }):<polyline key={name} fill="none" stroke={ink(i)} strokeWidth="2.5" strokeLinejoin="round" strokeDasharray={data.length===6&&unit==='A'?'5 3':undefined}
       points={values.map((v,j)=>x(j,values.length)+','+y(v,unit)).join(' ')}/>)}
     <text x={left} y={height-4}>−{range}</text><text x={right} y={height-4} textAnchor="end">Fim</text>
   </svg></div>
}
function demoSeries(c,n=18){return [c.temp,c.amp].map((v,k)=>Array.from({length:n},(_,i)=>i===n-1?v:v*(.56+.32*i/n+.09*Math.sin(i*.7+k))))}
export function Boards({v,cab,range,go}){const all=events.filter(e=>e[0]<=rangeMinutes[range]),rows=all.filter(e=>e[1]===cab.id),count=(a,s)=>a.filter(e=>e[3]===s).length;const [temp,amps]=demoSeries(cab);const [filter,setFilter]=useState('Todas');let byCab=cabins.map(c=>[c.label,all.filter(r=>r[1]===c.id).length]).sort((a,b)=>b[1]-a[1]);const trace=[['Temperatura',temp,'°C'],['Corrente',amps,'A']];let p=phases(cab),avg=p.reduce((a,x)=>a+x.i,0)/3,delta=100*Math.max(...p.map(x=>Math.abs(x.i-avg)))/avg;
return <div className={'protoBoard board-'+v}>{v==='analista'?<><div className="metricRow"><Card title="Quantidade de alertas críticos" value={count(all,'Crítico')}/><Card title="Cabine com mais ocorrências" value={byCab[0][1]?byCab[0][0]:'Sem ocorrências'}/><Card title="Tipo de alerta mais frequente" value={all.length?(all.filter(e=>e[2]==='Temperatura').length>=all.length/2?'Temperatura':'Corrente'):'—'}/><Card title="Cabines com ocorrências" value={number(100*byCab.filter(c=>c[1]).length/3,0)+'%'}/><Card title="Cabines com reincidência" value={number(100*byCab.filter(c=>c[1]>1).length/3,0)+'%'}/></div><div className="protoColumns overviewSplit"><Box title="Visão das cabines"><Cards go={go}/></Box><Box title="Alertas das cabines"><Log compact rows={all} go={go}/></Box></div><ReadingsComparison rows={cabins.map(c=>({Cabine:c.label,Corrente:c.amp,Temperatura:c.temp}))}/></>:v==='gestor'?<><div className="metricRow"><Card title="Alertas críticos" value={count(all,'Crítico')}/><Card title="Status da planta" value="Crítico"/><Card title="Tempo de exposição" value="3,0 min" note="Acumulado do cenário"/><Card title="Total de cabines" value="3"/></div><div className="protoTriple"><Box title="Alertas por nível e tipo">{['Corrente','Temperatura'].map(k=><div key={k}><small>{k}</small><Bars items={labels.map(s=>[s,count(all.filter(r=>r[2]===k),s),color(s)])}/></div>)}</Box><Box title="Ranking de cabines por alertas"><Bars items={byCab}/></Box><Box title="Tempo de exposição por cabine"><Bars items={cabins.slice().sort((a,b)=>b.exposure-a.exposure).map(c=>[c.label,c.exposure])} unit="s"/></Box></div><Box title="Mapa das cabines"><Cards manager go={go}/></Box></>:v==='investigar'?<><Box title={cab.label+' · '+cab.state}><div className="gaugeRow"><Gauge title="Temperatura da cabine" v={cab.temp} max={110} ideal={60} unit="°C"/><Gauge title="Corrente da cabine" v={cab.amp} max={600} ideal={396} unit="A"/></div></Box><div className="metricRow"><Card title="Desvio térmico atual" value={number(cab.temp-60)+' °C'}/><Card title="Margem até o crítico" value={number(90-cab.temp)+' °C'}/><Card title="Desequilíbrio entre fases" value={number(delta)+'%'}/></div><div className="protoColumns"><Box title="Corrente e temperatura por fase"><Series range={range} data={['R','S','T'].flatMap((s,i)=>[['Temp '+s,temp.map(x=>x-i*.6),'°C'],['Corr '+s,amps.map(x=>x*(1-i*.025)),'A']])}/></Box><Box title="Carregamento da cabine"><Series range={range} data={[[ 'Média das fases',amps.map(x=>x*avg/cab.amp),'A']]}/></Box></div><Box title="Saúde da telemetria"><div className="metricRow">{p.map((x,i)=><Card key={i} title={'Fase '+'RST'[i]} value={number(x.i)+' A'} note={number(x.t)+' °C · leitura ilustrativa'}/>)}</div></Box></>:v==='historico'?<><div className="metricRow">{labels.slice().reverse().map(s=><Card key={s} title={'Alertas · '+s} value={count(rows,s)}/>)}<Card title="Tempo de exposição" value={cab.exposure+' s'}/></div><Box title={'Análise da '+cab.label}><Series data={trace} range={range} combo/></Box><Box title="Histórico de ocorrências"><label className="logFilter">Gravidade <select value={filter} onChange={e=>setFilter(e.target.value)}>{['Todas',...labels].map(s=><option key={s}>{s}</option>)}</select></label><Log rows={rows.filter(e=>filter==='Todas'||e[3]===filter)} go={go}/></Box></>:<><div className="metricRow"><Card title="Utilização da corrente" value={number(cab.amp/600*100)+'%'}/><Card title="Temperatura observada" value={number(cab.temp)+' °C'}/><Card title="Exposição ao risco" value={cab.exposure+' s'}/><Card title="Disponibilidade" value="Sem registro"/></div><div className="protoColumns"><Box title="Principal risco observado"><strong className="factor">{rows.filter(x=>x[2]==='Temperatura').length?'Temperatura elevada':'Sem evidência'}</strong></Box><Box title="Histórico de corrente"><Series range={range} data={[[ 'Corrente',amps,'A']]}/></Box></div><div className="protoColumns"><Box title="Probabilidade de eventos"><p>Histórico insuficiente para estimar uma probabilidade.</p></Box><Box title="Projeção de alertas e criticidade"><p>O modelo do laboratório exige três meses com pelo menos vinte dias observados por mês.</p></Box></div></>}</div>}
const groups={analista:[[4,22,23],[5,6],[24,25]],investigar:[[2,3],[4,5,7],[6,8],[10,12]],gestor:[[1,2,3,4],[5,6,7],[8]],historico:[[2,3,4],[6],[7,8]],tendencias:[[1,2,3,4],[5,8],[11,10],[9]]};
export function LiveBoard({view,cab,range,base}){return <div className="protoBoard">{groups[view].map((row,i)=><div className="embedRow" key={i}>{row.map(id=><section className="embedBox" key={id}><iframe loading="lazy" title={catalog[views[view].uid][id]} height={i===0?145:290} src={base+target(view,cab.id,range,id)}/></section>)}</div>)}</div>}
