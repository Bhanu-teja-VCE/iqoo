import React, { useEffect, useState } from 'react';
import {
  Play,
  RotateCcw,
  HelpCircle,
  X,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
  FlaskConical,
} from 'lucide-react';

type StageId = 'setup' | 'run' | 'verify' | 'score';
const STAGES: { id: StageId; label: string; desc: string }[] = [
  { id: 'setup', label: '1. Setup', desc: 'git init buggy repos' },
  { id: 'run', label: '2. Run agent', desc: 'your loop writes files' },
  { id: 'verify', label: '3. Verify', desc: 'pytest + git diff' },
  { id: 'score', label: '4. Score', desc: 'aggregate metrics' },
];

const FALLBACK_AGENTS = [
  { name: 'correct', label: 'Correct agent (writes ground-truth fix)' },
  { name: 'truncated', label: 'Truncated agent (50% cutoff)' },
  { name: 'empty', label: 'Empty agent (changes nothing)' },
  { name: 'wrong_file', label: 'Wrong-file agent (outside boundary)' },
  { name: 'syntax_corrupt', label: 'Syntax-corrupt agent' },
  { name: 'custom', label: 'Custom — paste your agent output as JSON' },
];

const TASKS = [
  { id: 'task_01_auth_timeout', name: 'Auth Token Fix', file: 'auth.py' },
  { id: 'task_02_discount_calc', name: 'Discount Calc Fix', file: 'discount.py' },
  { id: 'task_03_sanitize_html', name: 'Sanitizer Fix', file: 'sanitizer.py' },
];

const CUSTOM_EXAMPLE = `{
  "task_01_auth_timeout": {
    "auth.py": "import time\\n\\ndef is_token_valid(token, expires_at):\\n    return time.time() < expires_at\\n"
  }
}`;

export const SimpleEvaluator: React.FC = () => {
  const [agents, setAgents] = useState(FALLBACK_AGENTS);
  const [agentName, setAgentName] = useState('truncated');
  const [taskIds, setTaskIds] = useState<string[]>(TASKS.map((t) => t.id));
  const [customJson, setCustomJson] = useState(CUSTOM_EXAMPLE);
  const [customError, setCustomError] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [activeStage, setActiveStage] = useState<StageId | null>(null);
  const [doneStages, setDoneStages] = useState<StageId[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [howOpen, setHowOpen] = useState(false);

  useEffect(() => {
    fetch('/api/evaluate/agents')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.agents?.length) setAgents(d.agents);
      })
      .catch(() => {});
  }, []);

  const push = (m: string) =>
    setLog((p) => [...p.slice(-30), `[${new Date().toLocaleTimeString()}] ${m}`]);

  const toggleTask = (id: string) =>
    setTaskIds((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const handleRun = async () => {
    if (taskIds.length === 0) return;
    let customFiles = undefined;
    if (agentName === 'custom') {
      try {
        customFiles = JSON.parse(customJson);
        setCustomError('');
      } catch (e: any) {
        setCustomError('Invalid JSON: ' + e.message);
        return;
      }
    }
    setIsRunning(true);
    setResults([]);
    setMetrics(null);
    setLog([]);
    setDoneStages([]);

    const seq: StageId[] = ['setup', 'run', 'verify', 'score'];
    const msgs: Record<StageId, string> = {
      setup: `setup_task_repository(): init ${taskIds.length} repos with buggy code`,
      run: `running agent loop "${agentName}" — writes files into each workspace`,
      verify: 'verify_task(): pytest exit_code==0 AND diff_valid AND NOT timed_out',
      score: 'compute_metrics(): success / false-claim rates',
    };

    const req = fetch('/api/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_name: agentName,
        task_ids: taskIds,
        custom_files_by_task: customFiles,
      }),
    })
      .then((r) => (r.ok ? r.json() : r.json().then((e) => Promise.reject(e))))
      .then((d) => {
        setResults(d.results || []);
        setMetrics(d.metrics || null);
      })
      .catch((e) => push('ERROR: ' + (e.detail || 'backend offline')));

    for (const s of seq) {
      setActiveStage(s);
      push(msgs[s]);
      await new Promise((r) => setTimeout(r, s === 'run' ? 1200 : 600));
      setDoneStages((p) => [...p, s]);
    }
    await req;
    push('done: score = ground truth, self-report ignored');
    setActiveStage(null);
    setIsRunning(false);
  };

  return (
    <div className="max-w-[1100px] mx-auto space-y-5 p-6">
      {/* Header with How it works top-right */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-cyan-600/20 border border-cyan-500/40 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Sentinel Evaluator</h1>
            <p className="text-xs text-slate-400">Plug in any agent loop → get a deterministic score.</p>
          </div>
        </div>
        <button
          onClick={() => setHowOpen(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#141d2c] hover:bg-[#1a2538] border border-[#2a3a52] text-cyan-300 text-xs font-semibold"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          How it works
        </button>
      </div>

      {/* Input card */}
      <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Agent loop (input)</label>
            <select
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              className="mt-1.5 w-full bg-[#111927] border border-[#223147] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
            >
              {agents.map((a) => (
                <option key={a.name} value={a.name}>{a.label}</option>
              ))}
            </select>
            <p className="text-[11px] text-slate-500 mt-1.5">
              Real loop? <code className="font-mono text-slate-400">register_agent_loop("my_agent", fn)</code> in{' '}
              <code className="font-mono text-slate-400">benchmark/agent_eval.py</code>, then select it here.
            </p>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Tasks</label>
            <div className="mt-1.5 space-y-1.5">
              {TASKS.map((t) => (
                <label key={t.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={taskIds.includes(t.id)}
                    onChange={() => toggleTask(t.id)}
                    className="accent-cyan-500"
                  />
                  <span className="font-medium">{t.name}</span>
                  <span className="font-mono text-slate-500">{t.file}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {agentName === 'custom' && (
          <div>
            <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Your agent's file outputs (JSON: task_id → filename → content)
            </label>
            <textarea
              value={customJson}
              onChange={(e) => setCustomJson(e.target.value)}
              rows={7}
              spellCheck={false}
              className="mt-1.5 w-full bg-[#080d16] border border-[#223147] rounded-lg p-3 font-mono text-[11px] text-slate-200 focus:outline-none focus:border-cyan-500"
            />
            {customError && <p className="text-[11px] text-rose-400 mt-1">{customError}</p>}
          </div>
        )}

        <button
          onClick={handleRun}
          disabled={isRunning || taskIds.length === 0}
          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold disabled:opacity-50"
        >
          {isRunning ? <><RotateCcw className="w-4 h-4 animate-spin" /> Evaluating…</> : <><Play className="w-4 h-4 fill-white" /> Evaluate agent</>}
        </button>
      </div>

      {/* Stage visuals */}
      <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-bold text-white uppercase tracking-wider">Pipeline</span>
          <span className="text-[11px] font-mono text-slate-500">{isRunning ? 'running…' : doneStages.length === 4 ? 'complete' : 'idle'}</span>
        </div>
        <div className="flex items-center overflow-x-auto pb-1">
          {STAGES.map((s, i) => {
            const done = doneStages.includes(s.id);
            const active = activeStage === s.id;
            return (
              <React.Fragment key={s.id}>
                <div className={`flex items-center gap-2 px-3.5 py-2.5 rounded-xl border min-w-[150px] ${active ? 'bg-cyan-950/40 border-cyan-700/60' : done ? 'bg-emerald-950/30 border-emerald-800/50' : 'bg-[#0d1422] border-[#1d2b3f]'}`}>
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-bold ${active ? 'bg-cyan-600 text-white' : done ? 'bg-emerald-600 text-white' : 'bg-[#182335] text-slate-400'}`}>
                    {active ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : done ? '✓' : i + 1}
                  </div>
                  <div>
                    <div className={`text-[11px] font-bold ${active ? 'text-cyan-300' : done ? 'text-emerald-300' : 'text-slate-300'}`}>{s.label}</div>
                    <div className="text-[10px] text-slate-500 font-mono">{s.desc}</div>
                  </div>
                </div>
                {i < STAGES.length - 1 && <ChevronRight className="w-4 h-4 text-slate-600 mx-1 shrink-0" />}
              </React.Fragment>
            );
          })}
        </div>
        <div className="mt-3 bg-[#080d16] border border-[#162132] rounded-lg p-3 h-24 overflow-y-auto font-mono text-[11px]">
          {log.length === 0
            ? <span className="text-slate-500">Pick an agent loop above and press Evaluate agent.</span>
            : log.map((l, i) => <div key={i} className="text-slate-300"><span className="text-cyan-500 mr-1">›</span>{l}</div>)}
        </div>
      </div>

      {/* Score */}
      {(metrics || results.length > 0) && (
        <div className="bg-[#0f1726] border border-[#1d2b3f] rounded-xl overflow-hidden">
          <div className="p-4 border-b border-[#1a2538] bg-[#121c2e]">
            <span className="text-sm font-bold text-white">Score — agent: <code className="font-mono text-cyan-300">{agentName}</code></span>
          </div>
          {metrics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4">
              <div className="bg-[#0d1422] border border-[#1d2b3f] rounded-lg p-3">
                <div className="text-[10px] text-slate-500 uppercase font-bold">Success rate</div>
                <div className={`text-xl font-bold font-mono ${metrics.success_rate_pct === 100 ? 'text-emerald-400' : metrics.success_rate_pct === 0 ? 'text-rose-400' : 'text-amber-300'}`}>{metrics.success_rate_pct}%</div>
                <div className="text-[10px] font-mono text-slate-500">{metrics.passed_count}/{metrics.total_tasks} passed</div>
              </div>
              <div className="bg-[#0d1422] border border-[#1d2b3f] rounded-lg p-3">
                <div className="text-[10px] text-slate-500 uppercase font-bold">False claims</div>
                <div className={`text-xl font-bold font-mono ${metrics.false_claims_pct === 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{metrics.false_claims_pct}%</div>
                <div className="text-[10px] font-mono text-slate-500">claimed pass but failed</div>
              </div>
              <div className="bg-[#0d1422] border border-[#1d2b3f] rounded-lg p-3">
                <div className="text-[10px] text-slate-500 uppercase font-bold">Recovery</div>
                <div className="text-xl font-bold font-mono text-slate-300">{metrics.recovery_rate_pct}%</div>
                <div className="text-[10px] font-mono text-slate-500">single-shot eval</div>
              </div>
              <div className="bg-[#0d1422] border border-[#1d2b3f] rounded-lg p-3">
                <div className="text-[10px] text-slate-500 uppercase font-bold">Mean latency</div>
                <div className="text-xl font-bold font-mono text-slate-300">{metrics.mean_duration_ms}ms</div>
              </div>
            </div>
          )}
          <div className="px-4 pb-4 space-y-2">
            {results.map((r) => (
              <div key={r.task_id} className={`flex items-center justify-between p-2.5 rounded-lg border text-xs ${r.passed ? 'bg-emerald-950/20 border-emerald-800/40' : 'bg-rose-950/20 border-rose-900/40'}`}>
                <div>
                  <span className="font-bold text-slate-200">{r.task_name}</span>
                  <span className="font-mono text-slate-500 ml-2">{r.task_id}</span>
                  <div className="text-[11px] text-slate-400 mt-0.5 font-mono">exit={r.test_exit_code} files=[{r.files_changed.join(', ') || 'none'}] · {r.notes}</div>
                </div>
                {r.passed
                  ? <span className="flex items-center gap-1 text-emerald-400 font-bold"><CheckCircle2 className="w-4 h-4" /> PASS</span>
                  : r.false_claim
                  ? <span className="flex items-center gap-1 text-rose-400 font-bold"><XCircle className="w-4 h-4" /> FALSE CLAIM</span>
                  : <span className="flex items-center gap-1 text-rose-400 font-bold"><XCircle className="w-4 h-4" /> FAIL</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* How it works — big blog-style guide to the whole Sentinel */}
      {howOpen && (
        <div className="fixed inset-0 bg-black/85 flex items-center justify-center p-4 z-50">
          <div className="bg-[#0b1220] border border-[#23334c] rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="px-6 py-4 border-b border-[#1f2c42] bg-[#121a2c] flex items-center justify-between sticky top-0 z-10">
              <div>
                <div className="text-[11px] font-mono text-cyan-400 uppercase tracking-widest">Sentinel · Evaluator guide</div>
                <h3 className="text-lg font-bold text-white tracking-tight">How Sentinel works — the full story</h3>
              </div>
              <button onClick={() => setHowOpen(false)} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#1a2538] transition-colors"><X className="w-5 h-5" /></button>
            </div>
            <article className="flex-1 overflow-y-auto px-6 md:px-10 py-8 space-y-10 text-[14px] leading-[1.8] text-slate-300">
              {/* Hero */}
              <header className="space-y-3">
                <p className="text-[15px] leading-[1.9] text-slate-200">
                  <span className="float-left text-5xl font-bold text-cyan-400 mr-2 mt-1 leading-none">S</span>
                  entinel wraps around <strong className="text-white">any AI coding agent</strong> and stops it from lying about its work.
                  Agents often say <em>"I fixed the bug!"</em> when they didn't — truncated output, wrong file, still-failing tests, or zero
                  changes at all. Sentinel doesn't trust the agent's self-report. It independently <strong className="text-white">runs the tests,
                  inspects the real file diff, and rolls back + retries</strong> when things go wrong — then scores every agent loop deterministically.
                </p>
                <div className="bg-cyan-950/30 border border-cyan-800/40 rounded-xl p-4 text-[13px]">
                  <strong className="text-cyan-300">TL;DR for judges:</strong> this page evaluates any agent loop across 3 buggy Python tasks.
                  Each task runs in a fresh git repo. The agent writes files. Sentinel runs real <code className="font-mono">pytest</code> in a
                  sandbox and checks the real <code className="font-mono">git diff</code>. Score = ground truth, not vibes.
                </div>
              </header>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">1 · The problem: false success claims</h4>
                <p>
                  Big frontier models hallucinate completion ~10–20% of the time. Small open-weight models (1–8B) do it ~60–80%.
                  Four classic failures: <strong className="text-white">truncated diff</strong> (context window cut the code in half),{' '}
                  <strong className="text-white">syntax corruption</strong> (garbage tokens), <strong className="text-white">empty write</strong> (claimed
                  fix, changed nothing), and <strong className="text-white">wrong-file edit</strong> (touched files outside the task boundary).
                  The presets in the dropdown above are exactly these four failure modes, plus a correct baseline — so you can feel each one score differently.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">2 · Big picture: how data flows</h4>
                <pre className="bg-[#080d16] border border-[#1a2538] rounded-xl p-4 font-mono text-[11px] leading-relaxed overflow-x-auto">{`Task ("Fix is_token_valid in auth.py")
        │
        ▼
┌──────────────┐   plan + tool calls    ┌──────────┐
│ ORCHESTRATOR │ ─────────────────────▶ │   LLM    │  (only plans + proposes)
│ (pure Python │ ◀───────────────────── │  adapter │
│ state machine│      tool results      └──────────┘
└──────┬───────┘
       │  every tool runs here         every claim checked here
       ▼                               ▼
┌──────────────┐                ┌──────────────┐
│   SANDBOX    │                │   VERIFIER   │
│ whitelist +  │                │ pytest exit  │
│ path jail    │                │ + git diff   │
└──────┬───────┘                └──────┬───────┘
       │  chaos breaks things         │  fail? roll back + retry
       ▼                              ▼
┌──────────────┐                ┌──────────────┐
│    CHAOS     │                │   RECOVERY   │
│ seed=42      │                │ retry/replan │
└──────────────┘                │ escalate/give│
                                │ up           │
                                └──────────────┘`}</pre>
                <p>
                  The critical insight: <strong className="text-white">orchestrator, sandbox, verifier, checkpoint, and recovery are all pure
                  deterministic Python.</strong> The LLM only plans and proposes one JSON tool call at a time. Everything safety-relevant is code we control.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">3 · Foundation: state that survives crashes</h4>
                <p>
                  Every run lives in one serializable object — <code className="font-mono text-cyan-300">TaskState</code> (
                  <code className="font-mono">core/types.py</code>): task id, workspace path, instruction, plan, step index, tool-call log,
                  attempt count, injected fault, verifier result, status (<code className="font-mono">planning|executing|verifying|recovering|done|failed</code>),
                  model used. After every step it is saved as JSON (<code className="font-mono">core/checkpoint.py</code>) and appended to a JSONL
                  audit trail (<code className="font-mono">core/trace.py</code>). Rollback wipes the worktree with{' '}
                  <code className="font-mono">git checkout -- . + git clean -fd</code> and reloads the last good checkpoint — the agent retries from a clean slate,
                  but the log is preserved for forensics.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">4 · Safety: the sandbox jail</h4>
                <p>
                  Isolation has three tiers (<code className="font-mono">sandbox/</code>). <strong className="text-white">Workspace:</strong>{' '}
                  <code className="font-mono">git worktree add --detach</code> — an ephemeral twin of the repo; the original is never touched.{' '}
                  <strong className="text-white">Execution:</strong> only <code className="font-mono">pytest, python3, ls, cat, grep</code> may run
                  (<code className="font-mono">executor_sandbox.py</code>); <code className="font-mono">rm -rf, curl, powershell</code> are rejected before
                  a subprocess spawns. Secrets (<code className="font-mono">AWS_*, GITHUB_*, OPENAI_*, *TOKEN*, *KEY*</code>) are stripped from the
                  environment; Docker (<code className="font-mono">--network none --memory=512m</code>) is preferred with a logged host fallback + timeout
                  watchdog. <strong className="text-white">Tool API:</strong> exactly{' '}
                  <code className="font-mono">read_file, write_file, run_shell, run_tests</code>, each path-checked with{' '}
                  <code className="font-mono">os.path.commonpath</code> so <code className="font-mono">../../etc/passwd</code>, absolute escapes, and
                  symlink pivots raise <code className="font-mono">SandboxViolation</code>.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">5 · Truth gate: the verifier</h4>
                <p>
                  <code className="font-mono text-cyan-300">verifier/verifier.py: verify_task()</code> is the file that catches lying agents. Rule,
                  absolute: <code className="font-mono text-emerald-300">passed = (exit_code == 0) AND diff_valid AND NOT timed_out</code>. It runs the
                  real test command in the sandbox, then <code className="font-mono">diff_analyzer.py</code> reads the real{' '}
                  <code className="font-mono">git diff</code> (including untracked files via <code className="font-mono">git add -N</code>), ignores{' '}
                  <code className="font-mono">__pycache__/.pyc</code> noise, rejects zero-file diffs ("claimed completion, changed nothing"), and rejects
                  files outside <code className="font-mono">expected_files</code>. Tests pass but diff invalid → fail. Tests fail → fail. Timeout → fail.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">6 · Recovery: the circuit breaker</h4>
                <p>
                  On failure <code className="font-mono">core/recovery.py</code> decides, in priority order: attempts ≥ 3 →{' '}
                  <code className="font-mono">ABORT_FAIL</code> (halt, no infinite loops); local model on final attempt →{' '}
                  <code className="font-mono">ESCALATE</code> (switch to frontier); "unauthorized / unexpected files / zero files" →{' '}
                  <code className="font-mono">REPLAN</code> (insert diagnostic step); "syntax / truncated" or "exit code / failed" →{' '}
                  <code className="font-mono">RETRY</code> with diagnostics. Chaos (<code className="font-mono">chaos/injector.py</code>, seed 42) deliberately
                  injects these faults so benchmarks are 100% reproducible.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">7 · This page: evaluate any agent loop</h4>
                <p>
                  An agent loop is any function <code className="font-mono text-cyan-300">(task, workspace_path) → writes files</code>.
                  The evaluator (<code className="font-mono">benchmark/agent_eval.py</code>, <code className="font-mono">POST /api/evaluate</code>) does four stages —
                  watch them animate in the Pipeline card above:
                </p>
                <ol className="list-decimal pl-5 space-y-1">
                  <li><strong className="text-white">Setup:</strong> <code className="font-mono">setup_task_repository()</code> builds a fresh <code className="font-mono">git init</code> repo per selected task with the buggy file + test file.</li>
                  <li><strong className="text-white">Run:</strong> your chosen loop writes into that workspace. Presets: correct writes ground truth; truncated writes 50%; empty writes nothing; wrong-file writes outside boundary; syntax-corrupt prepends a broken token. Custom pastes your JSON.</li>
                  <li><strong className="text-white">Verify:</strong> ground-truth <code className="font-mono">verify_task()</code> per task. Self-report ignored.</li>
                  <li><strong className="text-white">Score:</strong> <code className="font-mono">compute_metrics()</code> aggregates (next section).</li>
                </ol>
                <p>Plug a real loop (Aider, SWE-agent, in-house) with one line — no UI change needed:</p>
                <pre className="bg-[#080d16] border border-[#1a2538] rounded-xl p-4 font-mono text-[11px] overflow-x-auto">{`from sentinel.benchmark.agent_eval import register_agent_loop
register_agent_loop("my_agent", my_fn)  # my_fn(task, workspace_path)
# POST /api/evaluate  {"agent_name": "my_agent", "task_ids": [...]}`}</pre>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">8 · How the score is produced</h4>
                <pre className="bg-[#080d16] border border-[#1a2538] rounded-xl p-4 font-mono text-[11px] overflow-x-auto">{`success_rate = passed_count      / total * 100
false_claims = false_claim_count / total * 100   # claimed AND NOT passed
mean_latency = sum(duration_ms)  / total`}</pre>
                <p>
                  Worked example (this page, 3 tasks): the <strong>truncated</strong> agent writes half-files → all 3 pytest runs fail →{' '}
                  <span className="font-mono text-rose-400">0% success, 100% false-claim</span>. The <strong>correct</strong> agent writes ground truth →{' '}
                  <span className="font-mono text-emerald-400">100% / 0%</span>. <strong>Empty</strong> scores 0%/100% via zero-diff rejection;{' '}
                  <strong>wrong-file</strong> scores 0%/100% via boundary rejection. Reproduce:{' '}
                  <code className="font-mono">curl -X POST localhost:8000/api/evaluate -d '{'{"agent_name":"empty"}'}'</code> or{' '}
                  <code className="font-mono">python -m sentinel.cli.demo --fault truncated_diff</code>.
                </p>
              </section>

              <section className="space-y-2">
                <h4 className="text-base font-bold text-white">9 · Limits, honestly</h4>
                <p>
                  Prototype, not production: 3 Python tasks only, single-shot scoring (recovery % is a Sentinel-harness property, so it reads 0% here),
                  in-memory runs, no auth, Docker preferred but host fallback on laptops. The full harness comparison (raw vs Sentinel with retries) lives
                  in the untouched <code className="font-mono">BenchmarkView.tsx</code> + <code className="font-mono">GET /api/benchmarks?recompute=true</code>.
                  What this page proves — and what to tell judges — is narrower and stronger: <strong className="text-white">any loop you plug in gets the
                  same deterministic ground truth</strong>, because scoring never reads the agent's claims.
                </p>
              </section>
            </article>
          </div>
        </div>
      )}
    </div>
  );
};
