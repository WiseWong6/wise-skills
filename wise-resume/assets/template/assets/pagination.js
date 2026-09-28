/* Real A4 sheets. Split only between complete content units; never clip text. */
(function () {
  'use strict';
  var root = document.documentElement;
  var main = document.querySelector('main.wr-doc');
  if (!main) return;
  var original = main.cloneNode(true);
  var introduction = original.querySelector('.wr-section');
  if (introduction) introduction.classList.add('wr-intro');
  var generation = 0;
  var busy = false;
  var PX_PER_MM = 96 / 25.4;
  var height = 297 * PX_PER_MM;
  var padding = 11 * PX_PER_MM;

  // Spend spare height on group separation first; never stretch text or force filling.
  function balanceColumn(column, bottomLimit) {
    function contentBottom() {
      return Math.max.apply(null, [column.getBoundingClientRect().bottom].concat(
        Array.from(column.querySelectorAll('h2,h3,p,li,dt,dd,.wr-entry-head'))
          .map(function (node) { return node.getBoundingClientRect().bottom; })
      ));
    }
    function spread(rules) {
      var spare = bottomLimit - contentBottom();
      if (spare < 1) return;
      var gaps = [];
      rules.forEach(function (rule) {
        column.querySelectorAll(rule.selector).forEach(function (node) {
          var base = parseFloat(getComputedStyle(node).marginTop) || 0;
          var capacity = rule.extra * PX_PER_MM;
          gaps.push({node: node, base: base, capacity: capacity, original: node.style.marginTop});
        });
      });
      var capacity = gaps.reduce(function (sum, gap) { return sum + gap.capacity; }, 0);
      if (!capacity) return;
      var fraction = Math.min(1, spare / capacity);
      function apply(ratio) {
        gaps.forEach(function (gap) {
          gap.node.style.marginTop = (gap.base + gap.capacity * ratio) + 'px';
        });
      }
      apply(fraction);
      // Measure again: nested margins may collapse differently from the estimate.
      if (contentBottom() > bottomLimit) {
        var low = 0;
        var high = fraction;
        for (var step = 0; step < 10; step += 1) {
          var mid = (low + high) / 2;
          apply(mid);
          if (contentBottom() <= bottomLimit) low = mid;
          else high = mid;
        }
        apply(low);
        if (contentBottom() > bottomLimit) {
          gaps.forEach(function (gap) { gap.node.style.marginTop = gap.original; });
        }
      }
    }
    spread([
      {selector: '.wr-section + .wr-section', extra: 4},
      {selector: '.wr-entry + .wr-entry', extra: 3}
    ]);
    spread([
      {selector: '.wr-bullets > li + li, .wr-skill-list dd + dt', extra: 1.2}
    ]);
  }

  // Headings travel with their first paragraph/bullet, including section headings.
  function units(container) {
    var result = [];
    var pending = [];
    function visit(node, path) {
      if (node.matches('.wr-section-title,.wr-entry-head')) {
        pending.push({depth: path.length - 1, node: node});
      } else if (node.matches('.wr-section,.wr-entry,.wr-bullets')) {
        var next = path.concat(node);
        var count = result.length;
        Array.from(node.children).forEach(function (child) { visit(child, next); });
        if (result.length === count && pending.length) {
          result.push({path: next, lead: pending, nodes: []});
          pending = [];
        }
      } else if (node.matches('.wr-skill-list')) {
        var children = Array.from(node.children);
        for (var i = 0; i < children.length; i += 2) {
          result.push({path: path.concat(node), lead: pending, nodes: children.slice(i, i + 2)});
          pending = [];
        }
      } else {
        result.push({path: path, lead: pending, nodes: [node]});
        pending = [];
      }
    }
    Array.from(container.children).forEach(function (node) { visit(node, []); });
    // Education can contain just a heading, without a body list.
    if (pending.length) result.push({path: [], lead: pending, nodes: []});
    return result;
  }

  function showError(error) {
    // Keep the complete source visible when measurement or font loading fails.
    var oldError = document.querySelector('.wr-pagination-error');
    if (oldError) oldError.remove();
    main.replaceChildren.apply(main, Array.from(original.cloneNode(true).children));
    root.dataset.pagination = 'error';
    delete root.dataset.pages;
    var printButton = document.getElementById('wrPrintBtn');
    if (printButton) printButton.disabled = true;
    root.dataset.paginationError = error.message;
    var notice = document.createElement('p');
    notice.className = 'wr-pagination-error';
    notice.setAttribute('role', 'alert');
    notice.textContent = 'A4 分页未完成：' + error.message;
    main.before(notice);
    console.error(error);
  }

  function checkWorkHeadings(container) {
    container.querySelectorAll('[data-section-type="work"] .wr-entry-head').forEach(function (head) {
      var bounds = head.getBoundingClientRect();
      var lineCenter;
      var previousRight = bounds.left;
      var invalid = false;
      Array.from(head.children).forEach(function (part) {
        var walker = document.createTreeWalker(part, NodeFilter.SHOW_TEXT);
        var range = document.createRange();
        var partLeft = Infinity;
        var partRight = -Infinity;
        var node;
        while ((node = walker.nextNode())) {
          if (!node.textContent.trim()) continue;
          range.selectNodeContents(node);
          Array.from(range.getClientRects()).forEach(function (rect) {
            if (!rect.width || !rect.height) return;
            var center = (rect.top + rect.bottom) / 2;
            if (lineCenter === undefined) lineCenter = center;
            if (Math.abs(center - lineCenter) > 2 || rect.left < bounds.left - 2 || rect.right > bounds.right + 2) invalid = true;
            partLeft = Math.min(partLeft, rect.left);
            partRight = Math.max(partRight, rect.right);
          });
        }
        if (partRight === -Infinity) return;
        if (partLeft < previousRight - 2) invalid = true;
        previousRight = partRight;
      });
      if (invalid) {
        var title = Array.from(head.children).map(function (part) { return part.textContent.trim(); }).join(' / ');
        throw new Error('工作经历标题“' + title + '”无法完整保持一行，请确认准确简称或调整版式；原文已保留，打印暂不可用。');
      }
    });
  }

  function checkTextWidth(container, label) {
    if (!container) return;
    var bounds = container.getBoundingClientRect();
    var style = getComputedStyle(container);
    var left = bounds.left + (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.borderLeftWidth) || 0);
    var right = bounds.right - (parseFloat(style.paddingRight) || 0) - (parseFloat(style.borderRightWidth) || 0);
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    var range = document.createRange();
    var node;
    while ((node = walker.nextNode())) {
      if (!node.textContent.trim()) continue;
      // Text ranges catch overflowing words, unlike the paragraph's box.
      // CSS list markers are not text nodes and cannot trigger a false alarm.
      range.selectNodeContents(node);
      var overflow = Array.from(range.getClientRects()).some(function (rect) {
        return rect.width > 0 && rect.height > 0 && (rect.left < left - 2 || rect.right > right + 2);
      });
      if (overflow) throw new Error(label + '的文字超出可用宽度，请检查过长的邮箱、英文或日期；不会缩字或隐藏内容。');
    }
  }

  function build() {
    if (busy) return;
    busy = true;
    try {
      var oldError = document.querySelector('.wr-pagination-error');
      if (oldError) oldError.remove();
      main.replaceChildren();
      var source = original.querySelector('.wr-page');
      var portrait = root.dataset.layout === 'portrait';
      var pages = [];
      function newPage() {
        var sheet = document.createElement('article');
        sheet.className = 'wr-sheet';
        var page = document.createElement('div');
        page.className = 'wr-page';
        sheet.append(page);
        main.append(sheet);
        var record = {sheet: sheet, page: page, maps: {body: new Map(), left: new Map(), right: new Map()}};
        if (pages.length === 0) {
          var header = source.querySelector(':scope > .wr-header');
          if (header) page.append(header.cloneNode(true));
        }
        if (portrait) {
          var columns = document.createElement('div');
          columns.className = 'wr-columns';
          record.left = document.createElement('aside');
          record.left.className = 'wr-sidebar';
          record.right = document.createElement('div');
          record.right.className = 'wr-primary';
          columns.append(record.left, record.right);
          page.append(columns);
        } else record.body = page;
        pages.push(record);
        return record;
      }
      newPage();
      function appendUnit(record, side, unit) {
        var map = record.maps[side];
        var before = new Map(map);
        var inserted = [];
        var parent = record[side];
        var parents = [];
        unit.path.forEach(function (node) {
          if (!map.has(node)) {
            var clone = node.cloneNode(false);
            parent.append(clone);
            inserted.push(clone);
            map.set(node, clone);
          }
          parent = map.get(node);
          parents.push(parent);
        });
        unit.lead.forEach(function (item) {
          var clone = item.node.cloneNode(true);
          (parents[item.depth] || record[side]).insertBefore(clone, parents[item.depth + 1] || null);
          inserted.push(clone);
        });
        unit.nodes.forEach(function (node) {
          var clone = node.cloneNode(true);
          parent.append(clone);
          inserted.push(clone);
        });
        // Check ink/content bounds, not the sheet's min-height.
        var bottom = record.sheet.getBoundingClientRect().top + height - padding - 2;
        var nodes = record.page.querySelectorAll('h1,h2,h3,p,li,dt,dd,.wr-entry-head,.wr-contact');
        var fits = Array.from(nodes).every(function (node) { return node.getBoundingClientRect().bottom <= bottom; });
        if (!fits) {
          inserted.reverse().forEach(function (node) { node.remove(); });
          record.maps[side] = before;
        }
        return fits;
      }
      function flow(list, side) {
        var index = 0;
        list.forEach(function (unit) {
          if (!appendUnit(pages[index], side, unit)) {
            if (portrait) throw new Error('侧栏版仅支持一页 A4，请精简内容或改用单栏版；不会缩字或隐藏内容。');
            index += 1;
            if (!pages[index]) newPage();
            if (!appendUnit(pages[index], side, unit)) throw new Error('单个内容段落超过一页，请拆分内容后重试。');
          }
        });
        return index;
      }
      if (portrait) {
        if (flow(units(source.querySelector('.wr-sidebar')), 'left') > 0) {
          throw new Error('侧栏内容超过一页，请精简侧栏或改用单栏版以保持阅读顺序。');
        }
        flow(units(source.querySelector('.wr-primary')), 'right');
        var bottomLimit = pages[0].sheet.getBoundingClientRect().top + height - padding - 2;
        balanceColumn(pages[0].left, bottomLimit);
        balanceColumn(pages[0].right, bottomLimit);
      } else {
        var content = source.cloneNode(true);
        var header = content.querySelector(':scope > .wr-header');
        if (header) header.remove();
        flow(units(content), 'body');
      }
      pages.forEach(function (record) {
        checkWorkHeadings(record.page);
        if (portrait) {
          checkTextWidth(record.page.querySelector(':scope > .wr-header'), '页眉');
          checkTextWidth(record.left, '侧栏');
          checkTextWidth(record.right, '工作经历');
        } else checkTextWidth(record.body, '页面');
      });
      root.dataset.pages = String(pages.length);
      root.dataset.pagination = 'ready';
      var printButton = document.getElementById('wrPrintBtn');
      if (printButton) printButton.disabled = false;
      delete root.dataset.paginationError;
    } catch (error) {
      showError(error);
    } finally { busy = false; }
  }

  async function paginate() {
    var ticket = ++generation;
    root.dataset.pagination = 'loading';
    var printButton = document.getElementById('wrPrintBtn');
    if (printButton) printButton.disabled = true;
    try {
      var usedFonts = new Set();
      main.querySelectorAll('*').forEach(function (node) {
        if (!node.getClientRects().length) return;
        var style = getComputedStyle(node);
        usedFonts.add(style.fontStyle + ' ' + style.fontWeight + ' 12px ' + style.fontFamily);
      });
      if (!usedFonts.size) throw new Error('没有可测量的简历正文。');
      var loadingFonts = Array.from(usedFonts).map(function (font) {
        return document.fonts.load(font).then(function (faces) {
          if (!faces.length) throw new Error('未匹配到简历使用的本地字体。');
        });
      });
      await Promise.all(loadingFonts.concat(document.fonts.ready));
    } catch (error) {
      if (ticket === generation) showError(new Error('字体加载失败，请检查字体文件是否完整，或切换字体后重试。'));
      return;
    }
    if (ticket === generation) build();
  }
  window.wisePaginate = paginate;
  new MutationObserver(paginate).observe(root, {attributes: true, attributeFilter: ['data-preset', 'data-photo']});
  paginate();
})();
