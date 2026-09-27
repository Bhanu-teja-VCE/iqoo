export type Stage = 'setup' | 'planning' | 'executing' | 'verifying' | 'recovering' | 'complete';

export type EventType =
  | 'TASK_STARTED'
  | 'WORKSPACE_READY'
  | 'AGENT_THOUGHT'
  | 'TOOL_REQUESTED'
  | 'TOOL_COMPLETED'
  | 'FAILURE_INJECTED'
  | 'TOOL_FAILED'
  | 'RECOVERY_TRIGGERED'
  | 'VERIFICATION'
  | 'VERIFICATION_PASSED'
  | 'COMPLETE'
  | 'RUN_PAUSED'
  | 'RUN_RESUMED'
  | 'RUN_STOPPED';

export interface ConsoleEvent {
  id: string;
  timestamp: string;
  type: EventType;
  message: string;
  stage: Stage;
  progress?: number;
  payload?: any;
}

export interface TaskMetadata {
  id: string;
  name: string;
  repo: string;
  language: string;
  commit: string;
  instruction: string;
  expected_files: string[];
  default_fault: string;
}

export interface Metrics {
  tool_calls: number;
  test_runs: number;
  files_modified: number;
  tokens_est: number;
}
