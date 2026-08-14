import './globals.css';import type { Metadata } from 'next';
export const metadata:Metadata={title:'Ravan X Hosting',description:'Production hosting panel for Python, Node.js and Java apps'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
