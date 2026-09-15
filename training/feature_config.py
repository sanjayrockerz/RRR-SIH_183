FEATURE_SCHEMA_VERSION = "RRRFeatureSchemaV1"
FEATURE_COLUMNS = [
    "incoming_tx_count", "outgoing_tx_count", "unique_senders", "unique_receivers",
    "total_in", "total_out", "mean_in", "mean_out", "out_in_ratio",
    "activity_duration", "burstiness", "in_degree", "out_degree", "total_degree",
    "fan_in_score", "fan_out_score", "repeated_counterparty_ratio",
]
TARGET = "label"
META_COLUMNS = ["observation_id", "address", "time_step", "label", "feature_schema_version"]
