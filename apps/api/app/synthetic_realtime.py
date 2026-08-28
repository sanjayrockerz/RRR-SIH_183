from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from .domain import Chain, RealtimeEvent, WatchCreate

# Distinct amounts per scenario so value factor fires meaningfully
_SCENARIO_AMOUNTS: dict[str, list[str]] = {
    # LOW: tiny amounts, no value factor
    "NORMAL_ACTIVITY":    ["0.0032", "0.0018", "0.0041", "0.0025"],
    # GUARDED: small ETH, no large value
    "VASP_EXPOSURE":      ["0.38", "0.52", "0.29", "0.61"],
    # ELEVATED: moderate ETH, fan-out/fan-in patterns
    "FAN_OUT":            ["1.20", "1.85", "0.95", "2.10", "1.55"],
    "FAN_IN":             ["0.80", "1.40", "1.10", "0.65", "1.90"],
    # HIGH: peel chain with residual value
    "PEEL_CHAIN":         ["8.00", "7.20", "6.48", "5.83", "5.25", "4.72"],
    # HIGH: mixer exposure — contract interactions
    "MIXER_EXPOSURE":     ["3.50", "3.50", "3.50", "3.50"],
    # HIGH: bridge movement — large USDC cross-chain
    "BRIDGE_MOVEMENT":    ["5000", "5000", "5000", "5000"],
    # CRITICAL: multi-stage fraud — large amounts + all signals
    "MULTI_STAGE_FRAUD":  ["25000", "12500", "12500", "18000", "7000", "7000", "25000", "25000", "800", "800"],
    # CRITICAL: escalation — grows from small to large over cohorts
    "ESCALATION":         ["500", "1000", "2500", "5000", "10000", "20000", "40000", "80000", "160000", "320000"],
}

_SCENARIO_ASSETS: dict[str, list[str]] = {
    "NORMAL_ACTIVITY":   ["ETH", "ETH", "ETH", "ETH"],
    "VASP_EXPOSURE":     ["ETH", "ETH", "USDC", "ETH"],
    "FAN_OUT":           ["ETH", "ETH", "ETH", "USDC", "ETH"],
    "FAN_IN":            ["ETH", "USDC", "ETH", "ETH", "USDC"],
    "PEEL_CHAIN":        ["ETH", "ETH", "ETH", "ETH", "ETH", "ETH"],
    "MIXER_EXPOSURE":    ["ETH", "ETH", "ETH", "ETH"],
    "BRIDGE_MOVEMENT":   ["USDC", "USDC", "USDC", "USDC"],
    "MULTI_STAGE_FRAUD": ["USDC", "USDC", "USDC", "USDC", "USDC", "USDC", "USDC", "USDC", "ETH", "ETH"],
    "ESCALATION":        ["USDC", "USDC", "USDC", "USDC", "USDC", "USDC", "USDC", "USDC", "USDC", "USDC"],
}


class SyntheticBlockchainEventEngine:
    """Deterministic development source — each scenario produces a distinct risk profile.

    Risk profile by scenario:
        NORMAL_ACTIVITY    →  LOW   (0–15)
        VASP_EXPOSURE      →  GUARDED  (20–35)
        FAN_OUT            →  ELEVATED (40–55)
        FAN_IN             →  ELEVATED (45–55)
        PEEL_CHAIN         →  HIGH  (60–72)
        MIXER_EXPOSURE     →  HIGH  (65–75)
        BRIDGE_MOVEMENT    →  HIGH  (62–72)
        MULTI_STAGE_FRAUD  →  CRITICAL (82–95)
        ESCALATION         →  CRITICAL (88+, progressive)
    """

    ROOT   = '0x1111111111111111111111111111111111111111'
    A      = '0x2222222222222222222222222222222222222222'
    B      = '0x3333333333333333333333333333333333333333'
    C      = '0x4444444444444444444444444444444444444444'
    VASP   = '0x9999999999999999999999999999999999999999'
    MIXER  = '0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'   # synthetic mixer
    BRIDGE = '0xbr1dgebr1dgebr1dgebr1dgebr1dge00000000'     # synthetic bridge

    def __init__(self, realtime_service, repository):
        self.realtime_service = realtime_service
        self.repository = repository
        self.running = False
        self.paused = False
        self.case_id = None
        self.scenario = 'ESCALATION'
        self.seed = 'rrr-phase-9a'
        self.interval_seconds = 2.0
        self.maximum_events = 100
        self.event_number = 0
        self.last_event = None
        self.last_results = []
        self.started_at = None
        self._task = None

    def status(self):
        return {
            'mode': 'DEVELOPMENT_SYNTHETIC',
            'running': self.running,
            'paused': self.paused,
            'case_id': self.case_id,
            'scenario': self.scenario,
            'seed': self.seed,
            'interval_seconds': self.interval_seconds,
            'maximum_events': self.maximum_events,
            'event_count': self.event_number,
            'last_event': self.last_event.model_dump(mode='json') if self.last_event else None,
            'last_results': self.last_results,
            'started_at': self.started_at,
            'expected_risk_band': self._expected_band(),
        }

    def _expected_band(self) -> str:
        mapping = {
            'NORMAL_ACTIVITY': 'LOW',
            'VASP_EXPOSURE': 'GUARDED',
            'FAN_OUT': 'ELEVATED',
            'FAN_IN': 'ELEVATED',
            'PEEL_CHAIN': 'HIGH',
            'MIXER_EXPOSURE': 'HIGH',
            'BRIDGE_MOVEMENT': 'HIGH',
            'MULTI_STAGE_FRAUD': 'CRITICAL',
            'ESCALATION': 'CRITICAL',
        }
        return mapping.get(self.scenario, 'UNKNOWN')

    async def configure(self, case_id, scenario='ESCALATION', seed='rrr-phase-9a', interval_seconds=2., maximum_events=100):
        if interval_seconds < .25 or interval_seconds > 3600:
            raise ValueError('interval_seconds must be between 0.25 and 3600')
        if maximum_events < 1 or maximum_events > 10000:
            raise ValueError('maximum_events must be between 1 and 10000')
        if not await self.repository.get(case_id):
            raise ValueError('Case not found')
        self.case_id = case_id
        self.scenario = scenario.upper()
        self.seed = seed
        self.interval_seconds = interval_seconds
        self.maximum_events = maximum_events
        self.event_number = 0
        self.last_event = None
        self.last_results = []

    def _pair(self, i: int) -> tuple[str, str, str, str]:
        """Return (source, destination, asset, kind) for event index i."""
        s = self.scenario

        if s == 'NORMAL_ACTIVITY':
            # Simple back-and-forth between root and A — no layering
            pairs = [(self.ROOT, self.A), (self.A, self.ROOT), (self.ROOT, self.A), (self.A, self.B)]
            src, dst = pairs[i % len(pairs)]
            return src, dst, 'ETH', 'NATIVE'

        if s == 'VASP_EXPOSURE':
            # Direct root → VASP, a few hops through A
            pairs = [(self.ROOT, self.A), (self.A, self.VASP), (self.ROOT, self.VASP), (self.A, self.B)]
            src, dst = pairs[i % len(pairs)]
            asset = 'USDC' if i % 2 == 0 else 'ETH'
            return src, dst, asset, 'NATIVE' if asset == 'ETH' else 'TOKEN'

        if s == 'FAN_OUT':
            # ROOT distributes to A, B, C, VASP
            dests = [self.A, self.B, self.C, self.VASP]
            return self.ROOT, dests[i % 4], 'ETH', 'NATIVE'

        if s == 'FAN_IN':
            # A, B, C, ROOT all feed into VASP
            sources = [self.A, self.B, self.C, self.ROOT]
            return sources[i % 4], self.VASP, 'USDC', 'TOKEN'

        if s == 'PEEL_CHAIN':
            # Linear: ROOT→A→B→C→VASP, each forwarding slightly less
            chain = [self.ROOT, self.A, self.B, self.C, self.VASP]
            idx = i % (len(chain) - 1)
            return chain[idx], chain[idx + 1], 'ETH', 'NATIVE'

        if s == 'MIXER_EXPOSURE':
            # ROOT → B → MIXER → C → VASP loop
            pairs = [(self.ROOT, self.B), (self.B, self.MIXER), (self.MIXER, self.C), (self.C, self.VASP)]
            src, dst = pairs[i % 4]
            return src, dst, 'ETH', 'CONTRACT' if dst == self.MIXER else 'NATIVE'

        if s == 'BRIDGE_MOVEMENT':
            # ROOT → A → BRIDGE → C → VASP
            pairs = [(self.ROOT, self.A), (self.A, self.BRIDGE), (self.BRIDGE, self.C), (self.C, self.VASP)]
            src, dst = pairs[i % 4]
            return src, dst, 'USDC', 'CONTRACT' if dst == self.BRIDGE else 'TOKEN'

        if s == 'MULTI_STAGE_FRAUD':
            # 10-step topology per cohort: collection→fan-out→consolidation→mixer→bridge→VASP
            cohort = i // 10
            phase = i % 10

            def gen(label: str) -> str:
                h = uuid5(NAMESPACE_URL, f'{self.seed}:{label}:{cohort}').hex
                h2 = uuid5(NAMESPACE_URL, f'{self.seed}:{label}:{cohort}:tail').hex
                return '0x' + (h + h2)[:40]

            collection = gen('collection')
            branch_a   = gen('branch-a')
            branch_b   = gen('branch-b')
            consol     = gen('consolidation')
            mixer_addr = gen('mixer')
            bridge_addr= gen('bridge')

            stages = [
                (self.ROOT, collection, 'USDC', 'TOKEN'),
                (collection, branch_a, 'USDC', 'TOKEN'),
                (collection, branch_b, 'USDC', 'TOKEN'),
                (branch_a, consol, 'USDC', 'TOKEN'),
                (branch_b, consol, 'USDC', 'TOKEN'),
                (consol, mixer_addr, 'ETH', 'CONTRACT'),
                (mixer_addr, bridge_addr, 'ETH', 'CONTRACT'),
                (bridge_addr, self.C, 'USDC', 'TOKEN'),
                (self.C, self.VASP, 'USDC', 'TOKEN'),
                (self.ROOT, self.A, 'ETH', 'NATIVE'),   # distraction
            ]
            return stages[phase]

        # ESCALATION — expanding topology across cohorts (same as before)
        cohort = i // 10
        phase = i % 10

        def generated(label: str) -> str:
            h = uuid5(NAMESPACE_URL, f'{self.seed}:{label}:{cohort}').hex
            h2 = uuid5(NAMESPACE_URL, f'{self.seed}:{label}:{cohort}:tail').hex
            return '0x' + (h + h2)[:40]

        collection = generated('collection')
        branch_a   = generated('branch-a')
        branch_b   = generated('branch-b')
        consol     = generated('consolidation')
        bridge_e   = generated('bridge')

        stages = [
            (self.ROOT, collection, 'USDC', 'TOKEN'),
            (collection, branch_a, 'USDC', 'TOKEN'),
            (collection, branch_b, 'USDC', 'TOKEN'),
            (branch_a, consol, 'USDC', 'TOKEN'),
            (branch_b, consol, 'USDC', 'TOKEN'),
            (consol, bridge_e, 'ETH', 'CONTRACT'),
            (bridge_e, self.C, 'ETH', 'NATIVE'),
            (self.C, self.VASP, 'USDC', 'TOKEN'),
            (self.ROOT, self.A, 'ETH', 'NATIVE'),
            (self.A, collection, 'USDC', 'TOKEN'),
        ]
        return stages[phase]

    def _amount(self, i: int) -> str:
        """Pick amount for this event index, scenario-aware."""
        amounts = _SCENARIO_AMOUNTS.get(self.scenario, ["0.50"])
        return amounts[i % len(amounts)]

    def _event(self) -> RealtimeEvent:
        self.event_number += 1
        idx = self.event_number - 1
        source, destination, asset, kind = self._pair(idx)
        amount = self._amount(idx)
        key = f'{self.seed}:{self.scenario}:{self.event_number}'
        now = datetime.now(timezone.utc)
        return RealtimeEvent(
            event_id=uuid5(NAMESPACE_URL, 'event:' + key).__str__(),
            provider='DEVELOPMENT SYNTHETIC',
            provider_event_id=key,
            chain=Chain.ETHEREUM,
            received_at=now,
            observed_at=now,
            block_number=22000000 + self.event_number,
            block_hash='0x' + uuid5(NAMESPACE_URL, 'block:' + key).hex * 2,
            transaction_hash='0x' + uuid5(NAMESPACE_URL, 'tx:' + key).hex * 2,
            from_address=source,
            to_address=destination,
            asset=asset,
            amount=amount,
            contract_address=destination if kind == 'CONTRACT' else None,
            raw_provider_reference={
                'source_mode': 'DEVELOPMENT_SYNTHETIC',
                'scenario_id': self.scenario,
                'scenario_seed': self.seed,
                'expected_risk_band': self._expected_band(),
            },
        )

    async def step(self):
        if not self.case_id:
            raise ValueError('Configure a case before generating events')
        if self.event_number >= self.maximum_events:
            raise ValueError('Maximum synthetic event limit reached')
        event = self._event()
        try:
            await self.realtime_service.create_watch(
                self.case_id,
                WatchCreate(address=event.from_address, chain=event.chain, source='DEVELOPMENT_SYNTHETIC'),
            )
        except Exception:
            pass
        results = await self.realtime_service.receive_simulated(event)
        self.last_event = event
        self.last_results = [x.model_dump(mode='json') for x in results]
        return {'mode': 'DEVELOPMENT_SYNTHETIC', 'event': event.model_dump(mode='json'), 'results': self.last_results, 'status': self.status()}

    async def run_batch(self, event_count: int):
        """Generate an exact count through the canonical realtime ingestion pipeline."""
        if event_count < 1 or event_count > 1000:
            raise ValueError('event_count must be between 1 and 1000')
        if not self.case_id:
            raise ValueError('Configure a case before generating events')
        self.maximum_events = event_count
        processed = []
        while self.event_number < event_count:
            processed.append(await self.step())
        return {
            'mode': 'DEVELOPMENT_SYNTHETIC',
            'case_id': self.case_id,
            'requested_events': event_count,
            'processed_events': len(processed),
            'first_event_id': processed[0]['event']['event_id'],
            'last_event_id': processed[-1]['event']['event_id'],
            'expected_risk_band': self._expected_band(),
            'status': self.status(),
        }

    async def _run(self):
        while self.running:
            if not self.paused:
                try:
                    await self.step()
                except ValueError:
                    self.running = False
                    break
            await asyncio.sleep(self.interval_seconds)

    async def start(self):
        if not self.case_id:
            raise ValueError('Configure a case before starting')
        self.running = True
        self.paused = False
        self.started_at = datetime.now(timezone.utc)
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run())
        return self.status()

    async def pause(self):
        self.paused = True
        return self.status()

    async def resume(self):
        if not self.case_id:
            raise ValueError('Configure a case before resuming')
        self.running = True
        self.paused = False
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run())
        return self.status()

    async def stop(self):
        self.running = False
        self.paused = False
        return self.status()

    async def events(self, limit: int = 50):
        return [] if not self.case_id else await self.repository.list_realtime_events(self.case_id, limit)
