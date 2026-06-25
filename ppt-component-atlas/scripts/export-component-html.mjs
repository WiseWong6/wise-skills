#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const skillRoot = path.resolve(__dirname, '..');
const catalogPath = path.join(skillRoot, 'public', 'catalog-data.js');
const DETAIL_URL_BASE = 'https://wisewong.com/projects/html-ppt-components/#/layout/';
const SOURCE_REPO_URL = 'https://github.com/WiseWong6/wise-labs/tree/main/html-ppt-components';
const RAW_CATALOG_URL = 'https://raw.githubusercontent.com/WiseWong6/wise-labs/main/html-ppt-components/catalog-data.js';

const WRAPPED_FLOW_CSS = `
.swiss-card .process-chain[data-type="wrap"] {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(2, auto);
  grid-template-areas:
    "s1 s2 s3"
    "s6 s5 s4";
  gap: 24px 32px;
  position: relative;
  padding: 10px 20px;
  overflow: visible;
}
.swiss-card .process-chain[data-type="wrap"] .step {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px 12px;
  background: rgba(217,94,0,0.08);
  border: 2px solid #d95e00;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}
.swiss-card .process-chain[data-type="wrap"] .arrow {
  display: none;
}
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(1) { grid-area: s1; }
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(3) { grid-area: s2; }
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(5) { grid-area: s3; }
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(7) { grid-area: s4; }
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(9) { grid-area: s5; }
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(11) { grid-area: s6; }
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(1)::after,
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(3)::after {
  content: '->';
  position: absolute;
  right: -26px;
  top: 50%;
  transform: translateY(-50%);
  color: #d95e00;
  font-size: 16px;
  font-weight: 700;
}
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(5)::after {
  content: 'v';
  position: absolute;
  left: 50%;
  bottom: -26px;
  transform: translateX(-50%);
  color: #d95e00;
  font-size: 16px;
  font-weight: 700;
}
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(7)::after,
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(9)::after {
  content: '<-';
  position: absolute;
  left: -26px;
  top: 50%;
  transform: translateY(-50%);
  color: #d95e00;
  font-size: 16px;
  font-weight: 700;
  z-index: 2;
}
.swiss-card .process-chain[data-type="wrap"] .step:nth-child(11)::before {
  content: '^';
  position: absolute;
  left: 50%;
  top: -26px;
  transform: translateX(-50%);
  color: #d95e00;
  font-size: 16px;
  font-weight: 700;
  z-index: 2;
}`;

function parseArgs(argv) {
  const args = {
    list: false,
    query: '',
    outDir: path.resolve(process.cwd(), 'outputs', 'ppt-components'),
    verifySource: false
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--list') {
      args.list = true;
      continue;
    }
    if (arg === '--query') {
      args.query = argv[++i] || '';
      continue;
    }
    if (arg === '--out-dir') {
      args.outDir = path.resolve(argv[++i] || args.outDir);
      continue;
    }
    if (arg === '--verify-source') {
      args.verifySource = true;
      continue;
    }
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  return args;
}

function printJson(payload) {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}

function loadCatalogFromSource(source, filename) {
  const sandbox = { window: {} };
  vm.runInNewContext(source, sandbox, { filename });
  const data = sandbox.window.SWISS_CATALOG_DATA;
  if (!data || !Array.isArray(data.entries) || typeof data.componentCss !== 'string') {
    throw new Error(`Invalid catalog data: ${filename}`);
  }
  return data;
}

function loadCatalog() {
  const source = fs.readFileSync(catalogPath, 'utf8');
  return {
    source,
    data: loadCatalogFromSource(source, catalogPath)
  };
}

async function fetchRemoteCatalogSource() {
  const response = await fetch(RAW_CATALOG_URL, {
    headers: { 'user-agent': 'ppt-component-atlas' }
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch remote catalog: ${response.status} ${response.statusText}`);
  }
  return response.text();
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function entryKeyList(data) {
  return data.entries.map((entry) => (
    `${entry.num}:${entry.name}:${entry.variant || ''}:${entry.label}`
  ));
}

async function verifySource() {
  const local = loadCatalog();
  const remoteSource = await fetchRemoteCatalogSource();
  const remoteData = loadCatalogFromSource(remoteSource, RAW_CATALOG_URL);
  const localKeys = entryKeyList(local.data);
  const remoteKeys = entryKeyList(remoteData);
  const matches = {
    source: local.source === remoteSource,
    entryCount: local.data.entries.length === remoteData.entries.length,
    entries: JSON.stringify(localKeys) === JSON.stringify(remoteKeys),
    componentCss: local.data.componentCss === remoteData.componentCss
  };
  const ok = Object.values(matches).every(Boolean);

  printJson({
    status: ok ? 'ok' : 'mismatch',
    sourceRepoUrl: SOURCE_REPO_URL,
    rawCatalogUrl: RAW_CATALOG_URL,
    local: {
      path: catalogPath,
      count: local.data.entries.length,
      sha256: sha256(local.source)
    },
    remote: {
      count: remoteData.entries.length,
      sha256: sha256(remoteSource)
    },
    matches
  });

  if (!ok) process.exitCode = 1;
}

function normalizeText(value) {
  return String(value || '')
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/[＿_:/]+/g, ' ')
    .replace(/[‐‑‒–—―]+/g, '-')
    .replace(/\s+/g, ' ');
}

function normalizeLoose(value) {
  return normalizeText(value).replace(/[\s\-_:/]+/g, '');
}

function getDetailUrl(entry) {
  return `${DETAIL_URL_BASE}${encodeURIComponent(String(entry.num))}`;
}

function entrySummary(entry) {
  return {
    num: entry.num,
    name: entry.name,
    label: entry.label,
    variant: entry.variant || null,
    groupLabel: entry.groupLabel,
    description: entry.description,
    detailUrl: getDetailUrl(entry)
  };
}

function entryAliases(entry) {
  const aliases = [
    entry.label,
    entry.name,
    String(entry.num)
  ];

  if (entry.variant) {
    aliases.push(
      entry.variant,
      `${entry.name} ${entry.variant}`,
      `${entry.name}-${entry.variant}`,
      `${entry.name}/${entry.variant}`,
      `${entry.name}:${entry.variant}`,
      `${entry.label} ${entry.variant}`
    );
  }

  return aliases.filter(Boolean);
}

function findFuzzyCandidates(entries, query) {
  const q = normalizeText(query);
  const qLoose = normalizeLoose(query);
  const tokens = q.split(/[\s\-]+/).filter(Boolean);

  return entries
    .map((entry) => {
      const aliases = entryAliases(entry);
      const aliasText = normalizeText(aliases.join(' '));
      const aliasLoose = normalizeLoose(aliases.join(' '));
      const haystack = normalizeText([
        entry.label,
        entry.name,
        entry.variant,
        entry.groupLabel,
        entry.description
      ].filter(Boolean).join(' '));
      const haystackLoose = normalizeLoose(haystack);

      let score = 0;
      if (aliasText.includes(q)) score += 30;
      if (aliasLoose.includes(qLoose)) score += 24;
      if (haystack.includes(q)) score += 18;
      if (haystackLoose.includes(qLoose)) score += 12;
      if (tokens.length && tokens.every((token) => haystack.includes(token))) score += 10;
      if (tokens.length && tokens.every((token) => haystackLoose.includes(token))) score += 8;
      if (entry.variant && q.includes(normalizeText(entry.variant))) score += 5;
      if (score > 0 && !entry.variant) score += 1;

      return { entry, score };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.entry.num - b.entry.num)
    .map((item) => item.entry);
}

function selectByQuery(entries, query) {
  const q = normalizeText(query);
  const qLoose = normalizeLoose(query);

  const exact = entries.filter((entry) => (
    entryAliases(entry).some((alias) => (
      normalizeText(alias) === q || normalizeLoose(alias) === qLoose
    ))
  ));

  if (exact.length === 1) return { status: 'ok', entry: exact[0] };
  if (exact.length > 1) {
    const baseMatches = exact.filter((entry) => !entry.variant);
    if (baseMatches.length === 1) return { status: 'ok', entry: baseMatches[0] };
    return { status: 'ambiguous', candidates: exact };
  }

  const fuzzy = findFuzzyCandidates(entries, query);
  if (fuzzy.length === 1) return { status: 'ok', entry: fuzzy[0] };
  if (fuzzy.length > 1) return { status: 'ambiguous', candidates: fuzzy.slice(0, 12) };
  return { status: 'not_found', candidates: entries.slice(0, 12) };
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function decodeHtml(value) {
  const named = {
    amp: '&',
    lt: '<',
    gt: '>',
    quot: '"',
    apos: "'",
    nbsp: ' '
  };
  return String(value)
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(Number.parseInt(dec, 10)))
    .replace(/&([a-z]+);/gi, (match, name) => named[name.toLowerCase()] ?? match);
}

function normalizeVisibleText(value) {
  return decodeHtml(value).replace(/\s+/g, ' ').trim();
}

function extractEditableText(snippet) {
  const cleaned = String(snippet)
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, '');
  const seen = new Set();
  const texts = [];

  for (const match of cleaned.matchAll(/>([^<>]+)</g)) {
    const text = normalizeVisibleText(match[1]);
    if (!text || seen.has(text)) continue;
    seen.add(text);
    texts.push(text);
  }

  return texts;
}

function buildBareHtmlDoc(entry, componentCss, snippet) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>${escapeHtml(entry.label || entry.name)}</title>
  <style>
    :root {
      --bg: #fdf9ee;
      --surface: #f4f3ee;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #fff;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 16px;
    }
    .component-shell {
      width: 100%;
      max-width: 480px;
      padding: 16px;
      background: #fff;
    }
    .swiss-card { width: 100% !important; min-height: auto !important; box-shadow: none !important; }
    .swiss-card__content { min-height: auto !important; padding: 20px 0 !important; }
    .swiss-card--cover .swiss-card__content { padding: 24px 0 !important; }
    ${componentCss}
    ${WRAPPED_FLOW_CSS}
  </style>
</head>
<body>
  <div class="component-shell">
    ${snippet}
  </div>
</body>
</html>`;
}

function slugify(value) {
  const slug = normalizeText(value)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'component';
}

function outputFileName(entry) {
  const parts = [String(entry.num), slugify(entry.name)];
  if (entry.variant) parts.push(slugify(entry.variant));
  return `${parts.join('-')}.html`;
}

function usage() {
  return {
    usage: [
      'node scripts/export-component-html.mjs --list',
      'node scripts/export-component-html.mjs --query "cover" --out-dir outputs/ppt-components',
      'node scripts/export-component-html.mjs --verify-source'
    ]
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.verifySource) {
    await verifySource();
    return;
  }

  const catalog = loadCatalog().data;
  const entries = catalog.entries;

  if (args.help) {
    printJson({ status: 'ok', ...usage() });
    return;
  }

  if (args.list) {
    printJson({ status: 'ok', count: entries.length, entries: entries.map(entrySummary) });
    return;
  }

  if (!args.query.trim()) {
    printJson({ status: 'error', message: 'Missing --query.', ...usage() });
    process.exitCode = 1;
    return;
  }

  const result = selectByQuery(entries, args.query);
  if (result.status === 'ambiguous') {
    printJson({
      status: 'ambiguous',
      query: args.query,
      count: result.candidates.length,
      candidates: result.candidates.map(entrySummary)
    });
    return;
  }
  if (result.status === 'not_found') {
    printJson({
      status: 'not_found',
      query: args.query,
      candidates: result.candidates.map(entrySummary)
    });
    return;
  }

  const entry = result.entry;
  const editableText = extractEditableText(entry.snippet);
  const html = buildBareHtmlDoc(entry, catalog.componentCss, entry.snippet);
  const outDir = path.resolve(args.outDir);
  fs.mkdirSync(outDir, { recursive: true });
  const file = path.join(outDir, outputFileName(entry));
  fs.writeFileSync(file, html, 'utf8');

  printJson({
    status: 'ok',
    query: args.query,
    entry: entrySummary(entry),
    file,
    fileUrl: pathToFileURL(file).href,
    detailUrl: getDetailUrl(entry),
    editableText
  });
}

try {
  await main();
} catch (error) {
  printJson({ status: 'error', message: error.message });
  process.exitCode = 1;
}
