import assert from "node:assert/strict";
import { buildPlaybackIndexes } from "../frontend/playback-utils.js";

const result = {
  series: [
    {
      snapshots: [
        { date: "2020-01-02", year: 2020 },
        { date: "2020-01-31", year: 2020 },
        { date: "2020-02-03", year: 2020 },
        { date: "2020-02-28", year: 2020 },
        { date: "2020-03-02", year: 2020 },
      ],
    },
  ],
};

assert.deepEqual(buildPlaybackIndexes(result), [1, 3, 4]);
