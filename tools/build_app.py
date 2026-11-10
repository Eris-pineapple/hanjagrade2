#!/usr/bin/env python3
"""claude.ai 아티팩트 HTML → 앱(PWA)용 index.html 변환.
사용법: python3 tools/build_app.py <아티팩트.html> [index.html]
- manifest/아이콘/메타 태그 추가
- 앱에서도 오답정리노트 파일 저장(브라우저 다운로드)
- 서비스워커 등록(오프라인 실행)
- 앱 계정 로그인(api/ 서버)으로 기기 사이 기록 공유
"""
import sys
src, out = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'index.html')
s = open(src, encoding='utf-8').read()

HEAD = '''<meta charset=utf8><link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#eef1ec" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#121614" media="(prefers-color-scheme: dark)">
<link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">
<link rel="icon" type="image/png" sizes="48x48" href="icons/favicon-48.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="2급 한자">
<meta name="application-name" content="2급 한자">'''
a = '<html><head><meta charset=utf8>'
assert s.count(a) == 1, 'head 위치를 찾지 못함'
s = s.replace(a, '<html lang="ko"><head>' + HEAD, 1)

b = "(async()=>{ try{ if(window.claude && typeof window.claude.use==='function') DL = await window.claude.use('downloads'); }catch(e){} if(!$('note').hidden) renderNote(); })();"
assert s.count(b) == 1, '파일 저장 코드를 찾지 못함'
s = s.replace(b, '''/* 앱(PWA)에서는 Claude 저장 기능 대신 브라우저 다운로드로 파일 저장 */
const LOCAL_DL={ async save({filename,data}){
  const type=/\\.csv$/i.test(filename)?'text/csv;charset=utf-8':'text/html;charset=utf-8';
  const url=URL.createObjectURL(new Blob([data],{type}));
  const a=document.createElement('a'); a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),4000);
} };
(async()=>{ try{ if(window.claude && typeof window.claude.use==='function') DL = await window.claude.use('downloads'); }catch(e){} if(!DL) DL=LOCAL_DL; if(!$('note').hidden) renderNote(); })();
/* 서비스워커: 오프라인 실행 */
if('serviceWorker' in navigator && (location.protocol==='https:' || location.hostname==='localhost')){ addEventListener('load',()=>{ navigator.serviceWorker.register('sw.js').catch(()=>{}); }); }''', 1)

# ---------- 앱 계정(아이디·비밀번호) — 같은 계정이면 기기 사이 기록 공유 ----------
# 아티팩트의 계정 저장 코드(window.claude.use('db'/'user'))를 그대로 쓰고, 그 자리에 /api 서버를 연결한다.
SHIM = r"""<script>
/* 앱 계정 연결부: 로그인 토큰은 이 기기에 저장되어 로그아웃 전까지 유지됨 */
(function(){
  const KEY='hj2-auth';
  const A={ get(){ try{ return JSON.parse(localStorage.getItem(KEY)||'null'); }catch(e){ return null; } },
            set(v){ try{ v?localStorage.setItem(KEY,JSON.stringify(v)):localStorage.removeItem(KEY); }catch(e){} } };
  async function api(path,opt){
    opt=opt||{}; const a=A.get(); const h={'Content-Type':'application/json'}; if(a&&a.token) h.Authorization='Bearer '+a.token;
    const r=await fetch('/api/'+path,{method:opt.method||'GET',headers:h,body:opt.body?JSON.stringify(opt.body):undefined,cache:'no-store'});
    let j=null; try{ j=await r.json(); }catch(e){}
    if(!r.ok){ const err=new Error((j&&j.error)||('HTTP '+r.status)); err.status=r.status; err.code=j&&j.code;
      if(r.status===401 && path==='data'){ A.set(null); setTimeout(()=>window.dispatchEvent(new Event('hj2-auth')),0); }
      throw err; }
    return j;
  }
  let cache=null;
  const sessions={ doc(id){ return { set:(s)=>api('data',{method:'POST',body:{session:s}}) }; },
    orderBy(){ return sessions; }, limit(){ return sessions; },
    async get(){ const c=cache||await api('data'); cache=null; return {docs:(c.sessions||[]).slice(0,200).map(s=>({data:()=>s}))}; } };
  const progress={ async get(){ cache=await api('data'); return {exists:!!cache.progress, data:()=>cache.progress}; },
    set:(body)=>api('data',{method:'PUT',body:{progress:body}}), collection:()=>sessions };
  const db={ doc:()=>progress };
  window.HJ_ACCOUNT={A,api};
  window.claude={ use: async (name)=>{ const a=A.get(); if(!a||!a.token) return null;
    if(name==='db') return db; if(name==='user') return { id: async()=>'acct:'+a.id }; return null; } };
})();
</script>
"""
c = '<script>\nconst D = '
assert s.count(c) == 1, '본문 스크립트 시작을 찾지 못함'
s = s.replace(c, SHIM + c, 1)

d = '<section id="setup" style="display:flex;flex-direction:column;gap:16px">'
assert s.count(d) == 1, '시험 설정 위치를 찾지 못함'
s = s.replace(d, d + '\n    <div class="sheet acct" id="acctBar"></div>', 1)

e = '  <!-- RESULT -->'
assert s.count(e) == 1, '결과 영역을 찾지 못함'
s = s.replace(e, '  <!-- 앱 계정 -->\n  <div class="wback" id="aback" hidden></div>\n  <div class="wpop" id="apop" hidden role="dialog" aria-modal="true" aria-label="로그인"><div class="card" id="acard"></div></div>\n\n' + e, 1)

f = '</style>\n\n<div class="wrap" id="app">'
assert s.count(f) == 1, '스타일 끝을 찾지 못함'
s = s.replace(f, """.acct{flex-direction:row;align-items:center;gap:10px 14px;flex-wrap:wrap;padding:12px 16px}
.acct .who{flex:1 1 200px;min-width:0;font-size:.9rem}
.acct .who b{font-weight:600}
.acct .who span{display:block;font-size:.78rem;color:var(--muted)}
.acct .btn{padding:8px 14px}
#sync{cursor:pointer}
.aform{display:flex;flex-direction:column;gap:10px}
.aform label{display:flex;flex-direction:column;gap:4px;font-size:.8rem;color:var(--muted);font-weight:600}
.aform input{font:inherit;font-size:1.05rem;padding:10px 12px;border:1.5px solid var(--rule);border-radius:8px;background:var(--paper);color:var(--ink)}
.aform .msg{font-size:.85rem;min-height:1.2em;margin:0}
.aform .msg.bad{color:var(--bad)}
.aswitch{background:none;border:none;color:var(--muted);font-size:.85rem;text-decoration:underline;padding:4px 0;align-self:flex-start}
""" + f, 1)

g = "/* 서비스워커: 오프라인 실행 */"
assert s.count(g) == 1, '서비스워커 등록 위치를 찾지 못함'
s = s.replace(g, r"""/* ---------- 앱 계정 화면 ---------- */
const ACC = window.HJ_ACCOUNT;
function renderAcct(){
  const a = ACC.A.get();
  $('acctBar').innerHTML = a
    ? `<div class="who"><b>${esc(a.id)}</b> 계정으로 로그인됨<span>같은 계정으로 로그인한 기기끼리 기록·오답노트를 함께 씁니다.</span></div><button class="btn ghost" id="acctOut">로그아웃</button>`
    : `<div class="who"><b>로그인하면 기록을 함께 씁니다</b><span>휴대폰·컴퓨터 어디서든 같은 계정으로 들어오면 기록이 이어집니다. 지금은 이 기기에만 저장됩니다.</span></div><button class="btn" id="acctIn">로그인</button><button class="btn ghost" id="acctUp">가입</button>`;
  const on=(id,fn)=>{ const el=$(id); if(el) el.addEventListener('click',fn); };
  on('acctIn',()=>openAcct('login')); on('acctUp',()=>openAcct('signup')); on('acctOut',logoutAcct);
}
function closeAcct(){ $('apop').hidden=true; $('aback').hidden=true; }
function openAcct(mode){
  const up = mode==='signup';
  $('acard').innerHTML = `<div class="top"><span class="w" style="font-family:var(--f-ui);font-size:1.3rem">${up?'계정 만들기':'로그인'}</span><button class="x" id="aclose" aria-label="닫기">×</button></div>
  <form class="aform" id="aform" autocomplete="on">
    <label>아이디<input id="aid" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required minlength="2" maxlength="20"></label>
    <label>비밀번호<input id="apw" name="password" type="password" autocomplete="${up?'new-password':'current-password'}" required minlength="6"></label>
    ${up?'<label>비밀번호 확인<input id="apw2" type="password" autocomplete="new-password" required minlength="6"></label>':''}
    <p class="msg" id="amsg">${up?'아이디는 2~20자(한글·영문 소문자·숫자·_ . -), 비밀번호는 6자 이상입니다. 비밀번호는 찾을 수 없으니 잘 기억해 두세요.':'로그인하면 로그아웃할 때까지 이 기기에서 계속 로그인됩니다.'}</p>
    <button class="btn" type="submit" id="ago">${up?'가입하고 로그인':'로그인'}</button>
    <button class="aswitch" type="button" id="aswap">${up?'이미 계정이 있어요 → 로그인':'처음이에요 → 계정 만들기'}</button>
  </form>`;
  $('apop').hidden=false; $('aback').hidden=false;
  $('aclose').addEventListener('click',closeAcct);
  $('aswap').addEventListener('click',()=>openAcct(up?'login':'signup'));
  $('aform').addEventListener('submit',async ev=>{
    ev.preventDefault();
    const msg=$('amsg'), id=$('aid').value.trim(), pw=$('apw').value;
    if (up && pw!==$('apw2').value){ msg.className='msg bad'; msg.textContent='비밀번호 확인이 다릅니다.'; return; }
    $('ago').disabled=true; msg.className='msg'; msg.textContent='확인하는 중…';
    try{
      const r = await ACC.api('auth',{method:'POST',body:{mode:up?'signup':'login',id,pw}});
      ACC.A.set({id:r.id, token:r.token});
      closeAcct(); renderAcct(); setSync(false,'기록 맞추는 중');
      await initRemote();
    }catch(e){
      msg.className='msg bad';
      msg.textContent = e.code==='not_configured' ? '서버 저장소가 아직 연결되지 않았습니다. (관리자 설정 필요)'
        : (e.status ? e.message : '인터넷 연결을 확인해 주세요.');
      $('ago').disabled=false;
    }
  });
  setTimeout(()=>{ const el=$('aid'); if(el) el.focus(); },50);
}
function logoutAcct(){
  $('acctBar').innerHTML = `<div class="who"><b>로그아웃할까요?</b><span>이 기기에 있던 기록은 지워지고, 계정에 저장된 기록은 그대로 남습니다. 다시 로그인하면 돌아옵니다.</span></div><button class="btn seal" id="acctYes">로그아웃</button><button class="btn ghost" id="acctNo">취소</button>`;
  $('acctNo').addEventListener('click',renderAcct);
  $('acctYes').addEventListener('click',async ()=>{
    try{ await R.writing; }catch(e){}
    ACC.A.set(null);
    for (const k of ['hj2-progress','hj2-sessions','hj2-wrong']) { try{ localStorage.removeItem(k); }catch(e){} }
    location.reload();
  });
}
$('aback').addEventListener('click',closeAcct);
$('sync').addEventListener('click',()=>{ if(!ACC.A.get()) openAcct('login'); else { showTab('test'); window.scrollTo({top:0}); } });
document.addEventListener('keydown',ev=>{ if(ev.key==='Escape' && !$('apop').hidden){ ev.stopPropagation(); closeAcct(); } }, true);
window.addEventListener('hj2-auth',()=>{ R.ready=false; renderAcct(); setSync(false,'로그인이 풀렸습니다 · 다시 로그인해 주세요'); });
window.addEventListener('online',()=>{ if(ACC.A.get() && !R.ready) initRemote(); });
/* 앱으로 돌아올 때 다른 기기에서 푼 기록을 다시 받아 옴 (30초에 한 번까지) */
let lastPull=Date.now();
document.addEventListener('visibilitychange',()=>{
  if (document.visibilityState!=='visible' || !ACC.A.get() || (quiz && !quiz.saved) || Date.now()-lastPull<30000) return;
  lastPull=Date.now(); R.writing.then(()=>initRemote());
});
renderAcct();
""" + g, 1)

open(out, 'w', encoding='utf-8').write(s)
print('ok', out, len(s.encode()), 'bytes')
