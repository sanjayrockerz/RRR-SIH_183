# Entity and VASP attribution

Attribution is a separate intelligence layer over observed graph addresses. Entity records describe an organization or service and keep entity type separate from regulatory or legal status. AddressAttribution connects a normalized chain/address to an entity, role, confidence level, source, source reference, optional temporal validity, and optional evidence.

AttributionSource is first-class provenance. The resolver preserves all records, groups them by entity, exposes conflicts, and only selects an entity when exactly one candidate remains. Confidence levels are explainable source-backed categories, not calibrated probabilities or ML scores.

NearestEntityResolver evaluates every attributed graph node, uses actual path hop distance, and returns the supporting path, blockchain evidence, attribution observations, and source records. Ranking is hop distance first, then confidence, then source reliability; it is deterministic and not an intelligence score.

The phrase “observed flow reaches an address attributed to…” is intentional. Attribution does not independently prove ownership, receipt of victim funds, licensing, VASP status, or criminal activity. No verified production address dataset is currently bundled; seed/import boundaries are represented by the database schema and test fixtures are explicitly marked TEST FIXTURE.
