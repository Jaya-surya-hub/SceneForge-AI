import React from 'react';
import { Shield, CheckCircle2, XCircle } from 'lucide-react';

export const ContentFoundry: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">CLAIM GUARD ACTIVE</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Content Foundry & Claim Guard</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              10 answer-first, publish-ready growth pages verified strictly against the IncuBrix Product Truth Sheet.
            </p>
          </div>
          <div className="text-xs font-mono text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded flex items-center gap-1.5 font-semibold">
            <Shield className="w-3.5 h-3.5 text-emerald-600" />
            <span>UNSUPPORTED CLAIMS BLOCKED</span>
          </div>
        </div>

        {/* Claim Guard Principles */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs mb-5">
          <div className="p-4 rounded border border-emerald-200 bg-emerald-50/50 space-y-2">
            <div className="flex items-center gap-2 font-bold text-emerald-950">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Verified Product Truth Sheet Claims</span>
            </div>
            <ul className="text-[11px] text-emerald-900 space-y-1 list-disc list-inside">
              <li>Auto-generates animated captions with 98% accuracy</li>
              <li>Exports vertical 9:16 video optimized for TikTok and YouTube Shorts</li>
              <li>Provides rights-verified stock B-roll provenance log</li>
            </ul>
          </div>

          <div className="p-4 rounded border border-red-200 bg-red-50/50 space-y-2">
            <div className="flex items-center gap-2 font-bold text-red-950">
              <XCircle className="w-4 h-4 text-red-600" />
              <span>Blocked Unverified Marketing Claims</span>
            </div>
            <ul className="text-[11px] text-red-900 space-y-1 list-disc list-inside">
              <li>"Generates 10 million views guaranteed" (Blocked: Unverifiable)</li>
              <li>"Ranked #1 tool worldwide by Google" (Blocked: No source proof)</li>
              <li>"Completely free forever with unlimited 4K" (Blocked: Tier limits exist)</li>
            </ul>
          </div>
        </div>

        {/* 10 Pages Table preview */}
        <div className="border border-paper-border rounded-lg overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-paper border-b border-paper-border text-ink-muted font-mono text-[11px]">
              <tr>
                <th className="py-2.5 px-3">Page Slug</th>
                <th className="py-2.5 px-3">Target Opportunity Question</th>
                <th className="py-2.5 px-3">Claim Guard Audit</th>
                <th className="py-2.5 px-3">Publish Readiness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-border text-ink">
              <tr className="hover:bg-paper/70">
                <td className="py-2.5 px-3 font-mono font-bold text-signal-dark">/blog/repurpose-podcast-to-shorts</td>
                <td className="py-2.5 px-3">Q-001 — Podcast video repurposing</td>
                <td className="py-2.5 px-3 text-emerald-700 font-semibold text-[11px]">4 / 4 Claims Verified</td>
                <td className="py-2.5 px-3">
                  <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold text-[10px] uppercase font-mono">
                    PUBLISH-READY
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-paper/70">
                <td className="py-2.5 px-3 font-mono font-bold text-signal-dark">/solutions/ai-broll-automation</td>
                <td className="py-2.5 px-3">Q-003 — B-roll automation from voiceover</td>
                <td className="py-2.5 px-3 text-emerald-700 font-semibold text-[11px]">3 / 3 Claims Verified</td>
                <td className="py-2.5 px-3">
                  <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold text-[10px] uppercase font-mono">
                    PUBLISH-READY
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
