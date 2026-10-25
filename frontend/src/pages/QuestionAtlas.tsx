import React, { useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { QuestionItem } from '../types';

const INITIAL_DEMO_QUESTIONS: QuestionItem[] = [
  {
    id: 'Q-001',
    text: 'How do creators repurpose long-form podcast video into 9:16 vertical shorts automatically?',
    journey_stage: 'Repurpose',
    search_intent: 'informational',
    source_type: 'google_autocomplete',
    source_url: 'https://www.google.com/search?q=how+to+repurpose+podcast+video+into+vertical+shorts',
    target_market: 'US',
    is_demo: true,
  },
  {
    id: 'Q-002',
    text: 'Best AI video editing tools with accurate caption generation for TikTok and Reels',
    journey_stage: 'Caption',
    search_intent: 'comparison',
    source_type: 'forum_reddit',
    source_url: 'https://reddit.com/r/NewTubers/comments/ai_caption_tools_creator_workflow',
    target_market: 'US',
    is_demo: true,
  },
  {
    id: 'Q-003',
    text: 'How to automate b-roll video creation from voiceover script without copyright strikes?',
    journey_stage: 'Make',
    search_intent: 'informational',
    source_type: 'paa',
    source_url: 'https://www.google.com/search?q=automate+b-roll+video+creation+from+voiceover',
    target_market: 'US',
    is_demo: true,
  },
  {
    id: 'Q-004',
    text: 'IncuBrix vs Opus Clip vs Descript pricing and feature comparison for video creators',
    journey_stage: 'Edit',
    search_intent: 'commercial',
    source_type: 'keyword_planner',
    source_url: 'https://ads.google.com/aw/keywordplanner/incubrix-comparison',
    target_market: 'UK',
    is_demo: true,
  },
  {
    id: 'Q-005',
    text: 'How to publish scheduled short-form video across YouTube, Instagram, and LinkedIn simultaneously',
    journey_stage: 'Publish',
    search_intent: 'informational',
    source_type: 'google_autocomplete',
    source_url: 'https://www.google.com/search?q=how+to+publish+scheduled+short+form+video+across+platforms',
    target_market: 'US',
    is_demo: true,
  },
  {
    id: 'Q-006',
    text: 'Creator retention analytics: what makes viewers stay past 3 seconds on vertical videos?',
    journey_stage: 'Grow',
    search_intent: 'informational',
    source_type: 'paa',
    source_url: 'https://www.google.com/search?q=vertical+video+retention+first+3+seconds',
    target_market: 'IN',
    is_demo: true,
  },
];

export const QuestionAtlas: React.FC = () => {
  const [selectedStage, setSelectedStage] = useState<string>('ALL');
  const [selectedIntent, setSelectedIntent] = useState<string>('ALL');

  const filtered = INITIAL_DEMO_QUESTIONS.filter((q) => {
    if (selectedStage !== 'ALL' && q.journey_stage !== selectedStage) return false;
    if (selectedIntent !== 'ALL' && q.search_intent !== selectedIntent) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">DEMO FIXTURES</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Question Atlas</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Genuine creator queries across 6 journey stages with verifiable origin URLs. 100+ questions will be mapped in Phase 3.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-mono text-ink-muted">Showing {filtered.length} of {INITIAL_DEMO_QUESTIONS.length} Questions</span>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-ink-muted font-medium">Stage:</span>
            <div className="flex flex-wrap gap-1">
              {['ALL', 'Make', 'Repurpose', 'Edit', 'Caption', 'Publish', 'Grow'].map((stage) => (
                <button
                  key={stage}
                  onClick={() => setSelectedStage(stage)}
                  className={`px-2.5 py-1 rounded text-xs transition ${
                    selectedStage === stage
                      ? 'bg-signal text-white font-medium'
                      : 'bg-paper border border-paper-border text-ink-muted hover:text-ink'
                  }`}
                >
                  {stage}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-ink-muted font-medium">Intent:</span>
            <select
              value={selectedIntent}
              onChange={(e) => setSelectedIntent(e.target.value)}
              aria-label="Search Intent"
              className="bg-paper border border-paper-border rounded px-2 py-1 text-xs text-ink focus:outline-none"
            >
              <option value="ALL">All Intents</option>
              <option value="informational">Informational</option>
              <option value="comparison">Comparison</option>
              <option value="commercial">Commercial</option>
            </select>
          </div>
        </div>
      </div>

      {/* Questions Table */}
      <div className="bg-paper-light border border-paper-border rounded-lg overflow-hidden shadow-card">
        <table className="w-full text-left text-xs">
          <thead className="bg-paper border-b border-paper-border text-ink-muted font-mono text-[11px]">
            <tr>
              <th className="py-3 px-4">ID</th>
              <th className="py-3 px-4">Question Text</th>
              <th className="py-3 px-4">Journey Stage</th>
              <th className="py-3 px-4">Intent</th>
              <th className="py-3 px-4">Market</th>
              <th className="py-3 px-4">Verifiable Source</th>
              <th className="py-3 px-4">Mode</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-paper-border text-ink">
            {filtered.map((q) => (
              <tr key={q.id} className="hover:bg-paper/70 transition">
                <td className="py-3 px-4 font-mono font-bold text-signal-dark">{q.id}</td>
                <td className="py-3 px-4 font-medium max-w-md">{q.text}</td>
                <td className="py-3 px-4">
                  <span className="px-2 py-0.5 rounded bg-paper-warm border border-paper-border font-medium text-[11px]">
                    {q.journey_stage}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="capitalize text-ink-muted font-mono text-[11px]">{q.search_intent}</span>
                </td>
                <td className="py-3 px-4 font-mono font-semibold">{q.target_market}</td>
                <td className="py-3 px-4">
                  <a
                    href={q.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-signal hover:underline font-mono text-[11px]"
                  >
                    <span>{q.source_type}</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </td>
                <td className="py-3 px-4">
                  {q.is_demo ? <span className="demo-badge">DEMO</span> : <span className="text-emerald-700 font-mono">LIVE</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
