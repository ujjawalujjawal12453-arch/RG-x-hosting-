import fs from 'fs/promises';
import path from 'path';

export async function writeNginxAppConfig(opts:{domain:string;port:number;hostingId:string}){
  const dir = process.env.NGINX_APPS_DIR || path.resolve('uploads','nginx-apps');
  await fs.mkdir(dir,{recursive:true});
  const file = path.join(dir,`${opts.hostingId}.conf`);
  const config = `server {\n  listen 80;\n  server_name ${opts.domain};\n  location / {\n    proxy_pass http://127.0.0.1:${opts.port};\n    proxy_set_header Host $host;\n    proxy_set_header X-Real-IP $remote_addr;\n    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n    proxy_set_header X-Forwarded-Proto $scheme;\n  }\n}\n`;
  await fs.writeFile(file,config);
  return {file,message:'Nginx application config written. Reload Nginx on the server after validating this file.'};
}
