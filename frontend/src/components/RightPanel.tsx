import React, { useState } from 'react';
import {
  Clock,
  Wrench,
  FlaskConical,
  FileCode,
  Coins,
  FileText,
  Lightbulb
} from 'lucide-react';
import type { Metrics, Stage } from '../types';

interface RightPanelProps {
  stage: Stage;
  progress: number;
  elapsedSeconds: number;
  metrics: Metrics;
  diff: string;
  faultType: string;
}

export const RightPanel: React.FC<RightPanelProps> = ({
  stage,
  progress,
  elapsedSeconds,
  metrics,
  diff,
  faultType,
}) => {
  const [activeDiffTab, setActiveDiffTab] = useState<'diff' | 'files' | 'commits'>('diff');

  const formatElapsed = (sec: number) => {
    const hours = Math.floor(sec / 3600);
    const minutes = Math.floor((sec % 3600) / 60);
    const seconds = sec % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(
      seconds
    ).padStart(2, '0')}`;
  };

  const getStageTitle = (s: Stage) => {
    switch (s) {
      case 'setup':
        return { title: 'Setup', sub: 'Initializing workspace...' };
      case 'planning':
        return { title: 'Planning', sub: 'Analyzing task instruction...' };
      case 'executing':
        return { title: 'Tool Execution', sub: 'Running tests & code edits...' };
      case 'verifying':
        return { title: 'Verification', sub: 'Validating real test exit code...' };
      case 'recovering':
        return { title: 'Recovery', sub: 'Resolving injected failure...' };
      case 'complete':
        return { title: 'Complete', sub: 'Deterministic verification passed' };
    }
  };

  const stageInfo = getStageTitle(stage);

  // Circular progress math (radius = 38, perimeter = 2 * PI * 38 ≈ 238.76)
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  return (
    <div className="space-y-4 flex flex-col">
      {/* 1. Task Status Circular Progress Card */}
      <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-4 shadow-sm">
        <h3 className="text-xs font-bold text-slate-300 mb-3 uppercase tracking-wider">
          Task Status
        </h3>

        <div className="flex items-center space-x-4">
          {/* Circular Donut Gauge */}
          <div className="relative w-24 h-24 shrink-0 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 96 96">
              {/* Background ring */}
              <circle
                cx="48"
                cy="48"
                r={radius}
                className="stroke-[#182335]"
                strokeWidth="7"
                fill="transparent"
              />
              {/* Progress ring */}
              <circle
                cx="48"
                cy="48"
                r={radius}
                className="stroke-cyan-400 transition-all duration-500 ease-out"
                strokeWidth="7"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                fill="transparent"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xl font-extrabold text-white font-mono">{progress}%</span>
            </div>
          </div>

          {/* Stage details & Elapsed Time */}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-white tracking-tight truncate">
              {stageInfo.title}
            </div>
            <div className="text-[11px] text-slate-400 truncate mt-0.5">
              {stageInfo.sub}
            </div>

            <div className="mt-3 pt-2.5 border-t border-[#182335] flex items-center space-x-1.5 text-slate-400">
              <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="text-[11px] font-medium">Elapsed Time</span>
              <span className="text-xs font-mono font-bold text-white ml-auto">
                {formatElapsed(elapsedSeconds)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Live Metrics Card (4-grid) */}
      <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-4 shadow-sm">
        <h3 className="text-xs font-bold text-slate-300 mb-3 uppercase tracking-wider">
          Metrics (Live)
        </h3>

        <div className="grid grid-cols-2 gap-3">
          {/* Tool Calls */}
          <div className="bg-[#111927] border border-[#1b263a] rounded-lg p-3 flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-[#182335] text-cyan-400 flex items-center justify-center shrink-0">
              <Wrench className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Tool Calls</div>
              <div className="text-sm font-bold text-white font-mono mt-0.5">
                {metrics.tool_calls}
              </div>
            </div>
          </div>

          {/* Test Runs */}
          <div className="bg-[#111927] border border-[#1b263a] rounded-lg p-3 flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-[#1e1e38] text-purple-400 flex items-center justify-center shrink-0">
              <FlaskConical className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Test Runs</div>
              <div className="text-sm font-bold text-white font-mono mt-0.5">
                {metrics.test_runs}
              </div>
            </div>
          </div>

          {/* Files Modified */}
          <div className="bg-[#111927] border border-[#1b263a] rounded-lg p-3 flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-[#0d2a2a] text-emerald-400 flex items-center justify-center shrink-0">
              <FileCode className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Files Modified</div>
              <div className="text-sm font-bold text-white font-mono mt-0.5">
                {metrics.files_modified}
              </div>
            </div>
          </div>

          {/* Tokens (est.) */}
          <div className="bg-[#111927] border border-[#1b263a] rounded-lg p-3 flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-[#271d3a] text-pink-400 flex items-center justify-center shrink-0">
              <Coins className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium">Tokens (est.)</div>
              <div className="text-sm font-bold text-white font-mono mt-0.5">
                {metrics.tokens_est > 999
                  ? `${(metrics.tokens_est / 1000).toFixed(1)}K`
                  : metrics.tokens_est}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Workspace Changes (Diff / Files / Commits) */}
      <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-4 shadow-sm flex-1 flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Workspace Changes
          </h3>
          <span className="text-[11px] text-slate-500 font-medium">
            {diff ? '1 file modified' : 'No changes yet'}
          </span>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center space-x-1 p-1 bg-[#121a29] border border-[#1e2a3c] rounded-lg mb-3">
          {(['diff', 'files', 'commits'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveDiffTab(tab)}
              className={`flex-1 py-1 text-center text-xs rounded font-medium capitalize transition-all ${
                activeDiffTab === tab
                  ? 'bg-cyan-900/60 text-cyan-300 font-semibold shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Diff Content Viewer */}
        <div className="flex-1 bg-[#090e18] border border-[#182335] rounded-lg p-3 overflow-y-auto font-mono text-[11px] min-h-[140px] max-h-[220px]">
          {diff ? (
            <pre className="text-slate-300 whitespace-pre-wrap leading-relaxed">
              {diff.split('\n').map((line, i) => {
                if (line.startsWith('+') && !line.startsWith('+++')) {
                  return (
                    <div key={i} className="text-emerald-400 bg-emerald-950/20 px-1 rounded">
                      {line}
                    </div>
                  );
                } else if (line.startsWith('-') && !line.startsWith('---')) {
                  return (
                    <div key={i} className="text-rose-400 bg-rose-950/20 px-1 rounded">
                      {line}
                    </div>
                  );
                } else if (line.startsWith('@@')) {
                  return (
                    <div key={i} className="text-cyan-400 opacity-75">
                      {line}
                    </div>
                  );
                }
                return <div key={i}>{line}</div>;
              })}
            </pre>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center p-4">
              <FileText className="w-8 h-8 text-slate-600 mb-2" />
              <div className="text-xs font-semibold text-slate-400">No changes yet</div>
              <p className="text-[10px] text-slate-500 mt-1 max-w-[200px]">
                File modifications will appear here after the agent makes changes.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 4. Controlled Failure Active Alert */}
      <div className="bg-gradient-to-r from-[#19102c] to-[#141029] border border-purple-800/60 rounded-xl p-3.5 flex items-start space-x-3 glow-purple">
        <div className="w-7 h-7 rounded-lg bg-purple-900/60 text-purple-300 flex items-center justify-center shrink-0 mt-0.5">
          <Lightbulb className="w-4 h-4" />
        </div>
        <div>
          <div className="text-xs font-bold text-white tracking-tight">
            Controlled Failure Active
          </div>
          <p className="text-[11px] text-purple-200/80 mt-0.5 leading-relaxed">
            A {faultType.replace('_', ' ')} is injected on the first run_tests call to test the agent's recovery behavior.
          </p>
        </div>
      </div>
    </div>
  );
};
