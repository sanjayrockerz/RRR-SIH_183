import {useEffect,useState} from 'react';
import {listEvidence} from '../api';
import type {Case,EvidenceRecord} from '../types';

const labels:Record<string,string>={TRANSACTION:'Blockchain transaction',REALTIME_BLOCKCHAIN_OBSERVATION:'Realtime blockchain observation',REALTIME_TRANSACTION:'Realtime transaction',TRACE_OBSERVATION:'Trace observation'};
const short=(value?:string)=>value?`${value.slice(0,10)}…${value.slice(-8)}`:'—';
const pretty=(value:string)=>value.replaceAll('_',' ').toLowerCase().replace(/(^| )\S/g,c=>c.toUpperCase());

export function ReadableEvidencePage({caseData}:{caseData:Case|null}){
 const [items,setItems]=useState<EvidenceRecord[]>([]); const [error,setError]=useState(''); const [loading,setLoading]=useState(true);
 const load=()=>{setLoading(true);setError(''); if(!caseData){setItems([]);setLoading(false);return} listEvidence(caseData.case_id).then(setItems).catch((e)=>setError(e instanceof Error?e.message:'Evidence service unavailable')).finally(()=>setLoading(false));};
 useEffect(load,[caseData?.case_id]);
 return <section className="readable-evidence"><div className="page-header"><div><div className="eyebrow">FORENSIC LEDGER / {caseData?short(caseData.case_id):'NO CASE SELECTED'}</div><h1>Evidence</h1><p className="muted">Every record keeps its provider, observation time, transaction reference and integrity state.</p></div><div className="evidence-summary"><span>{items.length}</span><small>persisted records</small></div></div>
  {!caseData&&<div className="empty-state"><strong>Select an investigation first</strong><span>Open a case to inspect its evidence chain.</span></div>}
  {loading&&<div className="empty-state">Loading persisted evidence…</div>}
  {error&&<div className="error-state"><strong>Evidence could not be loaded</strong><span>{error}</span><button onClick={load}>RETRY</button></div>}
  {!loading&&!error&&caseData&&!items.length&&<div className="empty-state"><strong>No evidence captured yet</strong><span>Run a trace or process a realtime event to create provenance records.</span></div>}
  <div className="evidence-grid">{items.map(item=><article className="evidence-card" key={item.evidence_id}><div className="evidence-card-top"><span className="data-badge">{labels[item.type]||pretty(item.type)}</span><span className={`integrity ${item.integrity_status==='VALID'?'valid':''}`}>{item.integrity_status||'RECORDED'}</span></div><h3 title={item.evidence_id}>{short(item.evidence_id)}</h3><div className="evidence-meta"><span><b>Source</b>{item.source}</span><span><b>Captured</b>{new Date(item.captured_at).toLocaleString()}</span><span><b>Chain</b>{item.chain}</span>{item.tx_hash&&<span><b>Transaction</b><code title={item.tx_hash}>{short(item.tx_hash)}</code></span>}</div><div className="evidence-facts">{Object.entries(item.metadata||{}).filter(([k])=>['from','to','amount','asset','block_number','provider','method','event_id'].includes(k)).map(([key,value])=><span key={key}><b>{pretty(key)}</b>{String(value)}</span>)}</div><button className="copy-evidence" onClick={()=>navigator.clipboard?.writeText(item.evidence_id)}>COPY RECORD ID</button></article>)}</div>
 </section>;
}
