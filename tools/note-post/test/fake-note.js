// noteの画面構造を模したダミーサーバー（selectors.json のデフォルト値に合わせてある）
import http from 'node:http';

const editor = `<!doctype html><meta charset=utf-8><title>editor</title>
<textarea placeholder="記事タイトル"></textarea>
<div class="ProseMirror" contenteditable="true" style="min-height:200px"></div>
<button aria-label="メニューを開く" id=plus>+</button><div id=menu hidden><button id=imgbtn>画像</button></div>
<input type=file id=file accept="image/*" hidden>
<button id=save>下書き保存</button><button id=pub>公開に進む</button>
<div id=toast></div><div id=dlg hidden><input placeholder="ハッシュタグを追加する"><ul id=tags></ul><button id=submit>投稿する</button></div>
<script>
const body = document.querySelector('.ProseMirror');
body.addEventListener('paste', (e) => { e.preventDefault(); body.innerHTML += e.clipboardData.getData('text/html'); });
save.onclick = async () => {
  await fetch('/api/draft', { method: 'POST', body: JSON.stringify({
    title: document.querySelector('textarea').value, html: body.innerHTML }) });
  history.replaceState(null, '', '/notes/n123/edit'); toast.textContent = '保存しました';
};
pub.onclick = () => { dlg.hidden = false; };
plus.onclick = () => { menu.hidden = false; };
imgbtn.onclick = () => { menu.hidden = true; file.click(); };
file.onchange = () => { const f = file.files[0]; body.insertAdjacentHTML('beforeend', '<img data-name="' + f.name + '" src="x">'); file.value = ''; };
const ti = document.querySelector('#dlg input');
ti.onkeydown = (e) => { if (e.key === 'Enter') { tags.insertAdjacentHTML('beforeend', '<li>' + ti.value); ti.value = ''; } };
submit.onclick = async () => {
  await fetch('/api/publish', { method: 'POST', body: JSON.stringify({ tags: [...tags.children].map(li => li.textContent) }) });
  location.href = '/n/n123';
};
</script>`;

export function startFakeNote() {
  const state = { drafts: [], published: [], autoLogin: true };
  const server = http.createServer((req, res) => {
    const authed = /fake_session=1/.test(req.headers.cookie || '');
    let data = '';
    req.on('data', (c) => (data += c));
    req.on('end', () => {
      const html = (s, extra = {}) => { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', ...extra }); res.end(s); };
      if (req.url === '/login' && !state.autoLogin) return html('<meta charset=utf-8>ログイン画面');
      if (req.url === '/login') return html('<meta charset=utf-8>ログイン画面<script>document.cookie="fake_session=1; path=/; max-age=3600";location.href="/"</script>');
      if (req.url === '/') return html('<meta charset=utf-8>top');
      if (!authed) { res.writeHead(302, { location: '/login' }); return res.end(); }
      if (req.url === '/notes/new') return html(editor);
      if (req.url === '/api/draft') { state.drafts.push(JSON.parse(data)); return html('ok'); }
      if (req.url === '/api/publish') { state.published.push(JSON.parse(data)); return html('ok'); }
      if (req.url.startsWith('/n/')) return html('<meta charset=utf-8>published');
      res.writeHead(404); res.end();
    });
  });
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r({ server, state, base: `http://127.0.0.1:${server.address().port}` })));
}
