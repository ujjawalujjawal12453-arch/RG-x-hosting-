import { prisma } from '../config/prisma';
export async function audit(userId:string|undefined, action:string, entity:string, entityId?:string, metadata?:unknown, ip?:string){ await prisma.auditLog.create({data:{userId,action,entity,entityId,metadata:metadata as any,ip}}).catch(()=>undefined); }
