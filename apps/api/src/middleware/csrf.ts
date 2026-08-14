import { NextFunction, Request, Response } from 'express';
import crypto from 'crypto';
const unsafe = new Set(['POST','PUT','PATCH','DELETE']);
export function csrfToken(req:Request,res:Response){const token=crypto.randomBytes(32).toString('hex');res.cookie('csrfToken',token,{sameSite:'lax',secure:process.env.NODE_ENV==='production'});res.json({csrfToken:token});}
export function csrfProtection(req:Request,res:Response,next:NextFunction){if(process.env.ENABLE_CSRF!=='true'||!unsafe.has(req.method)) return next(); const cookie=req.cookies.csrfToken; const header=req.headers['x-csrf-token']; if(!cookie||cookie!==header) return res.status(403).json({message:'Invalid CSRF token'}); next();}
