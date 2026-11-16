import React,{useEffect,useRef,useState} from 'react';
import {allowed} from '../policy.mjs';
import {views} from './data.js';

const pages = {
  analista:['grid','Resumo operacional'], investigar:['pulse','Investigar cabine'],
  gestor:['layers','Resumo da planta'], historico:['history','Histórico da cabine'],
  tendencias:['chart','Tendências']
};
const preference='eletrometry.nav.compact';
function initialCompact(){
  try{
    const saved=localStorage.getItem(preference);
    if(saved!==null)return saved==='1';
  }catch{}
  return window.matchMedia('(max-width: 1050px)').matches;
}

export function ConsoleShell({view,person,to,open,Icon,children}){
  const [compact,setCompact]=useState(initialCompact);
  const [drawer,setDrawer]=useState(false);
  const dialog=useRef(null);
  const mobileTrigger=useRef(null);
  useEffect(()=>{
    if(drawer&&!dialog.current.open)dialog.current.showModal();
    if(!drawer&&dialog.current.open)dialog.current.close();
  },[drawer]);
  useEffect(()=>{
    const wide=window.matchMedia('(min-width: 721px)');
    const close=()=>{if(wide.matches)setDrawer(false)};
    wide.addEventListener('change',close);
    return ()=>wide.removeEventListener('change',close);
  },[]);
  function toggle(){
    const value=!compact;
    setCompact(value);
    try{localStorage.setItem(preference,value?'1':'0')}catch{}
  }
  function navigation(id){
    const visible=Object.keys(pages).filter(key=>allowed(person.role,key));
    return <>
      <a className="consoleBrand" href="#/" aria-label="Eletrometry · página inicial" title="Página inicial">
        <span className="brandTile"><Icon n="bolt" size={21}/></span><span className="railText">Eletrometry</span>
      </a>
      <nav id={id} aria-label="Dashboards">
        {['Analista','Gestor'].map(role=>{
          const items=visible.filter(v=>views[v].role===role);
          return items.length>0&&<section key={role} className="navGroup">
            <h2><span className="railText">{role}</span></h2>
            {items.map(key=><a key={key} href={to(key)} onClick={()=>setDrawer(false)}
              aria-label={pages[key][1]} title={pages[key][1]} aria-current={view===key?'page':undefined}>
              <Icon n={pages[key][0]}/><span className="railText">{pages[key][1]}</span>
            </a>)}
          </section>
        })}
      </nav>
      <div className="railFoot"><a href="#/" aria-label="Página inicial" title="Página inicial"><Icon n="home"/><span className="railText">Página inicial</span></a></div>
    </>
  }
  return <div className={'workspace instrument'+(compact?' isCompact':'')}>
    <aside className="rail">{navigation('nav-painel')}</aside>
    <dialog className="navDrawer" ref={dialog} aria-label="Navegação das dashboards" onClose={()=>{
      setDrawer(false);if(window.matchMedia('(max-width:720px)').matches)mobileTrigger.current?.focus();
    }} onClick={e=>{if(e.target===dialog.current)dialog.current.close()}}>
      <div className="drawerInner"><button className="drawerClose" onClick={()=>setDrawer(false)} aria-label="Fechar navegação"><Icon n="cross"/></button>{navigation('nav-movel')}</div>
    </dialog>
    <div className="desk">
      <div className="deskTop"><div className="topCrumb">
        <button className="railTrigger" onClick={toggle} aria-controls="nav-painel" aria-expanded={!compact}
          aria-label={compact?'Expandir menu lateral':'Recolher menu lateral'} title={compact?'Expandir menu lateral':'Recolher menu lateral'}><Icon n="rail"/></button>
        <button className="drawerTrigger" ref={mobileTrigger} onClick={()=>setDrawer(true)} aria-controls="nav-movel" aria-expanded={drawer} aria-label="Abrir navegação"><Icon n="menu"/></button>
        <span>Dashboards</span><i>/</i><strong>{views[view].role}</strong>
      </div><button className="profileButton" onClick={()=>open('account')}><span aria-hidden="true">{(person.name||'?').trim().slice(0,1).toUpperCase()}</span>{person.name}</button></div>
      <main>{children}</main>
    </div>
  </div>
}

export function CircuitMark(){
  return <svg className="circuitMark" aria-hidden="true" viewBox="0 0 250 112" fill="none">
    <g stroke="currentColor"><path d="M0 79h43l20-20h41l19-19h43l24-24h60M0 89h48l20-20h42l19-19h43l24-24h54M0 99h53l20-20h43l19-19h43l24-24h48" />
    <path d="M40 0v26l17 17h38m35 69V86l18-18h57l18-18h27"/></g>
    {[[43,79],[104,59],[166,40],[95,43],[148,68],[205,68]].map(([x,y])=><circle key={x} cx={x} cy={y} r="2.6" fill="currentColor"/>)}
  </svg>
}
