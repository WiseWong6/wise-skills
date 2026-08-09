(function (global) {
  'use strict';

  var root = document.documentElement;
  var query = new URLSearchParams(global.location.search);
  var runtimeScript = document.currentScript;
  var runtimeBase = new URL('.', runtimeScript.src);
  var tasks = new WeakMap();
  var registeredTasks = new WeakMap();

  if (query.has('accent')) root.classList.add('accent');
  if (query.get('print') === '1') root.classList.add('print-mode');

  function loadStylesheet(name) {
    var href = new URL(name, runtimeBase).href;
    var existing = document.querySelector('link[data-wise-runtime-style="' + name + '"]');
    if (existing) return Promise.resolve(existing);
    return new Promise(function (resolve, reject) {
      var link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = href;
      link.dataset.wiseRuntimeStyle = name;
      link.addEventListener('load', function () { resolve(link); }, { once: true });
      link.addEventListener('error', function () { reject(new Error('运行时样式加载失败: ' + href)); }, { once: true });
      document.head.appendChild(link);
    });
  }

  function loadRuntimeScript(name, ready) {
    if (ready()) return Promise.resolve();
    var src = new URL(name, runtimeBase).href;
    return new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.dataset.wiseRuntimeScript = name;
      script.addEventListener('load', function () {
        if (!ready()) reject(new Error('运行时脚本未导出预期接口: ' + src));
        else resolve();
      }, { once: true });
      script.addEventListener('error', function () { reject(new Error('运行时脚本加载失败: ' + src)); }, { once: true });
      document.head.appendChild(script);
    });
  }

  var shellReady = loadStylesheet('deck-shell.css');
  var stageFitReady = loadRuntimeScript('stage-fit.js', function () { return Boolean(global.WisePPTStageFit); });

  function slides() {
    return Array.prototype.slice.call(document.querySelectorAll('#track>.slide'));
  }

  function updateDeckReady() {
    var all = slides();
    var failed = all.some(function (slide) { return slide.dataset.renderError; });
    var fontsReady = root.dataset.fontCheck === 'pass';
    var ready = fontsReady && all.length > 0 && all.every(function (slide) {
      return slide.dataset.renderReady === 'true';
    });
    root.dataset.deckReady = ready && !failed ? 'true' : 'false';
    if (failed || root.dataset.fontCheck === 'fail') root.dataset.deckError = 'true';
    else delete root.dataset.deckError;
    if (ready && !failed) document.dispatchEvent(new CustomEvent('wise-ppt:ready'));
    return ready && !failed;
  }

  function markSlideError(slide, error) {
    if (!slide) return;
    slide.dataset.renderError = error && error.message ? error.message : String(error || 'unknown error');
    delete slide.dataset.renderReady;
    updateDeckReady();
  }

  function registerSlideTask(slide, task) {
    if (!slide || !slide.classList.contains('slide')) throw new Error('registerSlideTask 需要 .slide 节点');
    var items = registeredTasks.get(slide) || [];
    items.push(Promise.resolve(task));
    registeredTasks.set(slide, items);
    slide.dataset.renderPending = 'true';
    return task;
  }

  function emphasisColor(slide, contentRef, role, fallback) {
    if (!slide || !root.classList.contains('accent')) return fallback;
    var roles = (slide.dataset.emphasisRoles || '').split(/\s+/).filter(Boolean);
    if (slide.dataset.emphasisMode !== 'semantic-focus' || slide.dataset.emphasisRef !== contentRef || !roles.includes(role)) return fallback;
    var color = getComputedStyle(root).getPropertyValue('--accent-red').trim();
    if (!color) throw new Error('主题缺少 --accent-red token');
    return color;
  }

  function typeSize(role) {
    var allowed = [
      'display-mark', 'particle-sample', 'display', 'hero', 'title', 'metric',
      'heading', 'emphasis', 'caption', 'subheading', 'body', 'body-small',
      'micro-secondary', 'label', 'meta'
    ];
    if (!allowed.includes(role)) throw new Error('未知 paper-ink 字阶: ' + role);
    var value = Number.parseFloat(getComputedStyle(root).getPropertyValue('--type-' + role).trim());
    if (!Number.isFinite(value)) throw new Error('主题缺少 --type-' + role + ' token');
    return value;
  }

  function visitRules(ruleList, output) {
    Array.prototype.forEach.call(ruleList || [], function (rule) {
      if (rule.type === CSSRule.FONT_FACE_RULE) {
        var family = rule.style.getPropertyValue('font-family').trim().replace(/^['"]|['"]$/g, '');
        if (family) output.push({
          family: family,
          style: rule.style.getPropertyValue('font-style').trim() || 'normal',
          weight: rule.style.getPropertyValue('font-weight').trim() || '400'
        });
      } else if (rule.cssRules) {
        visitRules(rule.cssRules, output);
      } else if (rule.styleSheet) {
        /* @import keeps the compatibility shared.css usable as a font source. */
        try { visitRules(rule.styleSheet.cssRules, output); } catch (error) { /* local import not ready */ }
      }
    });
  }

  function declaredFontFaces() {
    var faces = [];
    Array.prototype.forEach.call(document.styleSheets, function (sheet) {
      try { visitRules(sheet.cssRules, faces); } catch (error) { /* only local styles are required */ }
    });
    var unique = new Map();
    faces.forEach(function (face) { unique.set([face.family, face.style, face.weight].join('|'), face); });
    return Array.from(unique.values());
  }

  function loadRequiredFonts() {
    if (!document.fonts || typeof document.fonts.load !== 'function') {
      return Promise.reject(new Error('浏览器不支持 FontFaceSet 加载门禁'));
    }
    root.dataset.fontCheck = 'pending';
    return Promise.all([shellReady, document.fonts.ready]).then(function () {
      var faces = declaredFontFaces();
      if (faces.length < 4) throw new Error('主题必需字体声明不完整，实际 ' + faces.length + ' 个');
      return Promise.all(faces.map(function (face) {
        var family = '"' + face.family.replace(/"/g, '\\"') + '"';
        var spec = face.style + ' ' + face.weight + ' 16px ' + family;
        var sample = face.family === 'Courier Prime' ? 'Aa01' : '汉字Aa01';
        return document.fonts.load(spec, sample).then(function (loaded) {
          if (!loaded.length || loaded.some(function (font) { return font.status !== 'loaded'; })) {
            throw new Error('字体文件未真实加载: ' + face.family + ' ' + face.weight);
          }
          if (!document.fonts.check(spec, sample)) throw new Error('字体检查失败: ' + face.family + ' ' + face.weight);
          return face;
        });
      }));
    }).then(function (faces) {
      root.dataset.fontCheck = 'pass';
      root.dataset.fontFaceCount = String(faces.length);
      updateDeckReady();
      return faces;
    }).catch(function (error) {
      root.dataset.fontCheck = 'fail';
      root.dataset.fontCheckError = error.message;
      root.dataset.deckError = 'true';
      if (query.get('selftest') === '1') {
        root.dataset.runtimeCheck = 'fail';
        root.dataset.runtimeCheckError = error.message;
      }
      throw error;
    });
  }

  var fontReady = loadRequiredFonts();
  fontReady.catch(function (error) { console.error(error); });

  function markSlideReady(slide) {
    if (!slide || !slide.classList.contains('slide')) throw new Error('markSlideReady 需要 .slide 节点');
    if (tasks.has(slide)) return tasks.get(slide);
    var task = Promise.resolve().then(function () {
      var images = Array.prototype.map.call(slide.querySelectorAll('img'), function (img) {
        if (img.dataset.materialMode === 'source') {
          return Promise.reject(new Error('原始图片不得直接插入 DOM，请使用 data-material-mode="reconstruction"'));
        }
        if (img.complete && img.naturalWidth > 0) return Promise.resolve();
        return new Promise(function (resolve, reject) {
          img.addEventListener('load', resolve, { once: true });
          img.addEventListener('error', function () { reject(new Error('图片加载失败: ' + (img.currentSrc || img.src))); }, { once: true });
        });
      });
      return Promise.all([fontReady].concat(images, registeredTasks.get(slide) || []));
    }).then(function () {
      slide.getBoundingClientRect();
      slide.dataset.renderReady = 'true';
      delete slide.dataset.renderPending;
      delete slide.dataset.renderError;
      updateDeckReady();
      return slide;
    }).catch(function (error) {
      markSlideError(slide, error);
      throw error;
    });
    tasks.set(slide, task);
    return task;
  }

  function parseDatasetBlock(block, datasetId) {
    var id = String(datasetId || '').trim();
    if (!block) throw new Error('找不到 ECharts dataset 数据块: ' + (id || '(missing id)'));
    var type = String(block.getAttribute('type') || '').toLowerCase();
    if (type !== 'application/json') throw new Error('ECharts dataset 数据块必须使用 application/json: ' + id);
    var raw = String(block.textContent || '').trim();
    if (!raw) throw new Error('ECharts dataset 数据块为空: ' + id);
    try {
      var dataset = JSON.parse(raw);
      if (dataset === null || typeof dataset !== 'object') throw new Error('dataset 必须是 JSON 对象或数组');
      return dataset;
    } catch (error) {
      throw new Error('ECharts dataset JSON 解析失败 [' + id + ']: ' + error.message);
    }
  }

  function readDataset(slide, target) {
    if (!slide || !slide.classList.contains('slide')) throw new Error('readDataset 需要 .slide 节点');
    var element = typeof target === 'string' ? slide.querySelector(target) : target;
    if (!element) throw new Error('找不到 ECharts 容器');
    if (typeof slide.contains === 'function' && !slide.contains(element)) throw new Error('ECharts 容器必须位于当前 slide 内');
    var datasetId = String(element.getAttribute('data-dataset-id') || '').trim();
    if (!datasetId) throw new Error('ECharts 容器缺少 data-dataset-id');
    var blocks = Array.prototype.filter.call(
      slide.querySelectorAll('script[type="application/json"][data-wise-ppt-dataset]'),
      function (block) { return block.getAttribute('data-wise-ppt-dataset') === datasetId; }
    );
    if (blocks.length !== 1) {
      throw new Error('ECharts dataset [' + datasetId + '] 在当前页必须且只能声明一次，实际 ' + blocks.length + ' 个');
    }
    return parseDatasetBlock(blocks[0], datasetId);
  }

  function datasetsEqual(left, right) {
    if (Object.is(left, right)) return true;
    if (left === null || right === null || typeof left !== 'object' || typeof right !== 'object') return false;
    var leftIsArray = Array.isArray(left);
    if (leftIsArray !== Array.isArray(right)) return false;
    if (leftIsArray) {
      if (left.length !== right.length) return false;
      return left.every(function (item, index) { return datasetsEqual(item, right[index]); });
    }
    var leftKeys = Object.keys(left).sort();
    var rightKeys = Object.keys(right).sort();
    if (leftKeys.length !== rightKeys.length) return false;
    return leftKeys.every(function (key, index) {
      return key === rightKeys[index] && datasetsEqual(left[key], right[key]);
    });
  }

  function createEChart(slide, target, option) {
    var rejectRender;
    try {
      var element = typeof target === 'string' ? slide.querySelector(target) : target;
      if (!element) throw new Error('找不到 ECharts 容器');
      var declaredDataset = readDataset(slide, element);
      if (!option || typeof option !== 'object' || !Object.prototype.hasOwnProperty.call(option, 'dataset')) {
        throw new Error('ECharts option 缺少 dataset');
      }
      if (!datasetsEqual(option.dataset, declaredDataset)) {
        throw new Error('ECharts option.dataset 与页面 JSON 数据块不一致: ' + element.getAttribute('data-dataset-id'));
      }
      if (!global.echarts) throw new Error('ECharts 未加载');
      var chart = global.echarts.init(element, null, { renderer:'svg' });
      var settled = false;
      var rendered = new Promise(function (resolve, reject) {
        var timer = setTimeout(function () {
          if (!settled) { settled = true; reject(new Error('ECharts 渲染超时')); }
        }, 8000);
        rejectRender = function (error) {
          if (!settled) { settled = true; clearTimeout(timer); reject(error); }
        };
        chart.on('finished', function () {
          if (!settled) { settled = true; clearTimeout(timer); resolve(chart); }
        });
      });
      registerSlideTask(slide, rendered);
      markSlideReady(slide);
      chart.setOption(option);
      return chart;
    } catch (error) {
      if (rejectRender) rejectRender(error);
      markSlideError(slide, error);
      throw error;
    }
  }

  var ICON_PATHS = Object.freeze({
    gallery: Object.freeze([
      'M3.5 4.5h6v6h-6z',
      'M14.5 4.5h6v6h-6z',
      'M3.5 15.5h6v6h-6z',
      'M14.5 15.5h6v6h-6z'
    ])
  });

  function createIcon(name, attributes) {
    var paths = ICON_PATHS[name];
    if (!paths) throw new Error('未知本地图标: ' + name);
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.dataset.iconName = name;
    Object.keys(attributes || {}).forEach(function (key) { svg.setAttribute(key, attributes[key]); });
    paths.forEach(function (pathData) {
      var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', pathData);
      svg.appendChild(path);
    });
    return svg;
  }

  function hydrateIcons(scope) {
    (scope || document).querySelectorAll('[data-icon]').forEach(function (node) {
      if (!node.querySelector('svg[data-icon-name]')) node.prepend(createIcon(node.dataset.icon));
    });
  }

  global.WisePPT = {
    markSlideReady: markSlideReady,
    markSlideError: markSlideError,
    registerSlideTask: registerSlideTask,
    parseDatasetBlock: parseDatasetBlock,
    readDataset: readDataset,
    createEChart: createEChart,
    emphasisColor: emphasisColor,
    typeSize: typeSize,
    updateDeckReady: updateDeckReady,
    createIcon: createIcon,
    icons: ICON_PATHS,
    fontReady: fontReady
  };

  function initialize() {
    var body = document.body;
    var track = document.getElementById('track');
    var board = document.getElementById('board-sections');
    var pager = document.getElementById('pager');
    var deckStage = document.getElementById('deck-stage');
    var current = 0;
    var touchStartX = null;
    var selfTestStarted = false;
    if (!track || !board || !deckStage) return;

    hydrateIcons(document);

    function allSlides() { return Array.prototype.slice.call(track.querySelectorAll(':scope>.slide')); }
    function clamp(number) { return Math.max(0, Math.min(allSlides().length - 1, number)); }
    function hasTextSelection() {
      var selection = global.getSelection && global.getSelection();
      return Boolean(selection && !selection.isCollapsed && selection.toString().trim());
    }
    function hasEditableTarget(target) {
      return Boolean(target && target.closest && target.closest('input,textarea,select,button,[contenteditable="true"]'));
    }
    function navigationIsReserved(event) {
      return event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || hasEditableTarget(event.target) || hasTextSelection();
    }
    function copyCanvasPixels(original, clone) {
      var originals = original.querySelectorAll('canvas');
      var clones = clone.querySelectorAll('canvas');
      originals.forEach(function (canvas, index) {
        var target = clones[index];
        if (!target) return;
        target.width = canvas.width;
        target.height = canvas.height;
        try {
          target.getContext('2d').drawImage(canvas, 0, 0);
          target.dataset.canvasCopied='true';
        } catch (error) {
          target.dataset.canvasCopied = 'error';
        }
      });
    }
    function cloneSlide(slide) {
      var clone = slide.cloneNode(true);
      clone.querySelectorAll('script').forEach(function (script) { script.remove(); });
      clone.removeAttribute('id');
      clone.querySelectorAll('[id]').forEach(function (node) { node.removeAttribute('id'); });
      clone.classList.add('board-clone');
      clone.setAttribute('aria-hidden','true');
      clone.inert=true;
      copyCanvasPixels(slide, clone);
      return clone;
    }
    function makeCard(slide, index) {
      var card = document.createElement('button');
      card.type = 'button';
      card.className = 'board-card';
      card.dataset.index = String(index);
      var preview = document.createElement('div');
      preview.className = 'board-preview';
      preview.appendChild(cloneSlide(slide));
      var title = document.createElement('div');
      title.className = 'board-title';
      title.textContent = 'S' + String(index + 1).padStart(2, '0') + ' · ' + slide.dataset.pageTitle;
      var summary = document.createElement('div');
      summary.className = 'board-summary';
      summary.textContent = slide.dataset.pageSummary;
      card.append(preview, title, summary);
      card.addEventListener('click', function () { enterDeck(index); });
      return card;
    }
    function syncScales() {
      board.querySelectorAll('.board-preview').forEach(function (preview) {
        preview.style.setProperty('--board-scale', String(preview.clientWidth / 1920));
      });
    }
    function rebuildBoard() {
      board.replaceChildren();
      var groups = new Map();
      allSlides().forEach(function (slide, index) {
        var key = slide.dataset.sectionId || 'section.default';
        if (!groups.has(key)) groups.set(key, { title: slide.dataset.sectionTitle || '', items: [] });
        groups.get(key).items.push([slide, index]);
      });
      groups.forEach(function (group) {
        var label = document.createElement('div');
        label.className = 'section-label';
        label.textContent = group.title;
        var grid = document.createElement('div');
        grid.className = 'board-grid';
        group.items.forEach(function (item) { grid.appendChild(makeCard(item[0], item[1])); });
        board.append(label, grid);
      });
      var deckTitle = document.getElementById('deck-title');
      var subtitle = document.getElementById('deck-subtitle');
      if (deckTitle) deckTitle.textContent = root.dataset.deckTitle || document.title;
      if (subtitle) subtitle.textContent = allSlides().length + ' SLIDES · 点击任意页面进入横向放映';
      var active = board.querySelector('[data-index="' + current + '"]');
      if (active) active.classList.add('active');
      syncScales();
      requestAnimationFrame(syncScales);
    }
    function fit() {
      return global.WisePPTStageFit.fitDeck(deckStage, { allowUpscale: false });
    }
    function go(index, updateHash) {
      current = clamp(index);
      track.style.transform = 'translate3d(' + (-current * 1920) + 'px,0,0)';
      if (pager) pager.textContent = (current + 1) + ' / ' + allSlides().length;
      if (updateHash !== false) history.replaceState(null, '', '#' + (current + 1));
    }
    function enterDeck(index, updateHash) {
      body.className = 'mode-deck';
      fit();
      go(index, updateHash);
      scrollTo(0, 0);
    }
    function exitDeck() {
      body.className = 'mode-board';
      history.replaceState(null, '', location.pathname + location.search);
      rebuildBoard();
      var card = board.querySelector('[data-index="' + current + '"]');
      if (card) card.scrollIntoView({ block: 'center' });
    }
    function fromHash() {
      var match = location.hash.match(/^#(\d+)$/);
      if (match) enterDeck(Number(match[1]) - 1, false);
      else if (!root.classList.contains('print-mode')) {
        body.className = 'mode-board';
        rebuildBoard();
      }
    }
    function dispatchKey(target, key) {
      target.dispatchEvent(new KeyboardEvent('keydown', { key: key, bubbles: true, cancelable: true }));
    }
    function selectText(target) {
      var range = document.createRange();
      var selection = global.getSelection();
      range.selectNodeContents(target);
      selection.removeAllRanges();
      selection.addRange(range);
      return selection;
    }
    function testEditableReservation(slide, index, kind) {
      go(index);
      var node = document.createElement(kind === 'input' ? 'input' : 'div');
      if (kind === 'input') node.value = 'editable';
      else { node.contentEditable = 'true'; node.textContent = 'editable'; }
      node.setAttribute('aria-label', 'runtime editable test');
      slide.appendChild(node);
      node.focus();
      var before = location.hash;
      dispatchKey(node, 'ArrowRight');
      var held = location.hash === before;
      node.remove();
      if (!held) throw new Error(kind + ' 编辑态被翻页快捷键抢占');
    }
    function assertRelativeRuntimeAssets() {
      var themeLink = document.querySelector('link[rel="stylesheet"]:not([data-wise-runtime-style])');
      var authored = [themeLink && themeLink.getAttribute('href'), runtimeScript.getAttribute('src')];
      authored.forEach(function (value) {
        if (!value || /^(?:[a-z]+:|\/)/i.test(value)) throw new Error('Deck 资源必须使用相对路径: ' + value);
      });
      document.querySelectorAll('[data-wise-runtime-style],[data-wise-runtime-script]').forEach(function (node) {
        var value = node.href || node.src;
        if (new URL(value, document.baseURI).protocol !== location.protocol) throw new Error('运行时资源协议不一致: ' + value);
      });
      root.dataset.resourceCheck = 'pass';
    }
    function assertViewportFit() {
      var result = fit();
      if (!global.WisePPTStageFit.contains(result.bounds, result.rect, 1)) {
        throw new Error('1920×1080 舞台超出可视视口: viewport=' + [result.bounds.left, result.bounds.top, result.bounds.width, result.bounds.height].join(',') + ' rect=' + [result.rect.left, result.rect.top, result.rect.width, result.rect.height].join(','));
      }
      allSlides().forEach(function (slide) {
        var stage = slide.querySelector(':scope>.stage');
        if (!stage) throw new Error('slide 缺少直属 .stage');
        if (slide.style.transform || stage.style.transform) throw new Error('正式 slide/stage 禁止 inline transform');
        if (getComputedStyle(stage).transform !== 'none') throw new Error('正式 .stage 发生二次缩放');
      });
      root.dataset.viewportFitCheck = 'pass';
    }
    function assertControls() {
      var controls = document.getElementById('presentation-controls');
      var toggle = document.getElementById('board-toggle');
      if (!controls || !toggle || !toggle.querySelector('svg[data-icon-name="gallery"]')) throw new Error('放映控件缺少本地语义 SVG');
      [toggle, pager].forEach(function (node) {
        var rect = node.getBoundingClientRect();
        if (rect.width < 40 || rect.height < 40) throw new Error('放映控件触控区小于 40px');
      });
      var bounds = global.WisePPTStageFit.viewportBounds();
      if (!global.WisePPTStageFit.contains(bounds, controls.getBoundingClientRect(), 1)) throw new Error('放映控件超出安全区');
      var style = getComputedStyle(toggle);
      if (style.backgroundColor === 'rgb(25, 25, 23)') throw new Error('放映控件不得使用深色胶囊');
      root.dataset.controlsCheck = 'pass';
    }
    function selfTest() {
      if (selfTestStarted) return;
      selfTestStarted = true;
      try {
        rebuildBoard();
        var all = allSlides();
        var cards = board.querySelectorAll('.board-card');
        if (cards.length !== all.length) throw new Error('画册卡片数量不一致');
        var canvasCount = track.querySelectorAll('canvas').length;
        var copied = board.querySelectorAll('canvas[data-canvas-copied="true"]').length;
        if (copied !== canvasCount) throw new Error('Canvas 克隆像素未完整复制');
        if (query.has('accent') !== root.classList.contains('accent')) throw new Error('强调模式未按 URL 激活');
        all.filter(function (slide) { return slide.dataset.emphasisMode === 'semantic-focus'; }).forEach(function (slide) {
          var target = slide.querySelector('[data-emphasis-role]');
          if (!target) throw new Error('semantic-focus 页面缺少强调载体');
          var style = getComputedStyle(target);
          var red = 'rgb(192, 57, 43)';
          var isRed = style.color === red || style.borderColor === red || style.outlineColor === red;
          if (query.has('accent') && !isRed) throw new Error('强调载体没有应用主题强调色');
          if (!query.has('accent') && isRed) throw new Error('默认模式残留主题强调色');
        });
        var svgTypeTarget = track.querySelector('[font-size*="var(--type-"]');
        if (svgTypeTarget) {
          var svgRole = svgTypeTarget.getAttribute('font-size').match(/--type-([a-z-]+)/);
          var svgSize = Number.parseFloat(getComputedStyle(svgTypeTarget).fontSize);
          if (!svgRole || !Number.isFinite(svgSize) || Math.abs(svgSize - typeSize(svgRole[1])) > .1) throw new Error('SVG 字阶 token 未解析');
        }
        typeSize('caption');
        typeSize('micro-secondary');
        root.dataset.typeCheck = 'pass';
        assertRelativeRuntimeAssets();
        history.replaceState(null, '', '#' + all.length);
        fromHash();
        if (!body.classList.contains('mode-deck')) throw new Error('深链未进入放映');
        assertViewportFit();
        assertControls();

        all.forEach(function (slide, index) {
          go(index);
          var caption = slide.querySelector('.caption');
          var candidates = [caption].concat(Array.prototype.slice.call(slide.querySelectorAll('h1,h2,p,[data-content-ref]'))).filter(Boolean);
          var copyTarget = candidates.find(function (node) { return node.textContent && node.textContent.trim(); });
          if (!copyTarget || getComputedStyle(copyTarget).userSelect === 'none') throw new Error('第 ' + (index + 1) + ' 页正文不可选择');
          var selection = selectText(copyTarget);
          if (!selection.toString().trim()) throw new Error('第 ' + (index + 1) + ' 页无法建立文本选区');
          var before = location.hash;
          dispatchKey(global, 'ArrowRight');
          if (location.hash !== before) throw new Error('文本选区被翻页快捷键抢占');
          selection.removeAllRanges();
          testEditableReservation(slide, index, 'input');
          testEditableReservation(slide, index, 'contenteditable');
        });
        root.dataset.selectionCheck = 'pass';
        root.dataset.inputCheck = 'pass';
        root.dataset.contenteditableCheck = 'pass';
        root.dataset.copyCheck='pass';

        go(0);
        if (all.length > 1) {
          dispatchKey(global, 'ArrowRight');
          if (location.hash !== '#2') throw new Error('键盘翻页失败');
        }
        dispatchKey(global, 'Escape');
        if (!body.classList.contains('mode-board') || location.hash) throw new Error('真实 ESC KeyboardEvent 状态切换失败');
        root.dataset.escCheck = 'pass';
        if (root.dataset.fontCheck !== 'pass') throw new Error('字体加载门禁未通过');
        root.dataset.runtimeCheck = 'pass';
      } catch (error) {
        root.dataset.runtimeCheck = 'fail';
        root.dataset.runtimeCheckError = error.message;
        console.error(error);
      }
    }

    function onViewportChange() {
      fit();
      if (body.classList.contains('mode-board')) rebuildBoard();
    }
    addEventListener('resize', onViewportChange);
    if (global.visualViewport) {
      global.visualViewport.addEventListener('resize', onViewportChange);
      global.visualViewport.addEventListener('scroll', onViewportChange);
    }
    addEventListener('hashchange', fromHash);
    addEventListener('keydown', function (event) {
      if (!body.classList.contains('mode-deck')) return;
      if (event.key === 'Escape') { event.preventDefault(); exitDeck(); return; }
      if (navigationIsReserved(event)) return;
      if (['ArrowRight', 'ArrowDown', ' ', 'PageDown'].includes(event.key)) { event.preventDefault(); go(current + 1); }
      else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) { event.preventDefault(); go(current - 1); }
      else if (event.key === 'Home') { event.preventDefault(); go(0); }
      else if (event.key === 'End') { event.preventDefault(); go(allSlides().length - 1); }
    });

    var toggle = document.getElementById('board-toggle');
    var deck = document.getElementById('deck');
    if (toggle) toggle.addEventListener('click', exitDeck);
    if (deck) {
      deck.addEventListener('touchstart', function (event) {
        touchStartX = hasTextSelection() ? null : event.changedTouches[0].clientX;
      }, { passive: true });
      deck.addEventListener('touchend', function (event) {
        if (touchStartX === null || hasTextSelection()) { touchStartX = null; return; }
        var delta = event.changedTouches[0].clientX - touchStartX;
        if (Math.abs(delta) > 48) go(current + (delta < 0 ? 1 : -1));
        touchStartX = null;
      }, { passive: true });
    }

    document.addEventListener('wise-ppt:ready', function () {
      if (!root.classList.contains('print-mode')) rebuildBoard();
      if (query.get('selftest') === '1') selfTest();
    });
    allSlides().forEach(function (slide) {
      if (slide.dataset.renderPending !== 'true' && slide.dataset.renderReady !== 'true') markSlideReady(slide);
    });
    updateDeckReady();
    fit();
    fromHash();
    if (query.get('selftest') === '1' && updateDeckReady()) selfTest();
    global.WisePPTRuntime = { rebuildBoard: rebuildBoard, enterDeck: enterDeck, exitDeck: exitDeck, go: go, fit: fit };
  }

  function start() {
    Promise.all([shellReady, stageFitReady]).then(function () {
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true });
      else initialize();
    }).catch(function (error) {
      root.dataset.runtimeCheck = 'fail';
      root.dataset.runtimeCheckError = error.message;
      root.dataset.deckError = 'true';
      console.error(error);
    });
  }

  start();
})(window);
