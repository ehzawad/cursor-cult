import { randomUUID } from "node:crypto";

import { mapLimit } from "./pool.js";
import { buildIntegratorPrompt, buildPostflightPrompt, buildRolePrompt } from "./prompts.js";
import { ActiveRunRegistry, runSdkRole } from "./sdk-runner.js";
import type {
  CultRunResult,
  CultStatus,
  RoleDefinition,
  RoleReport,
  RunPhase,
  RunProgressEvent,
} from "./types.js";

interface OrchestratorInput {
  readonly task: string;
  readonly cwd: string;
  readonly model: string;
  readonly apiKey: string;
  readonly allowEdits: boolean;
  readonly maxParallel: number;
  readonly preflightRoles: readonly RoleDefinition[];
  readonly integratorRole: RoleDefinition | null;
  readonly postflightRoles: readonly RoleDefinition[];
  readonly registry: ActiveRunRegistry;
  readonly signal?: AbortSignal;
  readonly onProgress?: (event: RunProgressEvent) => void;
}

function progress(
  callback: OrchestratorInput["onProgress"],
  event: RunProgressEvent,
): void {
  callback?.(event);
}

async function runPhase(input: {
  readonly phase: RunPhase;
  readonly roles: readonly RoleDefinition[];
  readonly concurrency: number;
  readonly orchestrator: OrchestratorInput;
  readonly promptFor: (role: RoleDefinition) => string;
}): Promise<RoleReport[]> {
  const { orchestrator } = input;
  progress(orchestrator.onProgress, {
    kind: "phase-start",
    phase: input.phase,
    message: `${input.phase}: launching ${input.roles.length} role(s)`,
  });

  const reports = await mapLimit(
    input.roles,
    input.concurrency,
    async (role) => {
      progress(orchestrator.onProgress, {
        kind: "role-start",
        phase: input.phase,
        role: role.id,
        message: `${input.phase}/${role.id}: started`,
      });
      const report = await runSdkRole({
        role,
        phase: input.phase,
        prompt: input.promptFor(role),
        cwd: orchestrator.cwd,
        model: orchestrator.model,
        apiKey: orchestrator.apiKey,
        registry: orchestrator.registry,
        ...(orchestrator.signal === undefined ? {} : { signal: orchestrator.signal }),
      });
      progress(orchestrator.onProgress, {
        kind: "role-finish",
        phase: input.phase,
        role: role.id,
        status: report.status,
        message: `${input.phase}/${role.id}: ${report.status} in ${report.durationMs}ms`,
      });
      return report;
    },
  );

  progress(orchestrator.onProgress, {
    kind: "phase-finish",
    phase: input.phase,
    message: `${input.phase}: complete`,
  });
  return reports;
}

function computeStatus(input: {
  readonly aborted: boolean;
  readonly preflight: readonly RoleReport[];
  readonly integration: RoleReport | null;
  readonly postflight: readonly RoleReport[];
}): CultStatus {
  if (input.aborted) return "cancelled";
  if (input.integration?.status === "error" || input.integration?.status === "cancelled") {
    return input.integration.status === "cancelled" ? "cancelled" : "error";
  }
  const all = [...input.preflight, ...input.postflight];
  if (all.length > 0 && all.every((report) => report.status !== "finished")) return "error";
  if (all.some((report) => report.status !== "finished")) return "partial";
  return "finished";
}

export async function runCult(input: OrchestratorInput): Promise<CultRunResult> {
  const started = Date.now();
  const startedAt = new Date(started).toISOString();

  const preflight = await runPhase({
    phase: "preflight",
    roles: input.preflightRoles,
    concurrency: input.maxParallel,
    orchestrator: input,
    promptFor: (role) =>
      buildRolePrompt({
        role,
        task: input.task,
        cwd: input.cwd,
        phase: "preflight",
      }),
  });

  let integration: RoleReport | null = null;
  if (input.integratorRole !== null && !input.signal?.aborted) {
    const reports = await runPhase({
      phase: "integration",
      roles: [input.integratorRole],
      concurrency: 1,
      orchestrator: input,
      promptFor: (role) =>
        buildIntegratorPrompt({
          role,
          task: input.task,
          cwd: input.cwd,
          reports: preflight,
          allowEdits: input.allowEdits,
        }),
    });
    integration = reports[0] ?? null;
  }

  let postflight: RoleReport[] = [];
  if (
    input.postflightRoles.length > 0 &&
    integration?.status === "finished" &&
    !input.signal?.aborted
  ) {
    postflight = await runPhase({
      phase: "postflight",
      roles: input.postflightRoles,
      concurrency: input.maxParallel,
      orchestrator: input,
      promptFor: (role) =>
        buildPostflightPrompt({
          role,
          task: input.task,
          cwd: input.cwd,
          integration,
        }),
    });
  }

  const finished = Date.now();
  const status = computeStatus({
    aborted: input.signal?.aborted ?? false,
    preflight,
    integration,
    postflight,
  });
  return {
    runId: randomUUID(),
    task: input.task,
    cwd: input.cwd,
    model: input.model,
    allowEdits: input.allowEdits,
    maxParallel: input.maxParallel,
    status,
    startedAt,
    finishedAt: new Date(finished).toISOString(),
    durationMs: finished - started,
    preflight,
    integration,
    postflight,
  };
}
