import { readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { RoleDefinition } from "./types.js";

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PREFIX = "cursor-cult-";

interface ParsedFrontmatter {
  readonly values: Readonly<Record<string, string>>;
  readonly body: string;
}

function parseBoolean(raw: string | undefined, fallback: boolean): boolean {
  if (raw === undefined) return fallback;
  if (raw === "true") return true;
  if (raw === "false") return false;
  throw new Error(`Expected boolean frontmatter value; received ${JSON.stringify(raw)}.`);
}

function unquote(raw: string): string {
  const trimmed = raw.trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function parseFrontmatter(content: string, filePath: string): ParsedFrontmatter {
  const normalized = content.replaceAll("\r\n", "\n");
  if (!normalized.startsWith("---\n")) {
    throw new Error(`${filePath}: role file must start with YAML frontmatter.`);
  }
  const closing = normalized.indexOf("\n---\n", 4);
  if (closing === -1) {
    throw new Error(`${filePath}: role frontmatter is not closed with '---'.`);
  }

  const values: Record<string, string> = {};
  const block = normalized.slice(4, closing);
  for (const [lineIndex, line] of block.split("\n").entries()) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const colon = trimmed.indexOf(":");
    if (colon <= 0) {
      throw new Error(`${filePath}:${lineIndex + 2}: expected 'key: value' frontmatter.`);
    }
    const key = trimmed.slice(0, colon).trim();
    const value = unquote(trimmed.slice(colon + 1));
    values[key] = value;
  }

  const body = normalized.slice(closing + "\n---\n".length).trim();
  if (!body) throw new Error(`${filePath}: role prompt body cannot be empty.`);
  return { values, body };
}

export function roleAlias(name: string): string {
  return name.startsWith(PREFIX) ? name.slice(PREFIX.length) : name;
}

export function parseRoleDefinition(content: string, filePath: string): RoleDefinition {
  const { values, body } = parseFrontmatter(content, filePath);
  const name = values.name?.trim();
  const description = values.description?.trim();
  if (!name) throw new Error(`${filePath}: missing required frontmatter field 'name'.`);
  if (!description) throw new Error(`${filePath}: missing required frontmatter field 'description'.`);

  const id = roleAlias(name);
  if (!/^[a-z0-9][a-z0-9-]*$/.test(id)) {
    throw new Error(`${filePath}: role alias ${JSON.stringify(id)} must be lowercase kebab-case.`);
  }

  return {
    id,
    name,
    description,
    model: values.model?.trim() || "inherit",
    readonly: parseBoolean(values.readonly, false),
    isBackground: parseBoolean(values.is_background, false),
    prompt: body,
    filePath,
  };
}

export function defaultRoleDirectory(): string {
  return resolve(PACKAGE_ROOT, "agents");
}

export async function loadRoleDefinitions(
  directory = defaultRoleDirectory(),
): Promise<RoleDefinition[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const roles: RoleDefinition[] = [];
  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
    const filePath = resolve(directory, entry.name);
    roles.push(parseRoleDefinition(await readFile(filePath, "utf8"), filePath));
  }
  if (roles.length === 0) throw new Error(`No role Markdown files found in ${directory}.`);

  const seen = new Map<string, string>();
  for (const role of roles) {
    for (const key of new Set([role.id, role.name])) {
      const previous = seen.get(key);
      if (previous !== undefined) {
        throw new Error(`Duplicate role key ${JSON.stringify(key)} in ${previous} and ${role.filePath}.`);
      }
      seen.set(key, role.filePath);
    }
  }
  return roles;
}

export function selectRoles(
  available: readonly RoleDefinition[],
  requested: readonly string[],
): RoleDefinition[] {
  const byKey = new Map<string, RoleDefinition>();
  for (const role of available) {
    byKey.set(role.id, role);
    byKey.set(role.name, role);
  }

  const selected: RoleDefinition[] = [];
  const selectedNames = new Set<string>();
  for (const raw of requested) {
    const key = raw.trim();
    const role = byKey.get(key) ?? byKey.get(roleAlias(key));
    if (role === undefined) {
      const choices = available.map((candidate) => candidate.id).sort().join(", ");
      throw new Error(`Unknown role ${JSON.stringify(raw)}. Available roles: ${choices}.`);
    }
    if (!selectedNames.has(role.name)) {
      selected.push(role);
      selectedNames.add(role.name);
    }
  }
  return selected;
}
