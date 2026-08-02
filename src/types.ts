export type OutputFormat = "markdown" | "json";
export type RunPhase = "preflight" | "integration" | "postflight";
export type ReportStatus = "finished" | "error" | "cancelled";
export type CultStatus = "finished" | "partial" | "error" | "cancelled";

export interface RoleDefinition {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly model: string;
  readonly readonly: boolean;
  readonly isBackground: boolean;
  readonly prompt: string;
  readonly filePath: string;
}

export interface RoleReport {
  readonly phase: RunPhase;
  readonly role: string;
  readonly roleName: string;
  readonly status: ReportStatus;
  readonly text: string;
  readonly startedAt: string;
  readonly finishedAt: string;
  readonly durationMs: number;
  readonly agentId?: string;
  readonly runId?: string;
  readonly error?: string;
  readonly retryable?: boolean;
  readonly warnings?: readonly string[];
  readonly usage?: {
    readonly inputTokens?: number;
    readonly outputTokens?: number;
  };
}

export interface CultRunResult {
  readonly runId: string;
  readonly task: string;
  readonly cwd: string;
  readonly model: string;
  readonly allowEdits: boolean;
  readonly maxParallel: number;
  readonly status: CultStatus;
  readonly startedAt: string;
  readonly finishedAt: string;
  readonly durationMs: number;
  readonly preflight: readonly RoleReport[];
  readonly integration: RoleReport | null;
  readonly postflight: readonly RoleReport[];
}

export interface CliOptions {
  readonly task?: string;
  readonly taskFile?: string;
  readonly cwd: string;
  readonly roleDir?: string;
  readonly preflightRoles: readonly string[];
  readonly postflightRoles: readonly string[];
  readonly integratorRole: string;
  readonly maxParallel: number;
  readonly model: string;
  readonly allowEdits: boolean;
  readonly skipIntegrator: boolean;
  readonly skipPostflight: boolean;
  readonly outputFormat: OutputFormat;
  readonly outputPath?: string;
  readonly dryRun: boolean;
  readonly listRoles: boolean;
  readonly help: boolean;
  readonly version: boolean;
}

export interface RunProgressEvent {
  readonly kind: "phase-start" | "role-start" | "role-finish" | "phase-finish";
  readonly phase: RunPhase;
  readonly role?: string;
  readonly status?: ReportStatus;
  readonly message: string;
}
