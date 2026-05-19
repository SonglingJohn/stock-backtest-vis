export const DEFAULT_VIEWPORT_MONTHS = 84;
export const SERIES_COLORS = [
  "#4E79A7",
  "#F28E2B",
  "#59A14F",
  "#E15759",
  "#76B7B2",
  "#EDC948",
  "#B07AA1",
  "#FF9DA7",
  "#9C755F",
  "#BAB0AB",
];

export function autoViewportStartFrame(currentFrame, viewportMonths = DEFAULT_VIEWPORT_MONTHS) {
  return Math.max(0, currentFrame - viewportMonths + 1);
}

export function manualViewportEndFrame(startFrame, totalFrames, viewportMonths = DEFAULT_VIEWPORT_MONTHS) {
  if (totalFrames <= 0) return 0;
  return Math.min(totalFrames - 1, Number(startFrame) + viewportMonths - 1);
}

export function maxViewportStartFrame(totalFrames, viewportMonths = DEFAULT_VIEWPORT_MONTHS) {
  return Math.max(0, totalFrames - viewportMonths);
}

export function viewportValueDomain(values, baselineValue, baselineRatio = 0.88) {
  const maxValue = Math.max(...values, baselineValue);
  const minValue = Math.min(...values, baselineValue);
  const upRange = Math.max(maxValue - baselineValue, 1);
  const downRange = Math.max(baselineValue - minValue, 0);
  const range = Math.max(upRange / baselineRatio, downRange / (1 - baselineRatio), 1) * 1.08;
  return {
    minValue: baselineValue - range * (1 - baselineRatio),
    maxValue: baselineValue + range * baselineRatio,
  };
}

export function seriesColor(index, palette = SERIES_COLORS) {
  return palette[index % palette.length];
}
