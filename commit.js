#!/usr/bin/env node
'use strict';

/**
 * commit.js - step-by-step git commit helper for this repository.
 *dasdasdAWEDaSDW#EDQWE#ER
 * Interactive:      node commit.js
 * With message:     node commit.js -m "feat: add driver duty controls"
 * Stage everything: node commit.js -a -m "..."
 * Commit and push:  node commit.js -a -m "..." --push
 * Dry run:          node commit.js --dry-run
 * Help:             node commit.js --help
 *
 * Split over time:   node commit.js --split -m "style: apply design tokens"
 *                    -> commit half now, then half again after ~5 min,
 *                       then the rest after ~15 min (randomised).
 * No dependencies, plain Node (>=16).
 */

const { spawnSync } = require('node:child_process');
const readline = require('node:readline/promises');

const ROOT = __dirname;

/* ------------------------------------------------------------------ */
/* ANSI helpers                                                        */
/* ------------------------------------------------------------------ */

const COLOR = Boolean(process.stdout.isTTY) && !process.env.NO_COLOR;
const paint = (code) => (text) => (COLOR ? `\u001b[${code}m${text}\u001b[0m` : String(text));

const bold = paint('1');
const dim = paint('2');
const red = paint('31');
const green = paint('32');
const yellow = paint('33');
const cyan = paint('36');

const say = (msg = '') => console.log(msg);
const ok = (msg) => say(`${green('ok')} ${msg}`);
const warn = (msg) => say(`${yellow('!')} ${msg}`);
const fail = (msg) => {
  say(`${red('error')} ${msg}`);
  process.exitCode = 1;
  throw new Error(msg);
};

function section(n, title) {
  say(`\n${cyan(bold(`Step ${n}/6`))} ${bold(title)}`);
}

/* ------------------------------------------------------------------ */
/* git helpers                                                         */
/* ------------------------------------------------------------------ */

function gitOut(args) {
  const res = spawnSync('git', args, { cwd: ROOT, encoding: 'utf8' });
  if (res.error) throw new Error(`Could not run git: ${res.error.message}`);
  if (res.status !== 0) {
    const detail = (res.stderr || res.stdout || '').trim();
    throw new Error(detail || `git ${args.join(' ')} failed with code ${res.status}`);
  }
  return res.stdout.trim();
}

function gitOutSafe(args) {
  try {
    return gitOut(args);
  } catch {
    return '';
  }
}

function gitRun(args, { allowFail = false } = {}) {
  const res = spawnSync('git', args, { cwd: ROOT, stdio: 'inherit' });
  if (res.error) throw new Error(`Could not run git: ${res.error.message}`);
  if (res.status !== 0 && !allowFail) {
    throw new Error(`git ${args.join(' ')} exited with code ${res.status}`);
  }
  return res.status === 0;
}

function parseStatus(raw) {
  if (!raw) return [];
  const parts = raw.split('\0');
  const entries = [];
  for (let i = 0; i < parts.length; i += 1) {
    const line = parts[i];
    if (!line) continue;
    const x = line[0];
    const y = line[1];
    const path = line.slice(3);
    if (x === 'R' || x === 'C') {
      i += 1;
      entries.push({ x, y, path, origPath: parts[i] || '' });
    } else {
      entries.push({ x, y, path });
    }
  }
  return entries;
}

function statusInfo(entry) {
  const { x, y } = entry;
  if (x === '?' && y === '?') return { code: '??', label: 'untracked', color: red };
  if (x === 'R') return { code: 'R ', label: 'renamed', color: cyan };
  if (x === 'A') return { code: 'A ', label: 'added', color: green };
  if (x === 'D' || y === 'D') return { code: `${x}${y}`, label: 'deleted', color: red };
  if (x === 'U' || y === 'U' || (x === 'A' && y === 'A')) return { code: `${x}${y}`, label: 'conflict', color: red };
  if (x === 'M' || y === 'M') return { code: `${x}${y}`, label: 'modified', color: yellow };
  return { code: `${x}${y}`, label: 'changed', color: dim };
}

function printEntries(entries, { limit = 60 } = {}) {
  const shown = entries.slice(0, limit);
  for (const entry of shown) {
    const info = statusInfo(entry);
    const name = entry.origPath ? `${entry.origPath} -> ${entry.path}` : entry.path;
    say(`  ${info.color(info.code)}  ${name}  ${dim(`(${info.label})`)}`);
  }
  if (entries.length > shown.length) {
    say(dim(`  ... and ${entries.length - shown.length} more`));
  }
}

function stagedPaths() {
  const raw = gitOutSafe(['diff', '--cached', '--name-only', '-z']);
  return raw ? raw.split('\0').filter(Boolean) : [];
}

function changedPaths() {
  return parseStatus(gitOutSafe(['status', '--porcelain=v1', '-z', '--untracked-files=all']));
}

/* ------------------------------------------------------------------ */
/* Scheduled split commits                                             */
/* ------------------------------------------------------------------ */

const DEFAULT_DELAYS = [0, 5, 15, 30, 60];

let aborted = false;
let activeTimer = null;
let activeResolve = null;

/** setTimeout that a Ctrl+C can cancel without leaving the event loop hanging. */
function cancelableSleep(ms) {
  return new Promise((resolve) => {
    activeResolve = resolve;
    activeTimer = setTimeout(() => {
      activeTimer = null;
      activeResolve = null;
      resolve();
    }, ms);
  });
}

function cancelSleep() {
  if (activeTimer) {
    clearTimeout(activeTimer);
    activeTimer = null;
  }
  const resolve = activeResolve;
  activeResolve = null;
  if (resolve) resolve();
}

function formatDuration(ms) {
  const seconds = Math.round(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (minutes === 0) return `${rest}s`;
  if (rest === 0) return `${minutes}m`;
  return `${minutes}m ${rest}s`;
}

/**
 * Split evenly-ish: every batch takes half of what is left, and the last
 * batch takes the remainder. 75 files over 3 parts -> 38 / 19 / 18.
 */
function splitIntoBatches(files, parts) {
  const batches = [];
  let remaining = files.slice();
  for (let index = 0; index < parts && remaining.length > 0; index += 1) {
    const take = index === parts - 1 ? remaining.length : Math.max(1, Math.ceil(remaining.length / 2));
    batches.push(remaining.slice(0, take));
    remaining = remaining.slice(take);
  }
  if (remaining.length > 0) batches[batches.length - 1].push(...remaining);
  return batches;
}

/** One delay per commit; later commits repeat the last configured delay. */
function buildDelayPlan(batchCount, opts) {
  return Array.from({ length: batchCount }, (_, index) => {
    const base = opts.delays[Math.min(index, opts.delays.length - 1)] * 60_000;
    if (base === 0 || opts.jitter === 0) return base;
    const spread = base * opts.jitter;
    return Math.max(0, Math.round(base - spread + Math.random() * spread * 2));
  });
}

function waitLabel(ms) {
  return ms === 0 ? 'now' : `after ~${formatDuration(ms)}`;
}

async function waitWithCountdown(ms) {
  let left = ms;
  while (left > 0 && !aborted) {
    const step = Math.min(left, 60_000);
    await cancelableSleep(step);
    if (aborted) return;
    left -= step;
    if (left > 0) say(dim(`  ${formatDuration(left)} until the next commit`));
  }
}

async function runSchedule(opts, { interactive, prompter, branch }) {
  const entries = changedPaths();
  if (entries.length === 0) {
    ok('Working tree is clean. Nothing to commit.');
    return;
  }

  // Renames contribute both sides so the commit keeps the move intact.
  const paths = [
    ...new Set(entries.flatMap((entry) => (entry.origPath ? [entry.origPath, entry.path] : [entry.path]))),
  ].sort();

  const parts = Math.max(1, Math.min(opts.parts, paths.length));
  const batches = splitIntoBatches(paths, parts);
  const delays = buildDelayPlan(batches.length, opts);

  let message = opts.message;
  if (message == null) {
    if (!interactive) fail('No message provided. Use -m "your message".');
    message = await prompter.ask('Commit message base:', 'chore: update project files');
  }
  const [rawSubject, ...bodyParts] = message.split(/\r?\n\r?\n/);
  const subject = rawSubject.trim();
  const body = bodyParts.join('\n\n').trim();
  if (!subject) fail('Commit subject is empty.');

  const totalWait = delays.slice(1).reduce((sum, value) => sum + value, 0);

  say(`\n${cyan(bold('Split commit plan'))}`);
  say(
    `  ${bold(String(batches.length))} commit(s) from ${paths.length} path(s)` +
      dim(` · delays ${opts.delays.join(' / ')} min`) +
      (opts.jitter > 0 ? dim(` ±${Math.round(opts.jitter * 100)}% random`) : ''),
  );
  batches.forEach((batch, index) => {
    say(`  ${bold(String(index + 1))}. ${waitLabel(delays[index]).padEnd(14)} ${dim(`${batch.length} path(s)`)}`);
  });

  if (opts.dryRun) {
    ok('Dry run enabled: no commits and no waiting.');
    return;
  }

  const question =
    totalWait > 0
      ? `Create ${batches.length} commits over the next ~${formatDuration(totalWait)}?`
      : `Create ${batches.length} commit(s) now?`;
  if (!(await prompter.confirm(bold(question), true))) {
    say(yellow('Stopped. Nothing was committed.'));
    return;
  }

  for (let index = 0; index < batches.length; index += 1) {
    if (aborted) break;

    const delay = delays[index];
    if (delay > 0) {
      const at = new Date(Date.now() + delay).toLocaleTimeString();
      say(
        `\n${dim(`Commit ${index + 1}/${batches.length}: waiting ${formatDuration(delay)} (around ${at})…`)}`,
      );
      await waitWithCountdown(delay);
      if (aborted) break;
    }

    const batch = batches[index];
    const title = batches.length > 1 ? `${subject} (${index + 1}/${batches.length})` : subject;
    try {
      gitRun(['add', '-A', '--', ...batch]);
      const args = ['commit', '-m', title];
      if (body) args.push('-m', body);
      args.push('--', ...batch);
      gitOut(args);
      ok(`${bold(title)} ${dim(`— ${batch.length} path(s)`)}`);
      say(`  ${dim(gitOutSafe(['log', '-1', '--oneline']))}`);
    } catch (error) {
      warn(`Commit ${index + 1} failed: ${error.message}`);
      break;
    }
  }

  if (aborted) {
    warn('Stopped early. The remaining changes are still in the working tree.');
    return;
  }

  const remaining = changedPaths();
  if (remaining.length > 0) {
    warn(`${remaining.length} uncommitted change(s) remain.`);
  } else {
    ok('Working tree is clean.');
  }

  if (!opts.push) {
    say(dim('Not pushed. Run "git push" when you are ready.'));
    return;
  }
  if (branch === '(detached HEAD)') {
    warn('Cannot push from a detached HEAD. Skipping push.');
    return;
  }
  const upstream = gitOutSafe(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']);
  if (upstream) {
    gitRun(['push']);
    ok(`Pushed to ${cyan(upstream)}.`);
  } else {
    gitRun(['push', '-u', 'origin', branch]);
    ok(`Pushed and tracking ${cyan(`origin/${branch}`)}.`);
  }
}

/* ------------------------------------------------------------------ */
/* CLI args                                                            */
/* ------------------------------------------------------------------ */

function usage() {
  say(`
${bold('commit.js')} - guided git commit

${bold('Usage')}
  node commit.js                 Interactive, step by step
  node commit.js -m "message"    Skip the message prompt
  node commit.js -a -m "msg"     Stage every change, then commit
  node commit.js -a -m "msg" -p  ...and push
  node commit.js --dry-run       Show the plan, then stop before committing

${bold('Split commits over time')}
  node commit.js --split -m "msg"        Halve the changes over 3 commits
  node commit.js --split=5 -m "msg"      Choose how many commits
  node commit.js --split --delays 0,5,15 -m "msg"
  node commit.js --split --jitter 0 -m "msg"   Use exact delays, no randomness
  node commit.js --split --dry-run -m "msg"    Preview batches, no waiting

${bold('Options')}
  -m, --message <text>  Commit message (subject; optional body via blank line)
  -a, --all             Stage all changes without asking
  -p, --push            Push after a successful commit
  -y, --yes             Accept every default without prompting
  --split[=n]           Half-by-half commits over time (default 3 parts)
  --parts <n>           Alias for --split=<n>
  --delays <list>       Minutes before each commit (default 0,5,15,30,60)
  --jitter <0..1>       Randomise each delay by ±fraction (default 0.4)
  --dry-run             Do not run "git commit" or "git push"
  -h, --help            Show this help

${bold('Steps')}
  1. Check repository            4. Review staged changes
  2. Show working tree status    5. Write the commit message
  3. Stage changes               6. Commit (and optionally push)
`);
}

function parseArgs(argv) {
  const opts = {
    message: null,
    all: false,
    push: false,
    yes: false,
    dryRun: false,
    help: false,
    files: [],
    split: false,
    parts: 3,
    delays: DEFAULT_DELAYS.slice(),
    jitter: 0.4,
  };

  const int = (value, min, max) => {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) fail(`Expected a number, got "${value}"`);
    return Math.min(max, Math.max(min, parsed));
  };
  const decimals = (value, min, max) => {
    const parsed = Number.parseFloat(value);
    if (!Number.isFinite(parsed)) fail(`Expected a number, got "${value}"`);
    return Math.min(max, Math.max(min, parsed));
  };
  const minutes = (value) => {
    const list = value
      .split(',')
      .map((item) => Number.parseFloat(item.trim()))
      .filter((item) => Number.isFinite(item) && item >= 0);
    if (list.length === 0) fail(`Expected comma-separated minutes, got "${value}"`);
    return list;
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    const withValue = arg.match(/^--(split|parts|delays|jitter)=(.*)$/);
    if (withValue) {
      const [, key, value] = withValue;
      if (key === 'split') {
        opts.split = true;
        opts.parts = int(value, 1, 50);
      } else if (key === 'parts') {
        opts.split = true;
        opts.parts = int(value, 1, 50);
      } else if (key === 'delays') {
        opts.delays = minutes(value);
      } else {
        opts.jitter = decimals(value, 0, 1);
      }
      continue;
    }

    switch (arg) {
      case '-m':
      case '--message':
        opts.message = argv[i + 1] || '';
        i += 1;
        break;
      case '-a':
      case '--all':
        opts.all = true;
        break;
      case '-p':
      case '--push':
        opts.push = true;
        break;
      case '-y':
      case '--yes':
        opts.yes = true;
        break;
      case '--dry-run':
        opts.dryRun = true;
        break;
      case '--split':
      case '--schedule':
        opts.split = true;
        break;
      case '--parts':
        opts.split = true;
        opts.parts = int(argv[i + 1], 1, 50);
        i += 1;
        break;
      case '--delays':
        opts.delays = minutes(argv[i + 1]);
        i += 1;
        break;
      case '--jitter':
        opts.jitter = decimals(argv[i + 1], 0, 1);
        i += 1;
        break;
      case '-h':
      case '--help':
        opts.help = true;
        break;
      default:
        if (arg.startsWith('-')) fail(`Unknown option: ${arg} (try --help)`);
        opts.files.push(arg);
    }
  }
  return opts;
}

/* ------------------------------------------------------------------ */
/* Prompt helpers                                                      */
/* ------------------------------------------------------------------ */

function createPrompter(interactive) {
  const rl = interactive ? readline.createInterface({ input: process.stdin, output: process.stdout }) : null;

  async function ask(question, fallback = '') {
    if (!interactive) return fallback;
    const hint = fallback ? ` ${dim(`[${fallback}]`)}` : '';
    const answer = (await rl.question(`${question}${hint} `)).trim();
    return answer || fallback;
  }

  async function confirm(question, fallback = true) {
    if (!interactive) return fallback;
    const hint = fallback ? 'Y/n' : 'y/N';
    const answer = (await rl.question(`${question} ${dim(`(${hint})`)} `)).trim().toLowerCase();
    if (!answer) return fallback;
    return answer === 'y' || answer === 'yes';
  }

  /** Raw line read, used for the multi-line commit body. */
  async function line(promptText = '> ') {
    if (!interactive) return '';
    return rl.question(promptText);
  }

  function close() {
    if (rl) rl.close();
  }

  return { ask, confirm, line, close };
}

function parseSelection(input, max) {
  const picked = new Set();
  for (const chunk of input.split(/[\s,]+/).filter(Boolean)) {
    if (chunk === 'all' || chunk === '*') {
      for (let i = 1; i <= max; i += 1) picked.add(i);
      continue;
    }
    const match = chunk.match(/^(\d+)(?:-(\d+))?$/);
    if (!match) throw new Error(`Invalid selection: "${chunk}"`);
    const start = Number(match[1]);
    const end = match[2] ? Number(match[2]) : start;
    if (start < 1 || end > max || start > end) {
      throw new Error(`Selection out of range: "${chunk}" (1-${max})`);
    }
    for (let i = start; i <= end; i += 1) picked.add(i);
  }
  if (picked.size === 0) throw new Error('Nothing selected');
  return [...picked].sort((a, b) => a - b);
}

/* ------------------------------------------------------------------ */
/* Main flow                                                           */
/* ------------------------------------------------------------------ */

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    usage();
    return;
  }

  const interactive = Boolean(process.stdin.isTTY) && !opts.yes;
  const { ask, confirm, line, close } = createPrompter(interactive);

  process.on('SIGINT', () => {
    if (opts.split) {
      aborted = true;
      cancelSleep();
      say(`\n${yellow('Stopping after the current step…')}`);
      return;
    }
    say(`\n${yellow('Aborted. Nothing was committed.')}`);
    close();
    process.exit(130);
  });

  try {
    /* ---------------------------------------------------------- */
    section(1, 'Checking repository');

    if (gitOutSafe(['rev-parse', '--is-inside-work-tree']) !== 'true') {
      fail('Not inside a git working tree.');
    }
    const branch = gitOutSafe(['branch', '--show-current']) || '(detached HEAD)';
    const name = gitOutSafe(['config', 'user.name']) || dim('(no user.name set)');
    const email = gitOutSafe(['config', 'user.email']) || dim('(no user.email set)');

    ok(`Repository: ${bold(ROOT)}`);
    say(`  Branch : ${cyan(branch)}`);
    say(`  Author : ${name} <${email}>`);

    if (opts.split) {
      await runSchedule(opts, { interactive, prompter: { ask, confirm }, branch });
      return;
    }

    /* ---------------------------------------------------------- */
    section(2, 'Checking working tree');

    let entries = changedPaths();
    const stagedBefore = stagedPaths();

    if (entries.length === 0) {
      ok('Working tree is clean. Nothing to commit.');
      return;
    }
    say(`  ${entries.length} change(s) detected:`);
    printEntries(entries);

    /* ---------------------------------------------------------- */
    section(3, 'Staging changes');

    if (opts.all) {
      gitRun(['add', '-A']);
      ok('Staged all changes.');
    } else if (opts.files.length > 0) {
      gitRun(['add', '--', ...opts.files]);
      ok(`Staged ${opts.files.length} path(s) from the command line.`);
    } else if (interactive) {
      say('How do you want to stage?');
      say(`  ${bold('1')}  Stage everything ${dim('(recommended)')}`);
      say(`  ${bold('2')}  Pick files one by one`);
      say(`  ${bold('3')}  Keep only what is already staged`);
      const choice = await ask('Choose [1-3]:', '1');

      if (choice === '1') {
        gitRun(['add', '-A']);
        ok('Staged all changes.');
      } else if (choice === '2') {
        for (;;) {
          say('');
          entries.forEach((entry, index) => {
            const info = statusInfo(entry);
            const name = entry.origPath ? `${entry.origPath} -> ${entry.path}` : entry.path;
            say(`  ${String(index + 1).padStart(3)}  ${info.color(info.code)}  ${name}`);
          });
          try {
            const answer = await ask('Files to stage (e.g. 1,3-5, all):', 'all');
            const picked = parseSelection(answer, entries.length);
            const paths = picked.map((index) => entries[index - 1].path);
            gitRun(['add', '--', ...paths]);
            ok(`Staged ${paths.length} file(s).`);
            break;
          } catch (error) {
            warn(error.message);
          }
        }
      } else {
        ok('Keeping the existing staged changes.');
      }
    } else {
      // Non-interactive without flags: respect whatever the user already staged.
      if (stagedBefore.length === 0) {
        fail('Nothing is staged. Use -a, pass file paths, or stage files with git first.');
      }
      ok(`Using the ${stagedBefore.length} file(s) already staged.`);
    }

    const staged = stagedPaths();
    if (staged.length === 0) {
      fail('Nothing staged, so there is nothing to commit. Aborting.');
    }

    /* ---------------------------------------------------------- */
    section(4, 'Reviewing staged changes');

    const stat = gitOutSafe(['diff', '--cached', '--stat']);
    say(stat || dim('(no diff available)'));

    if (!(await confirm('Continue to the commit message?', true))) {
      say(yellow('Stopped before committing. Your staged changes are preserved.'));
      return;
    }

    /* ---------------------------------------------------------- */
    section(5, 'Writing the commit message');

    let subject = opts.message;
    let body = '';

    if (subject == null) {
      if (!interactive) fail('No message provided. Use -m "your message".');
      subject = await ask('Subject (short summary):', '');
      while (!subject) {
        warn('A commit message is required.');
        subject = await ask('Subject (short summary):', '');
      }
      if (await confirm('Add a longer description?', false)) {
        say(dim('Enter body lines, finish with an empty line:'));
        const lines = [];
        for (;;) {
          const bodyLine = await line('> ');
          if (!bodyLine.trim()) break;
          lines.push(bodyLine.replace(/\s+$/, ''));
        }
        body = lines.join('\n');
      }
    } else {
      // Allow "subject\n\nbody" passed through -m.
      const split = opts.message.split(/\r?\n\r?\n/);
      subject = split.shift().trim();
      body = split.join('\n\n').trim();
    }

    subject = subject.replace(/\s+$/, '');
    if (!subject) fail('Commit subject is empty.');

    if (subject.length > 72) {
      warn(`Subject is ${subject.length} characters; 72 or fewer is easier to scan.`);
    }
    if (!/^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: /.test(subject)) {
      say(dim('Tip: "feat:", "fix:", "chore:" prefixes are common in this repo.'));
    }

    say('');
    say(dim('---------------- commit message ----------------'));
    say(bold(subject));
    if (body) {
      say('');
      say(body);
    }
    say(dim('------------------------------------------------'));

    /* ---------------------------------------------------------- */
    section(6, 'Committing');

    if (opts.dryRun) {
      ok('Dry run enabled: skipping "git commit" and "git push".');
      return;
    }

    if (!(await confirm(bold('Create this commit?'), true))) {
      say(yellow('Stopped. Your staged changes are preserved.'));
      return;
    }

    const commitArgs = ['commit', '-m', subject];
    if (body) commitArgs.push('-m', body);
    gitRun(commitArgs);
    ok(`Committed: ${bold(gitOutSafe(['log', '-1', '--oneline']))}`);

    const remaining = changedPaths();
    if (remaining.length > 0) {
      warn(`${remaining.length} uncommitted change(s) remain in the working tree.`);
    }

    /* ---------------------------------------------------------- */
    const wantsPush = opts.push || (interactive && (await confirm('Push to origin now?', false)));
    if (!wantsPush) {
      say(dim('Not pushed. Run "git push" when you are ready.'));
      return;
    }

    if (branch === '(detached HEAD)') {
      warn('Cannot push from a detached HEAD. Skipping push.');
      return;
    }
    if ((branch === 'main' || branch === 'master') && interactive) {
      if (!(await confirm(yellow(`You are on "${branch}". Push anyway?`), false))) {
        say(dim('Push skipped.'));
        return;
      }
    }

    const upstream = gitOutSafe(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']);
    if (upstream) {
      gitRun(['push']);
      ok(`Pushed to ${cyan(upstream)}.`);
    } else {
      warn(`No upstream set for "${branch}". Creating one.`);
      gitRun(['push', '-u', 'origin', branch]);
      ok(`Pushed and tracking ${cyan(`origin/${branch}`)}.`);
    }
  } finally {
    close();
  }
}

main().catch((error) => {
  if (process.exitCode !== 1) {
    say(`${red('error')} ${error.message || error}`);
    process.exitCode = 1;
  }
});
