import assert from "node:assert/strict";
import { applyListingYearToStartInput } from "../frontend/form-utils.js";

const startYearInput = {
  value: "2014",
  readOnly: true,
  min: "1990",
  title: "",
  dataset: {
    lockedListingYear: "2001",
  },
};
const yearRangeText = { textContent: "" };
const endYearInput = { value: "2026" };

applyListingYearToStartInput(startYearInput, yearRangeText, endYearInput, {
  symbol: "600519",
  name: "贵州茅台",
  listing_year: 2001,
});

assert.equal(startYearInput.value, "2001");
assert.equal(startYearInput.readOnly, false);
assert.equal(startYearInput.min, "2001");
assert.equal(startYearInput.dataset.listingYear, "2001");
assert.equal(startYearInput.dataset.lockedListingYear, undefined);
assert.equal(yearRangeText.textContent, "2001 - 2026");
