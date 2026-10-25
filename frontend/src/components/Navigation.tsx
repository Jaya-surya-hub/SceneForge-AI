import React from 'react';
import {
  LayoutDashboard,
  Compass,
  FileCheck2,
  RotateCcw,
  Eye,
  Wrench,
  Sparkles,
  Target,
  FileText,
  SlidersHorizontal,
} from 'lucide-react';
import { TabId } from '../types';

interface NavigationProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

interface NavItem {
  id: TabId;
  label: string;
  icon: React.ElementType;
  badge?: string;
}

const navItems: NavItem[] = [
  { id: 'command-center', label: 'Command Center', icon: LayoutDashboard },
  { id: 'question-atlas', label: 'Question Atlas', icon: Compass, badge: '100+' },
  { id: 'evidence-ledger', label: 'Proof Ledger', icon: FileCheck2 },
  { id: 'replay-lab', label: 'Replay Lab', icon: RotateCcw },
  { id: 'visibility-intelligence', label: 'Visibility Intelligence', icon: Eye },
  { id: 'fix-court', label: 'Fix Court', icon: Wrench, badge: '20' },
  { id: 'content-foundry', label: 'Content Foundry', icon: Sparkles, badge: '10' },
  { id: 'citation-gravity', label: 'Citation Gravity', icon: Target, badge: '30' },
  { id: 'weekly-reports', label: 'Weekly Reports', icon: FileText },
  { id: 'settings-honesty', label: 'Settings & Honesty', icon: SlidersHorizontal },
];

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  return (
    <nav className="w-64 bg-paper border-r border-paper-border flex flex-col justify-between shrink-0 min-h-[calc(100vh-61px)]">
      <div className="py-4 px-3 space-y-1">
        <div className="px-3 pb-2 text-[10px] font-mono tracking-wider text-ink-faint uppercase font-bold">
          Navigation Modules
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-all text-left ${
                isActive
                  ? 'bg-paper-warm text-signal font-semibold border-l-4 border-signal pl-2 shadow-xs'
                  : 'text-ink-muted hover:text-ink hover:bg-paper-warm/60'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-signal' : 'text-stone-muted'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                    isActive ? 'bg-signal-100 text-signal-dark font-bold' : 'bg-paper-subtle text-ink-faint'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="p-4 border-t border-paper-border bg-paper-warm/50 text-[11px] text-ink-muted">
        <div className="font-mono text-ink font-semibold flex items-center justify-between">
          <span>IncuBrix Growth</span>
          <span className="text-[10px] text-signal font-bold">2027</span>
        </div>
        <p className="mt-1 text-[10px] text-ink-faint leading-relaxed">
          Option 3: AEO, SEO & GEO Visibility Engine Assessment.
        </p>
      </div>
    </nav>
  );
};
