"""
Python analysis: do discounts really cause the losses?

The SQL step showed that profit falls when discounts rise (an association).
Here we ask five sharper questions:
  Q1. How much margin does each extra point of discount cost, holding the product,
      region and segment constant? (regression with robust standard errors)
  Q2. Do discounts bring more volume (units per order line)?
  Q3. At which discount does each sub-category reach break-even?
  Q4. After accounting for discounts and products, is the Central region still worse?
  Q5. Why does Supplies lose money when it hardly uses big discounts?

Reads  : data/superstore.db  (built by load_data.py)
Writes : reports/tables/*.csv, reports/figures/07..10_*.png, reports/analysis_results.json

Run from the project root:  python src/discount_analysis.py
"""
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
TAB = ROOT / "reports" / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

NAVY, GREEN, RED, GREY = "#1B3A6B", "#009C3B", "#C0392B", "#9AA5B1"
plt.rcParams.update({
    "figure.figsize": (10, 5.2), "figure.dpi": 150, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 14, "axes.titleweight": "bold", "axes.titlelocation": "left", "font.size": 10.5,
})

with sqlite3.connect(f"file:{ROOT / 'data' / 'superstore.db'}?mode=ro", uri=True) as conn:
    df = pd.read_sql("SELECT * FROM orders", conn)

# Line-level margin, and the cost as a share of the full (undiscounted) price.
# cost = sales - profit ; full price = sales / (1 - discount)
df["margin"] = df.profit / df.sales
df["cost"] = df.sales - df.profit
df["cost_ratio"] = df.cost / (df.sales / (1 - df.discount))
res = {}

# ------------------------------------------------------------- Q1 regression
rows = []
for name, formula in [
    ("1. discount only", "margin ~ discount"),
    ("2. + sub-category", "margin ~ discount + C(sub_category)"),
    ("3. + region + segment", "margin ~ discount + C(sub_category) + C(region) + C(segment)"),
]:
    m = smf.ols(formula, data=df).fit(cov_type="HC3")
    lo, hi = m.conf_int().loc["discount"]
    rows.append({"model": name, "discount_coef": m.params["discount"], "ci_low": lo, "ci_high": hi,
                 "p_value": m.pvalues["discount"], "r_squared": m.rsquared})
q1 = pd.DataFrame(rows)
q1.to_csv(TAB / "discount_regression.csv", index=False)
best = q1.iloc[-1]
res["q1_effect_of_10_points_discount_on_margin"] = float(best.discount_coef * 0.1)
res["q1_ci_10_points"] = [float(best.ci_low * 0.1), float(best.ci_high * 0.1)]
res["q1_r_squared"] = float(best.r_squared)

# chart: margin (sales-weighted) at each discount level that exists in the data
by_d = (df.groupby("discount").agg(sales=("sales", "sum"), profit=("profit", "sum"), lines=("sales", "size")))
by_d["margin"] = by_d.profit / by_d.sales
by_d.to_csv(TAB / "margin_by_discount_value.csv")
fig, ax = plt.subplots()
x = np.arange(len(by_d))
ax.bar(x, by_d.margin, color=[GREEN if v >= 0 else RED for v in by_d.margin], width=.7)
ax.set_xticks(x)
ax.set_xticklabels([f"{int(d*100)}%" for d in by_d.index])
ax.axhline(0, color="#333", lw=.8)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
ax.set_xlabel("Discount")
ax.set_title("Margin at each discount level: it turns negative around 20-30%")
for i, (m, n) in enumerate(zip(by_d.margin, by_d.lines)):
    ax.text(i, m + (0.02 if m >= 0 else -0.02), f"{m:.0%}\n(n={n})", ha="center",
            va="bottom" if m >= 0 else "top", fontsize=8)
ax.set_ylim(by_d.margin.min() * 1.35, by_d.margin.max() * 1.8)
fig.savefig(FIG / "07_margin_by_discount.png"); plt.close(fig)

# ------------------------------------------------------------- Q2 volume
df["bucket"] = pd.cut(df.discount, [-0.01, 0, 0.2, 0.4, 1], labels=["no discount", "1-20%", "21-40%", "over 40%"])
vol = df.groupby("bucket", observed=True).agg(lines=("quantity", "size"), avg_units_per_line=("quantity", "mean"))
vol.to_csv(TAB / "volume_by_discount.csv")
mv = smf.ols("np.log(quantity) ~ discount + C(sub_category)", data=df).fit(cov_type="HC3")
res["q2_units_per_line"] = {str(k): float(v) for k, v in vol.avg_units_per_line.items()}
res["q2_log_quantity_coef"] = float(mv.params["discount"])
res["q2_p_value"] = float(mv.pvalues["discount"])
fig, ax = plt.subplots(figsize=(8, 4.8))
ax.bar(vol.index.astype(str), vol.avg_units_per_line, color=NAVY, width=.6)
ax.set_ylim(0, 5)
ax.set_ylabel("Average units per order line")
ax.set_title("Bigger discounts do not sell more units")
for i, v in enumerate(vol.avg_units_per_line):
    ax.text(i, v + .08, f"{v:.2f}", ha="center", fontweight="bold")
fig.savefig(FIG / "08_volume_vs_discount.png"); plt.close(fig)

# ------------------------------------------------------------- Q3 break-even discount
be = df.groupby("sub_category").agg(median_cost_ratio=("cost_ratio", "median"), lines=("sales", "size"),
                                    profit=("profit", "sum"))
be["breakeven_discount"] = 1 - be.median_cost_ratio
above = df.merge(be[["breakeven_discount"]], left_on="sub_category", right_index=True)
be["pct_lines_above_breakeven"] = (above.discount > above.breakeven_discount).groupby(above.sub_category).mean()
be = be.sort_values("breakeven_discount")
be.to_csv(TAB / "breakeven_discount.csv")
res["q3_lowest_breakeven"] = {k: float(v) for k, v in be.breakeven_discount.head(4).items()}
res["q3_n_below_cap"] = int((be.breakeven_discount <= 0.25).sum())
fig, ax = plt.subplots(figsize=(10, 6))
colors = [RED if v <= 0.25 else NAVY for v in be.breakeven_discount]
ax.barh(be.index, be.breakeven_discount, color=colors)
ax.axvline(0.20, color="#333", ls="--", lw=1)
ax.text(0.205, len(be) - 0.4, "20% cap", fontsize=9)
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
ax.set_xlabel("Break-even discount (above it, the line loses money)")
ax.set_title("How much discount can each sub-category afford?")
for i, v in enumerate(be.breakeven_discount):
    ax.text(v + .005, i, f"{v:.0%}", va="center", fontsize=9)
fig.savefig(FIG / "09_breakeven_discount.png"); plt.close(fig)

# ------------------------------------------------------------- Q4 Central gap
def gaps(formula):
    m = smf.ols(formula, data=df).fit(cov_type="HC3")
    return {k.split("[T.")[1][:-1]: float(v) for k, v in m.params.items() if "region" in k}

df["region"] = pd.Categorical(df.region, ["Central", "East", "South", "West"])
before = gaps("margin ~ C(region) + C(sub_category)")
after = gaps("margin ~ C(region) + C(sub_category) + discount")
cg = pd.DataFrame({"gap_vs_central_before": before, "gap_vs_central_after_discount": after})
cg["gap_reduction"] = 1 - cg.gap_vs_central_after_discount / cg.gap_vs_central_before
cg.to_csv(TAB / "central_gap.csv")
res["q4_gap_reduction"] = {k: float(v) for k, v in cg.gap_reduction.items()}
fig, ax = plt.subplots(figsize=(8, 4.8))
w, xs = 0.36, np.arange(len(cg))
ax.bar(xs - w / 2, cg.gap_vs_central_before, w, color=GREY, label="Accounting for sub-category only")
ax.bar(xs + w / 2, cg.gap_vs_central_after_discount, w, color=GREEN, label="Also accounting for discount")
ax.set_xticks(xs)
ax.set_xticklabels([f"{r} vs Central" for r in cg.index])
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
ax.set_ylabel("Average line margin advantage over Central")
ax.set_title("Most of Central's gap disappears once discounts are accounted for")
ax.legend(frameon=False)
for i, (b, a) in enumerate(zip(cg.gap_vs_central_before, cg.gap_vs_central_after_discount)):
    ax.text(i - w / 2, b + .005, f"{b:.0%}", ha="center", fontsize=9)
    ax.text(i + w / 2, a + .005, f"{a:.0%}", ha="center", fontsize=9)
fig.savefig(FIG / "10_central_gap.png"); plt.close(fig)

# ------------------------------------------------------------- Q5 Supplies
sup = df[df.sub_category == "Supplies"]
prod = sup.groupby("product_name").agg(lines=("sales", "size"), sales=("sales", "sum"), profit=("profit", "sum"),
                                       cost_ratio=("cost_ratio", "median"), avg_discount=("discount", "mean"))
prod = prod.sort_values("profit")
prod.to_csv(TAB / "supplies_products.csv")
losers = prod[prod.profit < 0]
res["q5_supplies_products_total"] = int(len(prod))
res["q5_supplies_products_losing"] = int(len(losers))
res["q5_worst_cost_ratio"] = float(losers.cost_ratio.head(2).mean())
res["q5_worst_two_share_of_losses"] = float(losers.profit.head(2).sum() / losers.profit.sum())
res["q5_worst_two"] = list(losers.index[:2])

(ROOT / "reports" / "analysis_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
print(q1.round(3).to_string(index=False))
print(json.dumps(res, indent=2))
