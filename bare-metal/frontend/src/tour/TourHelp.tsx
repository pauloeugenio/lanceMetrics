import {useEffect,useRef,useState} from 'react';
import {tourText} from './steps';
export function TourHelp({start,available}:{start:(kind:'page'|'overview')=>void,available:boolean}){
 const [open,setOpen]=useState(false);const container=useRef<HTMLDivElement>(null),button=useRef<HTMLButtonElement>(null);
 useEffect(()=>{
  if(!open)return;
  const outside=(e:PointerEvent)=>{if(!container.current?.contains(e.target as Node))setOpen(false)};
  document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside);
 },[open]);
 useEffect(()=>{if(open)container.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus()},[open]);
 function launch(kind:'page'|'overview'){setOpen(false);button.current?.focus();start(kind)}
 return <div className="tour-help" ref={container} onKeyDown={e=>{
  if(e.key==='Escape'&&open){e.preventDefault();e.stopPropagation();setOpen(false);button.current?.focus()}
  if(open&&['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();const items=Array.from(container.current!.querySelectorAll<HTMLButtonElement>('[role="menuitem"]'));const index=items.indexOf(document.activeElement as HTMLButtonElement);items[(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus()}
 }}><button className="tour-help-button" data-tour="help" ref={button} type="button" aria-label="Ajuda e tutoriais" aria-haspopup="menu" aria-expanded={open} aria-controls="tour-help-menu" disabled={!available} onClick={()=>setOpen(!open)}><span aria-hidden="true">?</span> {tourText.help}</button>{open&&<div id="tour-help-menu" className="tour-help-menu" role="menu" aria-label="Tutoriais"><button role="menuitem" onClick={()=>launch('page')}>{tourText.page}</button><button role="menuitem" onClick={()=>launch('overview')}>{tourText.overview}</button></div>}</div>;
}
