import React, { useState, useEffect, useRef } from 'react';
import {
  ExternalLink,
  Play,
  FolderGit2,
  Brain,
  Wrench,
  Check,
  AlertTriangle,
  XCircle,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  Copy
} from 'lucide-react';
import type { ConsoleEvent, EventType } from '../types';

interface LiveConsoleProps {
  events: ConsoleEvent[];
  isAgentWorking: boolean;
  onViewFullTrace: () => void;
}

export const LiveConsole: React.FC<LiveConsoleProps> = ({
  events,
  isAgentWorking,
  onViewFullTrace,
}) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const consoleBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && consoleBottomRef.current) {
      consoleBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  const copyTrace = () => {
    const text = events
      .map((e) => `[${e.timestamp}] ${e.type}: ${e.message}`)
      .join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getEventBadge = (type: EventType) => {
    switch (type) {
      case 'TASK_STARTED':
        return {
          icon: Play,
          color: 'text-emerald-400',
          bg: 'bg-emerald-950/30',
          label: 'TASK_STARTED',
        };
      case 'WORKSPACE_READY':
        return {
          icon: FolderGit2,
          color: 'text-teal-400',
          bg: 'bg-teal-950/30',
          label: 'WORKSPACE_READY',
        };
      case 'AGENT_THOUGHT':
        return {
          icon: Brain,
          color: 'text-purple-400',
          bg: 'bg-purple-950/30',
          label: 'AGENT_THOUGHT',
        };
      case 'TOOL_REQUESTED':
        return {
          icon: Wrench,
          color: 'text-cyan-400',
          bg: 'bg-cyan-950/30',
          label: 'TOOL_REQUESTED',
        };
      case 'TOOL_COMPLETED':
        return {
          icon: Check,
          color: 'text-emerald-400',
          bg: 'bg-emerald-950/30',
          label: 'TOOL_COMPLETED',
        };
      case 'FAILURE_INJECTED':
        return {
          icon: AlertTriangle,
          color: 'text-rose-400',
          bg: 'bg-rose-950/40',
          label: 'FAILURE_INJECTED',
        };
      case 'TOOL_FAILED':
        return {
          icon: XCircle,
          color: 'text-rose-500',
          bg: 'bg-rose-950/50',
          label: 'TOOL_FAILED',
        };
      case 'RECOVERY_TRIGGERED':
        return {
          icon: RefreshCw,
          color: 'text-amber-400',
          bg: 'bg-amber-950/30',
          label: 'RECOVERY_TRIGGERED',
        };
      case 'VERIFICATION':
        return {
          icon: ShieldCheck,
          color: 'text-cyan-300',
          bg: 'bg-cyan-950/40',
          label: 'VERIFICATION',
        };
      case 'VERIFICATION_PASSED':
      case 'COMPLETE':
        return {
          icon: Check,
          color: 'text-emerald-400',
          bg: 'bg-emerald-950/40',
          label: 'VERIFICATION_PASSED',
        };
      default:
        return {
          icon: Play,
          color: 'text-slate-400',
          bg: 'bg-slate-900',
          label: type,
        };
    }
  };

  return (
    <div className="bg-[#0b101b] border border-[#1d2b3f] rounded-xl flex flex-col justify-between overflow-hidden shadow-lg h-[560px]">
      {/* Console Header */}
      <div className="p-4 border-b border-[#1a2538] flex flex-wrap items-center justify-between gap-3 bg-[#0d1322]">
        <div>
          <h2 className="text-sm font-bold text-white tracking-tight">Live Execution</h2>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Real-time view of agent activity, tool calls, and system events
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-3">
          {/* Auto-scroll toggle */}
          <div className="flex items-center space-x-2 text-xs text-slate-300 select-none">
            <span className="text-[11px] font-medium text-slate-400">Auto-scroll</span>
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-200 flex items-center ${
                autoScroll ? 'bg-cyan-600 justify-end' : 'bg-slate-700 justify-start'
              }`}
            >
              <div className="w-4 h-4 rounded-full bg-white shadow-sm"></div>
            </button>
          </div>

          {/* Copy Button */}
          <button
            onClick={copyTrace}
            className="flex items-center space-x-1 px-2.5 py-1 rounded-md bg-[#162132] hover:bg-[#1e2c44] border border-[#27374f] text-[11px] text-slate-300 font-medium transition-colors"
          >
            <Copy className="w-3 h-3" />
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          {/* View Full Trace link button */}
          <button
            onClick={onViewFullTrace}
            className="flex items-center space-x-1 px-3 py-1 rounded-md bg-[#162132] hover:bg-[#1e2c44] border border-[#27374f] text-[11px] text-slate-200 font-medium transition-colors"
          >
            <span>View Full Trace</span>
            <ExternalLink className="w-3 h-3 text-slate-400" />
          </button>
        </div>
      </div>

      {/* Log Feed Area */}
      <div className="flex-1 p-4 font-mono text-xs overflow-y-auto space-y-2 select-text bg-[#080d16]">
        {events.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500 text-xs italic">
            Waiting for task to begin...
          </div>
        ) : (
          events.map((ev) => {
            const badge = getEventBadge(ev.type);
            const Icon = badge.icon;

            return (
              <div
                key={ev.id}
                className="flex items-start space-x-3 py-1 px-2 rounded hover:bg-[#0f1726]/60 transition-colors leading-relaxed"
              >
                {/* Timestamp */}
                <span className="text-slate-500 shrink-0 text-[11px] select-none pt-0.5 font-mono">
                  {ev.timestamp}
                </span>

                {/* Badge Tag */}
                <span
                  className={`inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase shrink-0 border border-current/20 ${badge.color} ${badge.bg}`}
                >
                  <Icon className="w-3 h-3" />
                  <span>{badge.label}</span>
                </span>

                {/* Event Message */}
                <span
                  className={`flex-1 break-all text-[11px] ${
                    ev.type === 'FAILURE_INJECTED' || ev.type === 'TOOL_FAILED'
                      ? 'text-rose-300 font-medium'
                      : ev.type === 'AGENT_THOUGHT'
                      ? 'text-purple-300 italic'
                      : ev.type === 'TOOL_REQUESTED'
                      ? 'text-cyan-200'
                      : ev.type === 'VERIFICATION' || ev.type === 'VERIFICATION_PASSED'
                      ? 'text-emerald-300 font-medium'
                      : 'text-slate-300'
                  }`}
                >
                  {ev.message}
                </span>
              </div>
            );
          })
        )}
        <div ref={consoleBottomRef} />
      </div>

      {/* Bottom Status Notification Bar */}
      <div className="p-3 bg-[#0d1626] border-t border-[#1d2b3f] flex items-center space-x-3">
        <div className="w-7 h-7 rounded-lg bg-cyan-950/80 border border-cyan-500/50 flex items-center justify-center text-cyan-400 shrink-0">
          <Sparkles className="w-4 h-4 animate-spin-slow" />
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-200">
            {isAgentWorking ? 'Agent is working...' : 'Task ready'}
          </div>
          <p className="text-[11px] text-slate-400">
            {isAgentWorking
              ? 'This may take a few minutes. You can monitor progress here.'
              : 'Execution finished. Review metrics and verification results.'}
          </p>
        </div>
      </div>
    </div>
  );
};
