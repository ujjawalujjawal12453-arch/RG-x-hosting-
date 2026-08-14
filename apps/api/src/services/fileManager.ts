import fs from 'fs/promises';
import path from 'path';
import { createReadStream, createWriteStream } from 'fs';
import archiver from 'archiver';

function safe(root:string, target=''){
  const resolved = path.resolve(root,target);
  if(!resolved.startsWith(path.resolve(root))) throw new Error('Invalid path traversal attempt');
  return resolved;
}
export async function listFiles(root:string, rel=''){
  const dir=safe(root,rel); const entries=await fs.readdir(dir,{withFileTypes:true});
  return Promise.all(entries.map(async e=>{const p=path.join(dir,e.name); const s=await fs.stat(p); return {name:e.name,path:path.relative(root,p),type:e.isDirectory()?'folder':'file',size:s.size,updatedAt:s.mtime};}));
}
export async function writeText(root:string, rel:string, content:string){const p=safe(root,rel); await fs.mkdir(path.dirname(p),{recursive:true}); await fs.writeFile(p,content); return {path:rel};}
export async function readText(root:string, rel:string){return fs.readFile(safe(root,rel),'utf8');}
export async function renamePath(root:string, from:string, to:string){await fs.rename(safe(root,from),safe(root,to)); return {from,to};}
export async function deletePath(root:string, rel:string){await fs.rm(safe(root,rel),{recursive:true,force:true}); return {path:rel};}
export async function makeFolder(root:string, rel:string){await fs.mkdir(safe(root,rel),{recursive:true}); return {path:rel};}
export async function compressPath(root:string, rel:string){const source=safe(root,rel); const out=safe(root,`${rel || 'workspace'}.zip`); const archive=archiver('zip',{zlib:{level:9}}); const stream=createWriteStream(out); archive.pipe(stream); const stat=await fs.stat(source); stat.isDirectory()?archive.directory(source,false):archive.file(source,{name:path.basename(source)}); await archive.finalize(); return new Promise(resolve=>stream.on('close',()=>resolve({path:path.relative(root,out),bytes:archive.pointer()})));}
export function downloadStream(root:string, rel:string){return createReadStream(safe(root,rel));}
export function resolveSafe(root:string, rel:string){return safe(root,rel);}
