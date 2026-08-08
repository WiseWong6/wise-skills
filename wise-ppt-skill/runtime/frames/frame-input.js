(function () {
  /* 放映页允许选中文字；只拦截会改变页码的按键，Cmd/Ctrl+C 保留浏览器原生复制。 */
  var NAV_KEYS = {
    Escape: true,
    ArrowRight: true, ArrowDown: true, PageDown: true,
    ArrowLeft: true, ArrowUp: true, PageUp: true,
    Home: true, End: true, ' ': true
  };
  var lastPointerMessage = 0;

  addEventListener('keydown', function (e) {
    if (!NAV_KEYS[e.key] || window.parent === window) return;
    e.preventDefault();
    window.parent.postMessage({ source: 'wise-ppt-frame', type: 'keydown', key: e.key }, '*');
  }, true);

  addEventListener('mousemove', function () {
    if (window.parent === window) return;
    var now = Date.now();
    if (now - lastPointerMessage < 100) return;
    lastPointerMessage = now;
    window.parent.postMessage({ source: 'wise-ppt-frame', type: 'pointermove' }, '*');
  }, { passive: true });
})();
