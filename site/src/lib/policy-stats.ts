/**
 * Build-time statistics read straight from the repository's policies/ tree, so the
 * landing page can never claim more rules than actually ship.
 *
 * A "rule" is one `violations contains v if { ... }` block in a non-test .rego file.
 * A "test" is one `test_*` rule in a *_test.rego file.
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const POLICY_ROOT = resolve(process.cwd(), '..', 'policies');

export interface PolicyStats {
  /** Directory name under policies/, e.g. "eu". */
  dir: string;
  packages: string[];
  rules: number;
  tests: number;
}

function regoFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .map((name) => join(dir, name))
    .filter((path) => statSync(path).isFile() && path.endsWith('.rego'));
}

function count(source: string, pattern: RegExp): number {
  return source.match(pattern)?.length ?? 0;
}

export function statsFor(dir: string): PolicyStats {
  const stats: PolicyStats = { dir, packages: [], rules: 0, tests: 0 };
  for (const file of regoFiles(join(POLICY_ROOT, dir))) {
    const source = readFileSync(file, 'utf8');
    if (file.endsWith('_test.rego')) {
      stats.tests += count(source, /^test_\w+/gm);
      continue;
    }
    const pkg = source.match(/^package\s+([\w.]+)/m)?.[1];
    const rules = count(source, /^violations contains /gm);
    if (pkg && rules > 0) stats.packages.push(pkg);
    stats.rules += rules;
  }
  return stats;
}

export function totals(): { rules: number; tests: number } {
  if (!existsSync(POLICY_ROOT)) return { rules: 0, tests: 0 };
  return readdirSync(POLICY_ROOT)
    .filter((name) => statSync(join(POLICY_ROOT, name)).isDirectory())
    .map(statsFor)
    .reduce((acc, s) => ({ rules: acc.rules + s.rules, tests: acc.tests + s.tests }), {
      rules: 0,
      tests: 0,
    });
}
