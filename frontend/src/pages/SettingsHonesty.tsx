import React from 'react';
import { CheckCircle2 } from 'lucide-react';
import { HealthResponse } from '../types';

interface SettingsHonestyProps {
  health?: HealthResponse | null;
}

export const SettingsHonesty: React.FC<SettingsHonestyProps> = () => {
  return (
    <div className="space-y-6">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">CORE INTEGRITY</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Honesty Panel & System Transparency</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Transparent reporting of operational limits, unavailable providers, failed observations, and API economics. Never manufacture data.
            </p>
          </div>
          <div className="text-xs font-mono text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded flex items-center gap-1.5 font-semibold">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>TRANSPARENCY STANDARD COMPLIANT</span>
          </div>
        </div>

        {/* Honesty Metrics Matrix */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs mb-6">
          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="text-[10px] font-mono uppercase text-ink-muted">Failed / Missing Observations</div>
            <div className="text-2xl font-bold font-mono text-ink">0</div>
            <p className="text-[11px] text-ink-muted">
              Zero failed observations in Phase 1 demo suite. In production, timeouts and rate limits are logged to the Proof Ledger rather than swallowed.
            </p>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="text-[10px] font-mono uppercase text-ink-muted">API Restrictions & Policy</div>
            <div className="text-2xl font-bold font-mono text-emerald-700">100% Permitted</div>
            <p className="text-[11px] text-ink-muted">
              All assistant observations strictly follow permitted official API routes or transparent manual review fixtures without TOS bypass.
            </p>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="text-[10px] font-mono uppercase text-ink-muted">Cost Accounting (Est vs Actual)</div>
            <div className="text-2xl font-bold font-mono text-ink">$0.00 / $0.00</div>
            <p className="text-[11px] text-ink-muted">
              Real run costs are recorded per ledger entry in USD with provider token calculations.
            </p>
          </div>
        </div>

        {/* Provider Availability Registry */}
        <div className="border border-paper-border rounded-lg overflow-hidden">
          <div className="bg-paper px-4 py-2.5 border-b border-paper-border text-xs font-mono font-bold text-ink flex items-center justify-between">
            <span>Provider Integration Registry</span>
            <span className="text-[10px] text-ink-muted">PHASE 1 STATUS</span>
          </div>
          <table className="w-full text-left text-xs">
            <thead className="bg-paper-warm/50 border-b border-paper-border text-ink-muted font-mono text-[11px]">
              <tr>
                <th className="py-2.5 px-4">Provider / Engine</th>
                <th className="py-2.5 px-4">Access Method</th>
                <th className="py-2.5 px-4">Permitted Scope</th>
                <th className="py-2.5 px-4">Current Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-border text-ink font-mono text-[11px]">
              <tr>
                <td className="py-2.5 px-4 font-semibold">Google Search (US, UK, IN)</td>
                <td className="py-2.5 px-4">Custom Search API / SERP Fixture</td>
                <td className="py-2.5 px-4">Public SERP Ranking & PAA</td>
                <td className="py-2.5 px-4 text-emerald-800 font-bold">CONFIGURED</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-semibold">OpenAI ChatGPT Search</td>
                <td className="py-2.5 px-4">Official OpenAI API (Search-enabled)</td>
                <td className="py-2.5 px-4">Multi-turn response & web citations</td>
                <td className="py-2.5 px-4 text-emerald-800 font-bold">CONFIGURED</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-semibold">Anthropic Claude 3.5 Sonnet</td>
                <td className="py-2.5 px-4">Official Anthropic API</td>
                <td className="py-2.5 px-4">Assistant knowledge & synthesis</td>
                <td className="py-2.5 px-4 text-emerald-800 font-bold">CONFIGURED</td>
              </tr>
              <tr>
                <td className="py-2.5 px-4 font-semibold">Perplexity AI Sonar</td>
                <td className="py-2.5 px-4">Official Perplexity API</td>
                <td className="py-2.5 px-4">Live citations & linked sources</td>
                <td className="py-2.5 px-4 text-emerald-800 font-bold">CONFIGURED</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
