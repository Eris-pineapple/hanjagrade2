#!/usr/bin/env python3
"""claude.ai 아티팩트 HTML → 앱(PWA)용 index.html 변환.
사용법: python3 tools/build_app.py <아티팩트.html> [index.html]
- manifest/아이콘/메타 태그 추가
- 앱에서도 오답정리노트 파일 저장(브라우저 다운로드)
- 서비스워커 등록(오프라인 실행)
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
open(out, 'w', encoding='utf-8').write(s)
print('ok', out, len(s.encode()), 'bytes')
