# Research notes behind Charlie (Oct 22, 2026)

These are the findings that shaped the MVP, with sources, and what each one changed in the build.

## 1. "Invest in what you know" is an idea filter, not a safety signal

- **The case for it.** Peter Lynch's *One Up on Wall Street* argues that ordinary people spot changes in industries they work in or buy from before Wall Street does. Munger and Buffett frame the same idea as a *circle of competence*: know where the edge of your knowledge is and stay inside it.
- **The catch.** Long, Fernbach & De Langhe (2018, *Journal of Marketing Research* 55(4)) found that people's *sense of understanding* a company lowers how risky they think it is and raises the returns they expect, with **no link to its actual risk**. Experienced investors showed the pattern too. ([CU Boulder summary](https://www.colorado.edu/business/faculty-research/2019/08/15/circle-incompetence-sense-understanding-improper-guide-investment-risk))

**What we built:** familiarity is 25% of the ranking score, so it decides *which* companies you see. It never sets position size. Size comes only from the risk slider and your capital. The profile page says this out loud.

## 2. Munger's checklist, turned into a score

Sources: Munger's investing principles checklist as compiled from *Poor Charlie's Almanack* ([summary](https://acquirersmultiple.com/2017/10/charlies-munger-the-ultimate-investing-principles-checklist/)), and his risk checklist ([GuruFocus](https://www.gurufocus.com/news/928143/charlie-mungers-risk-checklist-)).

| Munger idea | Score factor | Inputs |
|---|---|---|
| Circle of competence | Competence (25%) | Resume, reading, brands, holdings |
| "A great business at a fair price" | Quality (25%) | ROIC, free-cash-flow conversion, gross margin |
| Durable competitive advantage | Moat (15%) | Margin *stability* over ~5 years, ROIC vs cost of capital |
| "Liquor, ladies and leverage" | Balance sheet (15%) | Debt/equity, share dilution vs buybacks |
| Margin of safety (Graham) | Value (20%) | Free-cash-flow yield vs Treasuries, earnings yield (Greenblatt), distance from 52-week high |
| "Invert, always invert" | Red-flag penalties | Cash burn, losses, heavy debt, dilution, shrinking revenue, extreme IV, outside your circle |
| Patience, few big bets | Engine rules | 1-3 ideas a day max, one per sector, "nothing today" is a valid answer |

Each stock also gets a Peter Lynch category (fast grower, stalwart, cyclical, turnaround).

An early version scored Costco poorly because its margins are thin by design. Munger was a long-time Costco director and shareholder, so quality now leans on ROIC and how much profit turns into cash, not raw margins.

## 3. Which option strategies are "safe enough" to start with

- **Broker approval levels** follow the same ladder. Alpaca: Level 1 is covered calls and cash-secured puts, Level 2 adds buying calls and puts, Level 3 adds spreads ([Alpaca docs](https://docs.alpaca.markets/docs/options-trading)). Baird puts covered calls at level 1, cash-secured puts at 2, buying options at 3, spreads at 4, and naked writing at 6 ([Baird PDF](https://www.BairdWealth.com/globalassets/pdfs/help/option-level-descriptions.pdf)).
- **Long-run evidence for selling options on quality.** A 25-year Cboe-commissioned study (Asset Consulting Group, 2012) found the PUT index (cash-secured S&P 500 puts) grew 1,153% vs 807% for the S&P 500 from 1986 to 2011, with about 30% lower volatility. BXM (covered calls) was similar to the index with lower volatility. ([Mondo Visione](https://mondovisione.com/media-and-resources/news/new-study-compares-25-year-performance-of-options-strategy-benchmarks-to-traditi-2012214/))
- **What hurts beginners.** Retail traders lost about $350k a day on 0DTE S&P options after daily expirations launched in 2022 ([Neudata](https://www.neudata.co/literature-reviews/zero-day-to-expiry-options-a-losing-bet-for-retail-traders)).

**What we built:** a 5-step slider. 1 = shares only. 2 (default) = covered calls and cash-secured puts at about 0.20 delta, 30-50 days out. 3 = adds defined-risk credit spreads and collars. 4 = adds debit spreads and LEAPS. 5 = adds short-dated long calls at 2% of capital. No level ever allows uncovered calls or same-week expirations. Every trade shows its maximum loss in dollars, its breakeven, a payoff chart, an exit plan, and a "what could go wrong" list.

## 4. Free data sources

| Source | Cost / key | What it gives | Used for |
|---|---|---|---|
| Cboe delayed quotes (`cdn.cboe.com/api/global/delayed_quotes/...`) | Free, no key, ~15 min delayed, unofficial | Full options chains with bid/ask, IV, delta, gamma, theta, vega; daily price history | Quotes, chains, greeks, charts |
| SEC EDGAR XBRL (`data.sec.gov/api/xbrl/companyfacts`) | Free, no key, User-Agent with email required, <10 req/s | Every 10-K fact | ROIC, margins, debt, FCF, dilution |
| Massive (formerly Polygon) | Free tier 5 calls/min, end-of-day options | Greeks and IV | Upgrade path |
| Tradier | Sandbox is delayed with no greeks; production needs a brokerage account | Chains + greeks hourly | Upgrade path |
| Alpaca | Free paper trading with options (levels 1-3) | Paper order execution | Next step for "easy to place" |

Source for the paid/free comparison: [FlashAlpha's Sept 2026 comparison](https://flashalpha.com/articles/best-options-data-apis-2026) (a vendor's own write-up, so treat its claims about itself with care).

The cloud machine used to build this MVP blocks outbound requests to market-data hosts, so the live Cboe and SEC adapters were written against their documented formats and unit-tested with fixtures, but not run against the live endpoints. On a normal laptop they should work. If they fail, the app falls back to clearly labeled demo data.

## 5. Common short-option management rules used as defaults

Take profits at around 50% of max profit, revisit at about 21 days to expiry, and pick 30-50 day expirations. These are widely used retail conventions (popularized by tastytrade research), not guarantees, and the app presents them as a starting plan.
