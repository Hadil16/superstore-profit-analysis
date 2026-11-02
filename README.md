# Superstore Profit Analysis: Where Does the Company Lose Money?

**A retailer sold $2.3M over four years, but where does the profit leak?**
An analysis of 9,994 order lines (2014-2017) with SQL and an Excel / Google Sheets dashboard. The main finding: **discounts above 20% lose money**.

![Dashboard](reports/figures/dashboard_google_sheets.png)

## Key findings

| # | Finding | Evidence |
|---|---|---|
| 1 | **Discounts above 20% lose money.** | Margin is **+29.5%** with no discount, +11.9% at 1-20%, **-15.3%** at 21-40% and **-77.4%** above 40%. The 1,393 lines above 20% (14% of all lines) lost **$135,376**. |
| 2 | **Furniture sells a lot but earns little.** | Furniture sales are $742K (more than Office Supplies at $719K) but its margin is **2.5%**, against 17.0% for Office Supplies and 17.4% for Technology. |
| 3 | **Central is the weakest region, and it discounts the most.** | Central margin is **7.9%** with a 24.0% average discount. West has the best margin (14.9%) with the lowest average discount (10.9%). |
| 4 | **Three sub-categories lose money.** | Tables (-$17,725), Bookcases (-$3,473) and Supplies (-$1,189), **-$22,387** in total. 55% of Tables lines carry a discount above 20%. |
| 5 | **Customer segments are similar.** | Margins range from 11.5% (Consumer) to 14.0% (Home Office), a small gap compared with the discount effect. |

Overall: sales $2,297,201, profit $286,397, margin 12.5%. **18.7% of order lines lose money.**

## Recommendations

1. **Cap discounts at 20%** and require manager approval above it. This is the biggest and clearest lever.
2. **Review the Tables pricing and discount policy**: it is the largest single loss and over half of its lines are heavily discounted.
3. **Investigate Supplies separately.** It loses money with almost no large discounts (0% of its lines are above 20%), so the cause is something else, such as cost or pricing.
4. **Review discount rules in the Central region**, where average discounts are more than double those of the West.

## Limitations (what this analysis cannot say)

- **Association is not causation.** Lines with big discounts may also be different products, so discounts are the strongest suspect, not a proven cause.
- This is a **public sample dataset**, so the findings illustrate a method rather than describe a real company.
- Profit is taken as given. The data has no detail on costs, shipping or returns.
- Four years only (2014-2017), one country, amounts in US dollars.

## How the analysis was done

| Stage | What was done | Where |
|---|---|---|
| Business understanding | One question: where is profit lost? Four sub-questions (category, region, discount, segment). | this README |
| Data audit | 9,994 rows, 21 columns, **0 missing values**, 0 duplicate IDs. Two traps found and fixed: the file is **not UTF-8** (read as latin-1) and dates are in **US format** (month/day/year). | [`load_data.py`](load_data.py) |
| SQL analysis | `GROUP BY`, `CASE WHEN` discount buckets, `HAVING`, margin calculation | [`sql/analysis.sql`](sql/analysis.sql) |
| Excel / Google Sheets | 3 sheets: data, `SUMIFS` summary, dashboard with 4 charts | [`excel/`](excel/) |
| Cross-check | All 31 summary rows were checked against the SQL results: no difference | [`excel/build_workbook.py`](excel/build_workbook.py) |
| Insights | Findings, recommendations and limitations | this README, [`reports/executive_summary.md`](reports/executive_summary.md) |

### A lesson from this project
When the first spreadsheet import was done in a French-locale Google Sheet, the decimal points were read as text and the totals were wrong (billions instead of $286K). The mistake was caught only because the result was **compared with SQL**. Always cross-check an analysis with a second tool.

## Reproduce it

1. Download the data from [Kaggle: Superstore Dataset](https://www.kaggle.com/datasets/vivek468/superstore-dataset-final) and put `Sample - Superstore.csv` in `data/`.
2. Install the libraries: `pip install -r requirements.txt`
3. Run:

```bash
python load_data.py              # CSV -> data/superstore.db (SQLite)
python excel/build_workbook.py   # regenerates the Excel workbook
```

Then run the queries of `sql/analysis.sql` in any SQLite tool (for example DB Browser for SQLite) against `data/superstore.db`.

## Project structure

```
02-superstore-profit-analysis/
├── load_data.py          CSV -> SQLite (handles encoding and date format)
├── sql/analysis.sql      the business questions in SQL
├── excel/                Excel workbook (data, formulas, dashboard) and its build script
├── reports/              executive summary and dashboard image
└── requirements.txt
```

**Tools:** SQL (SQLite), Excel / Google Sheets (SUMIFS, charts), Python (data loading).

**Author:** Hadil Ziane, MSc Statistics & Economic Foresight (ENSSEA).
