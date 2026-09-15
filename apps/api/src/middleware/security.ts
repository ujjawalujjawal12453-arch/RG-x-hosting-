import rateLimit from 'express-rate-limit';
import helmet from 'helmet';
export const helmetMiddleware = helmet({contentSecurityPolicy:false});
export const apiLimiter = rateLimit({windowMs:15*60*1000, limit:300, standardHeaders:true, legacyHeaders:false});
