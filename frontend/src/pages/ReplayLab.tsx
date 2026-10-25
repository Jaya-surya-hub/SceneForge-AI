import React, { useState } from 'react';
import { RotateCcw, CheckCircle2, Terminal } from 'lucide-react';

export const ReplayLab: React.FC = () => {
  const [selectedQuestion, setSelectedQuestion] = useState('Q-001');
  const [selectedMarket, setSelectedMarket] = useState('US');
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayComplete, setReplayComplete] = useState(false);

  const handleRunReplay = () => {
    setIsReplaying(true);
    setTimeout(() => {
      setIsReplaying(false);
      setReplayComplete(true);
    }, 1200);
  };

  return (
    <div className="space-y-6">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">LIVE REPLAY LAB</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Question Replay & Audit Lab</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Reviewers can rerun questions using recorded provider configurations without destroying historical evidence.
            </p>
          </div>
          <div className="text-xs font-mono bg-stone-charcoal text-paper-warm px-3 py-1.5 rounded flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-signal" />
            <span>signalroom replay {selectedQuestion} --market {selectedMarket}</span>
          </div>
        </div>

        {/* Input Parameters */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block text-ink-muted font-medium mb-1">Target Question</label>
            <select
              value={selectedQuestion}
              onChange={(e) => {
                setSelectedQuestion(e.target.value);
                setReplayComplete(false);
              }}
              className="w-full bg-paper border border-paper-border rounded px-3 py-2 text-ink focus:outline-none focus:border-signal"
            >
              <option value="Q-001">Q-001 — Repurpose podcast video into vertical shorts</option>
              <option value="Q-002">Q-002 — Best AI video editing tools with captions</option>
              <option value="Q-003">Q-003 — Automate b-roll video creation from voiceover</option>
              <option value="Q-004">Q-004 — IncuBrix vs Opus Clip vs Descript comparison</option>
            </select>
          </div>

          <div>
            <label className="block text-ink-muted font-medium mb-1">Observation Market</label>
            <select
              value={selectedMarket}
              onChange={(e) => setSelectedMarket(e.target.value)}
              className="w-full bg-paper border border-paper-border rounded px-3 py-2 text-ink focus:outline-none focus:border-signal"
            >
              <option value="US">United States (US)</option>
              <option value="UK">United Kingdom (UK)</option>
              <option value="IN">India (IN)</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleRunReplay}
              disabled={isReplaying}
              className="w-full py-2 px-4 rounded bg-signal hover:bg-signal-dark text-white font-semibold text-xs transition flex items-center justify-center gap-2 shadow-sm disabled:opacity-70"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${isReplaying ? 'animate-spin' : ''}`} />
              <span>{isReplaying ? 'Executing Replay Run...' : 'Execute Live Replay'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Side-by-Side Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Historical Evidence Card */}
        <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card space-y-4">
          <div className="flex items-center justify-between border-b border-paper-border pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-ink-muted uppercase">Original Baseline</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-paper-subtle text-ink-muted">
                RUN-20261022-001
              </span>
            </div>
            <span className="text-[11px] font-mono text-ink-faint">2026-10-22 06:00 UTC</span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 rounded bg-paper border border-paper-border space-y-1.5">
              <div className="text-[10px] font-mono uppercase text-ink-muted">Provider Response Summary</div>
              <p className="text-ink text-xs leading-relaxed italic">
                "To repurpose podcast recordings into vertical shorts, creators commonly use dedicated AI clip extraction tools like IncuBrix and OpusClip, which detect speaker framing and auto-generate captions..."
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="p-2 rounded bg-paper border border-paper-border">
                <span className="text-ink-muted block text-[10px]">Brand Mention</span>
                <span className="font-bold text-emerald-800">MENTIONED (Pos #1)</span>
              </div>
              <div className="p-2 rounded bg-paper border border-paper-border">
                <span className="text-ink-muted block text-[10px]">Link Citation</span>
                <span className="font-bold text-signal-dark">incubrix.com/repurpose</span>
              </div>
            </div>

            <div className="text-[10px] font-mono text-ink-muted truncate">
              Artifact Hash: <span className="text-ink">e3b0c44298fc1c149afbf4c8...</span>
            </div>
          </div>
        </div>

        {/* Fresh Observation / Replay Delta */}
        <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card space-y-4">
          <div className="flex items-center justify-between border-b border-paper-border pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-signal uppercase">Fresh Observation (Replay)</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-signal-100 text-signal-dark font-bold">
                NEW LEDGER ENTRY
              </span>
            </div>
            <span className="text-[11px] font-mono text-ink-muted">
              {replayComplete ? 'Just now' : 'Awaiting trigger'}
            </span>
          </div>

          {replayComplete ? (
            <div className="space-y-3 text-xs">
              <div className="p-3 rounded bg-paper border border-paper-border space-y-1.5">
                <div className="text-[10px] font-mono uppercase text-ink-muted">Provider Response Summary</div>
                <p className="text-ink text-xs leading-relaxed italic">
                  "Leading automated vertical video workflows utilize tools such as IncuBrix, Descript, and OpusClip to slice long video into 9:16 clips with animated captions..."
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="p-2 rounded bg-paper border border-paper-border">
                  <span className="text-ink-muted block text-[10px]">Brand Mention Drift</span>
                  <span className="font-bold text-emerald-800">CONSISTENT (Rank 1-2)</span>
                </div>
                <div className="p-2 rounded bg-paper border border-paper-border">
                  <span className="text-ink-muted block text-[10px]">Variance Delta</span>
                  <span className="font-bold text-ink">0.00% Drift</span>
                </div>
              </div>

              <div className="p-2.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-900 text-[11px] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Historical evidence preserved intact. New entry appended to Proof Ledger.</span>
              </div>
            </div>
          ) : (
            <div className="h-44 flex flex-col items-center justify-center text-center text-xs text-ink-muted border-2 border-dashed border-paper-border rounded-lg p-4">
              <RotateCcw className="w-6 h-6 text-stone-muted mb-2 opacity-50" />
              <p>Click "Execute Live Replay" above or run CLI command</p>
              <code className="text-[11px] font-mono text-signal mt-1">signalroom replay {selectedQuestion}</code>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
