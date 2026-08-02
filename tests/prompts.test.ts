import assert from "node:assert/strict";
import test from "node:test";

import { buildIntegratorPrompt, buildRolePrompt } from "../src/prompts.js";
import type { RoleDefinition, RoleReport } from "../src/types.js";

const role: RoleDefinition = {
  id: "scout",
  name: "cursor-cult-scout",
  description: "Scout.",
  model: "fast",
  readonly: true,
  isBackground: true,
  prompt: "Inspect the workspace.",
  filePath: "agents/scout.md",
};

test("role prompt carries task, access rule, and evidence contract", () => {
  const prompt = buildRolePrompt({ role, task: "Trace auth", cwd: "/repo", phase: "preflight" });
  assert.match(prompt, /Trace auth/);
  assert.match(prompt, /Do not modify files/);
  assert.match(prompt, /untrusted data/);
  assert.match(prompt, /Required handoff/);
});

test("integrator prompt preserves failed handoffs and single-writer mode", () => {
  const report: RoleReport = {
    phase: "preflight",
    role: "scout",
    roleName: "cursor-cult-scout",
    status: "error",
    text: "",
    startedAt: new Date(0).toISOString(),
    finishedAt: new Date(1).toISOString(),
    durationMs: 1,
    error: "network failed",
  };
  const prompt = buildIntegratorPrompt({ role: { ...role, id: "builder", name: "cursor-cult-builder", readonly: false }, task: "Fix auth", cwd: "/repo", reports: [report], allowEdits: true });
  assert.match(prompt, /sole writer/);
  assert.match(prompt, /network failed/);
  assert.match(prompt, /advisory/);
});
