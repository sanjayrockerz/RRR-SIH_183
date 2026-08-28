# Alert operations

RRR distinguishes generated investigative alerts from investigator workflow actions. A generated alert retains its case, subject, severity, risk delta, pattern references, and evidence references. Review actions are stored separately in `alert_reviews` and never overwrite the original evidence.

Supported actions:

- `ACKNOWLEDGE`: investigator has seen the alert.
- `ESCALATE`: investigator requests priority handling.
- `DISMISS`: investigator closes the alert for the current review workflow.

Every review records the prior and resulting status, optional note, optional actor identifier, and timestamp. The application also appends an audit event and case timeline event. Actor identity remains optional until authentication/RBAC is implemented; clients must not treat the absence of an actor ID as a real user identity.

Alert review is not a criminality determination. Generated titles and explanations use investigative language and retain evidence references for navigation.
