// POST /api/auth  {mode:'signup'|'login', id, pw}  →  {id, token}
const L = require('./_lib');

module.exports = async (req, res) => {
  if (req.method !== 'POST') return L.send(res, 405, { error: 'POST only' });
  if (!L.configured()) return L.notReady(res);
  try {
    const { mode, id: rawId, pw } = L.body(req);
    const id = L.normId(rawId);
    if (await L.limited(req, 'auth', 30)) return L.send(res, 429, { code: 'rate', error: '시도가 너무 많습니다. 15분 뒤에 다시 해 주세요.' });
    if (!L.ID_RE.test(id)) return L.send(res, 400, { code: 'bad_id', error: '아이디는 2~20자의 한글·영문 소문자·숫자·_ . - 로 정해 주세요.' });
    if (typeof pw !== 'string' || pw.length < 6 || pw.length > 100) return L.send(res, 400, { code: 'bad_pw', error: '비밀번호는 6자 이상으로 정해 주세요.' });
    const key = 'u:' + id;
    if (mode === 'signup') {
      const salt = L.crypto.randomBytes(16).toString('base64');
      const rec = JSON.stringify({ salt, hash: await L.hashPw(pw, salt), created: Date.now() });
      const ok = await L.redis(['SET', key, rec, 'NX']);
      if (ok !== 'OK') return L.send(res, 409, { code: 'taken', error: '이미 있는 아이디입니다. 다른 아이디를 쓰거나 로그인해 주세요.' });
      return L.send(res, 200, { id, token: L.sign(id) });
    }
    if (mode === 'login') {
      const raw = await L.redis(['GET', key]);
      const fail = () => L.send(res, 401, { code: 'bad_login', error: '아이디 또는 비밀번호가 맞지 않습니다.' });
      if (!raw) return fail();
      const rec = JSON.parse(raw);
      const h = await L.hashPw(pw, rec.salt);
      if (!L.crypto.timingSafeEqual(Buffer.from(h), Buffer.from(rec.hash))) return fail();
      return L.send(res, 200, { id, token: L.sign(id) });
    }
    return L.send(res, 400, { error: 'mode must be signup or login' });
  } catch (e) {
    return L.send(res, 500, { code: 'server', error: '서버 오류가 났습니다. 잠시 뒤 다시 해 주세요.' });
  }
};
