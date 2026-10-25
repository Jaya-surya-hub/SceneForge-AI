import React from 'react';
import { Shield, Globe } from 'lucide-react';
import { HealthResponse } from '../types';

interface HeaderProps {
  health: HealthResponse | null;
  selectedMarket: string;
  onMarketChange: (market: string) => void;
}

export const Header: React.FC<HeaderProps> = ({ health, selectedMarket, onMarketChange }) => {
  return (
    <header className="bg-paper-light border-b border-paper-border px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-30 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-md bg-signal text-white flex items-center justify-center font-mono font-bold shadow-sm">
          SR
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-ink tracking-tight">IncuBrix Signal Room</h1>
            <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-stone-charcoal text-paper-warm font-semibold">
              v0.1.0 • Phase 1
            </span>
          </div>
          <p className="text-xs text-ink-muted italic font-serif">
            Every signal has a source. Every decision has proof.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs">
        {/* Market Selector */}
        <div className="flex items-center gap-1.5 bg-paper px-2.5 py-1 rounded border border-paper-border">
          <Globe className="w-3.5 h-3.5 text-ink-muted" />
          <span className="text-ink-muted font-medium">Market:</span>
          <select
            value={selectedMarket}
            onChange={(e) => onMarketChange(e.target.value)}
            aria-label="Target Market"
            className="bg-transparent font-semibold text-ink focus:outline-none cursor-pointer"
          >
            <option value="US">United States (US)</option>
            <option value="UK">United Kingdom (UK)</option>
            <option value="IN">India (IN)</option>
          </select>
        </div>

        {/* Live Backend Connection Indicator */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded border bg-paper border-paper-border font-mono text-[11px]">
          {health?.status === 'healthy' ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-emerald-800 font-semibold">CORE API ONLINE</span>
              <span className="text-ink-faint">({health.database.latency_ms}ms)</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-amber-800 font-semibold">API CONNECTING...</span>
            </>
          )}
        </div>

        {/* Ledger Integrity Pill */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded border bg-paper border-paper-border font-mono text-[11px] text-ink-muted">
          <Shield className="w-3.5 h-3.5 text-signal" />
          <span>PROOF LEDGER:</span>
          <span className="font-semibold text-ink">APPEND-ONLY</span>
        </div>
      </div>
    </header>
  );
};
