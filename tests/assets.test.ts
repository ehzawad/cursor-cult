import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { VERSION } from "../src/version.js";

test("package and plugin versions stay in sync", async () => {
  const packageJson = JSON.parse(await readFile("package.json", "utf8")) as { version: string };
  const pluginJson = JSON.parse(await readFile(".cursor-plugin/plugin.json", "utf8")) as { version: string; agents: string; skills: string };
  assert.equal(packageJson.version, VERSION);
  assert.equal(pluginJson.version, VERSION);
  assert.equal(pluginJson.agents, "./agents/");
  assert.equal(pluginJson.skills, "./skills/");
});
