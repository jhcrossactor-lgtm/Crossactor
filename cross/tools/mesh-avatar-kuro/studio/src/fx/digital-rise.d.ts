export interface DigitalRiseConfig {
  enabled: boolean;
  density: number;
  back: { count: number; size: [number, number]; alpha: number; speed: [number, number] };
  front: { count: number; size: [number, number]; alpha: number; speed: [number, number] };
  kinds: { square: number; pixel: number; glyph: number; line: number };
  colors: string[];
  glow: number;
  spawn: { xCenter: number; xSpread: number; jitterY: number };
  fade: { start: number; end: number; power: number };
  wobble: { amp: number; freq: number };
  speaking: { rate: number; brightness: number; attack: number; release: number };
  autoQuality: { enabled: boolean; targetMs: number; minDensity: number; step: number };
  maxDpr: number;
}
type DeepPartial<T> = { [K in keyof T]?: T[K] extends object ? DeepPartial<T[K]> : T[K] };
export interface DigitalRise {
  tick(now?: number): void;
  setSpeaking(on: boolean): void;
  setLevel(level: number): void;
  setEnabled(on: boolean): void;
  setDensity(density: number): void;
  getStats(): { fps: number; frameMs: number; density: number; particles: number; enabled: boolean; speaking: boolean; boostRate: number };
  config: DigitalRiseConfig;
  canvases: { back: HTMLCanvasElement; front: HTMLCanvasElement };
  destroy(): void;
}
export function createDigitalRise(opts: {
  container: HTMLElement;
  before?: HTMLElement;
  config?: DeepPartial<DigitalRiseConfig>;
  autoLoop?: boolean;
}): DigitalRise;
