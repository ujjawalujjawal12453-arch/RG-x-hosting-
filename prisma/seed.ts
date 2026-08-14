import { PrismaClient, Runtime, Role } from '@prisma/client';
import bcrypt from 'bcryptjs';
const prisma = new PrismaClient();
async function main(){
 const adminPass = await bcrypt.hash('Admin@12345',12);
 const admin = await prisma.user.upsert({where:{email:'admin@ravanx.host'}, update:{}, create:{email:'admin@ravanx.host',name:'Ravan X Admin',passwordHash:adminPass,role:Role.ADMIN,emailVerified:true,wallet:{create:{balance:0}}}});
 const plans = [['python-starter','Python Starter',Runtime.PYTHON,1,512,5120,199,1999],['node-launch','Node Launch',Runtime.NODE,1,1024,10240,299,2999],['java-pro','Java Pro',Runtime.JAVA,2,2048,20480,599,5999]] as const;
 for (const p of plans) await prisma.plan.upsert({where:{id:p[0]}, update:{}, create:{id:p[0], name:p[1], runtime:p[2], cpu:p[3], ramMb:p[4], storageMb:p[5], monthlyPrice:p[6], yearlyPrice:p[7]}});
 console.log('Seeded admin', admin.email, 'password Admin@12345');
}
main().finally(()=>prisma.$disconnect());
