import assert from "node:assert/strict";
import test from "node:test";

import { parseArgs } from "../src/args.js";

test("parseArgs uses safe defaults", () => {
  const parsed = parseArgs(["--task", "inspect this"], {});
  assert.equal(parsed.task, "inspect this");
  assert.equal(parsed.model, "auto");
  assert.equal(parsed.maxParallel, 4);
  assert.equal(parsed.allowEdits, false);
  assert.deepEqual(parsed.preflightRoles, ["scout", "architect", "critic"]);
  assert.deepEqual(parsed.postflightRoles, ["reviewer", "verifier"]);
});

test("parseArgs accepts positional tasks and panel overrides", () => {
  const parsed = parseArgs([
    "fix",
    "the",
    "bug",
    "--roles=scout,specialist",
    "--post-roles",
    "none",
    "--allow-edits",
    "--max-parallel",
    "2",
  ], {});
  assert.equal(parsed.task, "fix the bug");
  assert.deepEqual(parsed.preflightRoles, ["scout", "specialist"]);
  assert.deepEqual(parsed.postflightRoles, []);
  assert.equal(parsed.allowEdits, true);
  assert.equal(parsed.maxParallel, 2);
});


test("parseArgs tolerates a package-manager argument separator", () => {
  const parsed = parseArgs(["--", "--task", "inspect this", "--dry-run"], {});
  assert.equal(parsed.task, "inspect this");
  assert.equal(parsed.dryRun, true);
});

test("parseArgs rejects ambiguous task sources", () => {
  assert.throws(
    () => parseArgs(["--task", "one", "two"], {}),
    /either --task or positional text/,
  );
});
