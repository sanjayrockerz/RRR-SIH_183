import {useState} from 'react';
import {generateSyntheticInvestigation} from '../api';

type Result={case_id:string;counts:Record<string,number>;flags:{type:string;severity:string}[];synthetic?:{processed_events:number}};

export function SyntheticGenerator({onOpen}:{onOpen:(caseId:string)=>void}){
 const [busy,setBusy]=useState(false); const [result,setResult]=useState<Result|null>(null); const [error,setError]=useState(''); const [count,setCount]=useState(50);
 async function run(){setBusy(true);setError('');try{setResult(await generateSyntheticInvestigation(count))}catch(e){setError(e instanceof Error?e.message:'Synthetic workflow failed')}finally{setBusy(false)}}
 return <section className="synthetic-generator"><div><span className="eyebrow">ANALYST DEVELOPMENT TOOL · DEVELOPMENT SYNTHETIC</span><h2>Generate and flag a synthetic investigation</h2><p>Creates an exact number of synthetic blockchain events (for example 50 or 100). Each event uses the real normalized → persisted → graph → pattern → risk → evidence → timeline pipeline.</p><label className="synthetic-volume">Events to generate <input type="number" min="1" max="1000" value={count} onChange={event=>setCount(Math.max(1,Math.min(1000,Number(event.target.value)||1)))} /></label>{result&&<div className="synthetic-result">Generated case <code>{result.case_id.slice(0,8)}…</code> · risk {result.counts.risk_score||0} · persisted synthetic events <strong>{result.synthetic?.processed_events||count}</strong><div className="synthetic-flags">{result.flags.map((flag,index)=><span key={index}>{flag.type.replaceAll('_',' ')} · {flag.severity}</span>)}</div><button className="synthetic-open" onClick={()=>onOpen(result.case_id)}>OPEN GENERATED CASE →</button></div>}</div><button className="primary" onClick={run} disabled={busy}>{busy?'GENERATING…':`GENERATE ${count} EVENTS & FLAG`}</button>{error&&<div className="error" role="alert">{error}</div>}</section>
}
