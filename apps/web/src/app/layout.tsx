import './globals.css';import type { Metadata } from 'next';
export const metadata:Metadata={title:'Ravan X Hosting',description:'A composed hosting control plane for Python, Node.js, and Java applications'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
