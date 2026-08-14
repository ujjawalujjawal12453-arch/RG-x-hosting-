import { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';
declare global { namespace Express { interface Request { user?: { id:string; role:'USER'|'RESELLER'|'ADMIN'; email:string } } } }
export function signAccess(user:{id:string;role:string;email:string}){ return jwt.sign(user, process.env.JWT_ACCESS_SECRET!, {expiresIn:'15m'}); }
export function signRefresh(user:{id:string;role:string;email:string}){ return jwt.sign(user, process.env.JWT_REFRESH_SECRET!, {expiresIn:'7d'}); }
export function auth(req:Request,res:Response,next:NextFunction){ const token = req.cookies.accessToken || req.headers.authorization?.replace('Bearer ',''); if(!token) return res.status(401).json({message:'Unauthorized'}); try{ req.user = jwt.verify(token, process.env.JWT_ACCESS_SECRET!) as any; next(); } catch { return res.status(401).json({message:'Invalid token'}); } }
export function requireRole(...roles:string[]){ return (req:Request,res:Response,next:NextFunction)=> roles.includes(req.user!.role) ? next() : res.status(403).json({message:'Forbidden'}); }
