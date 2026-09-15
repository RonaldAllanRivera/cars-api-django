#!/usr/bin/env node
/**
 * Regenerate expo-router's typed-route union at `.expo/types/router.d.ts`.
 *
 * Why this exists
 * ---------------
 * `experiments.typedRoutes` makes `Href` a literal union of the app's real
 * routes, so a link to a path that does not exist is a type error. That union
 * is generated, it lands in `.expo/`, and `.expo/` is gitignored - so CI never
 * had it. With the file absent, tsconfig's `include` matches nothing, `Href`
 * degrades to a permissive type, and `tsc` reports zero errors on a route that
 * cannot resolve. Measured on this repo: one unmatchable route literal gives
 * 1 error with the file present and 0 without it.
 *
 * Only the dev server writes it. `expo export` does not - verified both with
 * the file stale and with it absent entirely. So CI has to start Metro briefly,
 * which is all this script does.
 *
 * Local development does not need it: `expo start` regenerates the file as a
 * side effect of normal work. This is wired into CI only, rather than into a
 * `pretypecheck` hook, so that a local `npm run typecheck` stays a typecheck
 * instead of a Metro boot.
 */
import { spawn } from 'node:child_process';
import { existsSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const typesFile = resolve(mobileRoot, '.expo/types/router.d.ts');

/** High enough not to collide with a dev server someone already has running. */
const PORT = 8129;
const TIMEOUT_MS = 120_000;
const POLL_MS = 250;
/** Grace for SIGTERM before SIGKILL. Metro does not always take the hint. */
const SHUTDOWN_MS = 3_000;

/*
 * A file left over from a previous run would make the poll below succeed
 * instantly and report success without Metro having written anything - the
 * silent-failure mode this script exists to prevent. Comparing mtime against a
 * timestamp taken now is what makes "it appeared" mean "it was just written".
 */
const startedAt = Date.now();

const child = spawn('npx', ['expo', 'start', '--port', String(PORT)], {
  cwd: mobileRoot,
  // CI=1 puts Metro in non-interactive mode: no keypress menu, no watch mode,
  // nothing waiting on a TTY that a runner does not have.
  env: { ...process.env, CI: '1' },
  stdio: ['ignore', 'pipe', 'pipe'],
  // Its own process group, so the shutdown below can signal the whole tree.
  // `npx` spawns expo, which spawns Metro; signalling only the direct child
  // leaves Metro alive and holding the port.
  detached: true,
});

let output = '';
child.stdout.on('data', (chunk) => {
  output += chunk;
});
child.stderr.on('data', (chunk) => {
  output += chunk;
});

const fresh = () => existsSync(typesFile) && statSync(typesFile).mtimeMs >= startedAt;

let finishing = false;

const signal = (name) => {
  try {
    process.kill(-child.pid, name);
  } catch {
    // Already gone, or never became a group leader.
    try {
      child.kill(name);
    } catch {
      /* nothing left to signal */
    }
  }
};

/**
 * Stop Metro, then exit.
 *
 * Waits for the process to actually die rather than exiting straight after
 * SIGTERM: this script's own exit does not reap the tree, and an orphaned
 * Metro keeps the port bound - which makes the next run of this script fail
 * for a reason that has nothing to do with route types.
 */
const finish = (code, message) => {
  if (finishing) return;
  finishing = true;

  if (message) console.error(message);

  const done = () => process.exit(code);

  const killer = setTimeout(() => {
    signal('SIGKILL');
    setTimeout(done, 250);
  }, SHUTDOWN_MS);

  child.once('exit', () => {
    clearTimeout(killer);
    done();
  });

  signal('SIGTERM');
};

const deadline = Date.now() + TIMEOUT_MS;

const poll = setInterval(() => {
  if (fresh()) {
    clearInterval(poll);
    console.log(
      `Route types written to .expo/types/router.d.ts in ${Math.round((Date.now() - startedAt) / 1000)}s`,
    );
    finish(0);

    return;
  }

  if (Date.now() > deadline) {
    clearInterval(poll);
    // Loud, with the server's own output: a silent no-op here would restore
    // exactly the bug this script closes - a typecheck that passes because it
    // is checking nothing.
    finish(
      1,
      `Route types were not generated within ${TIMEOUT_MS / 1000}s.\nExpo output follows:\n\n${output || '(no output)'}`,
    );
  }
}, POLL_MS);

child.on('error', (error) => {
  clearInterval(poll);
  finish(1, `Could not start the Expo dev server: ${error.message}`);
});

child.on('exit', (code) => {
  // Metro exiting before the file appears means the run failed; without this
  // the script would sit out its full timeout for no reason.
  if (finishing || fresh()) return;

  clearInterval(poll);
  finishing = true;
  console.error(`Expo exited with code ${code} before writing the route types.`);
  console.error(output || '(no output)');
  process.exit(1);
});
