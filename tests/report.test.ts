import assert from "node:assert/strict";
import test from "node:test";

import { renderMarkdown } from "../src/report.js";
import type { CultRunResult } from "../src/types.js";

test("markdown output surfaces cleanup warnings without changing transport status", () => {
  const result: CultRunResult = {
    runId: "run-1",
    task: "Inspect the workspace",
    cwd: "/repo",
    model: "auto",
    allowEdits: false,
    maxParallel: 1,
    status: "finished",
    startedAt: new Date(0).toISOString(),
    finishedAt: new Date(1).toISOString(),
    durationMs: 1,
    preflight: [{
      phase: "preflight",
      role: "scout",
      roleName: "cursor-cult-scout",
      status: "finished",
      text: "Nothing material found.",
      startedAt: new Date(0).toISOString(),
      finishedAt: new Date(1).toISOString(),
      durationMs: 1,
      error: "stream ended unexpectedly after partial output",
      warnings: ["Cursor agent cleanup failed: socket remained open"],
    }],
    integration: null,
    postflight: [],
  };

  const rendered = renderMarkdown(result);
  assert.match(rendered, /warnings=1/);
  assert.match(rendered, /stream ended unexpectedly/);
  assert.match(rendered, /socket remained open/);
  assert.match(rendered, /status=finished/);
});
