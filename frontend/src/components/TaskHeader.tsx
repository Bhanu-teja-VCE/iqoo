import React from 'react';
import {
  Layers,
  Pause,
  Play,
  Square,
  Moon,
  ArrowUpRight
} from 'lucide-react';
import type { TaskMetadata } from '../types';

interface TaskHeaderProps {
  task: TaskMetadata;
  status: 'running' | 'paused' | 'stopped' | 'done' | 'failed' | 'idle';
  onPauseToggle: () => void;
  onStop: () => void;
  onStart: (useRealExecution?: boolean) => void;
  selectedModel: string;
}

export const TaskHeader: React.FC<TaskHeaderProps> = ({
  task,
  status,
  onPauseToggle,
  onStop,
  onStart,
  selectedModel,
}) => {
  return (
    <div className="space-y-4">
      {/* Top Title & Control Actions Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Run Task</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure and run a coding task with Sentinel
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2.5">
          {/* Status Badge */}
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#0d2228] border border-cyan-800/60 text-cyan-300 text-xs font-semibold shadow-sm">
            <span
              className={`w-2 h-2 rounded-full ${
                status === 'running'
                  ? 'bg-emerald-400 animate-pulse glow-green'
                  : status === 'paused'
                  ? 'bg-amber-400'
                  : status === 'done'
                  ? 'bg-emerald-400'
                  : 'bg-red-400'
              }`}
            ></span>
            <span className="capitalize">
              {status === 'running'
                ? 'Execution Running'
                : status === 'paused'
                ? 'Execution Paused'
                : status === 'done'
                ? 'Execution Complete'
                : status === 'stopped'
                ? 'Execution Stopped'
                : 'Ready'}
            </span>
          </div>

          {/* Pause / Resume Button */}
          {status === 'running' ? (
            <button
              onClick={onPauseToggle}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#141d2c] hover:bg-[#1a2538] border border-[#233147] text-slate-200 text-xs font-medium transition-colors"
            >
              <Pause className="w-3.5 h-3.5" />
              <span>Pause</span>
            </button>
          ) : status === 'paused' ? (
            <button
              onClick={onPauseToggle}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#141d2c] hover:bg-[#1a2538] border border-[#233147] text-emerald-400 text-xs font-medium transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Resume</span>
            </button>
          ) : (
            <>
              <button
                onClick={() => onStart(false)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition-colors shadow-sm"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Demo Run</span>
              </button>
              <button
                onClick={() => onStart(true)}
                title="Run real Sentinel harness (run_task_loop + pytest + git diff)"
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors shadow-sm"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Real Run</span>
              </button>
            </>
          )}

          {/* Stop Button */}
          <button
            onClick={onStop}
            disabled={status === 'stopped' || status === 'done'}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#251318] hover:bg-[#341821] border border-[#4a1c27] text-rose-300 text-xs font-medium transition-colors disabled:opacity-50"
          >
            <Square className="w-3.5 h-3.5 fill-rose-400 text-rose-400" />
            <span>Stop</span>
          </button>

          {/* Theme Toggle Button */}
          <button
            aria-label="Theme toggle"
            className="p-2 rounded-lg bg-[#111927] border border-[#1e2a3c] text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Moon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Task Meta Details Row (2 Side-by-Side Cards) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Repo & Commit Details */}
        <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-start space-x-3">
            <div className="w-10 h-10 rounded-lg bg-[#182335] border border-[#273852] flex items-center justify-center text-slate-200 shrink-0">
              <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-base font-bold text-white tracking-tight">{task.name}</span>
                <span className="px-2 py-0.5 rounded-md bg-[#162132] border border-[#273852] text-[11px] font-mono text-slate-300 font-medium">
                  {task.language}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                {task.instruction}
              </p>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-[#182335] flex items-center space-x-3 text-[11px] font-mono text-slate-400">
            <span>Task ID: <strong className="text-slate-300">{task.id}</strong></span>
            <span>•</span>
            <span>Commit: <strong className="text-slate-300">{task.commit}</strong></span>
            <span>•</span>
            <span>Model: <strong className="text-cyan-400">{selectedModel}</strong></span>
          </div>
        </div>

        {/* Task Objective Details */}
        <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-start space-x-3">
            <div className="w-10 h-10 rounded-lg bg-[#0e2238] border border-cyan-800/60 flex items-center justify-center text-cyan-400 shrink-0">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Task
              </div>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                {task.instruction}
              </p>
            </div>
          </div>

          <div className="mt-3 pt-3 border-t border-[#182335] flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              Target files: <code className="text-slate-300 font-mono">{task.expected_files.join(', ')}</code>
            </span>
            <button className="text-[11px] text-cyan-400 hover:text-cyan-300 font-medium flex items-center space-x-0.5 transition-colors">
              <span>View full description</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
