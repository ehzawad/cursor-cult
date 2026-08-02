import { resolve } from "node:path";

import type { CliOptions, OutputFormat } from "./types.js";

export const DEFAULT_PREFLIGHT_ROLES = ["scout", "architect", "critic"] as const;
export const DEFAULT_POSTFLIGHT_ROLES = ["reviewer", "verifier"] as const;
export const DEFAULT_INTEGRATOR_ROLE = "builder";

function parsePositiveInteger(raw: string, flag: string): number {
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new Error(`${flag} must be a positive integer; received ${JSON.stringify(raw)}.`);
  }
  return value;
}

function parseRoleList(raw: string): string[] {
  if (raw.trim().toLowerCase() === "none") return [];
  const roles = raw
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (roles.length === 0) {
    throw new Error("Role lists must contain at least one name or the literal 'none'.");
  }
  return [...new Set(roles)];
}

function parseOutputFormat(raw: string): OutputFormat {
  if (raw === "markdown" || raw === "json") return raw;
  throw new Error(`--format must be 'markdown' or 'json'; received ${JSON.stringify(raw)}.`);
}

function requireValue(argv: readonly string[], index: number, flag: string): string {
  const value = argv[index + 1];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${flag} requires a value.`);
  }
  return value;
}

export function parseArgs(
  argv: readonly string[],
  env: NodeJS.ProcessEnv = process.env,
): CliOptions {
  let task: string | undefined;
  let taskFile: string | undefined;
  let cwd = resolve(process.cwd());
  let roleDir: string | undefined;
  let preflightRoles: readonly string[] = DEFAULT_PREFLIGHT_ROLES;
  let postflightRoles: readonly string[] = DEFAULT_POSTFLIGHT_ROLES;
  let integratorRole = DEFAULT_INTEGRATOR_ROLE;
  let maxParallel = parsePositiveInteger(env.CURSOR_CULT_MAX_PARALLEL ?? "4", "CURSOR_CULT_MAX_PARALLEL");
  let model = env.CURSOR_CULT_MODEL?.trim() || "auto";
  let allowEdits = false;
  let skipIntegrator = false;
  let skipPostflight = false;
  let outputFormat: OutputFormat = "markdown";
  let outputPath: string | undefined;
  let dryRun = false;
  let listRoles = false;
  let help = false;
  let version = false;
  const positional: string[] = [];

  for (let index = 0; index < argv.length; index += 1) {
    const raw = argv[index]!;
    if (raw === "--") continue;
    if (!raw.startsWith("--")) {
      positional.push(raw);
      continue;
    }

    const equalsIndex = raw.indexOf("=");
    const flag = equalsIndex === -1 ? raw : raw.slice(0, equalsIndex);
    const inlineValue = equalsIndex === -1 ? undefined : raw.slice(equalsIndex + 1);
    const takeValue = (): string => {
      if (inlineValue !== undefined) return inlineValue;
      const value = requireValue(argv, index, flag);
      index += 1;
      return value;
    };

    switch (flag) {
      case "--task":
        task = takeValue();
        break;
      case "--task-file":
        taskFile = resolve(takeValue());
        break;
      case "--cwd":
        cwd = resolve(takeValue());
        break;
      case "--role-dir":
        roleDir = resolve(takeValue());
        break;
      case "--roles":
        preflightRoles = parseRoleList(takeValue());
        break;
      case "--post-roles":
        postflightRoles = parseRoleList(takeValue());
        break;
      case "--integrator":
        integratorRole = takeValue().trim();
        if (!integratorRole) throw new Error("--integrator cannot be empty.");
        break;
      case "--max-parallel":
        maxParallel = parsePositiveInteger(takeValue(), "--max-parallel");
        break;
      case "--model":
        model = takeValue().trim();
        if (!model) throw new Error("--model cannot be empty.");
        break;
      case "--format":
        outputFormat = parseOutputFormat(takeValue());
        break;
      case "--out":
        outputPath = resolve(takeValue());
        break;
      case "--allow-edits":
        allowEdits = true;
        break;
      case "--analysis-only":
        allowEdits = false;
        break;
      case "--skip-integrator":
        skipIntegrator = true;
        break;
      case "--skip-postflight":
        skipPostflight = true;
        break;
      case "--dry-run":
        dryRun = true;
        break;
      case "--list-roles":
        listRoles = true;
        break;
      case "--help":
        help = true;
        break;
      case "--version":
        version = true;
        break;
      default:
        throw new Error(`Unknown option: ${flag}`);
    }
  }

  if (task !== undefined && positional.length > 0) {
    throw new Error("Provide the task with either --task or positional text, not both.");
  }
  if (taskFile !== undefined && (task !== undefined || positional.length > 0)) {
    throw new Error("--task-file cannot be combined with --task or positional task text.");
  }
  if (task === undefined && positional.length > 0) {
    task = positional.join(" ");
  }

  return {
    ...(task === undefined ? {} : { task }),
    ...(taskFile === undefined ? {} : { taskFile }),
    cwd,
    ...(roleDir === undefined ? {} : { roleDir }),
    preflightRoles,
    postflightRoles,
    integratorRole,
    maxParallel,
    model,
    allowEdits,
    skipIntegrator,
    skipPostflight,
    outputFormat,
    ...(outputPath === undefined ? {} : { outputPath }),
    dryRun,
    listRoles,
    help,
    version,
  };
}

export const HELP_TEXT = `cursor-cult — phased multi-role orchestration with the Cursor SDK

Usage:
  cursor-cult --task "<goal>" [options]
  cursor-cult "<goal>" [options]
  cat task.md | cursor-cult [options]

Task input:
  --task <text>             Task text.
  --task-file <path>        Read task text from a file.
  positional text           Used as the task when --task is absent.
  stdin                     Used when no task flag or positional text is supplied.

Panel:
  --roles <csv|none>        Preflight roles (default: scout,architect,critic).
  --post-roles <csv|none>   Postflight roles (default: reviewer,verifier).
  --integrator <role>       Integrator role (default: builder).
  --max-parallel <n>        Maximum concurrent role agents (default: 4).
  --role-dir <path>         Override the directory containing role Markdown files.

Runtime:
  --cwd <path>              Workspace for every local SDK agent (default: current directory).
  --model <id>              Cursor model selection (default: auto).
  --allow-edits             Permit the integrator to modify the workspace.
  --analysis-only           Explicitly keep the integrator read-only (default).
  --skip-integrator         Return preflight handoffs only; integration and postflight are skipped.
  --skip-postflight         Skip reviewer/verifier after integration.

Output:
  --format markdown|json    Output format (default: markdown).
  --out <path>              Atomically write the result to a file as well as stdout.
  --dry-run                 Validate and print the planned phases without calling the SDK.
  --list-roles              List installed roles and exit.
  --version                 Print the version and exit.
  --help                    Show this help.

Environment:
  CURSOR_API_KEY             Required for non-dry SDK runs.
  CURSOR_CULT_MODEL          Default model override.
  CURSOR_CULT_MAX_PARALLEL   Default concurrency override.
`;
