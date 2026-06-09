// Local feature extraction from browser events
// Privacy-first: raw events are aggregated in-memory only.
// Only computed feature vectors (no coordinates, no keystrokes) leave this module.

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FeatureVector {
  avgTypingSpeed: number;    // characters per second
  typingVariance: number;    // variance of inter-key intervals (ms²)
  mouseLinearity: number;    // straight-line / path-length ratio  [0–1]
  idleRatio: number;         // fraction of session with no events [0–1]
  sessionDuration: number;   // total elapsed time in seconds
}

/** Minimal mouse point – coordinates are discarded after path math. */
interface Point {
  x: number;
  y: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Gap (ms) with no events that qualifies as "idle". */
const IDLE_GAP_MS = 2_000;

/** Maximum number of raw timestamps / points kept to bound memory usage. */
const MAX_BUFFER_SIZE = 2_000;

// ---------------------------------------------------------------------------
// BehaviorCollector
// ---------------------------------------------------------------------------

export class BehaviorCollector {
  private readonly sessionStartMs: number;

  // Raw timestamp buffers — never exposed outside this class.
  private readonly _keydownTs: number[] = [];
  private readonly _allEventTs: number[] = [];

  // Mouse path is reduced to cumulative statistics on-the-fly so that
  // individual coordinates are never retained beyond a single update.
  private _mouseMoveCount = 0;
  private _mousePathLength = 0;        // cumulative Euclidean path length (px)
  private _mouseFirstPoint: Point | null = null;
  private _mouseLastPoint: Point | null = null;

  // First-click timestamp for transaction_speed (not exposed raw).
  private _firstClickTs: number | null = null;

  // Bound listener references so removeListeners() can detach them cleanly.
  private readonly _onKeydown: (e: KeyboardEvent) => void;
  private readonly _onMousemove: (e: MouseEvent) => void;
  private readonly _onClick: (e: MouseEvent) => void;
  private readonly _onScroll: () => void;

  constructor() {
    this.sessionStartMs = performance.now();

    this._onKeydown   = this._handleKeydown.bind(this);
    this._onMousemove = this._handleMousemove.bind(this);
    this._onClick     = this._handleClick.bind(this);
    this._onScroll    = this._handleScroll.bind(this);

    document.addEventListener("keydown",   this._onKeydown,   { passive: true });
    document.addEventListener("mousemove", this._onMousemove, { passive: true });
    document.addEventListener("click",     this._onClick,     { passive: true });
    document.addEventListener("scroll",    this._onScroll,    { passive: true, capture: true });
  }

  // ------------------------------------------------------------------
  // Event handlers  (record timestamps / aggregates, never raw content)
  // ------------------------------------------------------------------

  private _handleKeydown(_e: KeyboardEvent): void {
    const now = performance.now();
    if (this._keydownTs.length < MAX_BUFFER_SIZE) {
      this._keydownTs.push(now);
    }
    this._recordEvent(now);
  }

  private _handleMousemove(e: MouseEvent): void {
    const now = performance.now();
    const point: Point = { x: e.clientX, y: e.clientY };

    if (this._mouseFirstPoint === null) {
      this._mouseFirstPoint = point;
    }

    // Accumulate path length incrementally — discard the previous point.
    if (this._mouseLastPoint !== null) {
      const dx = point.x - this._mouseLastPoint.x;
      const dy = point.y - this._mouseLastPoint.y;
      this._mousePathLength += Math.sqrt(dx * dx + dy * dy);
    }

    this._mouseLastPoint = point;
    this._mouseMoveCount++;
    this._recordEvent(now);
  }

  private _handleClick(e: MouseEvent): void {
    const now = performance.now();
    if (this._firstClickTs === null) {
      this._firstClickTs = now;
    }
    this._recordEvent(now);
  }

  private _handleScroll(): void {
    this._recordEvent(performance.now());
  }

  private _recordEvent(ts: number): void {
    if (this._allEventTs.length < MAX_BUFFER_SIZE) {
      this._allEventTs.push(ts);
    }
  }

  // ------------------------------------------------------------------
  // Feature computation helpers
  // ------------------------------------------------------------------

  /** Compute consecutive differences of a sorted timestamp array. */
  private static _intervals(ts: number[]): number[] {
    const result: number[] = [];
    for (let i = 1; i < ts.length; i++) {
      result.push(ts[i] - ts[i - 1]);
    }
    return result;
  }

  private static _mean(values: number[]): number {
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  private static _variance(values: number[]): number {
    if (values.length < 2) return 0;
    const m = BehaviorCollector._mean(values);
    return BehaviorCollector._mean(values.map((v) => (v - m) ** 2));
  }

  private _computeAvgTypingSpeed(): number {
    const intervals = BehaviorCollector._intervals(this._keydownTs);
    if (intervals.length === 0) return 0;
    const meanMs = BehaviorCollector._mean(intervals);
    return meanMs > 0 ? 1_000 / meanMs : 0; // chars per second
  }

  private _computeTypingVariance(): number {
    return BehaviorCollector._variance(
      BehaviorCollector._intervals(this._keydownTs)
    );
  }

  private _computeMouseLinearity(): number {
    if (
      this._mouseMoveCount < 2 ||
      this._mouseFirstPoint === null ||
      this._mouseLastPoint === null ||
      this._mousePathLength === 0
    ) {
      return 1; // degenerate — treat as perfectly linear
    }
    const dx = this._mouseLastPoint.x - this._mouseFirstPoint.x;
    const dy = this._mouseLastPoint.y - this._mouseFirstPoint.y;
    const straightLine = Math.sqrt(dx * dx + dy * dy);
    return Math.min(straightLine / this._mousePathLength, 1);
  }

  private _computeIdleRatio(durationMs: number): number {
    if (this._allEventTs.length < 2 || durationMs === 0) return 0;
    const intervals = BehaviorCollector._intervals(this._allEventTs);
    const idleMs = intervals
      .filter((gap) => gap > IDLE_GAP_MS)
      .reduce((a, b) => a + b, 0);
    return Math.min(idleMs / durationMs, 1);
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  /**
   * Compute and return the privacy-safe feature vector.
   * Raw event data (coordinates, keystrokes, timestamps) is never included.
   */
  getFeatureVector(): FeatureVector {
    const durationMs = performance.now() - this.sessionStartMs;
    const durationSec = durationMs / 1_000;

    return {
      avgTypingSpeed:  parseFloat(this._computeAvgTypingSpeed().toFixed(6)),
      typingVariance:  parseFloat(this._computeTypingVariance().toFixed(6)),
      mouseLinearity:  parseFloat(this._computeMouseLinearity().toFixed(6)),
      idleRatio:       parseFloat(this._computeIdleRatio(durationMs).toFixed(6)),
      sessionDuration: parseFloat(durationSec.toFixed(6)),
    };
  }

  /**
   * Detach all event listeners and clear internal buffers.
   * Call when the session ends or the component unmounts.
   */
  removeListeners(): void {
    document.removeEventListener("keydown",   this._onKeydown);
    document.removeEventListener("mousemove", this._onMousemove);
    document.removeEventListener("click",     this._onClick);
    document.removeEventListener("scroll",    this._onScroll, { capture: true });

    // Wipe all retained data immediately after detachment.
    this._keydownTs.length = 0;
    this._allEventTs.length = 0;
    this._mouseFirstPoint = null;
    this._mouseLastPoint = null;
    this._mousePathLength = 0;
    this._mouseMoveCount = 0;
    this._firstClickTs = null;
  }
}
