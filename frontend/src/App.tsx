import React from 'react';
import { SimpleEvaluator } from './components/SimpleEvaluator';

// Simple single-page evaluator UI.
// NOTE: BenchmarkView.tsx (old full dashboard) is left untouched in
// components/ for reference, but is no longer mounted.
export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 font-sans antialiased">
      <SimpleEvaluator />
    </div>
  );
};
export default App;
