import assert from "node:assert/strict";
import {
  autoViewportStartFrame,
  manualViewportEndFrame,
  maxViewportStartFrame,
  seriesColor,
  viewportValueDomain,
} from "../frontend/chart-utils.js";

assert.equal(autoViewportStartFrame(0, 3), 0);
assert.equal(autoViewportStartFrame(2, 3), 0);
assert.equal(autoViewportStartFrame(5, 3), 3);
assert.equal(maxViewportStartFrame(10, 3), 7);
assert.equal(maxViewportStartFrame(2, 3), 0);
assert.equal(manualViewportEndFrame(0, 10, 3), 2);
assert.equal(manualViewportEndFrame(7, 10, 3), 9);
assert.equal(manualViewportEndFrame(9, 10, 3), 9);

const domain = viewportValueDomain([100, 120, 90], 100);
assert(domain.maxValue > 120);
assert(domain.minValue < 90);
assert.equal(Math.round(((domain.maxValue - 100) / (domain.maxValue - domain.minValue)) * 100), 88);
assert.equal(seriesColor(0), "#4E79A7");
assert.equal(seriesColor(9), "#BAB0AB");
assert.equal(seriesColor(10), "#4E79A7");
