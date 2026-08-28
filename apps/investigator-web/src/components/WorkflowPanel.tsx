import {useEffect,useState} from 'react';
import type {WorkflowEvent} from '../types';
import {caseWorkflow} from '../api';

export function WorkflowPanel({caseId}:{caseId:string}){
  const [items,setItems]=useState<WorkflowEvent[]>([]); const [error,setError]=useState('');
  useEffect(()=>{caseWorkflow(caseId).then(setItems).catch(e=>setError(e instanceof Error?e.message:'Workflow unavailable'))},[caseId]);
  return <section className="surface"><div className="panel-title"><div className="eyebrow">CASE PIPELINE</div><h3>{items.length?items[0].stage:'Workflow not loaded'}</h3></div>{error&&<div className="error" role="alert">{error}</div>}{items.length?<div className="timeline-row">{items.map(item=><div key={item.event_id}><strong>{item.stage.replaceAll('_',' ')}</strong><p>{item.provider||'Internal workflow'} · {item.result_count??0} result(s)</p><small>{new Date(item.completed_at||item.started_at).toLocaleString()}{item.error?` · ${item.error}`:''}</small></div>)}</div>:<div className="empty-block"><b>No persisted workflow events</b><p>Workflow stages appear after PostgreSQL connectivity is available.</p></div>}</section>
}
