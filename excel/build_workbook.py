"""
Build the Excel workbook for the Superstore profit analysis.

Writes excel/Superstore_Profit_Workbook.xlsx with 3 sheets:
  Data       the 9,994 order lines (real numbers and real dates, no locale problems)
  Summary    SUMIFS formulas by category, region, segment, sub-category and discount bucket
  Dashboard  KPIs, key findings and 4 charts

Run from the project root:  python excel/build_workbook.py
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "Sample - Superstore.csv"
OUT = ROOT / "excel" / "Superstore_Profit_Workbook.xlsx"

NAVY, GREEN, RED, GREY, HEADER = "1B3A6B", "009C3B", "C0392B", "9AA5B1", "00843D"

df = pd.read_csv(CSV, encoding="latin-1")
for c in ("Order Date", "Ship Date"):
    df[c] = pd.to_datetime(df[c], format="%m/%d/%Y")
n = len(df)
last = n + 1  # last data row in the Data sheet

wb = Workbook()

# ------------------------------------------------------------------ Data
ws = wb.active
ws.title = "Data"
cols = list(df.columns) + ["Discount Bucket"]
ws.append(cols)
for row in df.itertuples(index=False):
    ws.append([v.to_pydatetime() if hasattr(v, "to_pydatetime") else v for v in row])
col_of = {name: get_column_letter(i + 1) for i, name in enumerate(cols)}
for r in range(2, last + 1):
    ws[f"{col_of['Discount Bucket']}{r}"] = (
        f'=IF(T{r}=0,"1. no discount",IF(T{r}<=0.2,"2. 1-20%",IF(T{r}<=0.4,"3. 21-40%","4. over 40%")))')
    ws[f"C{r}"].number_format = ws[f"D{r}"].number_format = "yyyy-mm-dd"
for cell in ws[1]:
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=HEADER)
ws.freeze_panes = "A2"
for i, w in enumerate([8, 16, 12, 12, 14, 12, 22, 13, 14, 16, 16, 11, 9, 16, 16, 13, 40, 10, 9, 9, 10, 16]):
    ws.column_dimensions[get_column_letter(i + 1)].width = w


def rng(name):
    c = col_of[name]
    return f"Data!${c}$2:${c}${last}"


# ------------------------------------------------------------------ Summary
sm = wb.create_sheet("Summary")
blocks = {}


def add_block(start, title, dim, labels):
    sm.cell(start, 1, title).font = Font(bold=True, size=12, color=HEADER)
    for j, h in enumerate([dim, "Sales", "Profit", "Margin %", "Order lines"]):
        c = sm.cell(start + 1, j + 1, h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=HEADER)
    for i, lab in enumerate(labels):
        r = start + 2 + i
        sm.cell(r, 1, lab)
        sm.cell(r, 2, f"=SUMIFS({rng('Sales')},{rng(dim)},A{r})").number_format = "#,##0"
        sm.cell(r, 3, f"=SUMIFS({rng('Profit')},{rng(dim)},A{r})").number_format = "#,##0"
        sm.cell(r, 4, f"=IF(B{r}=0,0,C{r}/B{r})").number_format = "0.0%"
        sm.cell(r, 5, f"=COUNTIF({rng(dim)},A{r})").number_format = "#,##0"
    blocks[dim] = (start + 1, start + 2, start + 1 + len(labels))
    return start + len(labels) + 4


def order_by(dim, key):
    g = df.groupby(dim).agg(sales=("Sales", "sum"), profit=("Profit", "sum"))
    g["margin"] = g.profit / g.sales
    return list(g.sort_values(key).index)


row = 1
row = add_block(row, "By category (sorted by margin)", "Category", order_by("Category", "margin"))
row = add_block(row, "By region (sorted by margin)", "Region", order_by("Region", "margin"))
row = add_block(row, "By segment (sorted by profit)", "Segment", order_by("Segment", "profit"))
row = add_block(row, "By sub-category (sorted by profit)", "Sub-Category", order_by("Sub-Category", "profit"))
row = add_block(row, "By discount level", "Discount Bucket",
                ["1. no discount", "2. 1-20%", "3. 21-40%", "4. over 40%"])
for col, w in zip("ABCDE", (22, 14, 14, 12, 13)):
    sm.column_dimensions[col].width = w

# ------------------------------------------------------------------ Dashboard
db = wb.create_sheet("Dashboard", 0)
db.sheet_view.showGridLines = False
db["A1"] = "Superstore: where does the company lose money?"
db["A1"].font = Font(size=20, bold=True, color="FFFFFF")
for c in range(1, 21):
    db.cell(1, c).fill = PatternFill("solid", fgColor=HEADER)
db.row_dimensions[1].height = 34

kpis = [
    ("Sales ($)", f"=SUM({rng('Sales')})", "#,##0"),
    ("Profit ($)", f"=SUM({rng('Profit')})", "#,##0"),
    ("Profit margin", f"=SUM({rng('Profit')})/SUM({rng('Sales')})", "0.0%"),
    ("Order lines", f"=COUNTA(Data!$A$2:$A${last})", "#,##0"),
    ("Lines losing money", f'=COUNTIF({rng("Profit")},"<0")/COUNTA(Data!$A$2:$A${last})', "0.0%"),
]
for i, (label, formula, fmt) in enumerate(kpis):
    c0 = 1 + i * 4
    db.merge_cells(start_row=3, start_column=c0, end_row=3, end_column=c0 + 2)
    db.merge_cells(start_row=4, start_column=c0, end_row=4, end_column=c0 + 2)
    db.cell(3, c0, label).font = Font(size=10, color="555555")
    k = db.cell(4, c0, formula)
    k.number_format, k.font = fmt, Font(size=20, bold=True, color=NAVY)
    k.alignment = Alignment(horizontal="left")
    for r in (3, 4):
        for c in range(c0, c0 + 3):
            db.cell(r, c).fill = PatternFill("solid", fgColor="F2F5F3")

findings = [
    "Key findings",
    "1. Discounts above 20% lose money: the margin is -15% at 21-40% and -77% above 40%.",
    "2. Furniture sells as much as Office Supplies but its margin is only 2.5% (vs about 17%).",
    "3. Central is the least profitable region (7.9% margin) and gives the biggest discounts (24% on average).",
    "4. Tables, Bookcases and Supplies lose $22K in total. Segments are similar (11.5% to 14.0%).",
    "Recommendation: cap discounts at 20% and require manager approval above it.",
]
for i, t in enumerate(findings):
    c = db.cell(6 + i, 1, t)
    c.font = Font(size=12 if i == 0 else 11, bold=(i in (0, 5)), color=HEADER if i == 0 else "1C2733")


def bar(title, dim, col, anchor, horizontal=False, pct=False, bad_idx=(), good_color=NAVY, width=16, height=8.5):
    hdr, first, lastr = blocks[dim]
    ch = BarChart()
    ch.type = "bar" if horizontal else "col"
    ch.title = title
    ch.style = 10
    ch.legend = None
    ch.width, ch.height = width, height
    data = Reference(sm, min_col=col, min_row=hdr, max_row=lastr)
    cats = Reference(sm, min_col=1, min_row=first, max_row=lastr)
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    s = ch.series[0]
    s.graphicalProperties.solidFill = good_color
    s.invertIfNegative = False
    for idx in bad_idx:
        pt = DataPoint(idx=idx)
        pt.graphicalProperties.solidFill = RED
        s.dPt.append(pt)
    s.dLbls = DataLabelList()
    s.dLbls.showVal = True
    s.dLbls.showSerName = s.dLbls.showCatName = s.dLbls.showLegendKey = False
    ch.x_axis.delete = ch.y_axis.delete = False
    ch.y_axis.numFmt = "0%" if pct else "#,##0"
    ch.y_axis.majorGridlines = None
    db.add_chart(ch, anchor)


# bad_idx follow the sort order used in the Summary sheet (worst first)
bar("Margin by discount level", "Discount Bucket", 4, "A14", pct=True, bad_idx=(2, 3), good_color=GREEN)
bar("Margin by category", "Category", 4, "K14", pct=True, bad_idx=(0,))
bar("Profit by sub-category ($)", "Sub-Category", 3, "A32", horizontal=True, bad_idx=(0, 1, 2), height=11)
bar("Margin by region", "Region", 4, "K32", pct=True, bad_idx=(0,), height=11)

for c in range(1, 21):
    db.column_dimensions[get_column_letter(c)].width = 9

wb.save(OUT)
print("Saved", OUT)
