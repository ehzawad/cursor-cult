import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import test from "node:test";

import {
  loadRoleDefinitions,
  parseRoleDefinition,
  selectRoles,
} from "../src/roles.js";

test("parseRoleDefinition reads Cursor agent frontmatter", () => {
  const role = parseRoleDefinition(`---
name: cursor-cult-example
description: Example role.
model: fast
readonly: true
is_background: true
---

Do the work.`, "example.md");
  assert.equal(role.id, "example");
  assert.equal(role.name, "cursor-cult-example");
  assert.equal(role.model, "fast");
  assert.equal(role.readonly, true);
  assert.equal(role.isBackground, true);
  assert.equal(role.prompt, "Do the work.");
});

test("repository role catalog is valid and uniquely selectable by alias", async () => {
  const roles = await loadRoleDefinitions(resolve(process.cwd(), "agents"));
  const selected = selectRoles(roles, ["scout", "cursor-cult-builder"]);
  assert.deepEqual(selected.map((role) => role.id), ["scout", "builder"]);
  assert.equal(roles.find((role) => role.id === "builder")?.readonly, false);
  assert.equal(roles.find((role) => role.id === "reviewer")?.readonly, true);
});

test("loadRoleDefinitions rejects duplicate role names", async () => {
  const directory = await mkdtemp(join(tmpdir(), "cursor-cult-roles-"));
  const content = `---
name: cursor-cult-same
description: Same.
---
Prompt.`;
  try {
    await writeFile(join(directory, "one.md"), content);
    await writeFile(join(directory, "two.md"), content);
    await assert.rejects(() => loadRoleDefinitions(directory), /Duplicate role key/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("loadRoleDefinitions supports unprefixed custom role names", async () => {
  const directory = await mkdtemp(join(tmpdir(), "cursor-cult-custom-role-"));
  try {
    await writeFile(join(directory, "domain-expert.md"), `---
name: domain-expert
description: Custom domain role.
readonly: true
---
Inspect the delegated domain.`);
    const roles = await loadRoleDefinitions(directory);
    assert.deepEqual(roles.map((role) => role.id), ["domain-expert"]);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
