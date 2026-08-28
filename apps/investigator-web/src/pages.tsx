import {useEffect,useState} from 'react'; import type {ReactNode} from 'react'; import type {Case,CaseListItem,Trace,DashboardSummary,EntityRecord,EvidenceRecord,RealtimeAlert,ProviderOperationalStatus,WalletIntelligence} from './types'; import {api,dashboardSummary,listAlerts,listCases,listEntities,listEvidence,providerStatuses,reviewAlert,walletIntelligence,systemProviders,databaseDiagnostics,databaseIntegrity,sanctionsStatus} from './api'; import {GraphInspector} from './components/GraphInspector';
export function Dashboard({onNavigate}:{onNavigate:(r:string)=>void}){return <><PageHeader eyebrow="OPERATIONS / COMMAND CENTER" title="Investigator command center" action={<button className="primary" onClick={()=>onNavigate('investigate')}>＋ New investigation</button>}/><section className="hero-strip"><div><span className="eyebrow blue-text">AUTHORIZED INVESTIGATION WORKSPACE</span><h2>Trace the observation.<br/><em>Preserve the evidence.</em></h2><p>One operational view for complaints, wallets, transaction flow and source-backed intelligence.</p></div><div className="mission-state"><span className="live-indicator"/>PLATFORM STATUS<strong>Historical analysis online</strong><small>Real-time engine · Not configured</small></div></section><div className="metric-grid">{[['ACTIVE CASES','—','Awaiting case index'],['WALLETS UNDER REVIEW','—','Provider-backed'],['HIGH-PRIORITY ALERTS','3','Review queue'],['ATTRIBUTED ENTITIES','—','Source-backed only']].map(x=><div className="metric-card"><span>{x[0]}</span><b>{x[1]}</b><small>{x[2]}</small></div>)}</div><section className="two-panels"><div className="surface"><PanelTitle eyebrow="WORK QUEUE" title="Recent investigation activity"/><Empty label="No case activity loaded" text="Create an investigation to begin the operational timeline."/></div><div className="surface"><PanelTitle eyebrow="INTEGRATION READINESS" title="External systems"/><Integration name="SAHYOG complaint intake" state="SIMULATED"/><Integration name="NCRP complaint intake" state="SIMULATED"/><Integration name="Live monitoring engine" state="NOT CONFIGURED"/></div></section></>}
export function Intake({onComplete}:{onComplete:(c:Case,t:Trace)=>void}){const [title,setTitle]=useState('');const [fraud,setFraud]=useState('Investment fraud');const [wallet,setWallet]=useState('');const [source,setSource]=useState('MANUAL');const [busy,setBusy]=useState(false);const [error,setError]=useState('');async function submit(){setBusy(true);setError('');try{const c=await api.createCase({title:title||'Untitled investigation',fraud_type:fraud,priority:'HIGH'});await api.addWallet(c.case_id,wallet);const t=await api.trace(c.case_id,wallet);onComplete(c,t)}catch(e){setError(e instanceof Error?e.message:'Unable to start investigation')}finally{setBusy(false)}}return <><PageHeader eyebrow="INVESTIGATIONS / INTAKE" title="Create investigation" action={<span className="capability-pill simulated">MANUAL INTAKE</span>}/><div className="intake-grid"><div className="surface intake-form"><PanelTitle eyebrow="01 / COMPLAINT SOURCE" title="Complaint context"/><div className="source-options">{['MANUAL','NCRP','SAHYOG','OTHER'].map(x=><button className={source===x?'source-option selected':'source-option'} onClick={()=>setSource(x)}>{x}<small>{x==='MANUAL'?'AVAILABLE':'SIMULATED'}</small></button>)}</div><label>Complaint reference<input placeholder="Optional external reference"/></label><label>Case title<input value={title} onChange={e=>setTitle(e.target.value)} placeholder="e.g. Project Northstar"/></label><label>Fraud type<select value={fraud} onChange={e=>setFraud(e.target.value)}><option>Investment fraud</option><option>Romance scam</option><option>Phishing</option><option>Ransomware</option></select></label><PanelTitle eyebrow="02 / WALLET INTAKE" title="Reported asset"/><label>Chain<select><option>Ethereum</option></select></label><label>Reported wallet<input className="mono" value={wallet} onChange={e=>setWallet(e.target.value)} placeholder="0x..."/></label>{error&&<div className="error">{error}</div>}<button className="primary wide" disabled={busy||wallet.length!==42} onClick={submit}>{busy?'Retrieving historical activity…':'Create case and start trace'} <span>→</span></button></div><div className="surface intake-side"><div className="callout"><span className="eyebrow blue-text">SAHYOG / NCRP ADAPTER</span><h3>Ready for the connection boundary.</h3><p>This environment does not connect to SAHYOG or NCRP. External complaints must be imported through a future adapter and normalized before case creation.</p><div className="capability-pill simulated">SIMULATED ADAPTER · NOT CONNECTED</div></div><div className="step-list"><Step n="01" text="Complaint source"/><Step n="02" text="Complaint information"/><Step n="03" text="Reported wallet"/><Step n="04" text="Review and trace"/></div></div></div></>}
export function Workspace({caseData,trace,onNavigate}:{caseData:Case;trace:Trace;onNavigate:(r:string)=>void}){return <><div className="case-header"><div><div className="eyebrow">CASE / {caseData.case_id.slice(0,8).toUpperCase()}</div><h1>{caseData.title}</h1><p>{caseData.fraud_type} · <span className="badge blue">{caseData.status}</span></p></div><button className="secondary" onClick={()=>onNavigate('graph')}>Open graph workspace →</button></div><div className="case-tabs"><span className="active">OVERVIEW</span><span onClick={()=>onNavigate('graph')}>GRAPH</span><span>TRANSACTIONS</span><span>ENTITIES</span><span>EVIDENCE</span><span>REPORT</span></div><div className="summary-grid"><div className="surface"><PanelTitle eyebrow="CASE INFORMATION" title="Investigation context"/><dl><dt>CASE ID</dt><dd>{caseData.case_id}</dd><dt>CREATED</dt><dd>{new Date(caseData.created_at).toLocaleString()}</dd><dt>REPORTED WALLETS</dt><dd>{caseData.wallets.length}</dd><dt>DATA MODE</dt><dd>HISTORICAL · ALCHEMY</dd></dl></div><div className="surface"><PanelTitle eyebrow="TRACE SUMMARY" title="Observed activity"/><div className="summary-numbers"><b>{trace.metrics.node_count}<small>ADDRESSES</small></b><b>{trace.metrics.edge_count}<small>TRANSFERS</small></b><b>{trace.evidence.length}<small>EVIDENCE ITEMS</small></b></div><p className="muted">No attribution or risk conclusion is implied by these observations.</p></div></div><div className="surface finding-panel"><PanelTitle eyebrow="KEY FINDINGS" title="Evidence-backed observations"/><div className="finding-row"><span className="finding-icon">◇</span><div><b>Observed flow available</b><p>{trace.metrics.edge_count} persisted transfer edges across {trace.metrics.maximum_hop} observed hops.</p></div><span className="badge blue">OBSERVED</span></div><div className="finding-row"><span className="finding-icon">◎</span><div><b>Entity attribution</b><p>Source-backed attribution is available from the Entities workspace when configured.</p></div><span className="badge neutral">NOT LOADED</span></div></div></>}
export function GenericPage({title,eyebrow,text}:{title:string;eyebrow:string;text:string}){return <><PageHeader eyebrow={eyebrow} title={title}/><div className="surface empty-page"><div className="empty-visual">◇</div><h3>Workspace ready</h3><p>{text}</p><span className="capability-pill simulated">CAPABILITY SURFACE · BACKEND INTEGRATION PENDING</span></div></>}
export function WalletsPage(){const [address,setAddress]=useState('');const [result,setResult]=useState<WalletIntelligence|null>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);async function search(){setBusy(true);setError('');setResult(null);try{setResult(await walletIntelligence('ethereum',address.trim()))}catch(e){setError(e instanceof Error?e.message:'Wallet intelligence unavailable')}finally{setBusy(false)}}return <><PageHeader eyebrow="INTELLIGENCE / WALLET" title="Wallet intelligence"/><section className="surface wallet-search"><div className="eyebrow">PERSISTED OBSERVATION LOOKUP</div><h2>Inspect a wallet identity</h2><p>Searches canonical PostgreSQL investigation records. No balance or ownership claim is made from this view.</p><div className="wallet-search-row"><input className="mono" value={address} onChange={e=>setAddress(e.target.value)} placeholder="0x..." aria-label="Ethereum wallet address"/><button className="primary" disabled={busy||address.trim().length!==42} onClick={search}>{busy?'LOOKING UP...':'LOOK UP WALLET'}</button></div>{error&&<div className="error" role="alert">{error}</div>}</section>{result&&<section className="wallet-intelligence-result"><div className="surface wallet-identity"><span className="data-badge">PERSISTED OBSERVATION</span><div className="eyebrow">{result.chain.toUpperCase()} / WALLET</div><h2 className="mono">{result.address}</h2><div className="wallet-stat-grid"><WalletMetric label="TRANSACTIONS" value={result.transaction_count}/><WalletMetric label="INBOUND" value={result.inbound_count}/><WalletMetric label="OUTBOUND" value={result.outbound_count}/><WalletMetric label="CASES" value={result.case_count}/><WalletMetric label="EVIDENCE" value={result.evidence_count}/></div></div><div className="surface"><PanelTitle eyebrow="OBSERVED ASSETS" title={result.assets.length?result.assets.join(' / '):'No assets recorded'}/><dl><dt>FIRST OBSERVED</dt><dd>{result.first_seen?new Date(result.first_seen).toLocaleString():'Unavailable'}</dd><dt>LAST OBSERVED</dt><dd>{result.last_seen?new Date(result.last_seen).toLocaleString():'Unavailable'}</dd><dt>RELATED CASE IDS</dt><dd>{result.related_case_ids.length?result.related_case_ids.join(', '):'No related cases'}</dd></dl><p className="muted">This summary is derived from persisted graph/evidence records. Attribution, criminality, and current balance are not established here.</p></div></section>}</>}
function PageHeader({eyebrow,title,action}:{eyebrow:string;title:string;action?:ReactNode}){return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1></div>{action}</div>}
function PanelTitle({eyebrow,title}:{eyebrow:string;title:string}){return <div className="panel-title"><div className="eyebrow">{eyebrow}</div><h3>{title}</h3></div>}
function Empty({label,text}:{label:string;text:string}){return <div className="empty-block"><span>⌁</span><b>{label}</b><p>{text}</p></div>}
function Integration({name,state}:{name:string;state:string}){return <div className="integration-row"><span className={state==='SIMULATED'?'integration-status simulated':'integration-status off'}/><b>{name}</b><small>{state}</small></div>}
function Step({n,text}:{n:string;text:string}){return <div className="step"><span>{n}</span>{text}<i>○</i></div>}
function WalletMetric({label,value}:{label:string;value:number}){return <div className="wallet-metric"><span>{label}</span><b>{value}</b></div>}
export function CasesPage({onNavigate,onOpenCase}:{onNavigate:(route:string)=>void;onOpenCase:(caseId:string)=>void}){
  const [items,setItems]=useState<CaseListItem[]>([]);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  useEffect(()=>{
    setLoading(true);
    listCases().then(setItems).catch(e=>setError(e instanceof Error?e.message:'Case index unavailable')).finally(()=>setLoading(false))
  },[]);
  return (
    <>
      <PageHeader eyebrow="INVESTIGATIONS / CASE REGISTRY" title="Investigation cases" action={<button className="primary" onClick={()=>onNavigate('investigate')}>＋ New investigation</button>}/>
      {error&&<div className="error" role="alert">{error}</div>}
      <section className="surface">
        <PanelTitle eyebrow="PERSISTED CASES" title={loading?'Loading cases…':error?'Backend unavailable':items.length?items.length+' investigations':'0 active cases'}/>
        {loading ? (
          <Empty label="Loading persisted cases" text="Querying PostgreSQL through FastAPI…"/>
        ) : error ? (
          <Empty label="Backend unavailable" text={error}/>
        ) : items.length ? (
          <table className="workspace-table">
            <thead>
              <tr>
                <th>CASE ID / TITLE</th>
                <th>REFERENCE</th>
                <th>FRAUD TYPE</th>
                <th>WALLET</th>
                <th>STATUS</th>
                <th>RISK</th>
                <th>STAGE</th>
                <th>WALLETS &amp; TRANSFERS</th>
                <th>LAST UPDATED</th>
                <th style={{ textAlign: 'right' }}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.case_id}>
                  <td style={{ fontWeight: 'bold', color: '#f3f4f6' }}><span className="mono-badge">{item.case_id.slice(0, 8).toUpperCase()}</span><br />{item.title}</td>
                  <td>{item.external_case_reference || 'No reference'}</td>
                  <td>{item.fraud_type}</td>
                  <td className="mono">{item.wallet_address ? `${item.wallet_address.slice(0, 8)}…${item.wallet_address.slice(-6)}` : 'No wallet'}</td>
                  <td>
                    <span className={`status-badge ${item.status.toLowerCase()}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>{item.risk_band || 'NOT ASSESSED'}</td>
                  <td>{item.workflow_stage || item.status}</td>
                  <td>
                    <span className="mono-badge">
                      {item.wallet_count} wallets · {item.transaction_count} txs
                    </span>
                  </td>
                  <td style={{ fontSize: '12px', color: '#9ca3af' }}>
                    {new Date(item.updated_at).toLocaleString()}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="case-open-btn" onClick={()=>onOpenCase(item.case_id)}>
                      OPEN CASE
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty label="Database connected — no cases" text="Create an investigation to begin the operational timeline."/>
        )}
      </section>
    </>
  );
}
export function LiveDashboard({onNavigate}:{onNavigate:(r:string)=>void}){const [summary,setSummary]=useState<DashboardSummary|null>(null);const [error,setError]=useState('');useEffect(()=>{dashboardSummary().then(setSummary).catch(e=>setError(e instanceof Error?e.message:'Dashboard data unavailable'))},[]);const value=(item:number|undefined)=>summary?String(item??0):'—';return <><PageHeader eyebrow="OPERATIONS / COMMAND CENTER" title="Investigator command center" action={<button className="primary" onClick={()=>onNavigate('investigate')}>＋ New investigation</button>}/>{error&&<div className="error" role="alert">{error}</div>}<section className="hero-strip"><div><span className="eyebrow blue-text">AUTHORIZED INVESTIGATION WORKSPACE</span><h2>Trace the observation.<br/><em>Preserve the evidence.</em></h2><p>Operational metrics are loaded from persisted PostgreSQL investigation state. Empty or unavailable data is not replaced with fixture values.</p></div><div className="mission-state"><span className="live-indicator"/>PLATFORM STATUS<strong>{summary?'Historical analysis online':'Awaiting backend data'}</strong><small>Realtime engine · Not configured</small></div></section><div className="metric-grid">{[['ACTIVE CASES',value(summary?.active_cases),'Persisted case registry'],['WALLETS UNDER REVIEW',value(summary?.wallets_under_review),'Persisted wallet identity'],['HIGH-PRIORITY ALERTS',value(summary?.high_priority_alerts),'New review candidates'],['ATTRIBUTED ENTITIES',value(summary?.attributed_entities),'Source-backed records']].map(x=><div className="metric-card" key={x[0]}><span>{x[0]}</span><b>{x[1]}</b><small>{x[2]}</small></div>)}</div><section className="two-panels"><div className="surface"><PanelTitle eyebrow="OBSERVED ACTIVITY" title="Operational summary"/><dl><dt>OBSERVED TRANSACTIONS</dt><dd>{value(summary?.observed_transactions)}</dd><dt>ACTIVE WATCHES</dt><dd>{value(summary?.active_watches)}</dd><dt>LAST ACTIVITY</dt><dd>{summary?.last_activity_at?new Date(summary.last_activity_at).toLocaleString():'No persisted activity'}</dd></dl></div><div className="surface"><PanelTitle eyebrow="INTEGRATION READINESS" title="External systems"/><Integration name="SAHYOG complaint intake" state="SIMULATED"/><Integration name="NCRP complaint intake" state="SIMULATED"/><Integration name="Live monitoring engine" state="NOT CONFIGURED"/></div></section></>}
export function EntitiesPage(){
  const [items,setItems]=useState<EntityRecord[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{
    listEntities().then(setItems).catch(e=>setError(e instanceof Error?e.message:'Entity catalog unavailable'))
  },[]);
  return (
    <>
      <PageHeader eyebrow="INTELLIGENCE / ENTITIES" title="Entities / VASPs"/>
      {error&&<div className="error" role="alert">{error}</div>}
      <section className="surface">
        <PanelTitle eyebrow="SOURCE-BACKED CATALOG" title={items.length?items.length+' entities':'No entities loaded'}/>
        {items.length ? (
          <table className="workspace-table">
            <thead>
              <tr>
                <th>ENTITY NAME</th>
                <th>TYPE</th>
                <th>JURISDICTION</th>
                <th>PROVENANCE</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.entity_id}>
                  <td style={{ fontWeight: 'bold', color: '#f3f4f6' }}>{item.name}</td>
                  <td>
                    <span className="status-badge" style={{ background: '#1f2937', color: '#9ca3af' }}>
                      {item.entity_type}
                    </span>
                  </td>
                  <td>{item.jurisdiction||'Jurisdiction unavailable'}</td>
                  <td style={{ fontSize: '11px', fontFamily: 'DM Mono', color: '#9ca3af' }}>
                    Source-backed VASP attribution
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty label="No attribution records available" text="Entity intelligence is only shown when a configured attribution dataset is persisted."/>
        )}
      </section>
    </>
  );
}
export function EvidencePage({caseData}:{caseData:Case|null}){
  const [items,setItems]=useState<EvidenceRecord[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{
    if(caseData)listEvidence(caseData.case_id).then(setItems).catch(e=>setError(e instanceof Error?e.message:'Evidence unavailable'))
  },[caseData]);
  return (
    <>
      <PageHeader eyebrow="CASEWORK / EVIDENCE" title="Evidence workspace"/>
      {!caseData ? (
        <div className="surface">
          <Empty label="No active case context" text="Open or create an investigation before querying case-scoped evidence."/>
        </div>
      ) : (
        <section className="surface">
          {error&&<div className="error" role="alert">{error}</div>}
          <PanelTitle eyebrow={'CASE '+caseData.case_id.slice(0,8).toUpperCase()} title={items.length?items.length+' evidence records':'No evidence loaded'}/>
          {items.length ? (
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>EVIDENCE ID</th>
                  <th>TYPE</th>
                  <th>CHAIN</th>
                  <th>TRANSACTION HASH</th>
                  <th>CAPTURED TIMELINE</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.evidence_id}>
                    <td style={{ fontFamily: 'DM Mono', fontSize: '12px' }}>{item.evidence_id.slice(0,8).toUpperCase()}...</td>
                    <td>
                      <span className="status-badge open">
                        {item.type}
                      </span>
                    </td>
                    <td>{item.chain.toUpperCase()}</td>
                    <td style={{ fontFamily: 'DM Mono', fontSize: '12px' }}>{item.tx_hash||'No transaction hash'}</td>
                    <td style={{ fontSize: '12px', color: '#9ca3af' }}>
                      {item.source} · {new Date(item.captured_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Empty label="No persisted evidence" text="Evidence appears after a trace or realtime observation is persisted."/>
          )}
        </section>
      )}
    </>
  );
}
export function AlertsPage(){
  const [items,setItems]=useState<RealtimeAlert[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState('');
  useEffect(()=>{
    listAlerts().then(setItems).catch(e=>setError(e instanceof Error?e.message:'Alert queue unavailable'))
  },[]);
  async function review(item:RealtimeAlert,action:'ACKNOWLEDGE'|'DISMISS'|'ESCALATE'){
    setBusy(item.alert_id);
    setError('');
    try{
      const updated=await reviewAlert(item.case_id,item.alert_id,action);
      setItems(current=>current.map(row=>row.alert_id===updated.alert_id?updated:row))
    }catch(e){
      setError(e instanceof Error?e.message:'Alert review failed')
    }finally{
      setBusy('')
    }
  }
  return (
    <>
      <PageHeader eyebrow="OPERATIONS / ALERTS" title="Alert center"/>
      {error&&<div className="error" role="alert">{error}</div>}
      <section className="surface">
        <PanelTitle eyebrow="PERSISTED INVESTIGATIVE SIGNALS" title={items.length?items.length+' alerts':'No alerts loaded'}/>
        {items.length ? (
          <table className="workspace-table">
            <thead>
              <tr>
                <th>TITLE</th>
                <th>SEVERITY</th>
                <th>STATUS</th>
                <th>TYPE</th>
                <th>GENERATED AT</th>
                <th style={{ textAlign: 'right' }}>REVIEWS &amp; ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.alert_id}>
                  <td style={{ fontWeight: 'bold', color: '#f3f4f6' }}>{item.title}</td>
                  <td>
                    <span className="status-badge" style={{
                      background: item.severity === 'CRITICAL' || item.severity === 'HIGH' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                      color: item.severity === 'CRITICAL' || item.severity === 'HIGH' ? '#f87171' : '#fbbf24'
                    }}>
                      {item.severity}
                    </span>
                  </td>
                  <td>{item.status}</td>
                  <td>{item.alert_type}</td>
                  <td style={{ fontSize: '12px', color: '#9ca3af' }}>
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="alert-actions" style={{ display: 'flex', gap: '5px', justifyContent: 'flex-end' }}>
                      <button className="case-open-btn" disabled={!!busy || item.status === 'DISMISSED'} onClick={() => review(item, 'ACKNOWLEDGE')} style={{ padding: '4px 8px', fontSize: '11px' }}>Ack</button>
                      <button className="case-open-btn" disabled={!!busy || item.status === 'DISMISSED'} onClick={() => review(item, 'ESCALATE')} style={{ padding: '4px 8px', fontSize: '11px', background: '#3b82f6', color: '#fff' }}>Escalate</button>
                      <button className="case-open-btn" disabled={!!busy || item.status === 'DISMISSED'} onClick={() => review(item, 'DISMISS')} style={{ padding: '4px 8px', fontSize: '11px', background: '#4b5563', color: '#fff' }}>Dismiss</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty label="No persisted alerts" text="Alerts are created only by configured realtime or analytical workflows. No fixture alerts are displayed."/>
        )}
      </section>
    </>
  );
}
const short = (s: string) => s.length > 12 ? s.slice(0, 8) + '...' : s;

const statusClass = (value: string) => {
  const v = String(value).toUpperCase();
  if (v === 'CONNECTED' || v === 'ONLINE' || v === 'HEALTHY') return 'good';
  if (v === 'DEVELOPMENT_FIXTURE' || v === 'SIMULATED') return 'simulated';
  if (v === 'DEGRADED') return 'warn';
  return 'off';
};

export function ProviderOperationsPage(){
  const [providers, setProviders] = useState<any[]>([]);
  const [db, setDb] = useState<any>(null);
  const [integrity, setIntegrity] = useState<any>(null);
  const [sanctions, setSanctions] = useState<any>(null);
  const [dash, setDash] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const loadDiagnostics = () => {
    setLoading(true);
    setError('');
    Promise.all([
      systemProviders().catch(() => []),
      databaseDiagnostics().catch(() => null),
      databaseIntegrity().catch(() => null),
      sanctionsStatus().catch(() => null),
      dashboardSummary().catch(() => null)
    ]).then(([p, d, i, s, ds]) => {
      setProviders(p);
      setDb(d);
      setIntegrity(i);
      setSanctions(s);
      setDash(ds);
    }).catch(e => {
      setError(e instanceof Error ? e.message : 'Operations diagnostics unavailable');
    }).finally(() => {
      setLoading(false);
    });
  };

  useEffect(() => {
    loadDiagnostics();
  }, []);

  return (
    <>
      <PageHeader eyebrow="OPERATIONS / CONTROL CENTER" title="Provider control center" action={<button className="primary" onClick={loadDiagnostics}>Refresh Diagnostics</button>} />
      {error && <div className="error" role="alert">{error}</div>}
      
      {loading ? (
        <div className="surface" style={{ padding: '20px', textAlign: 'center' }}>Awaiting dependency responses...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px', marginTop: '20px' }}>
          
          <section className="surface" style={{ padding: '20px', background: '#111827', borderRadius: '6px', border: '1px solid #1f2937' }}>
            <PanelTitle eyebrow="INTEGRATION HEALTH" title="Blockchain providers" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginTop: '15px' }}>
              {providers.map((item, idx) => (
                <div key={idx} style={{ padding: '12px', background: '#0a0d14', borderRadius: '6px', border: '1px solid #1f2937' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <strong style={{ color: '#f3f4f6' }}>{item.provider}</strong>
                    <span className={`integration-status ${statusClass(item.status)}`} style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', textTransform: 'uppercase', background: '#1f2937' }}>
                      {item.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                    {item.network && <div>Network: {item.network}</div>}
                    {item.latency_ms !== undefined && item.latency_ms > 0 && <div>Latency: {item.latency_ms} ms</div>}
                    <div>Detail: {item.detail || 'No description'}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="surface" style={{ padding: '20px', background: '#111827', borderRadius: '6px', border: '1px solid #1f2937' }}>
            <PanelTitle eyebrow="RELATIONAL PERSISTENCE" title="PostgreSQL database" />
            {db ? (
              <div style={{ marginTop: '15px', fontSize: '13px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span>Status:</span>
                  <strong className={db.status === 'CONNECTED' ? 'green-text' : 'red-text'}>{db.status}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span>Migration level:</span>
                  <strong>{db.migration_status || 'Up to date'}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span>Pool status:</span>
                  <strong>{db.pool}</strong>
                </div>
                {integrity && integrity.counts && (
                  <div style={{ marginTop: '15px', background: '#0a0d14', padding: '10px', borderRadius: '6px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '6px', borderBottom: '1px solid #1f2937', paddingBottom: '4px' }}>Table Counts</div>
                    {Object.entries(integrity.counts).map(([tbl, cnt]) => (
                      <div key={tbl} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#9ca3af' }}>
                        <span>{tbl}:</span>
                        <strong>{String(cnt)}</strong>
                      </div>
                    ))}
                    {integrity.orphans && (
                      <div style={{ marginTop: '8px', color: '#f87171', fontSize: '11px' }}>
                        Orphan count: {Object.values(integrity.orphans).reduce((sum: number, cnt: any) => sum + parseInt(cnt || 0), 0)} orphans
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p className="ops-empty">No Postgres connectivity diagnostics available.</p>
            )}
          </section>

          <section className="surface" style={{ padding: '20px', background: '#111827', borderRadius: '6px', border: '1px solid #1f2937' }}>
            <PanelTitle eyebrow="CURATED DATASETS" title="Threat intelligence & sanctions" />
            <div style={{ marginTop: '15px', fontSize: '13px' }}>
              <div style={{ background: '#0a0d14', padding: '12px', borderRadius: '6px', marginBottom: '15px' }}>
                <strong style={{ display: 'block', color: '#f3f4f6', marginBottom: '6px' }}>OFAC Sanctions Status</strong>
                {sanctions ? (
                  <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                    <div>Version: {sanctions.dataset_version}</div>
                    <div>Source: {short(sanctions.source)}</div>
                    <div>Record count: {sanctions.record_count} records</div>
                    <div>Checksum: {short(sanctions.checksum)}</div>
                    <div>Last synced: {sanctions.retrieved_at ? new Date(sanctions.retrieved_at).toLocaleString() : 'Never'}</div>
                  </div>
                ) : (
                  <div style={{ color: '#ef4444' }}>Dataset not configured or synced yet.</div>
                )}
              </div>

              <div style={{ background: '#0a0d14', padding: '12px', borderRadius: '6px' }}>
                <strong style={{ display: 'block', color: '#f3f4f6', marginBottom: '6px' }}>Attribution Catalog</strong>
                <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                  <div>Attributed entities: {dash?.attributed_entities || 0} entities</div>
                  <div>Active subscriptions/watches: {dash?.active_watches || 0} watches</div>
                </div>
              </div>
            </div>
          </section>

        </div>
      )}
    </>
  );
}
