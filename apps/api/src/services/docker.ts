import Docker from 'dockerode';
import fs from 'fs';
import { Runtime } from '@prisma/client';
export function dockerAvailable(){ return fs.existsSync(process.env.DOCKER_SOCKET || '/var/run/docker.sock'); }
export async function provisionContainer(opts:{name:string;runtime:Runtime;cpu:number;ramMb:number;storageMb:number;workdir:string}){
 if(!dockerAvailable()) return {status:'NEEDS_SERVER' as const, message:'Docker socket is unavailable. Deploy on a compatible Ubuntu server with Docker to run hosting containers.'};
 const docker = new Docker({socketPath:process.env.DOCKER_SOCKET || '/var/run/docker.sock'});
 const image = opts.runtime==='PYTHON'?'python:3.12-slim':opts.runtime==='NODE'?'node:22-alpine':'eclipse-temurin:21-jdk';
 const cmd = opts.runtime==='PYTHON'?['sh','-lc','[ -f requirements.txt ] && pip install -r requirements.txt; python app.py']:opts.runtime==='NODE'?['sh','-lc','[ -f package.json ] && npm install; npm start']:['sh','-lc','[ -f pom.xml ] && ./mvnw package || true; java -jar target/*.jar'];
 const container = await docker.createContainer({Image:image,name:opts.name,Cmd:cmd,WorkingDir:'/app',HostConfig:{Binds:[`${opts.workdir}:/app`],Memory:opts.ramMb*1024*1024,NanoCpus:opts.cpu*1_000_000_000,RestartPolicy:{Name:'unless-stopped'}}});
 await container.start(); return {status:'RUNNING' as const, containerId:container.id};
}
export async function containerAction(id:string, action:'start'|'stop'|'restart'|'delete'|'logs') { const c=new Docker({socketPath:process.env.DOCKER_SOCKET || '/var/run/docker.sock'}).getContainer(id); if(action==='logs') return (await c.logs({stdout:true,stderr:true,tail:200})).toString(); if(action==='delete'){ await c.remove({force:true}); return true;} await (c as any)[action](); return true; }
