import React from 'react';
import { AlertTriangle } from 'lucide-react';

export const VisibilityIntelligence: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">VARIANCE-AWARE INTELLIGENCE</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Search & AI Visibility Engine</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Dual-measurement tracking brand presence across Google search and 4 leading AI assistants with run-level variance.
            </p>
          </div>
          <div className="text-xs font-mono text-ink-muted">
            3 Repeated Observations per Question
          </div>
        </div>

        {/* 4 Assistant Visibility Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span className="font-semibold text-ink">ChatGPT Search</span>
              <span className="demo-badge">DEMO</span>
            </div>
            <div className="text-2xl font-bold font-mono text-ink">68.4%</div>
            <div className="text-[11px] text-ink-muted mt-1">Brand Mention Rate (US)</div>
            <div className="text-[10px] font-mono text-emerald-800 mt-2">Variance: &plusmn;3.2%</div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span className="font-semibold text-ink">Claude 3.5</span>
              <span className="demo-badge">DEMO</span>
            </div>
            <div className="text-2xl font-bold font-mono text-ink">54.2%</div>
            <div className="text-[11px] text-ink-muted mt-1">Brand Mention Rate (US)</div>
            <div className="text-[10px] font-mono text-emerald-800 mt-2">Variance: &plusmn;4.1%</div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span className="font-semibold text-ink">Gemini 1.5 Pro</span>
              <span className="demo-badge">DEMO</span>
            </div>
            <div className="text-2xl font-bold font-mono text-ink">48.9%</div>
            <div className="text-[11px] text-ink-muted mt-1">Brand Mention Rate (US)</div>
            <div className="text-[10px] font-mono text-emerald-800 mt-2">Variance: &plusmn;5.0%</div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper">
            <div className="flex items-center justify-between text-xs text-ink-muted mb-1">
              <span className="font-semibold text-ink">Perplexity Sonar</span>
              <span className="demo-badge">DEMO</span>
            </div>
            <div className="text-2xl font-bold font-mono text-ink">72.1%</div>
            <div className="text-[11px] text-ink-muted mt-1">Brand Mention Rate (US)</div>
            <div className="text-[10px] font-mono text-emerald-800 mt-2">Variance: &plusmn;2.8%</div>
          </div>
        </div>
      </div>

      {/* Honest aggregation notice */}
      <div className="p-4 rounded-lg border border-amber-200 bg-amber-50/70 text-xs text-amber-950 flex items-start gap-3">
        <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="font-bold">Engineering Rule — No Incompatible Provider Mixing:</div>
          <p className="text-[11px] leading-relaxed text-amber-900">
            Per project integrity rules, provider visibility scores are displayed per engine and never averaged into a single arbitrary blended score without explicit methodological weighting. Live measurements will be logged in Phase 4.
          </p>
        </div>
      </div>
    </div>
  );
};
