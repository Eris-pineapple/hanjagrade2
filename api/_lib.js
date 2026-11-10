// 앱 계정 서버 공용 코드 (Vercel 서버리스 함수)
// 저장소: Upstash Redis (Vercel Storage에서 연결하면 KV_REST_API_URL / KV_REST_API_TOKEN 이 자동으로 들어옴)
const crypto = require('crypto');

const R_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const R_TOK = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
const configured = () => !!(R_URL && R_TOK);

async function redis(cmd) {
  const r = await fetch(R_URL, { method: 'POST', headers: { Authorization: 'Bearer ' + R_TOK, 'Content-Type': 'application/json' }, body: JSON.stringify(cmd) });
  const j = await r.json();
  if (j.error) throw new Error(j.error);
  return j.result;
}
async function pipe(cmds) {
  const r = await fetch(R_URL.replace(/\/$/, '') + '/pipeline', { method: 'POST', headers: { Authorization: 'Bearer ' + R_TOK, 'Content-Type': 'application/json' }, body: JSON.stringify(cmds) });
  const j = await r.json();
  if (!Array.isArray(j)) throw new Error((j && j.error) || 'pipeline failed');
  return j.map(x => { if (x.error) throw new Error(x.error); return x.result; });
}

const secret = () => process.env.AUTH_SECRET || crypto.createHash('sha256').update('hanja2-auth:' + R_TOK).digest();
const TOKEN_DAYS = 400;
function sign(id) {
  const body = Buffer.from(JSON.stringify({ id, exp: Date.now() + TOKEN_DAYS * 864e5 })).toString('base64url');
  const mac = crypto.createHmac('sha256', secret()).update(body).digest('base64url');
  return body + '.' + mac;
}
function verify(tok) {
  if (typeof tok !== 'string') return null;
  const [body, mac] = tok.split('.');
  if (!body || !mac) return null;
  const want = crypto.createHmac('sha256', secret()).update(body).digest('base64url');
  if (want.length !== mac.length || !crypto.timingSafeEqual(Buffer.from(want), Buffer.from(mac))) return null;
  try { const p = JSON.parse(Buffer.from(body, 'base64url').toString()); return p.exp > Date.now() && typeof p.id === 'string' ? p.id : null; } catch (e) { return null; }
}
const userOf = req => verify(((req.headers.authorization || '').match(/^Bearer (.+)$/) || [])[1]);

function hashPw(pw, salt) {
  return new Promise((ok, no) => crypto.scrypt(pw, salt, 32, { N: 16384, r: 8, p: 1 }, (e, k) => e ? no(e) : ok(k.toString('base64'))));
}
const ID_RE = /^[a-z0-9가-힣_.-]{2,20}$/;
const normId = s => String(s || '').trim().toLowerCase();

async function limited(req, key, max) {
  const ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'x';
  const k = 'rl:' + key + ':' + ip;
  const [n] = await pipe([['INCR', k], ['EXPIRE', k, 900, 'NX']]);
  return n > max;
}
function body(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  try { return JSON.parse(req.body || '{}'); } catch (e) { return {}; }
}
const send = (res, code, obj) => { res.statusCode = code; res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.setHeader('Cache-Control', 'no-store'); res.end(JSON.stringify(obj)); };
const notReady = res => send(res, 503, { code: 'not_configured', error: '서버 저장소가 아직 연결되지 않았습니다.' });

module.exports = { configured, redis, pipe, sign, userOf, hashPw, ID_RE, normId, limited, body, send, notReady, crypto };
