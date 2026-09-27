import React from 'react';
import { Check } from 'lucide-react';
import type { Stage } from '../types';

interface PipelineStepperProps {
  currentStage: Stage;
}

interface StepDef {
  key: Stage;
  label: string;
  sublabel: string;
}

const STEPS: StepDef[] = [
  { key: 'setup', label: 'Setup', sublabel: 'Workspace ready' },
  { key: 'planning', label: 'Planning', sublabel: 'Agent analyzing' },
  { key: 'executing', label: 'Tool Execution', sublabel: 'Running tests...' },
  { key: 'verifying', label: 'Verification', sublabel: 'Checking results' },
  { key: 'recovering', label: 'Recovery', sublabel: 'If needed' },
  { key: 'complete', label: 'Complete', sublabel: 'Final evaluation' },
];

export const PipelineStepper: React.FC<PipelineStepperProps> = ({ currentStage }) => {
  const stageOrder: Stage[] = ['setup', 'planning', 'executing', 'verifying', 'recovering', 'complete'];
  const currentIndex = stageOrder.indexOf(currentStage);

  return (
    <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-5 overflow-x-auto">
      <div className="flex items-center justify-between min-w-[650px] relative">
        {STEPS.map((step, idx) => {
          const isCompleted = idx < currentIndex || currentStage === 'complete';
          const isActive = idx === currentIndex && currentStage !== 'complete';

          return (
            <React.Fragment key={step.key}>
              {/* Connector line between steps */}
              {idx > 0 && (
                <div className="flex-1 h-[2px] mx-2 relative -top-3">
                  <div className="w-full h-full bg-[#1e2d42]"></div>
                  <div
                    className="absolute top-0 left-0 h-full transition-all duration-500 bg-gradient-to-r from-emerald-500 to-cyan-500"
                    style={{
                      width: isCompleted ? '100%' : isActive ? '50%' : '0%',
                    }}
                  ></div>
                </div>
              )}

              {/* Step Node */}
              <div className="flex flex-col items-center text-center shrink-0">
                <div className="relative mb-2">
                  {isCompleted ? (
                    <div className="w-7 h-7 rounded-full bg-[#0d2e2b] border border-emerald-500/80 flex items-center justify-center text-emerald-400 glow-green transition-all">
                      <Check className="w-3.5 h-3.5 stroke-[3]" />
                    </div>
                  ) : isActive ? (
                    <div className="w-7 h-7 rounded-full bg-[#08283b] border-2 border-cyan-400 flex items-center justify-center glow-teal transition-all animate-pulse">
                      <div className="w-2.5 h-2.5 rounded-full bg-cyan-400"></div>
                    </div>
                  ) : (
                    <div className="w-7 h-7 rounded-full bg-[#111927] border border-[#26374f] flex items-center justify-center text-slate-500">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#26374f]"></div>
                    </div>
                  )}
                </div>

                <div className="space-y-0.5">
                  <div
                    className={`text-xs font-semibold ${
                      isActive
                        ? 'text-cyan-400'
                        : isCompleted
                        ? 'text-slate-200'
                        : 'text-slate-500'
                    }`}
                  >
                    {step.label}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {step.sublabel}
                  </div>
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
