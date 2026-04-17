-- Create the professional leads table
CREATE TABLE IF NOT EXISTS uae_leads (
    id SERIAL PRIMARY KEY,
    company TEXT UNIQUE NOT NULL,
    industry TEXT,
    confidence_score INTEGER,
    patron_chairman TEXT,
    ceo_founder TEXT,
    financials TEXT,
    strategic_signal TEXT,
    integration_opportunity TEXT,
    registry_status TEXT,
    url TEXT,
    status TEXT DEFAULT 'Pending',
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster dashboard loading
CREATE INDEX IF NOT EXISTS idx_discovered_at ON uae_leads (discovered_at DESC);

-- PHASE 2: Sales Agent Enrichment Columns
ALTER TABLE uae_leads ADD COLUMN IF NOT EXISTS contact_name TEXT;
ALTER TABLE uae_leads ADD COLUMN IF NOT EXISTS contact_email TEXT;
ALTER TABLE uae_leads ADD COLUMN IF NOT EXISTS contact_role TEXT;
ALTER TABLE uae_leads ADD COLUMN IF NOT EXISTS contact_linkedin TEXT;

-- PHASE 3: Exact Funding Extractions (Crunchbase/Magnitt)
ALTER TABLE uae_leads ADD COLUMN IF NOT EXISTS funding_amount TEXT;
ALTER TABLE uae_leads ADD COLUMN IF NOT EXISTS funding_round TEXT;

