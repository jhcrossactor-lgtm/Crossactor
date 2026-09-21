// NotebookLM の最新回答を取り出す。javascript_tool で実行する。
// busy が true の間は生成中なので待つ。回答は1件60秒前後かかる。
(() => {
  const busy = document.body.innerText.includes('回答しています');
  const ms = [...document.querySelectorAll('chat-message')];
  let t = (ms[ms.length - 1] || {}).innerText || '';
  t = t.split('keep_pin')[0].replace(/^[\s\S]*expand_more\s*\n?/, '').trim();
  return JSON.stringify({ busy, text: t });
})()
