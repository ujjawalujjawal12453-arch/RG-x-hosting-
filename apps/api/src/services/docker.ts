import Docker from 'dockerode';
import fs from 'fs';
import path from 'path';
import { Runtime } from '@prisma/client';

export function dockerAvailable(){ return fs.existsSync(process.env.DOCKER_SOCKET || '/var/run/docker.sock'); }
export function detectRuntime(workdir:string, requested?:Runtime):Runtime{
  if(fs.existsSync(path.join(workdir,'package.json'))) return 'NODE';
  if(fs.existsSync(path.join(workdir,'requirements.txt')) || fs.existsSync(path.join(workdir,'app.py'))) return 'PYTHON';
  if(fs.existsSync(path.join(workdir,'pom.xml')) || fs.existsSync(path.join(workdir,'build.gradle'))) return 'JAVA';
  return requested || 'NODE';
}
export function allocatePort(){ return Math.floor(20000 + Math.random()*30000); }
export async function provisionContainer(opts:{name:string;runtime:Runtime;cpu:number;ramMb:number;storageMb:number;workdir:string;port?:number}){
 if(!dockerAvailable()) return {status:'NEEDS_SERVER' as const, message:'Docker socket is unavailable. Deploy on a compatible Ubuntu server with Docker to run hosting containers.'};
 const docker = new Docker({socketPath:process.env.DOCKER_SOCKET || '/var/run/docker.sock'});
 const runtime = detectRuntime(opts.workdir, opts.runtime);
 const image = runtime==='PYTHON'?'python:3.12-slim':runtime==='NODE'?'node:22-alpine':'eclipse-temurin:21-jdk';
 const port = opts.port || allocatePort();
 const cmd = runtime==='PYTHON'?['sh','-lc','[ -f requirements.txt ] && pip install -r requirements.txt; python ${PYTHON_ENTRY:-app.py}']:runtime==='NODE'?['sh','-lc','[ -f package.json ] && npm install; npm start']:['sh','-lc','if [ -f mvnw ]; then ./mvnw package; elif [ -f pom.xml ]; then mvn package; fi; java -jar target/*.jar'];
 const container = await docker.createContainer({Image:image,name:opts.name,Cmd:cmd,WorkingDir:'/app',Env:[`PORT=${port}`],ExposedPorts:{[`${port}/tcp`]:{}},HostConfig:{Binds:[`${opts.workdir}:/app`],Memory:opts.ramMb*1024*1024,NanoCpus:opts.cpu*1_000_000_000,PortBindings:{[`${port}/tcp`]:[{HostPort:String(port)}]},RestartPolicy:{Name:'unless-stopped'},StorageOpt:{size:`${opts.storageMb}M`}}});
 await container.start(); return {status:'RUNNING' as const, containerId:container.id, port, runtime};
}
export async function containerAction(id:string, action:'start'|'stop'|'restart'|'delete'|'logs'|'suspend'|'unsuspend'|'stats') { const c=new Docker({socketPath:process.env.DOCKER_SOCKET || '/var/run/docker.sock'}).getContainer(id); if(action==='logs') return (await c.logs({stdout:true,stderr:true,tail:300,timestamps:true})).toString(); if(action==='stats') return c.stats({stream:false}); if(action==='delete'){ await c.remove({force:true}); return true;} if(action==='suspend'){ await c.pause(); return true;} if(action==='unsuspend'){ await c.unpause(); return true;} await (c as any)[action](); return true; }
export async function streamLogs(id:string,onData:(chunk:string)=>void){const c=new Docker({socketPath:process.env.DOCKER_SOCKET || '/var/run/docker.sock'}).getContainer(id); const stream=await c.logs({stdout:true,stderr:true,follow:true,timestamps:true}); stream.on('data',b=>onData(b.toString())); return stream;}
