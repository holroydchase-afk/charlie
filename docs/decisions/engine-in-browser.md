# Decision: running the engine in the browser (M1.1 spike)

Date: 2026-10-23. Status: **proposed, needs Chase's call** (see the end).

## Question
FastAPI can't run on GitHub Pages, so the static demo needs the engine in the browser. Should we run the existing Python in Pyodide or port scoring and strategies to JavaScript? PLAN's stop condition says: if the interactive app takes over 10 seconds on a throttled mid-range phone, even with a prebuilt first screen, port to JS.

## What the spike does
- `spike/` + `tools/build_spike.py` build a static page. It loads Pyodide 0.28.3, unpacks a 40 KB zip of the `charlie` modules the demo needs (`charlie/demo.py` and its imports only: no server, storage, chat, document parsers or network code), and shows today's ideas for the fictional sample resume on mock data.
- The engine now runs serially when there are no threads (`sys.platform == "emscripten"`).
- `tests/golden/sample_ideas.json` pins the ideas pytest produces for the sample person (2026-10-22, risk level 2). The browser run produced **exactly the same summary** (symbols, strategies, scores, legs, max loss, breakeven, chance of profit) in every run below.

## Measurements
Method: headless Chromium 140 (Playwright) on the cloud build machine, page served locally, CPU throttled with DevTools (`Emulation.setCPUThrottlingRate`). Network not throttled; the download cost is added separately below. "Cold" is a fresh browser context; "warm" is a reload in the same context. The numbers are milliseconds from page start.

| Profile | Run | Runtime ready | Package imported | First ideas shown | Re-run at another risk level |
|---|---|---|---|---|---|
| Laptop (no throttle) | cold | 1,696 | 1,871 | 2,483 | 105 |
| Laptop (no throttle) | warm | 1,387 | 1,551 | 2,094 | 84 |
| Phone, 4x CPU slowdown | cold | 7,752 | 8,623 | **11,631** | 439 |
| Phone, 4x CPU slowdown | warm | 6,490 | 7,542 | **10,087** | 448 |
| Phone, 6x CPU slowdown | cold | 12,491 | 13,938 | 19,183 | 687 |
| Phone, 6x CPU slowdown | warm | 11,777 | 13,127 | 17,742 | 632 |

The first ideas came in at 16.3 s (4x) before the mock option chains were optimized (computed once per strike, put from parity, about 2x faster in CPython). The table shows the optimized build.

Download: Pyodide's runtime is about 12 MB raw, about 5.5 MB gzipped as a CDN serves it (wasm 2.8 MB, stdlib 2.4 MB, JS 0.2 MB). At DevTools "Fast 4G" (about 9 Mbps) that adds roughly 5 s on a first visit. At "Slow 4G" (1.6 Mbps) it adds about 28 s. Repeat visits come from the HTTP cache.

## What it means
- **Correctness: go.** One engine and the same answers as the tests.
- **Speed: on the line.** About 7 s of the phone time is Pyodide starting up (wasm compile plus the stdlib), which our code can't shrink. Our own work after that is 3 to 4 s, and re-runs are fast (0.4 to 0.7 s). On a mid-range phone, the first *interactive* moment lands at about 10 to 12 s plus the first download, so **the PLAN stop condition is tripped**.
- A prebuilt first screen (M1.3) still shows the sample person's ideas in under 3 s, whichever way we go.

## Options
1. **Stay on Pyodide and prebuild more (recommended).** M1.3 prebuilds ideas for all five risk levels and the ticker drawer for each idea's symbol. The slider and the drawers are then instant, and the core recruiter path never waits on Python. Pyodide only matters for "paste your own resume" and the screener, which show a loading state. Cost: about a day, no new code paths, tests stay the reference. Risk: a recruiter who goes straight to "try your own resume" on a slow phone waits about 10 s.
2. **Port `scoring.py`, `strategies.py`, `options_math.py`, `profile.py` and the mock data to JS.** Instant everywhere, with no 5.5 MB download. Cost: about 1,500 lines duplicated in a second language, golden-output tests to keep them in step, and two engines to maintain.

Recommendation: option 1. Revisit if real-device testing (M1.7) shows more than 12 s to interactive on a mid-range Android.

## Not verified
- Real phones, real CDN delivery, and Safari/WebKit. Chromium throttling only approximates a mid-range phone.
- The jsDelivr CDN is blocked from the build machine, so the spike was served from the `pyodide` npm package (same files, same version).
