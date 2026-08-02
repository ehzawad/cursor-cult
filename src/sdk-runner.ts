import { Agent, CursorAgentError, type Run, type SDKAgent } from "@cursor/sdk";

import type { ReportStatus, RoleDefinition, RoleReport, RunPhase } from "./types.js";

interface ActiveRun {
  readonly role: string;
  readonly run: Run;
}

export class ActiveRunRegistry {
  readonly #runs = new Set<ActiveRun>();

  add(run: ActiveRun): void {
    this.#runs.add(run);
  }

  delete(run: ActiveRun): void {
    this.#runs.delete(run);
  }

  async cancelAll(): Promise<void> {
    const cancellations = [...this.#runs].map(async ({ run }) => {
      if (run.supports("cancel")) await run.cancel();
    });
    await Promise.allSettled(cancellations);
  }
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : undefined;
}

function collectAssistantText(event: unknown): string {
  const record = asRecord(event);
  if (record?.type !== "assistant") return "";
  const message = asRecord(record.message);
  const content = message?.content;
  if (!Array.isArray(content)) return "";
  return content
    .map((block) => {
      const item = asRecord(block);
      return item?.type === "text" && typeof item.text === "string" ? item.text : "";
    })
    .join("");
}

function terminalText(result: unknown): string {
  const record = asRecord(result);
  return typeof record?.result === "string" ? record.result : "";
}

function terminalStatus(result: unknown): ReportStatus {
  const status = asRecord(result)?.status;
  if (status === "cancelled" || status === "canceled") return "cancelled";
  if (status === "error") return "error";
  return "finished";
}

function terminalUsage(result: unknown): RoleReport["usage"] {
  const usage = asRecord(asRecord(result)?.usage);
  if (usage === undefined) return undefined;
  const inputTokens = typeof usage.inputTokens === "number" ? usage.inputTokens : undefined;
  const outputTokens = typeof usage.outputTokens === "number" ? usage.outputTokens : undefined;
  if (inputTokens === undefined && outputTokens === undefined) return undefined;
  return {
    ...(inputTokens === undefined ? {} : { inputTokens }),
    ...(outputTokens === undefined ? {} : { outputTokens }),
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function appendWarning(report: RoleReport, warning: string): RoleReport {
  return {
    ...report,
    warnings: [...(report.warnings ?? []), warning],
  };
}

function createFailureReport(input: {
  readonly role: RoleDefinition;
  readonly phase: RunPhase;
  readonly started: number;
  readonly startedAt: string;
  readonly status: "error" | "cancelled";
  readonly error: string;
  readonly text?: string;
  readonly agentId?: string;
  readonly runId?: string;
  readonly retryable?: boolean;
}): RoleReport {
  const finished = Date.now();
  return {
    phase: input.phase,
    role: input.role.id,
    roleName: input.role.name,
    status: input.status,
    text: input.text?.trim() ?? "",
    startedAt: input.startedAt,
    finishedAt: new Date(finished).toISOString(),
    durationMs: finished - input.started,
    ...(input.agentId === undefined ? {} : { agentId: input.agentId }),
    ...(input.runId === undefined ? {} : { runId: input.runId }),
    error: input.error,
    ...(input.retryable === undefined ? {} : { retryable: input.retryable }),
  };
}

export async function runSdkRole(input: {
  readonly role: RoleDefinition;
  readonly phase: RunPhase;
  readonly prompt: string;
  readonly cwd: string;
  readonly model: string;
  readonly apiKey: string;
  readonly registry: ActiveRunRegistry;
  readonly signal?: AbortSignal;
}): Promise<RoleReport> {
  const started = Date.now();
  const startedAt = new Date(started).toISOString();
  let agent: SDKAgent | undefined;
  let agentId: string | undefined;
  let runId: string | undefined;
  let report: RoleReport | undefined;
  let text = "";

  if (input.signal?.aborted) {
    return createFailureReport({
      role: input.role,
      phase: input.phase,
      started,
      startedAt,
      status: "cancelled",
      error: "Run cancelled before launch.",
    });
  }

  try {
    agent = await Agent.create({
      apiKey: input.apiKey,
      name: `Cursor Cult: ${input.role.id}`,
      model: { id: input.model },
      local: { cwd: input.cwd },
    });
    agentId = agent.agentId;

    const run = await agent.send(input.prompt);
    runId = run.id;
    const active: ActiveRun = { role: input.role.id, run };
    input.registry.add(active);

    const requestCancel = (): void => {
      if (run.supports("cancel")) {
        void run.cancel().catch(() => undefined);
      }
    };
    if (input.signal?.aborted) requestCancel();
    else input.signal?.addEventListener("abort", requestCancel, { once: true });

    try {
      for await (const event of run.stream()) {
        text += collectAssistantText(event);
      }
      const terminal = await run.wait();
      const fallback = terminalText(terminal);
      if (!text.trim() && fallback.trim()) text = fallback;
      const finished = Date.now();
      const status = terminalStatus(terminal);
      const usage = terminalUsage(terminal);
      report = {
        phase: input.phase,
        role: input.role.id,
        roleName: input.role.name,
        status,
        text: text.trim(),
        startedAt,
        finishedAt: new Date(finished).toISOString(),
        durationMs: finished - started,
        agentId,
        runId,
        ...(status === "error" ? { error: "Cursor agent run ended with status=error." } : {}),
        ...(usage === undefined ? {} : { usage }),
      };
    } finally {
      input.signal?.removeEventListener("abort", requestCancel);
      input.registry.delete(active);
    }
  } catch (error) {
    const retryable = error instanceof CursorAgentError ? error.isRetryable : undefined;
    report = createFailureReport({
      role: input.role,
      phase: input.phase,
      started,
      startedAt,
      status: input.signal?.aborted ? "cancelled" : "error",
      error: errorMessage(error),
      ...(text.trim() ? { text } : {}),
      ...(agentId === undefined ? {} : { agentId }),
      ...(runId === undefined ? {} : { runId }),
      ...(retryable === undefined ? {} : { retryable }),
    });
  } finally {
    if (agent !== undefined) {
      try {
        await agent[Symbol.asyncDispose]();
      } catch (error) {
        const warning = `Cursor agent cleanup failed: ${errorMessage(error)}`;
        report = report === undefined
          ? createFailureReport({
              role: input.role,
              phase: input.phase,
              started,
              startedAt,
              status: "error",
              error: warning,
              ...(agentId === undefined ? {} : { agentId }),
              ...(runId === undefined ? {} : { runId }),
            })
          : appendWarning(report, warning);
      }
    }
  }

  return report ?? createFailureReport({
    role: input.role,
    phase: input.phase,
    started,
    startedAt,
    status: "error",
    error: "Cursor role exited without a terminal report.",
    ...(agentId === undefined ? {} : { agentId }),
    ...(runId === undefined ? {} : { runId }),
  });
}
