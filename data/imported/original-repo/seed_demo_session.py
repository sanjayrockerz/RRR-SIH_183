#!/usr/bin/env python3
"""
Seed the demo session SESS_9921_CRITICAL with realistic degraded trust data
to support the UI narrative in Operations Center and Investigation Workbench.

This script creates a session passport with degraded component values that trigger
a BLOCK verdict, matching the "CRITICAL IN REVIEW" and "Verdict: BLOCK" narrative
already present in other parts of the demo UI.
"""

import sys
import os
import uuid
from datetime import datetime, timezone

# Add api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from session_intelligence.models import (
    SessionContext,
    SessionLifecycle,
    TrustPassport,
    TrustComponent,
    ComponentName,
    TrustTrend,
    TrustSnapshot,
)
from session_intelligence.repository import SessionTrustRepository
from session_intelligence.policy import LIFECYCLE_THRESHOLDS


def seed_demo_session():
    """
    Seed SESS_9921_CRITICAL with a realistic degraded trust passport.

    This session represents a user with widespread degradation across nearly
    every trust component, not just one or two isolated signals:
    - Suspicious device behavior (device_trust: 18)
    - Active threat indicators (threat_trust: 12)
    - Poor graph reputation (graph_trust: 14)
    - Overall trust score: ~23.6 (genuinely below api/session_intelligence/
      policy.py's blocked_below: 30.0 threshold, so the platform's own
      classification logic -- not just this script's hand-set lifecycle
      field -- agrees this session should be BLOCKED rather than SUSPICIOUS)

    NOTE: an earlier version of this script set component values that summed
    to overall_trust=42.9 while still forcing current_status=BLOCKED. That
    was inconsistent with policy.py's own blocked_below=30.0 rule (42.9 would
    actually classify as SUSPICIOUS/CHALLENGE), so the BLOCK verdict shown on
    /operations and /investigation didn't match the platform's real logic.
    The values below were lowered specifically so the computed overall_trust
    is honestly below 30, preserving the intended BLOCK demo narrative
    without contradicting the policy the platform actually runs.
    """

    repo = SessionTrustRepository()
    demo_session_id = "SESS_9921_CRITICAL"
    demo_user_id = "usr_9921"

    now = datetime.now(timezone.utc)

    # Create session context (background session info)
    context = SessionContext(
        session_id=demo_session_id,
        user_id=demo_user_id,
        device_id="dev_9921_suspicious",
        location="185.15.2.22",  # Known risky IP
        created_at=now,
        last_activity=now,
        lifecycle=SessionLifecycle.BLOCKED,  # This session is blocked
        threat_count=3,
        event_count=7,
    )

    # Create trust components with degraded values
    components = {
        ComponentName.IDENTITY: TrustComponent(
            name=ComponentName.IDENTITY,
            value=40.0,  # Severe identity risk
            confidence=0.85,
            previous_value=80.0,
            difference=-40.0,
            trend=TrustTrend.DECLINING,
            reasons=["Account age moderate", "Recent credential reset", "Prior fraud history flagged"],
            updated_at=now,
        ),
        ComponentName.DEVICE: TrustComponent(
            name=ComponentName.DEVICE,
            value=18.0,  # Critical device risk
            confidence=0.9,
            previous_value=85.0,
            difference=-67.0,
            trend=TrustTrend.DECLINING,
            reasons=["Unrecognized device", "Device emulation detected", "Root access indicators"],
            updated_at=now,
        ),
        ComponentName.RUNTIME: TrustComponent(
            name=ComponentName.RUNTIME,
            value=15.0,  # Critical runtime compromise
            confidence=0.88,
            previous_value=90.0,
            difference=-75.0,
            trend=TrustTrend.DECLINING,
            reasons=["Screen recording active", "Frida instrumentation detected", "Debugger attached"],
            updated_at=now,
        ),
        ComponentName.BEHAVIOUR: TrustComponent(
            name=ComponentName.BEHAVIOUR,
            value=35.0,  # Severe behavioral anomalies
            confidence=0.82,
            previous_value=75.0,
            difference=-40.0,
            trend=TrustTrend.DECLINING,
            reasons=["Unusual transaction amount", "Atypical transfer pattern", "Beneficiary mismatch"],
            updated_at=now,
        ),
        ComponentName.NETWORK: TrustComponent(
            name=ComponentName.NETWORK,
            value=22.0,  # Critical network risk
            confidence=0.85,
            previous_value=80.0,
            difference=-58.0,
            trend=TrustTrend.DECLINING,
            reasons=["VPN tunnel active", "Impossible travel detected", "Public WiFi usage"],
            updated_at=now,
        ),
        ComponentName.GEO: TrustComponent(
            name=ComponentName.GEO,
            value=30.0,  # Severe geographic anomaly
            confidence=0.80,
            previous_value=85.0,
            difference=-55.0,
            trend=TrustTrend.DECLINING,
            reasons=["GPS spoofing suspected", "Geofence violation", "Inconsistent location history"],
            updated_at=now,
        ),
        ComponentName.THREAT: TrustComponent(
            name=ComponentName.THREAT,
            value=12.0,  # Critical threat indicators
            confidence=0.95,
            previous_value=85.0,
            difference=-73.0,
            trend=TrustTrend.DECLINING,
            reasons=[
                "Banking trojan signatures detected",
                "C2 communication patterns observed",
                "Known mule account cluster detected",
            ],
            updated_at=now,
        ),
        ComponentName.GRAPH: TrustComponent(
            name=ComponentName.GRAPH,
            value=14.0,  # Critical graph risk
            confidence=0.93,
            previous_value=85.0,
            difference=-71.0,
            trend=TrustTrend.DECLINING,
            reasons=[
                "Connected to mule ring (distance: 1)",
                "High-risk money mule cluster",
                "Account dormancy abuse pattern",
            ],
            updated_at=now,
        ),
        ComponentName.TRANSACTION: TrustComponent(
            name=ComponentName.TRANSACTION,
            value=28.0,  # Severe transaction risk
            confidence=0.87,
            previous_value=82.0,
            difference=-54.0,
            trend=TrustTrend.DECLINING,
            reasons=["High transaction amount", "First-time beneficiary", "Weekend anomaly"],
            updated_at=now,
        ),
    }

    # Calculate weighted overall_trust matching the policy weights
    weights = {
        ComponentName.IDENTITY: 0.14,
        ComponentName.DEVICE: 0.13,
        ComponentName.RUNTIME: 0.13,
        ComponentName.BEHAVIOUR: 0.10,
        ComponentName.NETWORK: 0.10,
        ComponentName.GEO: 0.08,
        ComponentName.THREAT: 0.14,
        ComponentName.GRAPH: 0.08,
        ComponentName.TRANSACTION: 0.10,
    }

    overall_trust = sum(
        components[comp_name].value * weight
        for comp_name, weight in weights.items()
        if comp_name in components
    )
    overall_trust = round(overall_trust, 1)

    # This session is seeded with current_status=BLOCKED below. Guard that the
    # numbers we hand-picked actually agree with the platform's own policy
    # (api/session_intelligence/policy.py), rather than just asserting BLOCKED
    # in the lifecycle field regardless of what the component values compute
    # to -- that mismatch is exactly what caused this script to previously
    # seed a 42.9% "BLOCKED" session when the policy's own blocked_below=30.0
    # rule would have classified it as SUSPICIOUS.
    blocked_below = LIFECYCLE_THRESHOLDS["blocked_below"]
    assert overall_trust < blocked_below, (
        f"Seeded overall_trust={overall_trust} is not below policy.py's "
        f"blocked_below={blocked_below} -- current_status=BLOCKED below would "
        "contradict the platform's own real classification logic. Lower the "
        "component values above until this holds."
    )

    print(f"Calculated overall_trust: {overall_trust} (blocked_below={blocked_below})")

    # Create trust passport
    passport = TrustPassport(
        passport_id=f"{demo_session_id}_20260726",
        session_id=demo_session_id,
        user_id=demo_user_id,
        identity_trust=components[ComponentName.IDENTITY].value,
        device_trust=components[ComponentName.DEVICE].value,
        runtime_trust=components[ComponentName.RUNTIME].value,
        behaviour_trust=components[ComponentName.BEHAVIOUR].value,
        network_trust=components[ComponentName.NETWORK].value,
        geo_trust=components[ComponentName.GEO].value,
        threat_trust=components[ComponentName.THREAT].value,
        graph_trust=components[ComponentName.GRAPH].value,
        transaction_trust=components[ComponentName.TRANSACTION].value,
        overall_trust=overall_trust,
        confidence=0.88,
        current_status=SessionLifecycle.BLOCKED,
        created_time=now,
        updated_time=now,
        version="trust-v1.0.0",
        trust_trend=TrustTrend.DECLINING,
        components=components,
    )

    # Create a trust snapshot for history (use unique ID to allow re-seeding)
    snapshot = TrustSnapshot(
        snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
        session_id=demo_session_id,
        timestamp=now,
        event_type="DEMO_INITIALIZATION",
        previous_trust=100.0,
        current_trust=overall_trust,
        delta=overall_trust - 100.0,
        reason="Demo session initialized with realistic degraded trust profile for UI narrative",
        passport=passport,
    )

    # Save the session state
    repo.save_state(context, passport, snapshot, [])

    print(f"[SUCCESS] Seeded demo session: {demo_session_id}")
    print(f"  Overall Trust: {overall_trust}% (BLOCKED)")
    print(f"  Status: {passport.current_status}")
    print(f"  Key Risks:")
    print(f"    - Threat Intelligence: {components[ComponentName.THREAT].value}% (CRITICAL)")
    print(f"    - Graph Analysis: {components[ComponentName.GRAPH].value}% (CRITICAL)")
    print(f"    - Device Analysis: {components[ComponentName.DEVICE].value}% (HIGH)")


if __name__ == "__main__":
    seed_demo_session()
