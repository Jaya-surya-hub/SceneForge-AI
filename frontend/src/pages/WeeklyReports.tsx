import React from 'react';
import { ArrowDownToLine, CheckCircle2 } from 'lucide-react';

export const WeeklyReports: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">AUDIT EXPORTS</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Weekly Visibility Reports & 90-Day Kit</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Automated executive briefings and export pipelines formatted for the official assessment workbook.
            </p>
          </div>
          <button className="px-3.5 py-1.5 rounded bg-signal text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm hover:bg-signal-dark transition">
            <ArrowDownToLine className="w-3.5 h-3.5" />
            <span>Export Assessment Workbook (XLSX)</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-ink text-sm">Weekly Visibility Intelligence Brief</span>
              <span className="text-[10px] font-mono text-ink-muted">Week 42 • Oct 2026</span>
            </div>
            <p className="text-ink-muted text-xs leading-relaxed">
              Consolidated measurement digest covering Google Search impressions, ChatGPT brand visibility, Claude answer presence, and competitor mention displacement.
            </p>
            <div className="text-[11px] font-mono text-emerald-800 flex items-center gap-1 pt-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Full Audit Trail Included in Annex</span>
            </div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-ink text-sm">90-Day Organic & AEO Launch Kit</span>
              <span className="text-[10px] font-mono text-ink-muted">Phase 7 Milestone</span>
            </div>
            <p className="text-ink-muted text-xs leading-relaxed">
              Tactical execution roadmap including prioritized technical SEO fixes, high-probability citation pitches, and claim-guarded content publication sequence.
            </p>
            <div className="text-[11px] font-mono text-signal-dark flex items-center gap-1 pt-1">
              <span>Ready for Growth Team Onboarding</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
