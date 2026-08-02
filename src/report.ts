import { mkdir, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

import type { CultRunResult, RoleReport } from "./types.js";

function formatDuration(ms: number): string {
  if (ms < 1_000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1_000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

function renderReport(report: RoleReport): string {
  const metadata = [
    `status=${report.status}`,
    `duration=${formatDuration(report.durationMs)}`,
    report.agentId ? `agent=${report.agentId}` : undefined,
    report.runId ? `run=${report.runId}` : undefined,
    report.warnings?.length ? `warnings=${report.warnings.length}` : undefined,
  ]
    .filter((value): value is string => value !== undefined)
    .join(" · ");
  const text = report.text.trim() || "No textual handoff.";
  const error = report.error ? `\n\nError: ${report.error}` : "";
  const warnings = report.warnings?.length
    ? `\n\nWarnings:\n${report.warnings.map((warning) => `- ${warning}`).join("\n")}`
    : "";
  return `### ${report.role}\n\n${metadata}\n\n${text}${error}${warnings}`;
}

function renderPhase(title: string, reports: readonly RoleReport[]): string {
  if (reports.length === 0) return `## ${title}\n\n_Not run._`;
  return `## ${title}\n\n${reports.map(renderReport).join("\n\n")}`;
}

export function renderMarkdown(result: CultRunResult): string {
  const integration = result.integration === null
    ? "## Integration\n\n_Not run._"
    : `## Integration\n\n${renderReport(result.integration)}`;
  return [
    "# Cursor Cult run",
    "",
    `- Run: ${result.runId}`,
    `- Status: ${result.status}`,
    `- Workspace: ${result.cwd}`,
    `- Model: ${result.model}`,
    `- Mode: ${result.allowEdits ? "single-writer implementation" : "analysis-only"}`,
    `- Duration: ${formatDuration(result.durationMs)}`,
    "",
    "## Task",
    "",
    result.task.trim(),
    "",
    renderPhase("Preflight council", result.preflight),
    "",
    integration,
    "",
    renderPhase("Postflight gate", result.postflight),
    "",
  ].join("\n");
}

export function renderJson(result: CultRunResult): string {
  return `${JSON.stringify(result, null, 2)}\n`;
}

export async function writeOutputAtomically(path: string, content: string): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const temporary = `${path}.tmp-${process.pid}-${Date.now()}`;
  await writeFile(temporary, content, "utf8");
  await rename(temporary, path);
}
