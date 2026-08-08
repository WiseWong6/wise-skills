/* ============================================================
   Paper Ink · 共享粒子工具库
   语言规则：
   - 画面主体全部由粒子构成，字体只作离屏采样轮廓
   - 秩序网格粒子 = 正确/结构；坠落缺粒 = 错误/异常
   - 墨色 #191917，纸底 #DFE0D9（见 shared.css）
   ============================================================ */
var PART = (function () {
  var INK = '#191917';

  function dot(ctx, x, y, r, a) {
    ctx.globalAlpha = a;
    ctx.fillStyle = INK;
    ctx.beginPath(); ctx.arc(x, y, r, 0, 6.2832); ctx.fill();
    ctx.globalAlpha = 1;
  }

  function gauss() { return (Math.random() + Math.random() + Math.random() - 1.5) / 1.5; }

  /* 高斯点簇：token/节点的主角形态 */
  function cluster(ctx, x, y, r, n, aMax) {
    for (var i = 0; i < n; i++) {
      var rr = Math.abs(gauss()) * r;
      var an = Math.random() * 6.2832;
      dot(ctx, x + Math.cos(an) * rr, y + Math.sin(an) * rr * .85,
          .8 + Math.random() * 1.5, .3 + Math.random() * (aMax || .55));
    }
  }

  /* 尘埃：氛围/碎屑 */
  function dust(ctx, x, y, w, h, n, aMax) {
    for (var i = 0; i < n; i++) {
      dot(ctx, x + Math.random() * w, y + Math.random() * h,
          .5 + Math.random() * 1.3, .05 + Math.random() * (aMax || .22));
    }
  }

  /* 点流弧：沿二次贝塞尔撒点；density 粒/100px，width 横向抖动 */
  function arc(ctx, x1, y1, x2, y2, lift, density, alpha, width) {
    var mx = (x1 + x2) / 2, cy = y1 - Math.abs(x2 - x1) * lift;
    var steps = Math.max(40, density * Math.abs(x2 - x1) / 3);
    for (var t = 0; t <= 1; t += 1 / steps) {
      var bx = (1 - t) * (1 - t) * x1 + 2 * (1 - t) * t * mx + t * t * x2;
      var by = (1 - t) * (1 - t) * y1 + 2 * (1 - t) * t * cy + t * t * y2;
      dot(ctx, bx + (Math.random() - .5) * (width || 3),
              by + (Math.random() - .5) * (width || 3),
              .8 + Math.random() * 1.4, alpha * (.6 + Math.random() * .4));
    }
  }

  /* 断弧：走到 tEnd 断掉，断口向下散落 */
  function brokenArc(ctx, x1, y1, x2, y2, lift, tEnd) {
    var mx = (x1 + x2) / 2, cy = y1 - Math.abs(x2 - x1) * lift;
    var ex = 0, ey = 0;
    for (var t = 0; t <= tEnd; t += .004) {
      var bx = (1 - t) * (1 - t) * x1 + 2 * (1 - t) * t * mx + t * t * x2;
      var by = (1 - t) * (1 - t) * y1 + 2 * (1 - t) * t * cy + t * t * y2;
      dot(ctx, bx, by, .9 + Math.random() * 1.4, .75);
      ex = bx; ey = by;
    }
    for (var i = 0; i < 110; i++) {
      var d = Math.random();
      dot(ctx, ex + d * d * 150 * (Math.random() - .3), ey + d * d * 210 + Math.random() * 26,
          .6 + Math.random() * 1.4, .5 * (1 - d) + .08);
    }
  }

  /* 文字采样 → 粒子坐标数组（字体仅作离屏轮廓源） */
  function textPoints(text, x, y, font, gap) {
    var off = document.createElement('canvas');
    off.width = 1920; off.height = 1080;
    var octx = off.getContext('2d');
    octx.font = font;
    octx.textAlign = 'left';
    octx.textBaseline = 'middle';
    octx.fillStyle = '#000';
    octx.fillText(text, x, y);
    var img = octx.getImageData(0, 0, 1920, 1080).data;
    var pts = [];
    gap = gap || 5;
    for (var py = 0; py < 1080; py += gap) {
      for (var px = 0; px < 1920; px += gap) {
        if (img[(py * 1920 + px) * 4 + 3] > 90) pts.push({ x: px, y: py });
      }
    }
    return pts;
  }

  function measure(text, font) {
    var off = document.createElement('canvas');
    var octx = off.getContext('2d');
    octx.font = font;
    return octx.measureText(text).width;
  }

  return { INK: INK, dot: dot, gauss: gauss, cluster: cluster, dust: dust,
           arc: arc, brokenArc: brokenArc, textPoints: textPoints, measure: measure };
})();

/* 每镜通用：主题开关 + 舞台适配 */
function stageFit() {
  var T = location.search;
  if (T.indexOf('cool') >= 0) document.documentElement.classList.add('cool');
  if (T.indexOf('mono') >= 0) document.documentElement.classList.add('mono');
  if (T.indexOf('ppt') >= 0) document.documentElement.classList.add('ppt');
  if (T.indexOf('accent') >= 0) document.documentElement.classList.add('accent');
  function fit() {
    var s = document.querySelector('.stage');
    var k = Math.min(innerWidth / 1920, innerHeight / 1080);
    s.style.transform = 'scale(' + k + ')';
  }
  addEventListener('resize', fit);
  fit();
  if (document.documentElement.dataset.renderPending !== 'true') markRenderReady();
}

/*
 * ?audit 浏览器门禁：只测量 #body 中参与配平的语义主体。
 * 标准工程制图页以 FIG 分隔线与 caption 定位主题安全内容区；
 * 特殊页可在 #body 声明 data-balance-frame="x1,y1,x2,y2"。
 */
function auditBalance() {
  if (location.search.indexOf('audit') < 0) return;
  var root = document.documentElement;
  var stage = document.querySelector('.stage');
  var body = document.querySelector('#body[data-balance]');
  if (!stage || !body) {
    root.dataset.balanceStatus = 'error-no-body';
    return;
  }

  var mode = body.getAttribute('data-balance') || '';
  var allowedModes = ['structural', 'centered', 'intentional-asymmetry'];
  root.dataset.balanceMode = mode || 'missing';
  if (allowedModes.indexOf(mode) < 0) {
    root.dataset.balanceStatus = 'error-invalid-mode';
    return;
  }

  var stageRect = stage.getBoundingClientRect();
  var scale = stageRect.width / 1920;
  if (!scale) {
    root.dataset.balanceStatus = 'error-zero-scale';
    return;
  }

  function designRect(node) {
    var r = node.getBoundingClientRect();
    return {
      x: (r.left - stageRect.left) / scale,
      y: (r.top - stageRect.top) / scale,
      width: r.width / scale,
      height: r.height / scale
    };
  }
  function round(value) { return Math.round(value * 10) / 10; }

  var frame = null;
  var frameAttr = body.getAttribute('data-balance-frame');
  if (frameAttr) {
    var parts = frameAttr.split(/[ ,]+/).map(Number);
    if (parts.length !== 4 || !parts.every(Number.isFinite)
        || parts[2] <= parts[0] || parts[3] <= parts[1]) {
      root.dataset.balanceStatus = 'error-invalid-frame';
      return;
    }
    frame = {x1:parts[0], y1:parts[1], x2:parts[2], y2:parts[3]};
  }
  if (!frame) {
    var fig = Array.prototype.find.call(document.querySelectorAll('svg text'), function (node) {
      return (node.textContent || '').trim().indexOf('FIG.') === 0;
    });
    var figRule = fig && fig.nextElementSibling && fig.nextElementSibling.tagName.toLowerCase() === 'line'
      ? fig.nextElementSibling : fig;
    var caption = document.querySelector('.caption');
    if (figRule && caption) {
      var figRect = designRect(figRule);
      var captionRect = designRect(caption);
      frame = {
        x1:150,
        y1:Math.max(220, figRect.y + figRect.height + 28),
        x2:1770,
        y2:Math.min(890, captionRect.y - 24)
      };
    }
  }
  if (!frame || frame.x2 <= frame.x1 || frame.y2 <= frame.y1) {
    root.dataset.balanceStatus = 'error-missing-frame';
    return;
  }

  function isExcluded(node) {
    for (var current = node; current && current !== body; current = current.parentElement) {
      if (current.getAttribute && current.getAttribute('data-balance-exclude') === 'true') return true;
    }
    return false;
  }

  /* SVG 容器的 bbox 会重新包含被排除的后代；只合并实际绘制节点。 */
  var svgContainers = ['svg', 'g', 'defs', 'clippath', 'mask', 'pattern', 'marker', 'symbol'];
  var bounds = null;
  Array.prototype.forEach.call(body.querySelectorAll('*'), function (node) {
    if (isExcluded(node)) return;
    if (svgContainers.indexOf(node.tagName.toLowerCase()) >= 0) return;
    var style = getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return;
    var rect = designRect(node);
    if (!rect.width && !rect.height) return;
    var x2 = rect.x + rect.width;
    var y2 = rect.y + rect.height;
    if (!bounds) {
      bounds = {x1:rect.x, y1:rect.y, x2:x2, y2:y2};
    } else {
      bounds.x1 = Math.min(bounds.x1, rect.x);
      bounds.y1 = Math.min(bounds.y1, rect.y);
      bounds.x2 = Math.max(bounds.x2, x2);
      bounds.y2 = Math.max(bounds.y2, y2);
    }
  });
  if (!bounds) {
    root.dataset.balanceStatus = 'error-empty-body';
    root.dataset.balanceBox = '0,0,0,0';
    root.dataset.balanceFrame = [round(frame.x1), round(frame.y1), round(frame.x2), round(frame.y2)].join(',');
    return;
  }

  var box = {x:bounds.x1, y:bounds.y1, width:bounds.x2-bounds.x1, height:bounds.y2-bounds.y1};
  var dx = (frame.x1 + frame.x2) / 2 - (box.x + box.width / 2);
  var dy = (frame.y1 + frame.y2) / 2 - (box.y + box.height / 2);
  var tolerance = (body.getAttribute('data-balance-tolerance') || '24,32').split(/[ ,]+/).map(Number);
  if (tolerance.length !== 2 || !tolerance.every(Number.isFinite)
      || tolerance[0] < 0 || tolerance[1] < 0) {
    root.dataset.balanceStatus = 'error-invalid-tolerance';
    return;
  }
  var tx = tolerance[0];
  var ty = tolerance[1];
  var overflow = {
    left:Math.max(0, frame.x1 - box.x),
    top:Math.max(0, frame.y1 - box.y),
    right:Math.max(0, box.x + box.width - frame.x2),
    bottom:Math.max(0, box.y + box.height - frame.y2)
  };
  var exceedsFrame = Math.max(overflow.left, overflow.top, overflow.right, overflow.bottom) > 1;
  var status = exceedsFrame ? 'fail-overflow'
    : mode === 'centered'
      ? (Math.abs(dx) <= tx && Math.abs(dy) <= ty ? 'pass' : 'fail-center')
      : 'report';

  root.dataset.balanceStatus = status;
  root.dataset.balanceDx = String(round(dx));
  root.dataset.balanceDy = String(round(dy));
  root.dataset.balanceBox = [round(box.x), round(box.y), round(box.width), round(box.height)].join(',');
  root.dataset.balanceFrame = [round(frame.x1), round(frame.y1), round(frame.x2), round(frame.y2)].join(',');
  root.dataset.balanceOverflow = [round(overflow.left), round(overflow.top), round(overflow.right), round(overflow.bottom)].join(',');
}

/*
 * 截图协议：所有字体、图片和至少两帧布局完成后才标记 ready。
 * 异步图表/地图页面在 <html> 设置 data-render-pending="true"，并在组件完成后
 * 显式调用 markRenderReady()。runtime/screenshot.sh 会把缺少该标记视为失败。
 */
function markRenderReady() {
  var done = false;
  function finish() {
    if (done) return;
    done = true;
    /* 强制一次同步布局，避免 headless --dump-dom 不调度 requestAnimationFrame。 */
    document.documentElement.getBoundingClientRect();
    auditBalance();
    document.documentElement.dataset.renderReady = 'true';
  }
  var fonts = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
  var images = Array.prototype.map.call(document.images || [], function (img) {
    if (img.complete) return Promise.resolve();
    return new Promise(function (resolve) {
      img.addEventListener('load', resolve, {once:true});
      img.addEventListener('error', resolve, {once:true});
    });
  });
  Promise.all([fonts].concat(images)).then(finish);
  /* 某些 file:// + headless 组合不会完成 FontFaceSet promise；固定上限防止假死。
     异步图表只有在组件完成后才调用本函数，因此这里不会提前放行图表页。 */
  setTimeout(finish, 3000);
}
