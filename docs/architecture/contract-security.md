# Contract-security intelligence boundary

Migration `011_cyber_intelligence.sql` reserves `contract_security_findings` for source-backed contract analysis. Findings are separate from transaction behavior and wallet risk. A contract interaction does not imply that the contract is malicious.

The table requires chain, contract address, source, finding type, severity, confidence, description, observation time, and optional evidence identifiers. A future configured contract-security provider may populate it through an ingestion service; no live vendor or automated security conclusion is enabled in this slice.
