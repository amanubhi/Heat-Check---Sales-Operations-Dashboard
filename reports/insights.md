# Heat Check: Findings & Recommendations for 2026

**Prepared for:** the owner, Heat Check Hot Chicken
**Scope:** all 24,251 orders from Jan-Dec 2025 across the storefront, the Friday night market and eight vendor events
**Data:** synthetic, modeled on a small multi-channel restaurant (see README)

---

## Executive summary

Heat Check sold **$706,870** in 2025 at a **66.6% gross margin** (**$470,857** gross profit). That margin is healthy and almost identical in every channel, so the real question is not "what sells" but **"where does an hour of staff time earn the most?"**

The answer is clear: **events and the night market earn 4-6x more gross profit per labor hour than the storefront.** The storefront produces 52% of revenue but, after a realistic labor cost, only about $24.6k of contribution. The biggest 2026 opportunities are therefore about *where you spend labor*, not about selling more chicken.

| # | Finding | Annual value at stake |
|---|---|---|
| 1 | Keep 6 events, replace 2 weak ones | ~$15k-$32k *(opportunity, not a forecast)* |
| 2 | Cut Tue-Thu storefront crew from 3 to 2 | ~$33.9k saved |
| 3 | Fix the event kitchen bottleneck | Protects the highest-margin channel |
| 4 | +$1 on wings; add a drink attach program | ~$13.1k |
| 5 | Stock sauce by channel | Less waste, faster service |
| 6 | Turn booth customers into loyalty members | Members are worth ~2x per customer |
| 7 | Staff Friday 5-8pm to the limit; test a second weekly market | Largest upside per labor hour |
| 8 | Trim the Fri/Sat late-night window | ~$5.7k saved |

> **Assumptions behind the dollar figures.** Labor is $22/hr loaded. The storefront runs 3 staff x 10 hrs (+2.5 hrs on Fri/Sat); the night market 3 staff x 6 hrs + $85 booth fee; events use their real booth fee and staff count x 10 hrs/day. Rent, utilities, travel and owner pay are **not** included. Change them in `sql/analysis.sql` (the `assumptions` CTEs) to test your own numbers.

---

## 1. Vendor events: 31% of revenue in 21 selling days. Keep six, replace two.

**The number.** Events produced **$215,659 (31%) of revenue in 21 of 310 selling days**, and **$112,424 of contribution after staff and booth fees**, more than four times the storefront's. Six events return **412%-487%** on booth fee plus staff cost. Two do not: **Santa Clarita Holiday Market (56% ROI)** and **Camarillo Craft & Bites (12% ROI)**, which netted just $1,485 and $358.

**Why it matters.** The weak events drew only **70-87 orders a day vs 220-500** at the strong six, yet their booth fees ($900-$1,200) ate **14-24% of sales** compared with 3-4% at the big festivals. The summer months matter too: July-August alone are 28% of annual revenue, driven by the Long Beach and Ventura Summer Heat festivals.

**Recommendation.**
- Re-book Oxnard, Santa Paula, both Ventura events, Long Beach and Thousand Oaks.
- Do not renew Camarillo or Santa Clarita at current fees. Only accept them if the booth fee drops substantially or attendance data improves.
- Use the two freed weekends to apply to *larger* regional festivals. If both replacements only matched the weakest of the strong six (Oxnard, $8.6k net) that adds about **$15k**; at the median of the six (about $17k net) it adds about **$32k**. Either is an opportunity, not a forecast.

## 2. Storefront Tue-Thu: the crew costs more than the day earns

**The number.** Average storefront gross profit is **$568 on Tuesdays, $575 on Wednesdays and $653 on Thursdays**, versus **$660 of daily labor** for a 3-person, 10-hour crew. Friday and Saturday average **$1,004 and $1,118**. Tue/Wed run at only 72% of the storefront's average daily revenue.

**Why it matters.** Mid-week days lose money on labor alone before rent. At 31-37 orders a day (about 3-4 an hour outside the lunch rush) a third person is mostly waiting.

**Recommendation.** Run **2 staff Tue-Thu** and keep 3-4 on Fri-Sun. That is one fewer person x 10 hrs x $22 x 154 days = **~$33,900 a year**. Keep the third person on call for lunch if a rush appears. Re-check after 8 weeks using the hourly heatmap in the dashboard.

## 3. Event kitchens slow from 7.6 to 18.1 minutes once an hour passes 60 orders

**The number.** In event hours with 61+ orders, average prep time is **18.1 minutes vs 7.6 minutes** in quiet hours, and **83% of those orders take longer than 15 minutes**. **18% of all event orders** land in those peak hours. The same pattern shows at the night market (57% of orders over 15 min once an hour passes 40) and in the storefront above about 20 orders an hour.

**Why it matters.** Events are the most profitable channel, and the peak hours are where the money is. Long queues mean walk-aways and lost sales exactly when demand is highest.

**Recommendation.**
- Add a **second fry station** and pre-batch tenders for event lunch (11:30-1:30) and dinner (5-7pm) peaks.
- Test **QR pre-ordering** at the big summer events to smooth the queue.
- Track the target "under 12 minutes in peak hours" at each event.

## 4. Wings are the weakest margin (57%); drinks are the strongest (81%)

**The number.** Wings earn a **57.2%** margin vs **68.8%** for tenders and **66.8%** for sandwiches. Drinks earn **81.3%**, yet only **38% of orders include a drink**. Combos already carry **37% of total profit** (the Tender Combo alone is 14%).

**Why it matters.** A wing sale makes less profit per dollar than almost anything else on the menu. Drinks are nearly free profit that most guests are not buying.

**Recommendation.**
- **Raise wings and the Wing Combo by $1.** At flat volume that is about **$7,600** (7,576 units).
- Add a **drink prompt** at the register or in the delivery app (combo upgrade, "add a lemonade for $3"). Lifting drink attach by just 7 points is worth about **$5,500**.
- Lead promotions with the Tender Combo and Classic Sandwich, which together drive about 25% of total profit.

## 5. Medium and Hot are 57% of spiced orders, but events order hotter

**The number.** **Medium (29%) and Hot (28%)** dominate. Guests at events choose **Extra Hot or Reaper 27%** of the time, against **19%** at the storefront and **26%** on late-night orders. Reaper alone is only about 6% of units.

**Why it matters.** One sauce plan for every channel means either running out of hot sauces at events or wasting mild stock.

**Recommendation.**
- Build a **sauce prep sheet per channel**: heavier Extra Hot and Reaper for events and Fri/Sat late nights, lighter Mild and No Heat.
- Keep Reaper as a **small-batch challenge item** (for example with a $1 upcharge) instead of a full-volume staple.

## 6. Loyalty members repeat at 68% vs 48%, and most booth guests are never captured

**The number.** Loyalty members repeat **67.9%** of the time vs **48.1%** for non-members, place **4.9** orders vs **2.5**, and are worth **$137 vs $70** in revenue per customer, while using a discount on only 9% of orders. Members are 42% of tracked customers but **59% of their revenue**. Yet only **8% of event orders** and **22% of night-market orders** are linked to any customer.

**Why it matters.** The channels that bring in the most new faces are the ones where you capture the least about them. Customers typically come back after about **35 days**, so there is a clear window to bring them back.

**Recommendation.**
- Put a **QR sign-up** on every booth (free side or drink for joining) to lift capture above 30%.
- Send a "come back" offer around **day 21**, before the typical 35-day return.
- Track a simple KPI: *second order within 45 days*.

## 7. Friday 5-8pm is 25% of all orders. Protect it and test a second market.

**The number.** **25% of all orders** happen on Friday between 5 and 8pm, and Fri/Sat together are **63% of revenue**. The Friday night market contributes about **$1,373 per night** after staff and booth fees, vs **$79 per storefront day**. It earns **$103 of gross profit per labor hour** vs **$24** at the storefront.

**Why it matters.** The business is very dependent on a few peak windows. Underbuilding staff there costs real sales (see finding 3), while overstaffing other hours wastes money (finding 2).

**Recommendation.**
- Staff to the **full peak** on Friday 5-8pm (prep ahead, extra runner and fryer).
- Test a **second weekly market** (Saturday or Sunday midday) for 8 weeks. The economics suggest it beats adding storefront hours.

## 8. The Fri/Sat late-night window earns less than it costs to staff

**The number.** After 9pm the storefront brings in **$11,496 of gross profit over 104 nights** against about **$17,160 of labor** (3 staff x 2.5 hrs x $22). That is a **~$5,700** shortfall. Late-night guests do skew hotter (26% Extra Hot or Reaper), so this is a demand pocket, not a dead one.

**Recommendation.** Close at **10pm**, or run a **2-person skeleton crew** after 9pm. The window then roughly breaks even (2 staff x 2.5 hrs x $22 x 104 = $11,440 vs $11,496 gross profit), and you keep the audience for promotions.

---

## Limits of this analysis

- Only orders with a customer ID can be tracked for repeat behavior (35% of orders). Customers who already existed in January all land in the January cohort.
- Event ROI does not include travel, equipment, packaging or food waste, so true ROI is lower than shown, though the ranking of events would not change.
- Labor figures are assumptions, not payroll records; findings 2 and 8 depend on them most.
- This is a single year of synthetic data. Validate any change with an 8-week test before making it permanent.
