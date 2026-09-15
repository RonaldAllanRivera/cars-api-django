#!/usr/bin/env node
/**
 * Fail when `netlify.toml`'s rewrites and the exported dynamic routes disagree.
 *
 * Why this exists
 * ---------------
 * `web.output: "static"` exports one HTML file per route, and a dynamic route
 * keeps its Expo Router filename verbatim - `dist/library/[id].html`. Netlify
 * has no `[id]` convention, so each one needs a hand-written rewrite. Nothing
 * links that list to the router, so renaming a route leaves a rewrite pointing
 * at a file that no longer exists while the new route has none.
 *
 * That is not hypothetical. The P1 tab restructure moved `runs/` under
 * `search/` and added `library/`; this file kept redirecting `/runs/:id` while
 * `/library/:id` returned 404 in production. Clicking through inside the app
 * still worked, because that is client-side routing - only a hard navigation
 * or a shared link showed it, which is why local testing never caught it.
 *
 * Run after `npm run build:web`, against the real `dist/`.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const distDir = resolve(mobileRoot, 'dist');
const tomlFile = resolve(mobileRoot, 'netlify.toml');

/**
 * Every exported page whose filename carries a dynamic segment, as a path
 * relative to dist - e.g. `library/[id].html`.
 *
 * The `(app)` group directory is skipped: expo-router exports those beside the
 * ungrouped copies as an implementation detail, and no user-facing URL
 * contains a parenthesised segment.
 */
function dynamicPages(dir, pages = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);

    if (statSync(full).isDirectory()) {
      if (!entry.startsWith('(') && entry !== '_expo' && entry !== 'assets') {
        dynamicPages(full, pages);
      }

      continue;
    }

    if (entry.endsWith('.html') && entry.includes('[')) {
      pages.push(relative(distDir, full));
    }
  }

  return pages;
}

/** The `to =` target of every [[redirects]] block, in file order. */
function redirectTargets(toml) {
  return [...toml.matchAll(/^\s*to\s*=\s*"([^"]+)"/gm)].map((match) => match[1]);
}

const toml = readFileSync(tomlFile, 'utf8');
const targets = redirectTargets(toml);
const pages = dynamicPages(distDir);

const problems = [];

// A dynamic page with no rewrite is a 404 on any hard navigation.
for (const page of pages) {
  if (!targets.includes(`/${page}`)) {
    problems.push(`  no rewrite for exported page  dist/${page}`);
  }
}

// A rewrite whose target no longer exists is a 404 that looks configured.
for (const target of targets) {
  const page = target.replace(/^\//, '');

  if (!pages.includes(page)) {
    problems.push(`  rewrite points at a missing page  ${target}`);
  }
}

if (problems.length > 0) {
  console.error('netlify.toml and the exported routes disagree:\n');
  console.error(problems.join('\n'));
  console.error('\nEvery dist/**/[param].html needs a [[redirects]] entry, and every');
  console.error('entry needs its page. Fix netlify.toml to match the exported routes.');
  process.exit(1);
}

console.log(
  `netlify.toml covers all ${pages.length} dynamic route${pages.length === 1 ? '' : 's'}.`,
);
