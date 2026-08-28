"use client";

import { useState } from "react";

const navItems = ["Overview", "Clients", "Treasury", "Compliance", "IB Network"];

const kpis = [
  { label: "Assets under management", value: "$48.6M", change: "+8.4%", tone: "mint" },
  { label: "Net deposits · 24h", value: "$1.24M", change: "+12.1%", tone: "sky" },
  { label: "Active traders", value: "8,492", change: "+4.7%", tone: "amber" },
  { label: "Trading volume · 24h", value: "$316.8M", change: "+18.6%", tone: "rose" },
];

const queue = [
  { name: "Amelia Thompson", country: "United Kingdom", type: "Passport", age: "12 min", risk: "Low", initials: "AT" },
  { name: "Nikolai Petrov", country: "Cyprus", type: "Proof of funds", age: "27 min", risk: "Review", initials: "NP" },
  { name: "Sofia Mendes", country: "Portugal", type: "Identity check", age: "41 min", risk: "Low", initials: "SM" },
];

export default function Home() {
  const [active, setActive] = useState("Overview");

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">N</span><span>northstar<span className="brand-dot">.</span></span></div>
        <div className="workspace"><span className="status-dot" /> Northstar Markets <span className="chevron">⌄</span></div>
        <p className="nav-label">Workspace</p>
        <nav>{navItems.map((item, index) => <button className={active === item ? "nav-item active" : "nav-item"} onClick={() => setActive(item)} key={item}><span className="nav-icon">{["◈", "◌", "↕", "✓", "⌁"][index]}</span>{item}{item === "Compliance" && <span className="nav-count">24</span>}</button>)}</nav>
        <p className="nav-label lower">Manage</p>
        <nav><button className="nav-item"><span className="nav-icon">◫</span>Trading accounts</button><a className="nav-item" href="/settings"><span className="nav-icon">⚙</span>Settings</a></nav>
        <div className="sidebar-bottom"><div className="user-avatar">RK</div><div><strong>Rayan Khan</strong><small>Super administrator</small></div><span className="more">•••</span></div>
      </aside>

      <section className="content">
        <header className="topbar"><div><p className="eyebrow">Monday, 18 March 2024</p><h1>{active}</h1></div><div className="top-actions"><button className="icon-button" aria-label="Search">⌕</button><button className="icon-button notification" aria-label="Notifications">♢<span /></button><div className="top-avatar">RK</div></div></header>
        <div className="toolbar"><div className="live-pill"><span className="pulse" /> All systems operational</div><button className="date-button">Last 30 days <span>⌄</span></button></div>

        <div className="kpi-grid">{kpis.map((kpi) => <article className={`kpi-card ${kpi.tone}`} key={kpi.label}><div className="kpi-top"><span>{kpi.label}</span><span className="trend">↗ {kpi.change}</span></div><strong>{kpi.value}</strong><div className="sparkline"><i /><i /><i /><i /><i /><i /><i /><i /><i /></div></article>)}</div>

        <div className="main-grid"><section className="panel performance"><div className="panel-heading"><div><p className="eyebrow">Portfolio performance</p><h2>Net equity</h2></div><div className="metric"><strong>$48,642,910</strong><span>+ $3.8M this period</span></div></div><div className="chart"><div className="chart-y"><span>$50M</span><span>$45M</span><span>$40M</span><span>$35M</span></div><svg viewBox="0 0 760 230" preserveAspectRatio="none" role="img" aria-label="Net equity trend"><defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#82d8c4" stopOpacity=".32" /><stop offset="1" stopColor="#82d8c4" stopOpacity="0" /></linearGradient></defs><path d="M0 193 C42 184 50 162 86 174 S130 174 158 141 S210 152 244 126 S289 137 320 110 S366 117 397 93 S438 104 469 72 S504 84 535 60 S579 78 608 42 S649 61 681 26 S723 50 760 13 L760 230 L0 230 Z" fill="url(#area)" /><path d="M0 193 C42 184 50 162 86 174 S130 174 158 141 S210 152 244 126 S289 137 320 110 S366 117 397 93 S438 104 469 72 S504 84 535 60 S579 78 608 42 S649 61 681 26 S723 50 760 13" fill="none" stroke="#45b69c" strokeWidth="3" /></svg><div className="chart-x"><span>19 Feb</span><span>26 Feb</span><span>04 Mar</span><span>11 Mar</span><span>18 Mar</span></div></div></section>
          <section className="panel activity"><div className="panel-heading"><div><p className="eyebrow">Live operations</p><h2>Activity feed</h2></div><button className="text-button">View all ↗</button></div><div className="activity-list"><div><span className="activity-icon green">$</span><p><strong>Deposit approved</strong><small>Michael Chen · USDT</small></p><time>2m</time></div><div><span className="activity-icon blue">↗</span><p><strong>Account created</strong><small>Elena Rossi · MT5 Live</small></p><time>8m</time></div><div><span className="activity-icon orange">!</span><p><strong>Withdrawal review</strong><small>Daniel Okafor · $12,500</small></p><time>14m</time></div><div><span className="activity-icon purple">⌁</span><p><strong>Commission credited</strong><small>IB-1048 · February cycle</small></p><time>26m</time></div></div></section></div>

        <section className="panel queue-panel"><div className="panel-heading"><div><p className="eyebrow">Compliance desk</p><h2>Verification queue <span className="heading-count">24</span></h2></div><button className="outline-button">Open queue ↗</button></div><div className="table-wrap"><table><thead><tr><th>Applicant</th><th>Document</th><th>Submitted</th><th>Risk signal</th><th /></tr></thead><tbody>{queue.map((person) => <tr key={person.name}><td><div className="person"><span className="person-avatar">{person.initials}</span><span><strong>{person.name}</strong><small>{person.country}</small></span></div></td><td>{person.type}</td><td>{person.age} ago</td><td><span className={`risk ${person.risk.toLowerCase()}`}>{person.risk}</span></td><td><button className="row-button">Review</button></td></tr>)}</tbody></table></div></section>
        <footer><span>Northstar Markets · Production</span><span>Data refreshed just now · <b className="green-text">99.99% uptime</b></span></footer>
      </section>
    </main>
  );
}
