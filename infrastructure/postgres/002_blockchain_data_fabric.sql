-- Phase 2: preserve normalized asset-transfer rows and provider observations.
CREATE TABLE IF NOT EXISTS transaction_transfers (
  transfer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id UUID NOT NULL REFERENCES transactions(transaction_id) ON DELETE CASCADE,
  transfer_type TEXT NOT NULL DEFAULT 'native',
  asset TEXT NOT NULL,
  amount TEXT NOT NULL,
  source_address TEXT NOT NULL DEFAULT '',
  destination_address TEXT NOT NULL DEFAULT '',
  contract_address TEXT NOT NULL DEFAULT '',
  token_id TEXT NOT NULL DEFAULT '',
  decimals INTEGER,
  raw_reference JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(transaction_id,transfer_type,asset,amount,source_address,destination_address,contract_address,token_id)
);
CREATE INDEX IF NOT EXISTS idx_transaction_transfers_transaction_id ON transaction_transfers(transaction_id);
CREATE INDEX IF NOT EXISTS idx_transaction_transfers_contract ON transaction_transfers(contract_address);

-- Preserve provider retrieval metadata on canonical transactions.
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS provider_retrieved_at TIMESTAMPTZ;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS nonce BIGINT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS gas_limit NUMERIC;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS gas_price NUMERIC;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS gas_used NUMERIC;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS receipt_status TEXT;
CREATE INDEX IF NOT EXISTS idx_transactions_provider_retrieved_at ON transactions(provider_retrieved_at);
