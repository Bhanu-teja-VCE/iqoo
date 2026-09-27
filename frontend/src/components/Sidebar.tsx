import React, { useState } from 'react';
import {
  LayoutDashboard,
  Play,
  FlaskConical,
  BarChart3,
  Terminal,
  GitBranch,
  CheckCircle2,
  Settings,
  ChevronDown,
  ShieldAlert
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  selectedModel,
  setSelectedModel,
}) => {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'run_task', label: 'Run Task', icon: Play },
    { id: 'experiments', label: 'Experiments', icon: FlaskConical },
    { id: 'benchmarks', label: 'Benchmarks', icon: BarChart3 },
    { id: 'executions', label: 'Executions', icon: Terminal },
    { id: 'traces', label: 'Traces', icon: GitBranch },
    { id: 'evaluation', label: 'Evaluation', icon: CheckCircle2 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const models = [
    { id: 'llama3.1:8b (local)', label: 'Local (Ollama)', sub: 'llama3.1:8b' },
    { id: 'llama-3.2-3b (groq)', label: 'Groq Cloud', sub: 'llama-3.2-3b (600 tok/s)' },
    { id: 'mock-deterministic', label: 'Mock Model', sub: 'Deterministic Scripted' },
  ];

  const currentModel = models.find((m) => m.id === selectedModel) || models[0];

  return (
    <aside className="w-64 bg-[#0a0e17] border-r border-[#1a2333] flex flex-col justify-between shrink-0 h-screen sticky top-0 select-none">
      {/* Brand Header */}
      <div>
        <div className="p-5 flex items-center space-x-3 border-b border-[#161f30]">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shadow-sm glow-teal">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
              Sentinel
            </div>
            <div className="text-[11px] text-slate-400 font-medium tracking-tight">
              Safer Agents. Stronger Software.
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="p-3 space-y-1 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 text-left ${
                  isActive
                    ? 'bg-[#182234] text-white border border-[#2a3952] shadow-sm font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#111927]'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Area: Model Selector & Promo Card */}
      <div className="p-3 space-y-3 border-t border-[#161f30] bg-[#070b12]">
        {/* Model Selector Card */}
        <div className="relative">
          <div className="text-[11px] font-medium text-slate-400 mb-1 px-1">Agent Models</div>
          <button
            onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
            className="w-full bg-[#111927] hover:bg-[#162133] border border-[#1f2c42] rounded-lg p-2.5 text-left flex items-center justify-between transition-colors"
          >
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 glow-green"></span>
              <div>
                <div className="text-xs font-semibold text-slate-200">{currentModel.label}</div>
                <div className="text-[10px] text-slate-400 font-mono">{currentModel.sub}</div>
              </div>
            </div>
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>

          {modelDropdownOpen && (
            <div className="absolute bottom-full left-0 right-0 mb-1.5 bg-[#0f172a] border border-[#24334a] rounded-lg shadow-xl overflow-hidden z-50">
              {models.map((m) => (
                <button
                  key={m.id}
                  onClick={() => {
                    setSelectedModel(m.id);
                    setModelDropdownOpen(false);
                  }}
                  className={`w-full px-3 py-2 text-left text-xs transition-colors hover:bg-[#1e293b] flex flex-col ${
                    selectedModel === m.id ? 'bg-[#1e293b] text-cyan-400 font-semibold' : 'text-slate-300'
                  }`}
                >
                  <span>{m.label}</span>
                  <span className="text-[10px] text-slate-400 font-mono">{m.sub}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Bottom promo sparkline card */}
        <div className="bg-gradient-to-b from-[#111927] to-[#0d131f] border border-[#1c273a] rounded-lg p-3 relative overflow-hidden">
          <div className="text-[11px] font-semibold text-slate-300 leading-snug">
            Building more reliable AI agents.
          </div>
          <div className="mt-2 h-8 w-full flex items-end">
            {/* SVG stylized sparkline */}
            <svg viewBox="0 0 120 30" className="w-full h-full stroke-cyan-500 fill-none" strokeWidth="2">
              <path d="M0,25 Q30,22 50,15 T90,8 T120,3" />
            </svg>
          </div>
        </div>
      </div>
    </aside>
  );
};
