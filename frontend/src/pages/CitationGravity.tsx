import React from 'react';

export const CitationGravity: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-paper-light border border-paper-border rounded-lg p-5 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-paper-border pb-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="demo-badge">30 CITATION TARGETS</span>
              <h2 className="text-xl font-bold tracking-tight text-ink">Citation Gravity Engine</h2>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Identifies high-impact third-party citation sources frequently referenced by AI assistants and Google search.
            </p>
          </div>
          <div className="text-xs font-mono text-ink-muted">
            Target: 30 Editorial Citation Angles
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-signal-dark">TARGET #1</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-signal-100 text-signal-dark font-bold">
                HIGH GRAVITY
              </span>
            </div>
            <h4 className="font-bold text-ink">Zapier Blog: Best Video Repurposing Apps</h4>
            <p className="text-ink-muted text-[11px] leading-relaxed">
              Cited in 78% of ChatGPT and Perplexity answers for creator automation queries.
            </p>
            <div className="pt-2 border-t border-paper-border text-[11px] space-y-1">
              <div className="text-ink font-medium">Editorial Angle:</div>
              <p className="text-ink-muted italic">"Include IncuBrix in automated short-form workflows with webhook triggers."</p>
            </div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-signal-dark">TARGET #2</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-signal-100 text-signal-dark font-bold">
                HIGH GRAVITY
              </span>
            </div>
            <h4 className="font-bold text-ink">HubSpot Marketing: Video Repurposing Guide</h4>
            <p className="text-ink-muted text-[11px] leading-relaxed">
              Frequently indexed in Google Overview citations for B2B video recycling.
            </p>
            <div className="pt-2 border-t border-paper-border text-[11px] space-y-1">
              <div className="text-ink font-medium">Editorial Angle:</div>
              <p className="text-ink-muted italic">"Demonstrate ROI on webinars-to-shorts repurposing case study."</p>
            </div>
          </div>

          <div className="p-4 rounded border border-paper-border bg-paper space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-signal-dark">TARGET #3</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-signal-100 text-signal-dark font-bold">
                HIGH GRAVITY
              </span>
            </div>
            <h4 className="font-bold text-ink">Buffer Resources: Creator Social Strategies</h4>
            <p className="text-ink-muted text-[11px] leading-relaxed">
              Consistently referenced by Claude 3.5 for multi-platform short video distribution.
            </p>
            <div className="pt-2 border-t border-paper-border text-[11px] space-y-1">
              <div className="text-ink font-medium">Editorial Angle:</div>
              <p className="text-ink-muted italic">"Guest editorial on the mathematics of cross-posting retention curves."</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
