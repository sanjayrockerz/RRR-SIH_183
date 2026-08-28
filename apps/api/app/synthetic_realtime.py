from __future__ import annotations
import asyncio
from datetime import datetime,timezone
from uuid import NAMESPACE_URL,uuid5
from .domain import Chain,RealtimeEvent,WatchCreate

class SyntheticBlockchainEventEngine:
    """Deterministic development source; downstream work is RealtimeService."""
    ROOT='0x1111111111111111111111111111111111111111'; A='0x2222222222222222222222222222222222222222'; B='0x3333333333333333333333333333333333333333'; C='0x4444444444444444444444444444444444444444'; VASP='0x9999999999999999999999999999999999999999'
    def __init__(self,realtime_service,repository): self.realtime_service=realtime_service;self.repository=repository;self.running=False;self.paused=False;self.case_id=None;self.scenario='ESCALATION';self.seed='rrr-phase-9a';self.interval_seconds=2.;self.maximum_events=100;self.event_number=0;self.last_event=None;self.last_results=[];self.started_at=None;self._task=None
    def status(self): return {'mode':'DEVELOPMENT_SYNTHETIC','running':self.running,'paused':self.paused,'case_id':self.case_id,'scenario':self.scenario,'seed':self.seed,'interval_seconds':self.interval_seconds,'maximum_events':self.maximum_events,'event_count':self.event_number,'last_event':self.last_event.model_dump(mode='json') if self.last_event else None,'last_results':self.last_results,'started_at':self.started_at}
    async def configure(self,case_id,scenario='ESCALATION',seed='rrr-phase-9a',interval_seconds=2.,maximum_events=100):
        if interval_seconds<.25 or interval_seconds>3600: raise ValueError('interval_seconds must be between 0.25 and 3600')
        if maximum_events<1 or maximum_events>10000: raise ValueError('maximum_events must be between 1 and 10000')
        if not await self.repository.get(case_id): raise ValueError('Case not found')
        self.case_id=case_id;self.scenario=scenario.upper();self.seed=seed;self.interval_seconds=interval_seconds;self.maximum_events=maximum_events;self.event_number=0;self.last_event=None;self.last_results=[]
    def _pair(self,i):
        if self.scenario=='FAN_OUT': return self.ROOT,[self.A,self.B,self.C,self.VASP][i%4],'ETH','NATIVE'
        if self.scenario=='FAN_IN': return [self.A,self.B,self.C,self.VASP][i%4],self.ROOT,'ETH','NATIVE'
        if self.scenario=='VASP_EXPOSURE': return self.B,self.VASP,'USDC','TOKEN'
        if self.scenario in ('MIXER_EXPOSURE','BRIDGE_MOVEMENT'): return self.B,self.C,'ETH','CONTRACT'
        if self.scenario=='NORMAL_ACTIVITY': return self.ROOT,self.A,'ETH','NATIVE'
        if self.scenario in ('MULTI_STAGE_FRAUD','ESCALATION'):
            # A repeatable, expanding topology: collection -> fan-out -> consolidation -> service boundary.
            cohort=i//10; phase=i%10
            def generated(label):
                return '0x'+(uuid5(NAMESPACE_URL,f'{self.seed}:{label}:{cohort}').hex+uuid5(NAMESPACE_URL,f'{self.seed}:{label}:{cohort}:tail').hex)[:40]
            collection,branch_a,branch_b,consolidation,bridge=map(generated,('collection','branch-a','branch-b','consolidation','bridge'))
            stages=[(self.ROOT,collection,'ETH','NATIVE'),(collection,branch_a,'ETH','NATIVE'),(collection,branch_b,'ETH','NATIVE'),(branch_a,consolidation,'ETH','NATIVE'),(branch_b,consolidation,'ETH','NATIVE'),(consolidation,bridge,'ETH','CONTRACT'),(bridge,self.C,'ETH','NATIVE'),(self.C,self.VASP,'USDC','TOKEN'),(self.ROOT,self.A,'ETH','NATIVE'),(self.A,collection,'ETH','NATIVE')]
            return stages[phase]
        return [(self.ROOT,self.A),(self.A,self.B),(self.B,self.C),(self.C,self.VASP)][i%4]+('ETH','NATIVE')
    def _event(self):
        self.event_number+=1;i=self.event_number-1;source,destination,asset,kind=self._pair(i);key=f'{self.seed}:{self.scenario}:{self.event_number}';now=datetime.now(timezone.utc)
        return RealtimeEvent(event_id=uuid5(NAMESPACE_URL,'event:'+key).__str__(),provider='DEVELOPMENT SYNTHETIC',provider_event_id=key,chain=Chain.ETHEREUM,received_at=now,observed_at=now,block_number=22000000+self.event_number,block_hash='0x'+uuid5(NAMESPACE_URL,'block:'+key).hex*2,transaction_hash='0x'+uuid5(NAMESPACE_URL,'tx:'+key).hex*2,from_address=source,to_address=destination,asset=asset,amount=f'{.75+(i%5)*.41:.4f}',contract_address=self.VASP if kind=='CONTRACT' else None,raw_provider_reference={'source_mode':'DEVELOPMENT_SYNTHETIC','scenario_id':self.scenario,'scenario_seed':self.seed})
    async def step(self):
        if not self.case_id: raise ValueError('Configure a case before generating events')
        if self.event_number>=self.maximum_events: raise ValueError('Maximum synthetic event limit reached')
        event=self._event()
        try: await self.realtime_service.create_watch(self.case_id,WatchCreate(address=event.from_address,chain=event.chain,source='DEVELOPMENT_SYNTHETIC'))
        except Exception: pass
        results=await self.realtime_service.receive_simulated(event);self.last_event=event;self.last_results=[x.model_dump(mode='json') for x in results];return {'mode':'DEVELOPMENT_SYNTHETIC','event':event.model_dump(mode='json'),'results':self.last_results,'status':self.status()}
    async def run_batch(self,event_count):
        """Generate an exact count through the canonical realtime ingestion pipeline."""
        if event_count < 1 or event_count > 1000: raise ValueError('event_count must be between 1 and 1000')
        if not self.case_id: raise ValueError('Configure a case before generating events')
        self.maximum_events=event_count
        processed=[]
        while self.event_number < event_count:
            processed.append(await self.step())
        return {'mode':'DEVELOPMENT_SYNTHETIC','case_id':self.case_id,'requested_events':event_count,'processed_events':len(processed),'first_event_id':processed[0]['event']['event_id'],'last_event_id':processed[-1]['event']['event_id'],'status':self.status()}
    async def _run(self):
        while self.running:
            if not self.paused:
                try: await self.step()
                except ValueError: self.running=False;break
            await asyncio.sleep(self.interval_seconds)
    async def start(self):
        if not self.case_id: raise ValueError('Configure a case before starting')
        self.running=True;self.paused=False;self.started_at=datetime.now(timezone.utc)
        if not self._task or self._task.done(): self._task=asyncio.create_task(self._run())
        return self.status()
    async def pause(self): self.paused=True;return self.status()
    async def resume(self):
        if not self.case_id: raise ValueError('Configure a case before resuming')
        self.running=True;self.paused=False
        if not self._task or self._task.done(): self._task=asyncio.create_task(self._run())
        return self.status()
    async def stop(self): self.running=False;self.paused=False;return self.status()
    async def events(self,limit=50): return [] if not self.case_id else await self.repository.list_realtime_events(self.case_id,limit)
