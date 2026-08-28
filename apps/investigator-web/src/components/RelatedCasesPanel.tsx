import {useEffect,useState} from 'react';
import type {CaseLink} from '../types';
import {relatedCases} from '../api';

export function RelatedCasesPanel({caseId}:{caseId:string}){
  const [items,setItems]=useState<CaseLink[]>([]); const [error,setError]=useState('');
  useEffect(()=>{relatedCases(caseId).then(setItems).catch(e=>setError(e instanceof Error?e.message:'Related case intelligence unavailable'))},[caseId]);
  return <section className="surface"><div className="panel-title"><div className="eyebrow">CROSS-CASE INTELLIGENCE</div><h3>{items.length?items.length+' related cases':'No exact overlaps found'}</h3></div>{error&&<div className="error" role="alert">{error}</div>}{items.length?<div className="case-table">{items.map(item=><article className="case-row" key={item.link_id}><strong>{item.related_case_id}</strong><span>{item.relationship_type}</span><span>{item.shared_wallets.length} wallets · {item.shared_transactions.length} transactions</span><small>{item.explanation}</small></article>)}</div>:<div className="empty-block"><b>No persisted exact relationship</b><p>Only shared persisted wallet or transaction identities are shown. Similar labels and timing do not create a case link.</p></div>}</section>
}
