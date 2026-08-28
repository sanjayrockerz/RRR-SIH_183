import {useEffect,useState} from 'react';
import {Shell} from './components/Shell';
import {GraphInspector,GraphUnavailable} from './components/GraphInspector';
import {PatternsPage} from './components/PatternsPage';
import {RiskPage} from './components/RiskPage';
import {RealtimePage} from './components/RealtimePage';
import {CrossChainPage} from './components/CrossChainPage';
import {EvidenceLedgerPanel} from './components/EvidenceLedgerPanel';
import {ReportsPage} from './components/ReportsPage';
import {RelatedCasesPanel} from './components/RelatedCasesPanel';
import {ConnectedIntake} from './components/ConnectedIntake';
import {WorkflowPanel} from './components/WorkflowPanel';
import {ReadableEvidencePage} from './components/ReadableEvidencePage';
import {SyntheticGenerator} from './components/SyntheticGenerator';
import {SyntheticRealtimeControl} from './components/SyntheticRealtimeControl';
import {LiveIntelligence} from './components/LiveIntelligence';
import {RunInvestigationDemo} from './components/RunInvestigationDemo';
import {api,systemStatus} from './api';
import type {Case,Trace} from './types';
import {Dashboard,LiveDashboard,GenericPage,Intake,Workspace,CasesPage,WalletsPage,EntitiesPage,EvidencePage,AlertsPage,ProviderOperationsPage} from './pages';

export default function App(){
 useEffect(()=>{const onClick=(event:Event)=>{const target=event.target as HTMLElement;const tab=target.closest('.case-tabs span');if(tab){const route=tab.textContent?.toLowerCase();if(route&&route!=='overview'){location.hash=route;return}}const integration=target.closest('.integration-link');if(integration&&integration.textContent?.includes('VASP')){location.hash='entities';return}const metric=target.closest('.metric-card');const label=metric?.querySelector('span')?.textContent||'';const metricRoutes:{[key:string]:string}={"ACTIVE CASES":'cases',"WALLETS UNDER REVIEW":'wallets',"HIGH-PRIORITY ALERTS":'alerts',"ATTRIBUTED ENTITIES":'entities',"OBSERVED TRANSACTIONS":'transactions',"ACTIVE WATCHES":'monitoring'};if(metric&&metricRoutes[label])location.hash=metricRoutes[label]};document.addEventListener('click',onClick);return()=>document.removeEventListener('click',onClick)},[]);
 const [route,setRoute]=useState(location.hash.slice(1)||'dashboard');
 const [caseData,setCaseData]=useState<Case|null>(null);
 const [trace,setTrace]=useState<Trace|null>(null);
 const [apiState,setApiState]=useState('UNKNOWN');
 useEffect(()=>{const onHash=()=>setRoute(location.hash.slice(1)||'dashboard');addEventListener('hashchange',onHash);systemStatus().then(result=>setApiState(result.system==='CONNECTED'?'ONLINE':result.system)).catch(()=>setApiState('UNAVAILABLE'));return()=>removeEventListener('hashchange',onHash)},[]);
 function navigate(next:string){location.hash=next;setRoute(next)}
 function completed(caseResult:Case,traceResult:Trace){setCaseData(caseResult);setTrace(traceResult);navigate('case')}
 async function openCase(caseId:string){try{const loaded=await api.getCase(caseId);setCaseData(loaded);setTrace(loaded.latest_trace||null);navigate('case')}catch{setCaseData(null);setTrace(null);navigate('cases')}}
 let page;
 if(route==='dashboard') page=<><LiveDashboard onNavigate={navigate}/><RunInvestigationDemo onOpen={()=>navigate('realtime')}/><SyntheticGenerator onOpen={openCase}/></>;
 else if(route==='dev/realtime') page=<><SyntheticRealtimeControl/><LiveIntelligence/></>;
 else if(route==='investigate'||route==='intake') page=<ConnectedIntake onComplete={completed}/>;
 else if(route==='case'&&caseData&&trace) page=<><Workspace caseData={caseData} trace={trace} onNavigate={navigate}/><WorkflowPanel caseId={caseData.case_id}/><RelatedCasesPanel caseId={caseData.case_id}/></>;
 else if(route==='case'&&caseData) page=<CaseTraceUnavailable caseData={caseData} onNavigate={navigate}/>;
 else if((route==='graph'||route==='transactions')&&trace) page=<><PageTitle eyebrow={route==='transactions'?'CASEWORK / TRANSACTIONS':'INVESTIGATION / GRAPH'} title={route==='transactions'?'Observed transactions':'Transaction graph'}/><GraphInspector trace={trace}/></>;
 else if(route==='graph') page=<GraphUnavailable onNavigate={navigate}/>;
 else if(route==='patterns'&&caseData&&trace) page=<PatternsPage caseData={caseData} trace={trace} onNavigate={navigate}/>;
 else if(route==='risk'&&caseData&&trace) page=<RiskPage caseData={caseData} trace={trace} onNavigate={navigate}/>;
 else if(route==='realtime') page=<><SyntheticRealtimeControl/><LiveIntelligence/></>;
 else if(route==='monitoring'&&caseData&&trace) page=<RealtimePage caseData={caseData} trace={trace}/>;
 else if((route==='cross-chain'||route==='chains')&&caseData&&trace) page=<CrossChainPage caseData={caseData} trace={trace}/>;
 else if(route==='cases') page=<CasesPage onNavigate={navigate} onOpenCase={openCase}/>;
 else if(route==='wallets') page=<WalletsPage/>;
 else if(route==='entities') page=<EntitiesPage/>;
 else if(route==='evidence') page=<><ReadableEvidencePage caseData={caseData}/>{caseData&&<EvidenceLedgerPanel caseId={caseData.case_id}/>}</>;
 else if(route==='alerts') page=<AlertsPage/>;
 else if(route==='reports') page=<ReportsPage caseData={caseData} trace={trace||undefined}/>;
 else if(route==='operations') page=<ProviderOperationsPage/>;
 else page=<LiveDashboard onNavigate={navigate}/>;
 return <Shell route={route} onNavigate={navigate} apiState={apiState}><div className="api-notice"><span className={apiState==='ONLINE'?'ok-dot':'warn-dot'}/> API {apiState} · Historical blockchain data only</div>{page}</Shell>
}
function PageTitle({eyebrow,title}:{eyebrow:string;title:string}){return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1></div></div>}
function CaseTraceUnavailable({caseData,onNavigate}:{caseData:Case;onNavigate:(route:string)=>void}){return <section className="case-unavailable"><div className="eyebrow">CASE / {caseData.case_id}</div><h1>{caseData.title}</h1><div className="surface"><span className="data-badge warning">NO PERSISTED TRACE</span><h2>Case context loaded</h2><p>This case was reopened from PostgreSQL, but no completed trace is available yet. Start a bounded historical trace from the investigation intake before opening the graph workspace.</p><button className="primary" onClick={()=>onNavigate('investigate')}>START TRACE</button></div></section>}
