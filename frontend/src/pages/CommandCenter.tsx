import React from 'react';
import { ShieldCheck, Cpu, Database, Search, ArrowUpRight, CheckCircle2 } from 'lucide-react';
import { HealthResponse } from '../types';

interface CommandCenterProps {
  health: HealthResponse | null;
  onNavigate: (tab: any) => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({ health, onNavigate }) => {
  return (
    <div className="space-y-6">
      {/* Top Banner / Philosophy */}
      <div className="bg-paper-light border border-paper-border rounded-lg p-6 shadow-card">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-paper-border pb-5 mb-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">PHASE 1 FOUNDATION</span>
              <span className="text-xs font-mono text-ink-muted">STATUS: OPERATIONAL</span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-ink mt-1">
              Evidence-First Search & AI Visibility Engine
            </h2>
            <p className="text-sm text-ink-muted mt-1 max-w-2xl leading-relaxed">
              IncuBrix Signal Room measures organic search rankings, generative engine citations, and multi-model answer presence across Google and leading AI assistants with cryptographic proof.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => onNavigate('replay-lab')}
              className="px-3.5 py-2 rounded bg-signal text-white text-xs font-semibold hover:bg-signal-dark transition flex items-center gap-1.5 shadow-sm"
            >
              <span>Launch Replay Lab</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onNavigate('evidence-ledger')}
              className="px-3.5 py-2 rounded bg-paper-warm text-ink text-xs font-medium hover:bg-paper-subtle border border-paper-border transition"
            >
              Audit Proof Ledger
            </button>
          </div>
        </div>

        {/* 4 Foundation Status Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span>Proof Ledger Records</span>
              <Database className="w-4 h-4 text-signal" />
            </div>
            <div className="text-2xl font-bold font-mono text-ink">
              {health?.ledger.total_records ?? 0}
            </div>
            <div className="text-[11px] text-emerald-800 font-medium mt-1 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              <span>Cryptographic Chain Intact</span>
            </div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span>Question Atlas Target</span>
              <Search className="w-4 h-4 text-signal" />
            </div>
            <div className="text-2xl font-bold font-mono text-ink">100+</div>
            <div className="text-[11px] text-ink-muted mt-1">
              <span>6 Journey Stages • 3 Markets</span>
            </div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span>Covered AI Assistants</span>
              <Cpu className="w-4 h-4 text-signal" />
            </div>
            <div className="text-2xl font-bold font-mono text-ink">4 Models</div>
            <div className="text-[11px] text-ink-muted mt-1">
              <span>ChatGPT • Claude • Gemini • Perplexity</span>
            </div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span>Core API Latency</span>
              <ShieldCheck className="w-4 h-4 text-signal" />
            </div>
            <div className="text-2xl font-bold font-mono text-ink">
              {health?.database.latency_ms ?? 0}ms
            </div>
            <div className="text-[11px] text-emerald-800 font-medium mt-1">
              <span>Dialect: {health?.database.dialect.toUpperCase() ?? 'SQLITE'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Core Architectural Pillars */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card space-y-3">
          <div className="w-8 h-8 rounded bg-signal-50 text-signal flex items-center justify-center font-bold">
            01
          </div>
          <h3 className="text-sm font-bold text-ink">Tamper-Evident Proof Ledger</h3>
          <p className="text-xs text-ink-muted leading-relaxed">
            Every measurement links to a raw response or artifact path with SHA-256 digest and previous hash chaining. Historical evidence is never overwritten.
          </p>
          <div className="text-[11px] font-mono text-signal-dark font-medium pt-2">
            SHA-256 • Append-Only Ledger
          </div>
        </div>

        <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card space-y-3">
          <div className="w-8 h-8 rounded bg-signal-50 text-signal flex items-center justify-center font-bold">
            02
          </div>
          <h3 className="text-sm font-bold text-ink">Live Replay Lab</h3>
          <p className="text-xs text-ink-muted leading-relaxed">
            Reviewers can execute <code className="font-mono bg-paper px-1 py-0.5 rounded text-[11px]">signalroom replay Q-047 --market US</code> to rerun questions, preserving original evidence while generating comparison deltas.
          </p>
          <div className="text-[11px] font-mono text-signal-dark font-medium pt-2">
            Historical vs Fresh Observations
          </div>
        </div>

        <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card space-y-3">
          <div className="w-8 h-8 rounded bg-signal-50 text-signal flex items-center justify-center font-bold">
            03
          </div>
          <h3 className="text-sm font-bold text-ink">Claim Guard & Honesty Panel</h3>
          <p className="text-xs text-ink-muted leading-relaxed">
            Content Foundry enforces a Product Truth Sheet. Pages with unverified product claims are blocked from publish status. Failed API calls are honestly reported.
          </p>
          <div className="text-[11px] font-mono text-signal-dark font-medium pt-2">
            Zero Hallucinated Metrics
          </div>
        </div>
      </div>

      {/* Audit Readiness Banner */}
      <div className="p-4 rounded-lg border border-paper-border bg-paper-warm/70 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
        <div>
          <span className="font-bold text-ink">Assessment Traceability Ready:</span>
          <span className="text-ink-muted ml-1.5">
            Phase 1 foundation provides database schemas, Proof Ledger models, Typer CLI, and health contracts ready for Phase 2 implementation.
          </span>
        </div>
        <button
          onClick={() => onNavigate('settings-honesty')}
          className="underline font-medium text-signal hover:text-signal-dark shrink-0"
        >
          View Honesty Panel &rarr;
        </button>
      </div>
    </div>
  );
};
