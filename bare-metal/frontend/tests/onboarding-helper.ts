import type {BrowserContext} from '@playwright/test';
/** Existing workflow tests exercise operations; dismiss onboarding as a user would. */
export async function dismissInitialTour(context:BrowserContext){
 await context.addInitScript(()=>{
  const observe=()=>{
   const watcher=new MutationObserver(()=>{
    const skip=document.querySelector<HTMLButtonElement>('[data-tour-skip]');
    if(skip){watcher.disconnect();skip.click()}
   });
   watcher.observe(document.body,{childList:true,subtree:true});
  };
  if(document.body)observe();else document.addEventListener('DOMContentLoaded',observe,{once:true});
 });
}
