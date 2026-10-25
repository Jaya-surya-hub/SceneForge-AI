export interface HealthResponse {
  status: 'healthy' | 'degraded';
  app: string;
  version: string;
  environment: string;
  demo_mode: boolean;
  timestamp: string;
  database: {
    connected: boolean;
    dialect: string;
    latency_ms: number;
  };
  storage: {
    writable: boolean;
    path: string;
  };
  ledger: {
    total_records: number;
    verified: boolean;
  };
}

export type TabId =
  | 'command-center'
  | 'question-atlas'
  | 'evidence-ledger'
  | 'replay-lab'
  | 'visibility-intelligence'
  | 'fix-court'
  | 'content-foundry'
  | 'citation-gravity'
  | 'weekly-reports'
  | 'settings-honesty';

export interface QuestionItem {
  id: string;
  text: string;
  journey_stage: 'Make' | 'Repurpose' | 'Edit' | 'Caption' | 'Publish' | 'Grow';
  search_intent: 'informational' | 'comparison' | 'commercial';
  source_type: string;
  source_url: string;
  target_market: string;
  is_demo: boolean;
}

export interface LedgerItem {
  id: string;
  question_id: string;
  run_id: string;
  provider: string;
  collection_method: string;
  timestamp: string;
  market: string;
  artifact_path: string;
  sha256_hash: string;
  prev_ledger_hash: string;
  current_ledger_hash: string;
  execution_status: string;
  is_demo: boolean;
}
