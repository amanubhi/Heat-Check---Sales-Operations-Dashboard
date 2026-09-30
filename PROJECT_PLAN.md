# Project Plan: Heat Check Sales & Operations Analysis

How this project was scoped, sequenced, risk-managed and closed. It is written the way a project coordinator would document an analytics engagement.

## 1. Charter

| | |
|---|---|
| **Sponsor / client** | The restaurant owner (a fictional stand-in modeled on a multi-channel small food business) |
| **Project lead / analyst** | Aman Ubhi |
| **Business question** | Which channels, menu items, spice levels and time slots drive profit, and where should staff, inventory and marketing focus next year? |
| **Success criteria** | (1) Every number reconciles across systems. (2) Findings are specific, quantified and stress-tested. (3) The owner can act on the recommendations without an analyst in the room. (4) Anyone can reproduce the work with one command. |
| **In scope** | Data creation and cleaning, SQL analysis, Excel and web dashboards, recommendations report, documentation |
| **Out of scope** | Real customer data, rent/utilities/owner-pay modeling, forecasting beyond scenario ranges, live POS integration |
| **Constraints** | Single analyst, free tools only (Python, SQLite, Excel, GitHub Pages), public repository |

## 2. Stakeholders and communication

| Stakeholder | Needs | How they were served |
|---|---|---|
| Owner (client) | Decisions, not charts; dollar impact; plain language | `reports/insights.md` written as number -> why it matters -> recommendation |
| Hiring managers / reviewers | Proof of method, quick to evaluate | Live dashboard, README case study, reproducible repo, tests |
| Future maintainers | Clear structure and assumptions | Commented code, `data/cleaning_log.md`, stated cost assumptions |

## 3. Work breakdown and deliverables

| Phase | Deliverable | "Done" means | Quality gate |
|---|---|---|---|
| 1. Data | `scripts/generate_data.py`, `data/raw/*.csv` | Seeded, realistic patterns and deliberately injected errors | Re-running gives identical files |
| 2. Cleaning | `scripts/clean_data.py`, `data/clean/`, `data/cleaning_log.md` | Every change logged with row counts | Integrity asserts pass (unique IDs, no orphans, revenue > 0) |
| 3. SQL | `sql/analysis.sql`, `outputs/sql_results/` | 15 commented queries, each answering a business question | Totals tie to the clean CSVs |
| 4. Stress test | `scripts/sensitivity_analysis.py`, `outputs/sensitivity/` | Labor, attendance, confidence intervals, scenarios | Each recommendation re-checked against the results |
| 5. Excel | `excel/HeatCheck_Dashboard.xlsx` | Live formulas, native charts, dropdown-driven Explorer sheet | Opened in Excel, recalculated, filters verified against pandas |
| 6. Web | `docs/index.html` | Filterable, mobile-responsive, loads fast (~160 KB) | Filter results match independent calculations; no console errors |
| 7. Reporting | `reports/insights.md`, README, this plan | Findings are quantified and caveated | Claims re-verified against source data |
| 8. Hardening | `tests/`, `.github/workflows/ci.yml` | 15 automated checks run on every push | CI green on Python 3.10 and 3.12 |

## 4. Risks and how they were managed

| Risk | Likelihood / impact | Response |
|---|---|---|
| Synthetic data makes findings look circular | High / High | Said so plainly everywhere; built a **real-data import path** (`REAL_DATA_GUIDE.md`) so the same pipeline runs on genuine exports |
| Cost assumptions drive conclusions | High / High | Stated in SQL and README; added sensitivity analysis and sliders; one finding was **narrowed** after testing |
| Numbers disagree between tools | Medium / High | Tests reconcile CSV, SQLite, Excel and web totals |
| Privacy leak if real data is used | Low / Severe | Real data lives only in git-ignored `private/`; anonymous IDs required |
| Dependency or version drift | Medium / Medium | Pinned minimum versions, tested on pandas 2.x and 3.x, CI matrix |
| Scope creep | Medium / Medium | Out-of-scope list above; "nice to have" items (pivots, video) tracked separately |

## 5. Decision log

| Decision | Why |
|---|---|
| Revenue excludes tips | Tips go to staff, not the business |
| Discounts spread across lines by value | Makes item profit add up to order profit |
| Negative quantities flipped to positive | No matching refund records, so treated as sign typos (logged) |
| Labor at $22/hr loaded, fixed crew sizes | Transparent and editable; conclusions tested from $16 to $28 |
| Sales tracked only with a customer ID | Walk-ups cannot be followed; limits are stated |
| Thursday left as a pilot, not a cut | Confidence interval straddles break-even |
| Static site on GitHub Pages | Free, fast, no server to maintain |

## 6. Lessons learned

1. **Stress-test before you recommend.** My first staffing recommendation (Tue-Thu, ~$33.9k) was narrowed to Tue-Wed (~$22.9k) once confidence intervals showed Thursday was break-even.
2. **Reconcile early.** Comparing totals across tools caught formula and range mistakes before they reached a chart.
3. **Write assumptions where the reader will see them.** Every dollar figure carries its assumptions.
4. **Design for the next dataset.** Building the real-data path exposed hidden assumptions (all months present, all channels present) that I then removed.
5. **Automate the boring checks.** Tests and CI turned "I think it still works" into evidence.

## 7. Status and next steps

**Status:** complete for the synthetic dataset.

**Next:** run it on real Rambo's-style sales exports; add pivot tables and slicers by hand in Excel (Python cannot create them); add a forecast once 12+ months of real data exist.
