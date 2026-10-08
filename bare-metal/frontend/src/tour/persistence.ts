/** Scope by browser origin and credential identity; never store the credential. */
export const TOUR_STORAGE_PREFIX='lance.metrics.tour.v1';
export async function tourScope(authEnabled:boolean,token:string){
 if(!authEnabled)return `${TOUR_STORAGE_PREFIX}:guest`;
 if(!token)return '';
 const bytes=new TextEncoder().encode(token);
 let fingerprint:string;
 if(globalThis.crypto?.subtle){
  const hash=await crypto.subtle.digest('SHA-256',bytes);
  fingerprint=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
 }else{
  // Plain HTTP LANs may lack Web Crypto. This is an opaque storage identifier,
  // not an authentication mechanism. Four independent accumulators avoid
  // sharing onboarding state across different high-entropy access tokens.
  const hashes=[0x811c9dc5,0x9e3779b9,0x85ebca6b,0xc2b2ae35];
  for(const b of bytes)for(let i=0;i<hashes.length;i++)hashes[i]=Math.imul(hashes[i]^b,0x01000193+i*2)>>>0;
  fingerprint=hashes.map(h=>h.toString(16).padStart(8,'0')).join('');
 }
 return `${TOUR_STORAGE_PREFIX}:auth-${fingerprint}`;
}
