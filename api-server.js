#!/usr/bin/env node
// api-server.js — Family Hub local API server
// Receives JSON data, saves to files, syncs to GitHub
// Usage: node api-server.js

const http = require('http');
const fs   = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PORT     = 4747;
const DATA_DIR = path.join(__dirname, 'data');
const SYNC_SH  = '/root/clawd/scripts/sync_data.sh';

const ALLOWED = {
  'acoes':         'acoes.json',
  'acoes_pessoas': 'acoes_pessoas.json',
  'acoes_imoveis': 'acoes_imoveis.json',
  'compras':       'compras.json',
  'lancamentos':   'lancamentos.json',
  'receitas':      'receitas.json',
  'viagem':        'viagem.json',
};

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function ok(res, body) {
  cors(res);
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function err(res, code, msg) {
  cors(res);
  res.writeHead(code, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: msg }));
}

const server = http.createServer((req, res) => {
  cors(res);

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  const url = req.url.split('?')[0];

  // GET /ping — health check
  if (req.method === 'GET' && url === '/ping') {
    return ok(res, { ok: true, port: PORT });
  }

  // POST /save/:dataset
  if (req.method === 'POST' && url.startsWith('/save/')) {
    const dataset = url.replace('/save/', '').replace(/\//g, '');
    const filename = ALLOWED[dataset];
    if (!filename) return err(res, 400, `Dataset '${dataset}' not allowed`);

    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const filePath = path.join(DATA_DIR, filename);
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');

        // Run git sync: add → commit → push (no pull first to avoid conflicts)
        try {
          const msg = data._commitMsg || `update: ${dataset} via dashboard`;
          delete data._commitMsg;
          fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
          const repoDir = __dirname;
          execSync(`cd "${repoDir}" && git add data/${filename}`, { timeout: 10000 });
          // Only commit if there are staged changes
          const diff = execSync(`cd "${repoDir}" && git diff --cached --name-only`, { timeout: 5000 }).toString().trim();
          if (diff) {
            execSync(`cd "${repoDir}" && git commit -m "${msg.replace(/"/g, "'")}"`, { timeout: 10000 });
            execSync(`cd "${repoDir}" && git push origin main`, { timeout: 30000 });
          }
          return ok(res, { saved: true, synced: true });
        } catch (syncErr) {
          return ok(res, { saved: true, synced: false, syncError: syncErr.message });
        }
      } catch (e) {
        return err(res, 400, 'Invalid JSON: ' + e.message);
      }
    });
    return;
  }

  err(res, 404, 'Not found');
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`✅ Family Hub API running on http://127.0.0.1:${PORT}`);
});

server.on('error', e => {
  if (e.code === 'EADDRINUSE') {
    console.error(`❌ Port ${PORT} already in use. Kill existing process first.`);
  } else {
    console.error('Server error:', e);
  }
  process.exit(1);
});
