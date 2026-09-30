# Case Study: Where Should a Hot Chicken Restaurant Spend Its Next Hour of Labor?

**Role:** Analyst and project lead · **Tools:** Python, SQL (SQLite), Excel, Chart.js, GitHub Actions · **Data:** synthetic, 24,251 orders, 12 months

## The problem
A small restaurant sells through a storefront, a Friday night market and eight vendor events. The owner knows what sells, but not which channel, day or hour actually makes money once staff and booth fees are paid, or where to add or cut labor.

## Approach
1. **Built and cleaned the data.** Generated realistic orders with deliberate errors (duplicates, negative quantities, inconsistent labels), then fixed and logged every change.
2. **Asked 15 business questions in SQL.** Profit by channel, event ROI, top items by *profit* rather than revenue, spice preferences, retention cohorts, kitchen bottlenecks.
3. **Built two dashboards.** An Excel workbook with live formulas and a dropdown-driven Explorer sheet, and an interactive web dashboard with filters and a stress-test section.
4. **Stress-tested the answers.** Labor-rate and attendance scenarios, bootstrap confidence intervals and significance tests.
5. **Wrote it for the owner.** Eight findings, each with the number, why it matters and a specific action.

## What I found
- Margin was about 66% in every channel, so the real lever was **labor, not menu**.
- **Vendor events** earned 31% of revenue in 21 of 310 selling days; six of eight returned 412-487% on booth fee plus staff, and two barely broke even.
- **Tue-Wed storefront days** earned less than a 3-person crew costs (95% confidence). Thursday was break-even and became a pilot rather than a cut.
- **Event kitchens** slowed from 7.6 to 18.1 minutes per order once an hour passed 60 orders.
- **Loyalty members** repeated 19.7 points more often and were worth about 2x per customer, yet only 8% of event orders were linked to a customer.

## Recommendations and impact
Five changes (replace two events, 2 staff Tue-Wed, a drink add-on, a wings price test, a late-night skeleton crew) are worth **$14k / $65k / $90k a year** in worst / typical / best case, about 7% / 33% / 45% of 2025 contribution.

## What I would do differently
The data is synthetic, so the findings demonstrate method, not real-world truth. The pipeline now has a real-data mode (kept in a git-ignored folder) so the next version can run on actual sales exports.

**See it:** [live dashboard](https://amanubhi.github.io/Heat-Check---Sales-Operations-Dashboard/) · [insights report](reports/insights.md) · [project plan](PROJECT_PLAN.md)
