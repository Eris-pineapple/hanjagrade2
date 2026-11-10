// /api/data  (Authorization: Bearer <token>)
//  GET            → {progress, sessions[]}
//  PUT  {progress} → 진도 저장
//  POST {session}  → 시험 기록 1건 추가
const L = require('./_lib');
const MAX_SESS = 300;

// chars[n] = [맞힘, 틀림, 마지막 정답여부, 마지막 시각]: 글자마다 더 최근 것을 씀
// 오답노트: 보낸 기기의 것을 기준으로, 그 기기가 아직 모르는 더 최근 기록만 서버 것을 따름 (비우기 유지)
function mergeIn(cur, inc) {
  const t = v => (v && v[3]) || 0;
  const cc = cur.chars || {}, ic = inc.chars || {};
  const chars = Object.assign({}, cc);
  for (const [n, v] of Object.entries(ic)) if (!chars[n] || t(v) >= t(chars[n])) chars[n] = v;
  const wrong = Object.assign({}, inc.wrong || {});
  for (const [n, v] of Object.entries(cc)) {
    if (t(v) > t(ic[n])) { if (v[2] === 0 && (cur.wrong || {})[n]) wrong[n] = cur.wrong[n]; else if (v[2] === 1) delete wrong[n]; }
  }
  return Object.assign({}, inc, { chars, wrong, updated: Math.max(cur.updated || 0, inc.updated || 0) });
}

module.exports = async (req, res) => {
  if (!L.configured()) return L.notReady(res);
  const id = L.userOf(req);
  if (!id) return L.send(res, 401, { code: 'auth', error: '다시 로그인해 주세요.' });
  const pk = 'p:' + id, sk = 's:' + id;
  try {
    if (req.method === 'GET') {
      const [p, h] = await L.pipe([['GET', pk], ['HGETALL', sk]]);
      const sessions = [];
      for (let i = 0; i + 1 < (h || []).length; i += 2) { try { sessions.push(JSON.parse(h[i + 1])); } catch (e) {} }
      sessions.sort((a, b) => (b.ts || 0) - (a.ts || 0));
      return L.send(res, 200, { progress: p ? JSON.parse(p) : null, sessions });
    }
    const b = L.body(req);
    if (req.method === 'PUT') {
      const p = b.progress;
      if (!p || typeof p !== 'object') return L.send(res, 400, { error: 'progress required' });
      // 다른 기기가 먼저 저장한 기록을 덮어쓰지 않도록 서버에 있는 것과 합쳐서 저장
      const curRaw = await L.redis(['GET', pk]);
      const merged = curRaw ? mergeIn(JSON.parse(curRaw), p) : p;
      const s = JSON.stringify(merged);
      if (s.length > 900000) return L.send(res, 413, { code: 'quota_exceeded', error: '기록이 너무 큽니다.' });
      await L.redis(['SET', pk, s]);
      return L.send(res, 200, { ok: true });
    }
    if (req.method === 'POST') {
      const s = b.session;
      if (!s || typeof s !== 'object' || typeof s.id !== 'string' || s.id.length > 80) return L.send(res, 400, { error: 'session required' });
      const js = JSON.stringify(s);
      if (js.length > 200000) return L.send(res, 413, { code: 'quota_exceeded', error: '기록이 너무 큽니다.' });
      const [, n] = await L.pipe([['HSET', sk, s.id, js], ['HLEN', sk]]);
      if (n > MAX_SESS + 20) {
        const h = await L.redis(['HGETALL', sk]);
        const all = [];
        for (let i = 0; i + 1 < h.length; i += 2) { let ts = 0; try { ts = JSON.parse(h[i + 1]).ts || 0; } catch (e) {} all.push([h[i], ts]); }
        all.sort((x, y) => y[1] - x[1]);
        const old = all.slice(MAX_SESS).map(x => x[0]);
        if (old.length) await L.redis(['HDEL', sk, ...old]);
      }
      return L.send(res, 200, { ok: true });
    }
    return L.send(res, 405, { error: 'method' });
  } catch (e) {
    return L.send(res, 500, { code: 'server', error: '서버 오류가 났습니다.' });
  }
};
