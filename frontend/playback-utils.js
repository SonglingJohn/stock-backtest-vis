export function buildPlaybackIndexes(result) {
  const firstSeries = result.series[0];
  const byMonth = new Map();
  firstSeries.snapshots.forEach((point, index) => {
    byMonth.set(String(point.date).slice(0, 7), index);
  });
  return [...byMonth.values()];
}
