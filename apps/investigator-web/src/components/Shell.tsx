import { useState, type ReactNode } from 'react';
import type { Case } from '../types';

type Props = { route: string; onNavigate: (route: string) => void; children: ReactNode; apiState?: string; caseData?: Case | null };
type NavItem = [string, string, string];

const groups: Array<[string, NavItem[]]> = [
  ['CASE FUSION', [['case-fusion', 'Case Fusion', '○']]],
  ['OPERATIONS', [['dashboard', 'Dashboard', '⌂'], ['cases', 'Cases', '□'], ['investigate', 'Investigations', '＋']]],
  ['INTELLIGENCE', [['wallets', 'Wallet intelligence', '◌'], ['risk-registry', 'Risk Registry', '◈'], ['graph', 'Transaction graph', '⌘'], ['cross-chain', 'Cross-chain intelligence', '↗'], ['patterns', 'Risk intelligence', '◒'], ['monitoring', 'Real-time retracing', '◉'], ['entities', 'Entities', '◇'], ['vasp-intelligence', 'VASP intelligence', '▣']]],
  ['EVIDENCE & RESPONSE', [['alerts', 'Alerts', '△'], ['evidence', 'Evidence', '▤'], ['reports', 'Reports', '▧']]],
  ['SYSTEM', [['operations', 'System operations', '◫']]]
];

export function Shell({ route, onNavigate, children, apiState = 'UNKNOWN', caseData }: Props) {
  const [search, setSearch] = useState('');
  const operational = apiState === 'ONLINE';
  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    if (search.trim()) onNavigate('risk-registry');
  };
  return <div className="shell shell-premium">
    <header className="topbar">
      <button className="brand-button" onClick={() => onNavigate('dashboard')} aria-label="Open dashboard"><span className="brand-mark">⬡</span><span><b>RRR</b><small>REAL-TIME RETRACING</small></span></button>
      <div className="platform-title"><strong>INVESTIGATION COMMAND CENTER</strong><span>Crypto Fraud Intelligence &amp; VASP Attribution</span></div>
      <form className="global-search" role="search" onSubmit={submitSearch}><span aria-hidden="true">⌕</span><input aria-label="Search case, wallet, transaction or entity" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search case / wallet / tx / entity…" /><kbd>ENTER</kbd></form>
      <div className="top-actions"><button className="icon-button" aria-label="Open alerts" onClick={() => onNavigate('alerts')}>♧</button><span className="alert-count">{apiState === 'ONLINE' ? 'LIVE' : 'STATUS'}</span><span className={`system-chip ${operational ? '' : 'is-warning'}`}><i className={operational ? '' : 'warn-dot'} />{apiState}</span><span className="user" aria-label="Investigator profile">AR</span><span className="user-label">Investigator<br /><small>Analysis Unit</small></span></div>
    </header>
    <div className="shell-body">
      <aside className="sidebar">
        <div className="case-context"><small>ACTIVE INVESTIGATION</small><strong>{caseData?.title || 'No active investigation'}</strong><code>{caseData ? caseData.external_case_reference || caseData.case_id.slice(0, 8).toUpperCase() : 'SELECT OR CREATE CASE'}</code><span className={caseData ? 'case-state' : 'case-state muted-state'}>{caseData ? caseData.status : 'EMPTY'}</span></div>
        <nav className="side-nav" aria-label="Primary navigation">{groups.map(([group, items]) => <div className="nav-group" key={group}><div className="side-caption">{group}</div>{items.map(([id, label, icon]) => <button key={id} className={route === id ? 'nav-item active' : 'nav-item'} onClick={() => onNavigate(id)}><span className="nav-icon" aria-hidden="true">{icon}</span><span>{label}</span></button>)}</div>)}</nav>
        <div className="sidebar-integrations"><div className="side-caption">EXTERNAL SYSTEMS</div><button className="integration-link" onClick={() => onNavigate('intake')}><i className="integration-status simulated" />NCRP <small>SIMULATED</small></button><button className="integration-link" onClick={() => onNavigate('intake')}><i className="integration-status simulated" />SAHYOG <small>SIMULATED</small></button><div className="integration-link"><i className="integration-status off" />VASP NETWORK <small>NOT CONFIGURED</small></div></div>
        <div className="sidebar-footer"><span className="live-indicator" /> Provider capability states<br /><b>Historical data is configuration-gated</b></div>
      </aside>
      <main className="workspace"><div className="breadcrumbs"><span>RRR</span><b>/</b><span>{route === 'dashboard' ? 'COMMAND CENTER' : route.toUpperCase()}</span></div>{children}</main>
    </div>
  </div>;
}
