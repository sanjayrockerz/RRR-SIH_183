ALTER TABLE cross_chain_links ADD COLUMN IF NOT EXISTS asset TEXT;
ALTER TABLE cross_chain_links ADD COLUMN IF NOT EXISTS amount TEXT;
ALTER TABLE cross_chain_links ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ;
ALTER TABLE cross_chain_links ADD COLUMN IF NOT EXISTS bridge_protocol TEXT;
