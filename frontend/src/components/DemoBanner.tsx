import React from 'react';
import { ShieldCheck } from 'lucide-react';

interface DemoBannerProps {
  message?: string;
}

export const DemoBanner: React.FC<DemoBannerProps> = ({
  message = "DEMO DATA MODE ACTIVE — The metrics, questions, and ledger entries shown below are illustrative Phase 1 fixtures. Real-world search rankings and AI responses will be captured via live collectors in Phase 3 without synthetic manipulation."
}) => {
  return (
    <div className="bg-amber-50/80 border-b border-amber-200/80 px-4 py-2.5 text-xs text-amber-900 flex items-center justify-between gap-3 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="demo-badge">DEMO</span>
        <span className="font-medium text-amber-950">{message}</span>
      </div>
      <div className="hidden sm:flex items-center gap-1.5 text-amber-800 font-mono text-[11px]">
        <ShieldCheck className="w-3.5 h-3.5 text-amber-700" />
        <span>AUDIT RULE: NO SYNTHETIC OBSERVATIONS</span>
      </div>
    </div>
  );
};
