(function (global) {
  'use strict';

  function createFrame(container, name) {
    var frame = document.createElement('iframe');
    frame.className = 'gallery-frame';
    frame.title = name;
    frame.setAttribute('aria-hidden', 'true');
    container.appendChild(frame);
    return frame;
  }

  function waitForRenderProtocol(doc) {
    if (doc.documentElement.dataset.renderReady === 'true') return Promise.resolve();
    return new Promise(function (resolve) {
      var settled = false;
      var observer = new MutationObserver(function () {
        if (doc.documentElement.dataset.renderReady === 'true') finish();
      });
      var timeout = setTimeout(finish, 3500);

      function finish() {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        observer.disconnect();
        resolve();
      }

      observer.observe(doc.documentElement, {
        attributes: true,
        attributeFilter: ['data-render-ready']
      });
    });
  }

  function createGalleryFrameLoader(container) {
    if (!container) throw new Error('gallery frame container is required');

    var visibleFrame = createFrame(container, '当前版式预览');
    var loadingFrame = createFrame(container, '下一版式预览');
    var navigationId = 0;

    visibleFrame.classList.add('is-visible');
    visibleFrame.removeAttribute('aria-hidden');
    container.dataset.previewState = 'idle';

    function reveal(frame, token) {
      if (token !== navigationId || frame !== loadingFrame) return;

      visibleFrame.classList.remove('is-visible');
      visibleFrame.setAttribute('aria-hidden', 'true');
      frame.classList.add('is-visible');
      frame.removeAttribute('aria-hidden');

      var previousFrame = visibleFrame;
      visibleFrame = frame;
      loadingFrame = previousFrame;
      container.dataset.previewState = 'ready';
    }

    function awaitFrame(frame, token) {
      var doc;
      try {
        doc = frame.contentDocument;
      } catch (error) {
        reveal(frame, token);
        return;
      }
      if (!doc || !doc.documentElement) {
        reveal(frame, token);
        return;
      }

      var fontsReady = doc.fonts && doc.fonts.ready
        ? doc.fonts.ready.catch(function () {})
        : Promise.resolve();

      Promise.all([fontsReady, waitForRenderProtocol(doc)]).then(function () {
        requestAnimationFrame(function () {
          requestAnimationFrame(function () { reveal(frame, token); });
        });
      });
    }

    function load(src) {
      var token = ++navigationId;
      container.dataset.previewState = 'loading';
      loadingFrame.onload = function () { awaitFrame(loadingFrame, token); };
      loadingFrame.src = src;
    }

    return { load: load };
  }

  global.createGalleryFrameLoader = createGalleryFrameLoader;
})(window);
