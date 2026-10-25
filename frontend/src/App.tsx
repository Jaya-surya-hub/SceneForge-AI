import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Navigation } from './components/Navigation';
import { DemoBanner } from './components/DemoBanner';
import { CommandCenter } from './pages/CommandCenter';
import { QuestionAtlas } from './pages/QuestionAtlas';
import { EvidenceLedger } from './pages/EvidenceLedger';
import { ReplayLab } from './pages/ReplayLab';
import { VisibilityIntelligence } from './pages/VisibilityIntelligence';
import { FixCourt } from './pages/FixCourt';
import { ContentFoundry } from './pages/ContentFoundry';
import { CitationGravity } from './pages/CitationGravity';
import { WeeklyReports } from './pages/WeeklyReports';
import { SettingsHonesty } from './pages/SettingsHonesty';
import { HealthResponse, TabId } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('command-center');
  const [selectedMarket, setSelectedMarket] = useState<string>('US');
  const [health, setHealth] = useState<HealthResponse | null>(null);

  // Poll or fetch health status from backend
  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/v1/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch {
      // Backend may be starting or offline
      setHealth(null);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const renderActiveView = () => {
    switch (activeTab) {
      case 'command-center':
        return <CommandCenter health={health} onNavigate={setActiveTab} />;
      case 'question-atlas':
        return <QuestionAtlas />;
      case 'evidence-ledger':
        return <EvidenceLedger />;
      case 'replay-lab':
        return <ReplayLab />;
      case 'visibility-intelligence':
        return <VisibilityIntelligence />;
      case 'fix-court':
        return <FixCourt />;
      case 'content-foundry':
        return <ContentFoundry />;
      case 'citation-gravity':
        return <CitationGravity />;
      case 'weekly-reports':
        return <WeeklyReports />;
      case 'settings-honesty':
        return <SettingsHonesty health={health} />;
      default:
        return <CommandCenter health={health} onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink font-sans">
      <DemoBanner />
      <Header
        health={health}
        selectedMarket={selectedMarket}
        onMarketChange={setSelectedMarket}
      />
      <div className="flex flex-1">
        <Navigation activeTab={activeTab} onTabChange={setActiveTab} />
        <main className="flex-1 p-6 max-w-7xl mx-auto overflow-y-auto">
          {renderActiveView()}
        </main>
      </div>
    </div>
  );
};

export default App;
