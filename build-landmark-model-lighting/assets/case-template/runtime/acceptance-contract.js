const EFFECT_MODES = Object.freeze(["color", "build", "edge-color"]);
const CANONICAL_VIEWS = Object.freeze([
  "front",
  "back",
  "left",
  "right",
  "roof",
  "ground-contact",
  "three-quarter",
]);

function requireMethod(adapter, name) {
  if (typeof adapter[name] !== "function") {
    throw new TypeError(`Acceptance adapter requires ${name}()`);
  }
}

function clamp01(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new TypeError("Effect progress must be a finite number");
  }
  return Math.min(1, Math.max(0, number));
}

export function installLandmarkAcceptanceBridge(adapter) {
  if (!adapter || typeof adapter !== "object") {
    throw new TypeError("Acceptance adapter must be an object");
  }

  [
    "freezeRafTimeAndDamping",
    "setPlaybackPaused",
    "replay",
    "setEffectProgress",
    "setCanonicalView",
    "applyDeterministicUserViewDelta",
    "capture",
    "captureMotionDiagnostics",
    "captureSubjectIdMask",
    "dispose",
  ].forEach((name) => requireMethod(adapter, name));

  const bridge = Object.freeze({
    version: 4,
    effects: EFFECT_MODES,
    canonicalViews: CANONICAL_VIEWS,
    ready: Promise.resolve(adapter.ready),
    freezeRafTimeAndDamping: (timeMs = 0) =>
      adapter.freezeRafTimeAndDamping(Number(timeMs)),
    setPlaybackPaused: (paused) => adapter.setPlaybackPaused(Boolean(paused)),
    replay: () => adapter.replay(),
    setEffectProgress: (effect, progress) => {
      if (!EFFECT_MODES.includes(effect)) {
        throw new RangeError(`Unknown effect: ${effect}`);
      }
      return adapter.setEffectProgress(effect, clamp01(progress));
    },
    setCanonicalView: (view) => {
      if (!CANONICAL_VIEWS.includes(view)) {
        throw new RangeError(`Unknown canonical view: ${view}`);
      }
      return adapter.setCanonicalView(view);
    },
    applyDeterministicUserViewDelta: (yaw, pitch, zoom) =>
      adapter.applyDeterministicUserViewDelta(
        Number(yaw),
        Number(pitch),
        Number(zoom),
      ),
    capture: (label = "") => adapter.capture(String(label)),
    captureMotionDiagnostics: () => adapter.captureMotionDiagnostics(),
    captureSubjectIdMask: () => adapter.captureSubjectIdMask(),
    dispose: () => adapter.dispose(),
  });

  window.__BUILD_WHITE_MODEL_MOTION_ACCEPTANCE__ = bridge;
  return () => {
    if (window.__BUILD_WHITE_MODEL_MOTION_ACCEPTANCE__ === bridge) {
      delete window.__BUILD_WHITE_MODEL_MOTION_ACCEPTANCE__;
    }
  };
}
