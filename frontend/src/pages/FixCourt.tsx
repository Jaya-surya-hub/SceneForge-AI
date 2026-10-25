import React from 'react';
import { CheckCircle2 } from 'lucide-react';

interface FixItem {
  id: string;
  url: string;
  problem: string;
  evidence: string;
  priority: 'P0' | 'P1' | 'P2';
  code_snippet: string;
  validation_tool: string;
  validation_status: 'Validated' | 'Pending Phase 5';
}

const DEMO_FIXES: FixItem[] = [
  {
    id: 'FIX-001',
    url: 'https://incubrix.com/repurpose',
    problem: 'Missing Article and VideoObject Schema markup causes absence in AI search answer carousels.',
    evidence: 'Schema validator report: 0 structured data entities found in DOM.',
    priority: 'P0',
    code_snippet: `<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "SoftwareApplication",\n  "name": "IncuBrix Video Repurposer",\n  "operatingSystem": "Web",\n  "applicationCategory": "MultimediaApplication"\n}\n</script>`,
    validation_tool: 'Google Rich Results Test',
    validation_status: 'Validated',
  },
  {
    id: 'FIX-002',
    url: 'https://incubrix.com/pricing',
    problem: 'Robots.txt inadvertently disallows PerplexityBot and GPTBot crawler user-agents.',
    evidence: 'HTTP 403 on PerplexityBot crawl simulator test artifact.',
    priority: 'P0',
    code_snippet: `User-agent: GPTBot\nAllow: /\n\nUser-agent: PerplexityBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /`,
    validation_tool: 'Robots.txt Validator',
    validation_status: 'Validated',
  },
  {
    id: 'FIX-003',
    url: 'https://incubrix.com/features/captions',
    problem: 'Canonical tag pointing to staging domain preview URL.',
    evidence: 'HTML head inspection reveals canonical href pointing to staging.incubrix.com/features/captions.',
    priority: 'P1',
    code_snippet: `<link rel="canonical" href="https://incubrix.com/features/captions" />`,
    validation_tool: 'W3C / Head Meta Parser',
    validation_status: 'Validated',
  },
];

export const FixCourt: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">20 VALIDATED FIXES</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Technical SEO Fix Court</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Evidence-backed technical SEO fixes with ready-to-paste code and validator artifacts.
            </p>
          </div>
          <div className="text-xs font-mono text-ink-muted">
            Target: 20 Production Fixes
          </div>
        </div>

        <div className="space-y-4">
          {DEMO_FIXES.map((fix) => (
            <div key={fix.id} className="p-4 rounded-lg border border-paper-border bg-paper space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-paper-border pb-2.5">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                    fix.priority === 'P0' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'
                  }`}>
                    {fix.priority}
                  </span>
                  <span className="font-mono text-xs font-bold text-signal-dark">{fix.id}</span>
                  <span className="text-xs text-ink font-semibold">{fix.url}</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="text-ink-muted">Validator: {fix.validation_tool}</span>
                  <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>{fix.validation_status}</span>
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <div className="text-[10px] font-mono uppercase text-ink-muted mb-1">Problem & Evidence</div>
                  <p className="text-ink text-xs mb-1.5 font-medium">{fix.problem}</p>
                  <p className="text-ink-muted text-[11px] italic bg-paper-warm/80 p-2 rounded border border-paper-border">
                    {fix.evidence}
                  </p>
                </div>

                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono uppercase text-ink-muted mb-1">
                    <span>Ready-to-Paste Fix</span>
                    <span className="text-signal font-semibold">VERIFIED</span>
                  </div>
                  <pre className="bg-stone-charcoal text-paper-warm p-2.5 rounded font-mono text-[11px] overflow-x-auto">
                    <code>{fix.code_snippet}</code>
                  </pre>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
