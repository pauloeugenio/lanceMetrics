import {useCallback,useEffect,useRef,useState} from 'react';
import {driver,type Driver,type DriveStep} from 'driver.js';
import 'driver.js/dist/driver.css';
import './tour.css';
import {tourScope} from './persistence';
import {overview,pageTours,tourText,type TourDefinition} from './steps';

const memory=new Map<string,string>();
function read(key:string){try{return localStorage.getItem(key)||memory.get(key)}catch{return memory.get(key)}}
function write(key:string,value:string){memory.set(key,value);try{localStorage.setItem(key,value)}catch{/* Storage may be disabled; keep this visit functional. */}}
function visible(target:string){return Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${target}"]`)).find(el=>{const style=getComputedStyle(el);return el.isConnected&&el.getClientRects().length>0&&style.display!=='none'&&style.visibility!=='hidden'&&!el.closest('[hidden],details:not([open])')})}
export function useProductTour({ready,page,authEnabled,token}:{ready:boolean,page:string,authEnabled:boolean,token:string}){
 const [scope,setScope]=useState('');
 const closeActive=useRef<(()=>void)|null>(null);
 const active=useRef<Driver|null>(null),context=useRef(''),started=useRef('');
 const latest=useRef({page,scope});latest.current={page,scope};
 useEffect(()=>{
  let cancelled=false;setScope('');
  async function identify(){const key=await tourScope(authEnabled,token);if(!cancelled)setScope(key)}
  void identify().catch(()=>{});return()=>{cancelled=true};
 },[authEnabled,token]);
 const start=useCallback((kind:'page'|'overview'='page')=>{
  const definition:TourDefinition=kind==='overview'?overview:pageTours[latest.current.page]||overview;
  closeActive.current?.();
  started.current=latest.current.scope;
  const focusBefore=document.activeElement instanceof HTMLElement&&document.activeElement!==document.body?document.activeElement:document.querySelector<HTMLElement>('[data-tour="help"]');
  const scopeAtStart=latest.current.scope;
  const steps:DriveStep[]=definition.steps.filter(s=>visible(s.target)).map(s=>({
   element:()=>visible(s.target)!,skipMissingElement:true,waitForElement:600,
   popover:{title:s.title,description:s.description,side:window.innerWidth<700?'bottom':'right',align:'center'},
  }));
  if(!steps.length)return;
  let finished=false;
  function finish(outcome:'completed'|'skipped'='skipped'){
   if(finished)return;finished=true;observer.disconnect();
   if(active.current===guide){active.current=null;closeActive.current=null}
   if(scopeAtStart)write(`${scopeAtStart}:${definition.id}`,JSON.stringify({status:outcome,at:new Date().toISOString()}));
   guide.destroy();
   requestAnimationFrame(()=>{if(!active.current&&focusBefore?.isConnected)focusBefore.focus({preventScroll:true})});
  }
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const guide=driver({steps,animate:!reduced,duration:250,overlayColor:'#112b36',overlayOpacity:.55,stagePadding:7,stageRadius:10,
   popoverClass:'lance-tour',showProgress:true,progressText:tourText.progress,nextBtnText:tourText.next,prevBtnText:tourText.previous,doneBtnText:tourText.done,
   closeBtnLabel:tourText.close,allowKeyboardControl:true,allowClose:true,overlayClickBehavior:'none',disableActiveInteraction:true,
   onNextClick:(_el,_step,{driver:g})=>{if(g.hasNextStep())g.moveNext();else finish('completed')},
   onDoneClick:()=>finish('completed'),onCloseClick:()=>finish(),onDestroyStarted:()=>finish(),
   onPopoverRender:(popover)=>{
    popover.progress.setAttribute('aria-live','polite');
    popover.wrapper.setAttribute('aria-modal','true');
    const skip=document.createElement('button');skip.type='button';skip.className='tour-skip';skip.dataset.tourSkip='';skip.textContent=tourText.skip;
    skip.addEventListener('click',()=>finish());popover.footerButtons.prepend(skip);
   },
   onDestroyed:()=>finish(),
  });
  const observer=new MutationObserver(()=>{
   if(!guide.isActive())return;
   const element=guide.getActiveElement();
   if(element&&(!element.isConnected||!element.getClientRects().length||getComputedStyle(element).visibility==='hidden')){
    if(guide.hasNextStep())guide.moveNext();else finish();
   }
  });
  observer.observe(document.querySelector('.layout')||document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','style','class','open']});
  closeActive.current=()=>finish();active.current=guide;context.current=`${latest.current.page}|${scopeAtStart}`;guide.drive();
 },[]);
 useEffect(()=>{
  if(active.current&&context.current!==`${page}|${scope}`)closeActive.current?.();
 },[page,scope]);
 useEffect(()=>{
  if(!ready||!scope||read(`${scope}:overview`)||started.current===scope)return;
  const timer=setTimeout(()=>{if(read(`${scope}:overview`)||started.current===scope||active.current)return;started.current=scope;start('overview')},650);
  return()=>clearTimeout(timer);
 },[ready,scope,start]);
 useEffect(()=>{if(!ready)closeActive.current?.()},[ready]);
 useEffect(()=>()=>{closeActive.current?.()},[]);
 return {start,available:!!scope};
}
