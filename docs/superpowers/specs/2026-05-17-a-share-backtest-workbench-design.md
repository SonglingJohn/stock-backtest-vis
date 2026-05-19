# A Share Backtest Workbench Design

## Goal

Build a local A-share strategy backtest workbench that answers: if I bought these stocks in a given year with this buying method, how much would I have gained by the latest available trading day?

## Product Shape

The MVP is a playback storyboard. Users configure assumptions, then play an animated valuation curve that advances year by year. During playback, the parameter panel collapses into a narrow left rail so the chart owns the page. A top full-width story sentence shows the dynamic year and current result:

`正在回放 2018 年：累计投入 50,000 元，当前市值 78,320 元，浮盈 +28,320 元。`

Users can skip animation and show the final result immediately.

## Inputs

- Stock rows: stock code plus allocation percentage. Empty percentage defaults to 100%.
- Add button creates another stock row.
- MVP supports multiple stocks as separate comparison lines. Portfolio allocation percentages are captured now and used for the later portfolio mode.
- Buying method: one-time buy or annual fixed investment.
- Amount: one-time amount or annual amount.
- Date range: year range picker semantics, from start year to end year or latest available trading day.

## Backtest Semantics

- Data source: AKShare `stock_zh_a_hist`.
- Price: forward-adjusted close, `adjust="qfq"`.
- One-time buy: buy on the first available trading day in the selected start year.
- Annual fixed investment: buy on the first available trading day of each selected year.
- Latest result uses the latest trading day available from the data source, not the natural current day.
- Multiple stocks in MVP are rendered as separate comparison series.

## Architecture

- `backend/backtest.py`: pure calculation engine, no network dependency.
- `backend/data_source.py`: AKShare adapter plus JSON cache.
- `backend/server.py`: local HTTP API and static file server.
- `frontend/`: static HTML, CSS, and JavaScript playback UI.
- `tests/`: standard-library unit tests for calculation behavior.

## Error Handling

- Missing AKShare dependency returns a clear setup error.
- Empty or invalid stock data returns a user-readable API error.
- Invalid percentages, amounts, or year ranges are rejected before running the calculation.

## Testing

Unit tests cover buying schedule, one-time buy, annual fixed investment, percentage normalization, yearly snapshots, and drawdown/summary math.
