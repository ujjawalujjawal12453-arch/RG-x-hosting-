'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Logo } from './Logo';

type IconName = 'bolt' | 'shield' | 'terminal' | 'chart' | 'folder' | 'globe' | 'check' | 'arrow';

function Icon({ name, className = 'h-5 w-5' }: { name: IconName; className?: string }) {
  const paths: Record<IconName, React.ReactNode> = {
    bolt: <path d="m13 2-9 12h7l-1 8 10-13h-7V2Z" />,
    shield: <path d="M12 3 4 6v5c0 5.2 3.4 9.8 8 11 4.6-1.2 8-5.8 8-11V6l-8-3Zm-3.2 9 2.1 2.1 4.4-4.6" />,
    terminal: <><path d="m5 8 4 4-4 4M12 16h7" /><path d="M3 4h18v16H3z" /></>,
    chart: <><path d="M4 19V5M4 19h17" /><path d="m7 15 4-4 3 2 5-6" /></>,
    folder: <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v8A2.5 2.5 0 0 1 18.5 20h-13A2.5 2.5 0 0 1 3 17.5v-10Z" />,
    globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.2 2.5 3.4 5.5 3.4 9S14.2 18.5 12 21c-2.2-2.5-3.4-5.5-3.4-9S9.8 5.5 12 3Z" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    arrow: <path d="M5 12h13m-5-5 5 5-5 5" />,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>{paths[name]}</svg>;
}

const capabilities = [
  ['Instant container orchestration', 'Ship an isolated Python, Node.js, or Java workload with clear runtime detection and guarded resource limits.', 'bolt'],
  ['A secure operational perimeter', 'Role-aware account controls, audit-ready events, encrypted session cookies, and deliberate infrastructure checks.', 'shield'],
  ['A workspace, not a black box', 'Manage files, deployment controls, live output, and container lifecycle from one connected operating surface.', 'terminal'],
  ['Telemetry that tells a story', 'Watch resource patterns, service activity, and deployment state without losing the signal in noisy dashboards.', 'chart'],
  ['Your projects stay within reach', 'Upload, browse, edit, archive, and download workspace files through the integrated file-management API.', 'folder'],
  ['Ready for your edge layer', 'Generate reverse-proxy configuration for a compatible Nginx server and attach your own domain when ready.', 'globe'],
] as const;

const plans = [
  { name: 'Python Orbit', price: '199', tint: 'cyan', label: 'For bots & APIs', resources: ['1 vCPU burst', '1 GB RAM', '10 GB NVMe storage', 'Python 3.12 runtime'] },
  { name: 'Node Vector', price: '299', tint: 'violet', label: 'For web services', resources: ['2 vCPU burst', '2 GB RAM', '25 GB NVMe storage', 'Node.js 22 runtime'], featured: true },
  { name: 'Java Apex', price: '599', tint: 'amber', label: 'For JVM workloads', resources: ['2 vCPU reserved', '4 GB RAM', '50 GB NVMe storage', 'JDK 21 runtime'] },
];

const faqs = [
  ['Does Ravan X create real containers?', 'Yes. On a compatible Ubuntu host with Docker access, the server-side provisioning service creates and controls actual Docker containers. If Docker is absent, the API returns a visible infrastructure requirement rather than a false running state.'],
  ['Which project types are supported?', 'The control plane detects requirements.txt or Python files, package.json, and common Java project markers such as pom.xml, build.gradle, or a JAR.'],
  ['Can I connect a custom domain?', 'Yes, once your DNS and Nginx-compatible reverse-proxy host are configured. Ravan X can generate the application upstream configuration; DNS and certificates remain real external infrastructure you must operate.'],
  ['How does billing work?', 'The platform tracks wallet credits, purchases, invoices, refund records, and pending top-ups in its configured database. Production payment approval should be connected to a verified gateway or operational review flow.'],
];

function MiniChart() {
  return <svg viewBox="0 0 560 190" className="h-full w-full" role="img" aria-label="Resource activity graph"><defs><linearGradient id="wave" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#47e4ff" stopOpacity=".46"/><stop offset="1" stopColor="#47e4ff" stopOpacity="0"/></linearGradient></defs><path d="M0 144 C42 124 58 142 94 104 S162 150 203 97 S271 117 310 77 S386 114 424 61 S491 83 560 30 V190 H0Z" fill="url(#wave)"/><path d="M0 144 C42 124 58 142 94 104 S162 150 203 97 S271 117 310 77 S386 114 424 61 S491 83 560 30" fill="none" stroke="#62e9ff" strokeWidth="3"/><path d="M0 166 C65 138 110 173 166 139 S251 155 312 118 S394 148 448 103 S505 122 560 88" fill="none" stroke="#a881ff" strokeDasharray="7 8" strokeWidth="2"/></svg>;
}

export function MarketingSite() {
  const [openFaq, setOpenFaq] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  return <main className="marketing-shell overflow-hidden">
    <div className="aurora aurora-one"/><div className="aurora aurora-two"/><div className="grid-noise"/>
    <header className="marketing-nav">
      <Link href="/" aria-label="Ravan X Hosting home"><Logo/></Link>
      <nav className="hidden items-center gap-7 text-sm font-medium text-white/60 lg:flex"><a href="#platform">Platform</a><a href="#plans">Plans</a><a href="#workflow">Workflow</a><a href="#faq">FAQ</a></nav>
      <div className="hidden items-center gap-3 sm:flex"><Link className="nav-login" href="/auth/login">Sign in</Link><Link className="nav-cta" href="/auth/register">Launch a project <Icon name="arrow" className="h-4 w-4"/></Link></div>
      <button className="mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen} aria-label="Toggle navigation"><span/><span/><span/></button>
      {menuOpen && <div className="mobile-nav"><a href="#platform" onClick={() => setMenuOpen(false)}>Platform</a><a href="#plans" onClick={() => setMenuOpen(false)}>Plans</a><a href="#workflow" onClick={() => setMenuOpen(false)}>Workflow</a><a href="#faq" onClick={() => setMenuOpen(false)}>FAQ</a><Link href="/auth/register">Create account</Link></div>}
    </header>

    <section className="hero-wrap">
      <div className="hero-copy">
        <div className="eyebrow"><span className="pulse-dot"/> Built for the deployment moment</div>
        <h1>Infrastructure that lets your <em>ideas stay in motion.</em></h1>
        <p>Ravan X brings application hosting, operational visibility, customer billing, and team controls into a composed command surface—built around the services you actually run.</p>
        <div className="hero-actions"><Link className="primary-action" href="/auth/register">Build your first service <Icon name="arrow" className="h-5 w-5"/></Link><a className="secondary-action" href="#platform"><span className="play-mark">▶</span> Explore the platform</a></div>
        <div className="hero-proof"><div className="avatars"><i>AL</i><i>NK</i><i>SR</i><i>+4K</i></div><span>Chosen by builders who prefer signal over noise.</span></div>
      </div>
      <div className="hero-visual" aria-label="Ravan X deployment dashboard preview">
        <div className="orbital-ring ring-a"/><div className="orbital-ring ring-b"/>
        <div className="console-card">
          <div className="console-top"><div><span className="console-kicker">DEPLOYMENT</span><strong>vector-api</strong></div><span className="status-live"><b/> Running</span></div>
          <div className="command-row"><span>›</span><code>ravan deploy ./vector-api</code><small>00:42</small></div>
          <div className="deploy-steps"><div><span className="step-check">✓</span><p>Runtime detected <b>Node.js 22</b></p></div><div><span className="step-check">✓</span><p>Container provisioned <b>1.8s</b></p></div><div><span className="step-check">✓</span><p>Network route allocated <b>Ready</b></p></div></div>
          <div className="console-bottom"><span>Live deployment telemetry</span><span className="tiny-bars"><i/><i/><i/><i/><i/></span></div>
        </div>
        <div className="metric-float metric-top"><span>Network egress</span><strong>184 <small>MB/s</small></strong><div className="tiny-line cyan-line"/></div>
        <div className="metric-float metric-bottom"><span>CPU allocation</span><strong>42.8<small>%</small></strong><div className="progress-track"><i/></div></div>
      </div>
    </section>

    <section className="trust-strip"><p>DESIGNED FOR THE ENTIRE DEPLOYMENT LOOP</p><div><span>BUILD</span><b>✦</b><span>SHIP</span><b>✦</b><span>OBSERVE</span><b>✦</b><span>GROW</span></div></section>

    <section id="platform" className="section-wrap feature-section"><div className="section-heading"><div><span className="section-kicker">THE PLATFORM</span><h2>One clear surface for a complicated operation.</h2></div><p>Everything needed to move a service from a project folder to a managed runtime—without pretending the server does more than it truly can.</p></div><div className="capability-grid">{capabilities.map(([title, copy, icon], index) => <article className={`capability-card capability-${index + 1}`} key={title}><div className="icon-tile"><Icon name={icon}/></div><span className="card-index">0{index + 1}</span><h3>{title}</h3><p>{copy}</p><a href="#workflow">Learn more <Icon name="arrow" className="h-4 w-4"/></a></article>)}</div></section>

    <section id="workflow" className="section-wrap workflow-section"><div className="workflow-copy"><span className="section-kicker">FLOW WITHOUT FRICTION</span><h2>From source folder to a service you can see.</h2><p>Ravan X follows an intentional sequence: validate the account, recognize the project, create a managed service, and give you useful signals afterwards.</p><div className="workflow-list">{[['01','Choose a runtime','Upload source or connect your workspace.'],['02','Set your deployment profile','Allocate CPU, memory, storage, and a plan.'],['03','Operate with confidence','Read logs, manage lifecycle, and review usage.']].map(([number,title,text]) => <div key={number}><b>{number}</b><span><strong>{title}</strong><small>{text}</small></span></div>)}</div><Link href="/auth/register" className="text-link">Start building today <Icon name="arrow" className="h-4 w-4"/></Link></div><div className="telemetry-card"><div className="telemetry-head"><div><span>RESOURCE SIGNAL</span><h3>vector-api / production</h3></div><span className="status-live"><b/> Stable</span></div><div className="chart-meta"><span>Compute utilization</span><strong>68.4%</strong><small>+12.8% in the last hour</small></div><div className="chart-area"><MiniChart/></div><div className="telemetry-stats"><div><span>MEMORY</span><b>1.26 <small>GB</small></b></div><div><span>REQUESTS</span><b>24.8 <small>/ sec</small></b></div><div><span>UPTIME</span><b>99.98<small>%</small></b></div></div></div></section>

    <section id="plans" className="section-wrap plans-section"><div className="section-heading centered"><span className="section-kicker">START WHERE YOU ARE</span><h2>Simple resources. Serious headroom.</h2><p>Choose a plan designed around your runtime. Adjustments, billing, invoices, and renewal records stay visible in your account.</p></div><div className="plan-grid">{plans.map(plan => <article className={`plan-card ${plan.featured ? 'plan-featured' : ''}`} key={plan.name}>{plan.featured && <span className="popular-label">MOST SELECTED</span>}<div className={`plan-orbit ${plan.tint}`}/><p>{plan.label}</p><h3>{plan.name}</h3><div className="price"><sup>₹</sup>{plan.price}<small>/ month</small></div><hr/>{plan.resources.map(resource => <div className="plan-resource" key={resource}><Icon name="check" className="h-4 w-4"/>{resource}</div>)}<Link href="/auth/register" className={plan.featured ? 'plan-button filled' : 'plan-button'}>Choose plan <Icon name="arrow" className="h-4 w-4"/></Link></article>)}</div><p className="plan-note">Annual billing, top-up workflows, and wallet-based purchasing are available within the authenticated billing control plane.</p></section>

    <section className="section-wrap operations-section"><div className="operations-panel"><div><span className="section-kicker">OPERATE DELIBERATELY</span><h2>Built to tell you the truth about your infrastructure.</h2><p>When a Docker host, DNS route, certificate, or payment gateway needs setup, Ravan X shows the requirement. It does not turn operational unknowns into fake green checkmarks.</p><Link href="/dashboard" className="primary-action">Open the cockpit <Icon name="arrow" className="h-5 w-5"/></Link></div><div className="operation-list"><p><span>01</span>Container lifecycle and resource limits</p><p><span>02</span>File operations, logs, and service output</p><p><span>03</span>Admin, reseller, wallet, and ticket workflows</p><p><span>04</span>Reverse-proxy configuration for compatible hosts</p></div></div></section>

    <section id="faq" className="section-wrap faq-section"><div className="section-heading"><div><span className="section-kicker">GOOD QUESTIONS</span><h2>What builders ask before they launch.</h2></div><p>Clear systems are candid about where software ends and your infrastructure begins.</p></div><div className="faq-list">{faqs.map(([question, answer], index) => <article className={openFaq === index ? 'faq-open' : ''} key={question}><button onClick={() => setOpenFaq(openFaq === index ? -1 : index)} aria-expanded={openFaq === index}><span>{question}</span><b>{openFaq === index ? '−' : '+'}</b></button>{openFaq === index && <p>{answer}</p>}</article>)}</div></section>

    <section className="section-wrap final-section"><div className="final-glow"/><span className="section-kicker">READY WHEN YOU ARE</span><h2>Give your next release a home with a pulse.</h2><p>Create an account, choose a runtime, and let Ravan X make the operating picture easier to read.</p><div className="hero-actions"><Link className="primary-action" href="/auth/register">Create your account <Icon name="arrow" className="h-5 w-5"/></Link><Link className="secondary-action" href="/auth/login">Sign in to your workspace</Link></div></section>

    <footer><div><Link href="/"><Logo/></Link><p>Hosting control for builders who stay close to their infrastructure.</p></div><div className="footer-links"><a href="#platform">Platform</a><a href="#plans">Plans</a><a href="#faq">FAQ</a><Link href="/auth/login">Client login</Link></div><small>© {new Date().getFullYear()} Ravan X Hosting. Built for real infrastructure.</small></footer>
  </main>;
}
