export function applyListingYearToStartInput(startYearInput, yearRangeText, endYearInput, stockInfo) {
  const listingYear = Number(stockInfo?.listing_year);
  if (!Number.isFinite(listingYear)) return;

  startYearInput.value = String(listingYear);
  startYearInput.readOnly = false;
  startYearInput.min = String(listingYear);
  startYearInput.title = `${stockInfo.name || stockInfo.symbol || "股票"} 上市年份 ${listingYear}，可改为上市后的年份`;
  startYearInput.dataset.listingYear = String(listingYear);
  delete startYearInput.dataset.lockedListingYear;
  yearRangeText.textContent = `${startYearInput.value} - ${endYearInput.value}`;
}
