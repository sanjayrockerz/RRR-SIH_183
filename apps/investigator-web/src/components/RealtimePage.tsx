import {useEffect,useState} from 'react';
import {api,createSimulatedWatch,sendSimulatedEvent} from '../api';
import type {Case,Trace,Watch,TimelineEvent,ChangeSet,RealtimeAlert,Capability} from '../types';

export function RealtimePage({caseData,trace}:{caseData:Case;trace:Trace}){
 const [watches,setWatches]=useState<Watch[]>([]);
 const [timeline,setTimeline]=useState<TimelineEvent[]>([]);
 const [changes,setChanges]=useState<ChangeSet[]>([]);
 const [alerts,setAlerts]=useState<RealtimeAlert[]>([]);
 const [caps,setCaps]=useState<Capability[]>([]);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [simBusy,setSimBusy]=useState(false);
 const [latestResult,setLatestResult]=useState<any>(null);

 const refresh=()=>Promise.all([
   api.watches(caseData.case_id),
   api.timeline(caseData.case_id),
   api.changes(caseData.case_id),
   api.realtimeAlerts(caseData.case_id),
   api.realtimeCapabilities()
 ]).then(([w,t,c,a,p])=>{
   setWatches(w);
   setTimeline(t);
   setChanges(c);
   setAlerts(a);
   setCaps(p);
 }).catch(e=>setError(e.message));

 useEffect(()=>{refresh()},[caseData.case_id]);

 const capability=caps.find(c=>c.name==='address_activity_webhooks');
 const configured=capability?.status==='SUPPORTED';

 async function start(){
   setBusy(true);setError('');
   try{
     await api.createWatch(caseData.case_id,trace.root_address);
     await refresh();
   }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }

 async function startSimulated(){
   setSimBusy(true);setError('');
   try{
     await createSimulatedWatch(caseData.case_id,trace.root_address);
     await refresh();
   }catch(e){setError((e as Error).message)}finally{setSimBusy(false)}
 }

 async function sendSimulated(){
   setSimBusy(true);setError('');
   try{
     const destination='0x'+'1'.repeat(40);
     const id=crypto.randomUUID().replaceAll('-','');
     const res = await sendSimulatedEvent({
       event_id:id,
       provider:'SIMULATED EVENT SOURCE',
       chain:'ethereum',
       received_at:new Date().toISOString(),
       observed_at:new Date().toISOString(),
       block_number:19000000,
       transaction_hash:'0x'+(id+id).slice(0,64),
       from_address:trace.root_address,
       to_address:destination,
       asset:'ETH',
       amount:'0.25'
     });
     setLatestResult(res);
     await refresh();
   }catch(e){setError((e as Error).message)}finally{setSimBusy(false)}
 }

 async function toggle(w:Watch){
   try{
     if(w.status==='ACTIVE')await api.pauseWatch(caseData.case_id,w.watch_id);
     else await api.resumeWatch(caseData.case_id,w.watch_id);
     await refresh();
   }catch(e){setError((e as Error).message)}
 }

 const pipelineSteps = [
   { key: 'LIVE_EVENT', label: 'LIVE EVENT', active: !!latestResult || timeline.length > 0 },
   { key: 'TX_ADDED', label: 'TRANSACTION ADDED', active: changes.length > 0 },
   { key: 'GRAPH_UPDATED', label: 'GRAPH UPDATED', active: changes.some(c => c.changes?.graph_edge_id) },
   { key: 'RISK_CHANGED', label: 'RISK CHANGED', active: timeline.some(t => (t?.event_type || '').includes('RISK')) },
   { key: 'VASP_UPDATED', label: 'VASP UPDATED', active: timeline.some(t => (t?.event_type || '').includes('VASP')) },
   { key: 'RELATED_CASE', label: 'RELATED CASE FOUND', active: timeline.some(t => (t?.event_type || '').includes('CASE_FUSION')) },
   { key: 'ALERT_GEN', label: 'ALERT GENERATED', active: alerts.length > 0 },
 ];

 return (
   <>
     <div className="page-header">
       <div>
         <div className="eyebrow">RRR / REAL-TIME RETRACING</div>
         <h1>Monitoring command center</h1>
         <p className="muted">Realtime event processing pipeline & reactive investigation workflow.</p>
       </div>
       <span className={configured ? 'status-pill good' : 'status-pill warn'}>
         {configured ? 'LIVE WEBHOOK READY' : 'SIMULATED / TEST MODE'}
       </span>
     </div>

     {error && <div className="error" role="alert">{error}</div>}

     {/* Reactive Pipeline Stepper */}
     <section className="surface" style={{ marginBottom: '1.5rem', padding: '1.25rem' }}>
       <div className="panel-head">
         <div>
           <span className="eyebrow blue-text">AUTOMATED REACTIVE PIPELINE</span>
           <h3 style={{ margin: '0.25rem 0' }}>Realtime Retracing Progression</h3>
         </div>
         <small className="muted">Auto-triggers on watched wallet activity</small>
       </div>
       <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflowX: 'auto', padding: '0.75rem 0' }}>
         {pipelineSteps.map((step, idx) => (
           <div key={step.key} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
             <div style={{
               padding: '0.5rem 0.75rem',
               borderRadius: '6px',
               fontSize: '0.75rem',
               fontWeight: 600,
               letterSpacing: '0.05em',
               background: step.active ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255, 255, 255, 0.05)',
               border: step.active ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
               color: step.active ? '#60a5fa' : '#9ca3af',
               whiteSpace: 'nowrap'
             }}>
               {step.label}
             </div>
             {idx < pipelineSteps.length - 1 && (
               <span style={{ color: '#4b5563', fontWeight: 'bold' }}>↓</span>
             )}
           </div>
         ))}
       </div>
     </section>

     <div className="monitor-banner">
       <div>
         <span className="eyebrow">DATA MODE</span>
         <strong>{configured ? 'LIVE' : 'HISTORICAL / SIMULATED'}</strong>
         <small>Alchemy Address Activity Webhook · Ethereum / Tron</small>
       </div>
       <div>
         <span className="eyebrow">REAL-TIME ENGINE</span>
         <strong>{configured ? 'READY' : 'ACTIVE SIMULATED SEAM'}</strong>
         <small>Idempotent deduplication & durable event logging online</small>
       </div>
     </div>

     <div className="monitor-grid">
       <section className="panel">
         <div className="panel-head">
           <div>
             <span className="eyebrow">WATCH TARGETS</span>
             <h2>Tracked addresses</h2>
           </div>
           <div>
             <button className="primary-button" disabled={busy || !configured} onClick={start}>
               {busy ? 'Starting…' : 'Watch root wallet'}
             </button>
             <button className="ghost-button" disabled={simBusy} onClick={startSimulated}>
               {simBusy ? 'Starting…' : 'Start simulated watch'}
             </button>
           </div>
         </div>

         {!watches.length ? (
           <div className="empty-state">No watch targets exist. Start a watch to trigger the pipeline.</div>
         ) : (
           watches.map(w => (
             <div className="watch-row" key={w.watch_id}>
               <div>
                 <strong>{w.address.slice(0, 10)}…{w.address.slice(-8)}</strong>
                 <small>{w.chain} · {w.provider}</small>
               </div>
               <span className={'status-pill ' + (w.status === 'ACTIVE' ? 'good' : 'warn')}>{w.status}</span>
               <button className="ghost-button" onClick={() => toggle(w)}>
                 {w.status === 'ACTIVE' ? 'Pause' : 'Resume'}
               </button>
               {w.error && <small className="error-text">{w.error}</small>}
             </div>
           ))
         )}

         {watches.some(w => w.source === 'SIMULATED' && w.status === 'ACTIVE') && (
           <button className="secondary wide-action" disabled={simBusy} onClick={sendSimulated}>
             {simBusy ? 'Applying event…' : 'Send simulated realtime event'}
           </button>
         )}
       </section>

       <section className="panel">
         <div className="panel-head">
           <div>
             <span className="eyebrow">EVENT TIMELINE & PROCESSING STATUS</span>
             <h2>Realtime activity stream</h2>
           </div>
         </div>
         {!timeline.length ? (
           <div className="empty-state">No realtime observations have been applied yet.</div>
         ) : (
           timeline.slice(0, 8).map(e => (
             <div className="timeline-row" key={e.event_id}>
               <time>{new Date(e.timestamp).toLocaleTimeString()}</time>
               <div>
                 <strong>{(e?.event_type || '').replaceAll('_', ' ') || 'EVENT'}</strong>
                 <p>{e.summary}</p>
                 <small>{e.source} · {e.evidence_ids ? `${e.evidence_ids.length} evidence ref(s)` : 'No evidence'}</small>
               </div>
             </div>
           ))
         )}
       </section>
     </div>

     <div className="monitor-grid">
       <section className="panel">
         <div className="panel-head">
           <div>
             <span className="eyebrow">STATE CHANGES & GRAPH UPDATES</span>
             <h2>Durable change sets</h2>
           </div>
         </div>
         {!changes.length ? (
           <div className="empty-state">No graph mutations recorded yet.</div>
         ) : (
           changes.map(c => (
             <div className="change-row" key={c.change_set_id}>
               <span className="signal-dot" />
               <div>
                 <strong>{String(c.changes.transactions_added || 0)} transaction(s) added</strong>
                 <small>Event {c.event_id ? c.event_id.slice(0, 12) : ''}… · edge {String(c.changes.graph_edge_id || 'unassigned')}</small>
               </div>
             </div>
           ))
         )}
       </section>

       <section className="panel">
         <div className="panel-head">
           <div>
             <span className="eyebrow">RISK & CASE FUSION ALERTS</span>
             <h2>Active alerts & recommendations</h2>
           </div>
         </div>
         {!alerts.length ? (
           <div className="empty-state">No active alerts. Alerts generate automatically on risk delta or case fusion match.</div>
         ) : (
           alerts.map(a => (
             <div className="alert-row" key={a.alert_id}>
               <span className="status-pill warn">{a.severity}</span>
               <div>
                 <strong>{a.title}</strong>
                 <p>{a.explanation}</p>
                 <small>Δ {a.risk_delta.toFixed(1)} · {a.status}</small>
               </div>
             </div>
           ))
         )}
       </section>
     </div>
   </>
 );
}
