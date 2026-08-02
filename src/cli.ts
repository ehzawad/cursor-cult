#!/usr/bin/env node

import { readFile } from "node:fs/promises";

import { HELP_TEXT, parseArgs } from "./args.js";
import { runCult } from "./orchestrator.js";
import { renderJson, renderMarkdown, writeOutputAtomically } from "./report.js";
import { loadRoleDefinitions, selectRoles } from "./roles.js";
import { ActiveRunRegistry } from "./sdk-runner.js";
import type { CliOptions, RoleDefinition, RunProgressEvent } from "./types.js";
import { VERSION } from "./version.js";

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk)));
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function resolveTask(options: CliOptions): Promise<string> {
  if (options.task !== undefined) return options.task.trim();
  if (options.taskFile !== undefined) return (await readFile(options.taskFile, "utf8")).trim();
  if (process.stdin.isTTY) {
    throw new Error("No task supplied. Use --task, --task-file, positional text, or stdin.");
  }
  return (await readStdin()).trim();
}

function printRoles(roles: readonly RoleDefinition[]): void {
  const width = Math.max(...roles.map((role) => role.id.length));
  for (const role of roles) {
    const access = role.readonly ? "read-only" : "workspace-capable";
    process.stdout.write(`${role.id.padEnd(width)}  ${access.padEnd(17)}  ${role.description}\n`);
  }
}

function dryRunDocument(input: {
  readonly options: CliOptions;
  readonly task: string;
  readonly preflight: readonly RoleDefinition[];
  readonly integrator: RoleDefinition | null;
  readonly postflight: readonly RoleDefinition[];
}): string {
  const data = {
    task: input.task,
    cwd: input.options.cwd,
    model: input.options.model,
    allowEdits: input.options.allowEdits,
    maxParallel: input.options.maxParallel,
    phases: {
      preflight: input.preflight.map((role) => role.id),
      integration: input.integrator?.id ?? null,
      postflight: input.postflight.map((role) => role.id),
    },
  };
  if (input.options.outputFormat === "json") return `${JSON.stringify(data, null, 2)}\n`;
  return [
    "# Cursor Cult dry run",
    "",
    `- Workspace: ${data.cwd}`,
    `- Model: ${data.model}`,
    `- Mode: ${data.allowEdits ? "single-writer implementation" : "analysis-only"}`,
    `- Max parallel: ${data.maxParallel}`,
    `- Preflight: ${data.phases.preflight.join(", ") || "none"}`,
    `- Integrator: ${data.phases.integration ?? "none"}`,
    `- Postflight: ${data.phases.postflight.join(", ") || "none"}`,
    "",
    "## Task",
    "",
    data.task,
    "",
  ].join("\n");
}

function logProgress(event: RunProgressEvent): void {
  process.stderr.write(`[cursor-cult] ${event.message}\n`);
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(HELP_TEXT);
    return;
  }
  if (options.version) {
    process.stdout.write(`${VERSION}\n`);
    return;
  }

  const available = await loadRoleDefinitions(options.roleDir);
  if (options.listRoles) {
    printRoles(available);
    return;
  }

  const task = await resolveTask(options);
  if (!task) throw new Error("Task input is empty.");
  const preflight = selectRoles(available, options.preflightRoles);
  const postflight = options.skipPostflight || options.skipIntegrator
    ? []
    : selectRoles(available, options.postflightRoles);
  const integrator = options.skipIntegrator
    ? null
    : selectRoles(available, [options.integratorRole])[0] ?? null;

  if (integrator !== null && preflight.some((role) => role.name === integrator.name)) {
    throw new Error(`Integrator role '${integrator.id}' cannot also run in preflight.`);
  }
  if (integrator !== null && postflight.some((role) => role.name === integrator.name)) {
    throw new Error(`Integrator role '${integrator.id}' cannot also run in postflight.`);
  }
  if (preflight.length === 0 && integrator === null) {
    throw new Error("The run has no executable phase. Select at least one preflight role or keep the integrator enabled.");
  }

  if (options.dryRun) {
    const output = dryRunDocument({ options, task, preflight, integrator, postflight });
    process.stdout.write(output);
    if (options.outputPath !== undefined) await writeOutputAtomically(options.outputPath, output);
    return;
  }

  const apiKey = process.env.CURSOR_API_KEY?.trim();
  if (!apiKey) {
    throw new Error("CURSOR_API_KEY is required for SDK runs. Use --dry-run to validate without an API call.");
  }

  const registry = new ActiveRunRegistry();
  const abort = new AbortController();
  let interruptCount = 0;
  const onSignal = (): void => {
    interruptCount += 1;
    abort.abort(new Error("Interrupted by user."));
    void registry.cancelAll();
    if (interruptCount > 1) process.exit(130);
  };
  process.on("SIGINT", onSignal);
  process.on("SIGTERM", onSignal);

  try {
    const result = await runCult({
      task,
      cwd: options.cwd,
      model: options.model,
      apiKey,
      allowEdits: options.allowEdits,
      maxParallel: options.maxParallel,
      preflightRoles: preflight,
      integratorRole: integrator,
      postflightRoles: postflight,
      registry,
      signal: abort.signal,
      onProgress: logProgress,
    });
    const output = options.outputFormat === "json" ? renderJson(result) : renderMarkdown(result);
    process.stdout.write(output);
    if (options.outputPath !== undefined) await writeOutputAtomically(options.outputPath, output);
    process.exitCode = result.status === "finished"
      ? 0
      : result.status === "partial"
        ? 3
        : result.status === "cancelled"
          ? 130
          : 2;
  } finally {
    process.off("SIGINT", onSignal);
    process.off("SIGTERM", onSignal);
    await registry.cancelAll();
  }
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`[cursor-cult] ${message}\n`);
  process.exitCode = 1;
});
