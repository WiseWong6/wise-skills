/* Offline-only controls: never reorder or rewrite resume content. */
(function () {
  var root = document.documentElement;
  var query = new URLSearchParams(location.search);
  var font = document.getElementById('wrFont');
  var layout = document.getElementById('wrLayout');
  var color = document.getElementById('wrColor');
  var background = document.getElementById('wrBackground');
  var print = document.getElementById('wrPrintBtn');
  var fonts = ['modern', 'classic', 'wenkai'];
  function initialValue(parameter, attribute) {
    return query.has(parameter) ? query.get(parameter) : root.dataset[attribute];
  }
  var preset = initialValue('style', 'preset');
  root.dataset.preset = fonts.indexOf(preset) !== -1 ? preset :
    (fonts.indexOf(root.dataset.preset) !== -1 ? root.dataset.preset : 'wenkai');
  root.dataset.background = initialValue('background', 'background') === 'paper' ? 'paper' : 'white';
  if (background) {
    background.value = root.dataset.background;
    background.addEventListener('change', function () {
      root.dataset.background = background.value === 'paper' ? 'paper' : 'white';
      save('background', root.dataset.background);
    });
  }
  var colorNames = {navy: '墨蓝', ink: '正黑'};
  function save(parameter, value) {
    try {
      var url = new URL(location.href);
      url.searchParams.set(parameter, value);
      history.replaceState(null, '', url.href);
    } catch (error) { /* File controls work even without history access. */ }
  }
  if (font) {
    font.value = root.dataset.preset;
    font.addEventListener('change', function () {
      root.dataset.preset = font.value;
      save('style', font.value);
    });
  }
  if (layout) {
    layout.value = root.dataset.layout === 'portrait' ? 'portrait.html' : 'index.html';
    layout.addEventListener('change', function () {
      var url = new URL(layout.value, location.href);
      url.search = location.search;
      ['photo', 'decoration', 'color', 'background'].forEach(function (key) { url.searchParams.set(key, root.dataset[key]); });
      url.searchParams.set('style', root.dataset.preset);
      location.href = url.href;
    });
  }
  function setColor(value) {
    value = Object.prototype.hasOwnProperty.call(colorNames, value) ? value : 'ink';
    root.dataset.color = value;
    if (!color) return;
    color.querySelector('.wr-color-name').textContent = colorNames[value];
    color.querySelector('summary .wr-swatch').dataset.color = value;
    color.querySelectorAll('button[data-color]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.color === value));
    });
  }
  setColor(initialValue('color', 'color'));
  if (color) {
    color.querySelectorAll('button[data-color]').forEach(function (button) {
      button.addEventListener('click', function () {
        setColor(button.dataset.color);
        save('color', root.dataset.color);
        color.open = false;
        color.querySelector('summary').focus();
      });
    });
    document.addEventListener('click', function (event) { if (!color.contains(event.target)) color.open = false; });
    color.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { color.open = false; color.querySelector('summary').focus(); }
    });
  }
  function setupToggle(id, parameter) {
    var button = document.getElementById(id);
    function apply(enabled) {
      root.dataset[parameter] = enabled ? 'on' : 'off';
      if (button) button.setAttribute('aria-checked', String(enabled));
    }
    apply(initialValue(parameter, parameter) !== 'off');
    if (button) button.addEventListener('click', function () {
      apply(button.getAttribute('aria-checked') !== 'true');
      save(parameter, root.dataset[parameter]);
    });
  }
  setupToggle('wrPhotoToggle', 'photo');
  setupToggle('wrEdgeToggle', 'decoration');
  if (print) {
    print.disabled = true;
    print.addEventListener('click', function () {
      if (root.dataset.pagination === 'ready') window.print();
    });
  }
})();
