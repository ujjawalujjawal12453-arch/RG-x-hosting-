export const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:4000/api';
export async function api(path:string, init:RequestInit={}){const res=await fetch(`${API}${path}`,{...init,credentials:'include',headers:{'Content-Type':'application/json',...(init.headers||{})},cache:'no-store'}); if(!res.ok) throw new Error(await res.text()); return res.json();}
