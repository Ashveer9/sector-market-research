# Executive Summary — Retail Sector Market Research

_Generated 2026-07-02 from 2009-12-01 → 2011-12-09 transactions._

## The market at a glance

| KPI | Value |
|---|---|
| Total revenue | £17,082,086 |
| Orders | 36,613 |
| Active customers | 5,853 |
| Products sold | 4,624 |
| Markets (countries) | 41 |
| Average order value | £467 |
| UK revenue share | 83.7% |
| Revenue from top 20% of customers | 77.2% |

## Customer segments (K-Means on RFM)

| Segment | Customers | Revenue share | Median spend |
|---|---|---|---|
| Champions | 1,186 | 73.9% | £4,908 |
| Loyal Customers | 1,452 | 16.3% | £1,453 |
| Potential / Recent | 1,246 | 6.1% | £720 |
| At-Risk / Dormant | 1,969 | 3.7% | £276 |

## Retention

- Average **month-1 retention**: **21.0%**
- Average **month-3 retention**: **21.7%**
- Average **month-6 retention**: **17.9%**

Retention drops sharply after the first month — a classic acquisition-heavy,
loyalty-light profile. Converting one-time buyers into a second purchase is the
single highest-leverage growth lever.

## Cross-sell opportunities (market-basket analysis)

Top product associations by lift (18 rules mined):

| If basket contains | …customer also buys | Lift | Confidence |
|---|---|---|---|
| SWEETHEART CERAMIC TRINKET BOX | STRAWBERRY CERAMIC TRINKET BOX | 13.9 | 68.9% |
| STRAWBERRY CERAMIC TRINKET BOX | SWEETHEART CERAMIC TRINKET BOX | 13.9 | 45.6% |
| WOODEN PICTURE FRAME WHITE FINISH | WOODEN FRAME ANTIQUE WHITE | 11.7 | 60.3% |
| WOODEN FRAME ANTIQUE WHITE | WOODEN PICTURE FRAME WHITE FINISH | 11.7 | 56.5% |
| LOVE BUILDING BLOCK WORD | HOME BUILDING BLOCK WORD | 10.0 | 52.8% |

## Churn prediction

A **gradient_boosting** trained on pre-cutoff behaviour predicts
which customers will lapse in the following 90 days:

- ROC-AUC: **0.810**, PR-AUC: **0.821**
- Recall on churners: **82.7%**, precision: **74.2%**
- Strongest churn signal: **recency**
- Baseline churn rate in the window: **56.5%**

## Recommendations

1. **Protect the top 20%.** A small share of customers drives the majority of
   revenue — fund a retention / VIP programme for *Champions* and *Loyal*
   segments before chasing new acquisition.
2. **Win the second order.** With steep month-1 churn, a triggered post-first-
   purchase journey (day 14/30 incentives) targets the biggest leak.
3. **Operationalise the churn model.** Score customers monthly; route high-risk,
   high-value accounts to proactive outreach. Recall of 82.7%
   means most future churners are catchable.
4. **Bundle on the rules above.** Use the highest-lift associations for
   cross-sell on product pages, in baskets and in email.
5. **Diversify beyond the UK.** 83.7% of revenue is
   single-market — the strongest EU markets are candidates for focused expansion.

---
*Figures referenced in this summary are in `reports/figures/`; full metrics in
`reports/metrics.json`.*
