"""
Generate the Power BI project (PBIP format) for the Superstore profit dashboard.

Writes powerbi/superstore_dashboard.pbip + .SemanticModel/ + .Report/
Open superstore_dashboard.pbip in Power BI Desktop, click Refresh now (once per banner, and wait),
then File > Save as .pbix.

Data sources (parameters DataFolder and TablesFolder, edit them if you move the project):
  data/Sample - Superstore.csv              the order lines
  reports/tables/breakeven_discount.csv     break-even discount per sub-category (src/discount_analysis.py)

Run from the project root:  python powerbi/build_pbip.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NAME = "superstore_dashboard"
SM = PBI / f"{NAME}.SemanticModel"
RP = PBI / f"{NAME}.Report"
DATA_DIR = str(ROOT / "data")
TABLES_DIR = str(ROOT / "reports" / "tables")

T = "\t"
# Superstore is a fictional company (Tableau sample data), so it has no brand colors.
# The identity is a design choice: deep slate header, blue as the main data color,
# orange as the accent, and red reserved for losses.
NAVY, TEAL, RED, AMBER, GREY = "#1F2A44", "#4E79A7", "#C0392B", "#F28E2B", "#9AA5B1"


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def wj(path, obj):
    w(path, json.dumps(obj, indent=2))


# =====================================================================
# SEMANTIC MODEL (TMDL)
# =====================================================================
def col(name, dtype, source=None, fmt=None, summarize="none"):
    n = f"'{name}'" if " " in name or "-" in name else name
    s = [f"{T}column {n}", f"{T}{T}dataType: {dtype}"]
    if fmt:
        s.append(f"{T}{T}formatString: {fmt}")
    s.append(f"{T}{T}summarizeBy: {summarize}")
    s.append(f"{T}{T}sourceColumn: {source or name}")
    return "\n".join(s) + "\n"


def calc_col(name, dtype, dax):
    lines = dax.strip().splitlines()
    body = f"{T}column '{name}' = ```\n" + "\n".join(f"{T}{T}{T}{l}" for l in lines) + f"\n{T}{T}{T}```\n"
    return body + f"{T}{T}dataType: {dtype}\n{T}{T}summarizeBy: none\n{T}{T}isDataTypeInferred\n"


def measure(name, dax, fmt=None, folder=None):
    n = f"'{name}'" if " " in name else name
    lines = dax.strip().splitlines()
    if len(lines) == 1:
        s = f"{T}measure {n} = {lines[0]}\n"
    else:
        s = f"{T}measure {n} = ```\n" + "\n".join(f"{T}{T}{T}{l}" for l in lines) + f"\n{T}{T}{T}```\n"
    if fmt:
        s += f"{T}{T}formatString: {fmt}\n"
    if folder:
        s += f"{T}{T}displayFolder: {folder}\n"
    return s


def m_partition(table, m_code):
    lines = m_code.strip().splitlines()
    return (f"{T}partition {table} = m\n{T}{T}mode: import\n{T}{T}source = ```\n"
            + "\n".join(f"{T}{T}{T}{l}" for l in lines) + f"\n{T}{T}{T}```\n")


# ---- orders table: renamed to snake_case in Power Query
ORDER_COLS = [  # (csv name, model name, M type, TMDL type, format)
    ("Order ID", "order_id", "type text", "string", None),
    ("Order Date", "order_date", "type date", "dateTime", "dd/MM/yyyy"),
    ("Segment", "segment", "type text", "string", None),
    ("State", "state", "type text", "string", None),
    ("Region", "region", "type text", "string", None),
    ("Category", "category", "type text", "string", None),
    ("Sub-Category", "sub_category", "type text", "string", None),
    ("Product Name", "product_name", "type text", "string", None),
    ("Sales", "sales", "type number", "double", "#,0.00"),
    ("Quantity", "quantity", "Int64.Type", "int64", "0"),
    ("Discount", "discount", "type number", "double", "0%"),
    ("Profit", "profit", "type number", "double", "#,0.00"),
]
csv_names = ", ".join(f'"{c[0]}"' for c in ORDER_COLS)
renames = ", ".join(f'{{"{c[0]}", "{c[1]}"}}' for c in ORDER_COLS)
types = ", ".join(f'{{"{c[1]}", {c[2]}}}' for c in ORDER_COLS)
orders_m = f"""let
    Source = Csv.Document(File.Contents(DataFolder & "\\Sample - Superstore.csv"), [Delimiter = ",", Encoding = 1252, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Kept = Table.SelectColumns(Promoted, {{{csv_names}}}),
    Renamed = Table.RenameColumns(Kept, {{{renames}}}),
    Typed = Table.TransformColumnTypes(Renamed, {{{types}}}, "en-US")
in
    Typed"""

orders_tmdl = "table orders\n\n"
for _, m_name, _, dt, fmt in ORDER_COLS:
    orders_tmdl += col(m_name, dt, fmt=fmt) + "\n"
orders_tmdl += calc_col("Discount Bucket", "string", """SWITCH (
    TRUE (),
    orders[discount] = 0, "1. no discount",
    orders[discount] <= 0.2, "2. 1-20%",
    orders[discount] <= 0.4, "3. 21-40%",
    "4. over 40%"
)""") + "\n"
orders_tmdl += m_partition("orders", orders_m)

# ---- break-even table (written by src/discount_analysis.py)
BE_COLS = [("sub_category", "type text", "string", None), ("median_cost_ratio", "type number", "double", "0.000"),
           ("lines", "type number", "double", "#,0"), ("profit", "type number", "double", "#,0"),
           ("breakeven_discount", "type number", "double", "0%"),
           ("pct_lines_above_breakeven", "type number", "double", "0%")]
be_types = ", ".join(f'{{"{c[0]}", {c[1]}}}' for c in BE_COLS)
be_m = f"""let
    Source = Csv.Document(File.Contents(TablesFolder & "\\breakeven_discount.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{{be_types}}}, "en-US")
in
    Typed"""
be_tmdl = "table breakeven\n\n"
for name, _, dt, fmt in BE_COLS:
    be_tmdl += col(name, dt, fmt=fmt) + "\n"
be_tmdl += m_partition("breakeven", be_m)

calendar_tmdl = f"""table Calendar
{T}dataCategory: Time

{col("Date", "dateTime", source="[Date]", fmt="dd/MM/yyyy").replace(f"{T}{T}summarizeBy: none", f"{T}{T}isKey{chr(10)}{T}{T}summarizeBy: none")}
{col("Year", "int64", source="[Year]")}
{col("Quarter", "string", source="[Quarter]")}
{T}partition Calendar = calculated
{T}{T}mode: import
{T}{T}source = ```
{T}{T}{T}ADDCOLUMNS (
{T}{T}{T}    CALENDAR ( DATE ( 2014, 1, 1 ), DATE ( 2017, 12, 31 ) ),
{T}{T}{T}    "Year", YEAR ( [Date] ),
{T}{T}{T}    "Quarter", YEAR ( [Date] ) & " Q" & QUARTER ( [Date] )
{T}{T}{T})
{T}{T}{T}```
"""

M = []
M.append(measure("Sales", "SUM ( orders[sales] )", "#,0", "Core KPIs"))
M.append(measure("Profit", "SUM ( orders[profit] )", "#,0", "Core KPIs"))
M.append(measure("Profit Margin", "DIVIDE ( [Profit], [Sales] )", "0.0%", "Core KPIs"))
M.append(measure("Orders", "DISTINCTCOUNT ( orders[order_id] )", "#,0", "Core KPIs"))
M.append(measure("Order Lines", "COUNTROWS ( orders )", "#,0", "Core KPIs"))
M.append(measure("Avg Discount", "AVERAGE ( orders[discount] )", "0.0%", "Discounts"))
M.append(measure("Avg Units per Line", "AVERAGE ( orders[quantity] )", "0.00", "Discounts"))
M.append(measure("Loss-making Lines %", """DIVIDE (
    CALCULATE ( COUNTROWS ( orders ), orders[profit] < 0 ),
    COUNTROWS ( orders )
)""", "0.0%", "Discounts"))
M.append(measure("Lines Over 20% Discount %", """DIVIDE (
    CALCULATE ( COUNTROWS ( orders ), orders[discount] > 0.2 ),
    COUNTROWS ( orders )
)""", "0.0%", "Discounts"))
M.append(measure("Profit on Lines Over 20% Discount", "CALCULATE ( [Profit], orders[discount] > 0.2 )", "#,0", "Discounts"))
M.append(measure("Break-even Discount", "MAX ( breakeven[breakeven_discount] )", "0%", "Discounts"))
# two-series trick: positive values in series 1 (teal), negative values in series 2 (red)
M.append(measure("Margin Positive", "VAR m = [Profit Margin] RETURN IF ( m >= 0, m )", "0.0%", "Chart helpers"))
M.append(measure("Margin Negative", "VAR m = [Profit Margin] RETURN IF ( m < 0, m )", "0.0%", "Chart helpers"))
M.append(measure("Profit Positive", "VAR p = [Profit] RETURN IF ( p >= 0, p )", "#,0", "Chart helpers"))
M.append(measure("Profit Negative", "VAR p = [Profit] RETURN IF ( p < 0, p )", "#,0", "Chart helpers"))

measures_tmdl = (f"table _Measures\n\n{T}column Dummy\n{T}{T}dataType: int64\n{T}{T}isHidden\n{T}{T}summarizeBy: none\n"
                 f"{T}{T}sourceColumn: [Dummy]\n\n" + "\n".join(M) +
                 f"\n{T}partition _Measures = calculated\n{T}{T}mode: import\n{T}{T}source = ROW ( \"Dummy\", 1 )\n")

expressions_tmdl = (
    f'expression DataFolder = "{DATA_DIR}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n\n'
    f'expression TablesFolder = "{TABLES_DIR}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n')

relationships_tmdl = """relationship orders_to_calendar
	fromColumn: orders.order_date
	toColumn: Calendar.Date

relationship orders_to_breakeven
	fromColumn: orders.sub_category
	toColumn: breakeven.sub_category
"""

model_tmdl = """model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
	discourageImplicitMeasures
	sourceQueryCulture: en-US

ref table orders
ref table breakeven
ref table Calendar
ref table _Measures
"""

for p in (SM, RP):
    if p.exists():
        shutil.rmtree(p)
wj(SM / "definition.pbism", {"version": "4.0", "settings": {}})
w(SM / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
w(SM / "definition" / "model.tmdl", model_tmdl)
w(SM / "definition" / "expressions.tmdl", expressions_tmdl)
w(SM / "definition" / "relationships.tmdl", relationships_tmdl)
w(SM / "definition" / "tables" / "orders.tmdl", orders_tmdl)
w(SM / "definition" / "tables" / "breakeven.tmdl", be_tmdl)
w(SM / "definition" / "tables" / "Calendar.tmdl", calendar_tmdl)
w(SM / "definition" / "tables" / "_Measures.tmdl", measures_tmdl)

# =====================================================================
# REPORT (PBIR)
# =====================================================================
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def solid(color):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{color}'"}}}}}


def fld(table, prop, kind="Column"):
    return {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def proj(table, prop, kind="Column", active=None):
    d = {"field": fld(table, prop, kind), "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}
    if active:
        d["active"] = True
    return d


def title(text):
    return {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{text}'"),
                                      "fontSize": lit("12D"), "bold": lit("true")}}]}


def visual(name, x, y, w_, h, vtype, query=None, objects=None, container=None, z=1000):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if query:
        v["query"] = query
    if objects:
        v["objects"] = objects
    d = {"$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json", "name": name,
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w_, "tabOrder": z}, "visual": v}
    if container:
        d["visual"]["visualContainerObjects"] = container
    return d


def card(name, x, measure_name, label, units=None, precision=None):
    props = {"fontSize": lit("24D")}
    if units is not None:
        props["labelDisplayUnits"] = lit(f"{units}D")
        if precision is not None:
            props["labelPrecision"] = lit(f"{precision}L")
    objects = {"labels": [{"properties": props}], "categoryLabels": [{"properties": {"show": lit("false")}}]}
    return visual(name, x, 70, 165, 80, "card",
                  {"queryState": {"Values": {"projections": [proj("_Measures", measure_name, "Measure")]}}},
                  objects=objects,
                  container={"title": [{"properties": {"show": lit("true"), "text": lit(f"'{label}'"),
                                                       "fontSize": lit("10D")}}]})


def chart(name, x, y, w_, h, vtype, cat, vals, ttl, sort=None, y2=None, labels=False, pct=False, colors=None, dec=None):
    qs = {"Category": {"projections": [proj(*cat, active=True)]},
          "Y": {"projections": [proj(t, p, "Measure") for t, p in vals]}}
    if y2:
        qs["Y2"] = {"projections": [proj(t, p, "Measure") for t, p in y2]}
    q = {"queryState": qs}
    if sort:
        kind, ref, direction = sort
        q["sortDefinition"] = {"sort": [{"field": fld(*ref, kind) if kind == "Column" else fld(ref[0], ref[1], "Measure"),
                                         "direction": direction}]}
    no_title = {"properties": {"showAxisTitle": lit("false")}}
    objects = {"categoryAxis": [no_title], "valueAxis": [no_title]}
    if labels:
        precision = dec if dec is not None else (1 if pct else 0)
        objects["labels"] = [{"properties": {"show": lit("true"), "labelPrecision": lit(f"{precision}L")}}]
    if colors:  # explicit series colors: {measure name: hex}
        objects["dataPoint"] = [{"properties": {"fill": solid(c)}, "selector": {"metadata": f"_Measures.{m}"}}
                                for m, c in colors.items()]
    return visual(name, x, y, w_, h, vtype, q, objects=objects, container=title(ttl))


def textbox(name, x, y, w_, h, paragraphs):
    paras = []
    for text, bold, size, *rest in paragraphs:
        run = {"value": text, "textStyle": {"fontSize": f"{size}pt"}}
        if rest:
            run["textStyle"]["color"] = rest[0]
        if bold:
            run["textStyle"]["fontWeight"] = "bold"
        paras.append({"textRuns": [run]})
    return visual(name, x, y, w_, h, "textbox", objects={"general": [{"properties": {"paragraphs": paras}}]})


def slicer(name, x, y, w_, h, table, prop, ttl):
    q = {"queryState": {"Values": {"projections": [proj(table, prop, active=True)]}}}
    return visual(name, x, y, w_, h, "slicer", q,
                  objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}, container=title(ttl))


def table(name, x, y, w_, h, cols, ttl, sort=None):
    q = {"queryState": {"Values": {"projections": [proj(t, p, k) for t, p, k in cols]}}}
    if sort:
        t, p, k, direction = sort
        q["sortDefinition"] = {"sort": [{"field": fld(t, p, k), "direction": direction}]}
    return visual(name, x, y, w_, h, "tableEx", q, container=title(ttl),
                  objects={"total": [{"properties": {"totals": lit("false")}}]})


def nav(name):
    selected = {"properties": {"fillColor": solid(AMBER)}, "selector": {"id": "selected"}}
    selected_text = {"properties": {"fontColor": solid(NAVY)}, "selector": {"id": "selected"}}
    return visual(name, 500, 8, 450, 44, "pageNavigator", objects={"fill": [selected], "text": [selected_text]})


def band(name):
    objs = {"shape": [{"properties": {"tileShape": lit("'rectangle'")}}],
            "fill": [{"properties": {"fillColor": solid(NAVY)}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit("false")}}]}
    return visual(name, 0, 0, 1280, 64, "shape", objects=objs, z=0)


def clear_button(name):
    objs = {"text": [{"properties": {"show": lit("true"), "text": lit("'Clear filters'"),
                                     "fontColor": solid("#FFFFFF")}, "selector": {"id": "default"}}],
            "icon": [{"properties": {"shapeType": lit("'blank'")}, "selector": {"id": "default"}}]}
    link = {"visualLink": [{"properties": {"show": lit("true"), "type": lit("'ClearAllSlicers'")}}]}
    return visual(name, 958, 8, 110, 44, "actionButton", objects=objs, container=link)


def title_box(name, text):
    return textbox(name, 20, 0, 470, 46, [(text, True, 18, "#FFFFFF")])


def subtitle_box(name):
    return textbox(name, 20, 38, 470, 26,
                   [("US retail chain (sample data)  |  Orders 2014-2017  |  4 US regions",
                     False, 9, "#C9D3E6")])


def accent_stripe(name):
    objs = {"shape": [{"properties": {"tileShape": lit("'rectangle'")}}],
            "fill": [{"properties": {"fillColor": solid(AMBER)}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit("false")}}]}
    return visual(name, 0, 64, 1280, 4, "shape", objects=objs, z=1)


def cards(names_and_specs):
    return [card(n, 20 + i * 172, m, lab, **kw) for i, (n, m, lab, kw) in enumerate(names_and_specs)]


def TOP(t, n, year_slicer=True):
    items = [title_box(f"title{n}", t), subtitle_box(f"subtitle{n}"), accent_stripe(f"stripe{n}"),
             nav(f"nav{n}"), clear_button(f"clear{n}")]
    if year_slicer:
        items.append(slicer(f"slicer_year{n}", 1075, 8, 185, 50, "Calendar", "Year", "Year"))
    return items

# ---------------- page 1: overview
page1 = TOP("Superstore: where is profit lost?", 1) + cards([
    ("c_sales", "Sales", "Sales ($)", dict(units=1000000, precision=2)),
    ("c_profit", "Profit", "Profit ($)", dict(units=1000, precision=0)),
    ("c_margin", "Profit Margin", "Profit margin", {}),
    ("c_orders", "Orders", "Orders", dict(units=1)),
    ("c_loss", "Loss-making Lines %", "Order lines losing money", {}),
    ("c_disc", "Avg Discount", "Average discount", {}),
]) + [
    slicer("slicer_region1", 1055, 70, 205, 80, "orders", "region", "Region"),
    chart("ch_quarter", 20, 160, 620, 270, "lineClusteredColumnComboChart", ("Calendar", "Quarter", "Column"),
          [("_Measures", "Sales")], "Sales and profit margin by quarter", y2=[("_Measures", "Profit Margin")]),
    chart("ch_category", 660, 160, 600, 270, "columnChart", ("orders", "category", "Column"),
          [("_Measures", "Margin Positive"), ("_Measures", "Margin Negative")], "Profit margin by category",
          labels=True, pct=True),
    chart("ch_region", 20, 445, 620, 265, "barChart", ("orders", "region", "Column"),
          [("_Measures", "Margin Positive"), ("_Measures", "Margin Negative")], "Profit margin by region",
          labels=True, pct=True),
    textbox("findings1", 660, 445, 600, 265, [
        ("Key findings", True, 14),
        ("1. Sales of $2.30M and profit of $286K over four years (12.5% margin). 18.7% of order lines lose money.", False, 11),
        ("2. Furniture earns only a 2.5% margin (17% for the other two categories).", False, 11),
        ("3. Central is the weakest region at 7.9%, and it gives the biggest discounts.", False, 11),
        ("4. Discounts above 20% lose money: see the Discounts page.", False, 11),
    ]),
]

# ---------------- page 2: discounts
page2 = TOP("Discounts destroy profit", 2) + cards([
    ("d_over", "Lines Over 20% Discount %", "Lines over 20% discount", {}),
    ("d_lost", "Profit on Lines Over 20% Discount", "Profit on those lines ($)", dict(units=1000, precision=0)),
    ("d_units", "Avg Units per Line", "Avg units per line", {}),
    ("d_avg", "Avg Discount", "Average discount", {}),
    ("d_loss", "Loss-making Lines %", "Order lines losing money", {}),
]) + [
    chart("ch_bucket", 20, 160, 620, 270, "columnChart", ("orders", "Discount Bucket", "Column"),
          [("_Measures", "Margin Positive"), ("_Measures", "Margin Negative")],
          "Profit margin by discount level", labels=True, pct=True),
    chart("ch_units", 20, 445, 620, 265, "clusteredColumnChart", ("orders", "Discount Bucket", "Column"),
          [("_Measures", "Avg Units per Line")], "Units per order line: discounts do not sell more", labels=True, dec=2),
    chart("ch_breakeven", 660, 160, 600, 410, "clusteredBarChart", ("breakeven", "sub_category", "Column"),
          [("_Measures", "Break-even Discount"), ("_Measures", "Avg Discount")],
          "Average discount vs break-even discount, by sub-category", labels=True, pct=True,
          sort=("Measure", ("_Measures", "Break-even Discount"), "Ascending")),
    textbox("findings2", 660, 580, 600, 130, [
        ("What this shows", True, 14),
        ("Where the average discount is above the break-even discount, the sub-category loses money (Tables: 26% vs 20%).", False, 11),
        ("Units per line stay at about 3.8 whatever the discount.", False, 11),
    ]),
]

# ---------------- page 3: products and regions
page3 = TOP("Products and regions", 3) + [
    chart("ch_subcat", 20, 70, 620, 640, "barChart", ("breakeven", "sub_category", "Column"),
          [("_Measures", "Profit Positive"), ("_Measures", "Profit Negative")], "Profit by sub-category ($)",
          labels=True, sort=("Measure", ("_Measures", "Profit Positive"), "Descending")),
    table("t_region", 660, 70, 600, 190,
          [("orders", "region", "Column"), ("_Measures", "Sales", "Measure"), ("_Measures", "Profit", "Measure"),
           ("_Measures", "Profit Margin", "Measure"), ("_Measures", "Avg Discount", "Measure")],
          "Regions: sales, profit and discounts"),
    table("t_losses", 660, 275, 600, 435,
          [("orders", "sub_category", "Column"), ("orders", "discount", "Column"),
           ("orders", "sales", "Column"), ("orders", "profit", "Column"), ("orders", "product_name", "Column")],
          "Biggest losses by order line (react to the filters)", sort=("orders", "profit", "Column", "Ascending")),
]

# ---------------- page 4: about the company and the data
def info_box(name, x, y, w_, h, heading, lines):
    paras = [(heading, True, 17)]
    for t in lines:
        paras += [(" ", False, 4), (t, False, 12)]  # a small blank line between items
    return textbox(name, x, y, w_, h, paras)


page4 = TOP("About the company and the data", 4, year_slicer=False) + [
    info_box("about_company", 20, 82, 620, 290, "The company", [
        "Superstore is a fictional US retail chain, taken from Tableau's public sample data. It is not a real company, so it has no brand colors: the colors of this report are a design choice.",
        "It sells furniture, office supplies and technology to consumers, corporate clients and home offices.",
        "Four US regions: Central, East, South and West. Orders from January 2014 to December 2017.",
    ]),
    info_box("about_data", 660, 82, 600, 290, "The data in numbers", [
        "9,994 order lines in 5,009 orders (2 lines per order on average)",
        "793 customers, 1,862 products, 17 sub-categories, 49 states",
        "Average order value: $459",
        "Sales $2.30M, profit $286K, margin 12.5%",
        "From 2014 to 2017: sales +51%, profit +89%",
    ]),
    info_box("about_defs", 20, 388, 620, 322, "Definitions", [
        "Profit margin = profit / sales.",
        "Order line = one product in one order (the unit of analysis).",
        "Loss-making line = an order line with a negative profit.",
        "Break-even discount = the discount at which a sub-category's margin reaches zero. It is estimated from the median cost as a share of the full price, with cost = sales - profit.",
    ]),
    info_box("about_method", 660, 388, 600, 322, "Method and limits", [
        "SQL answers the business questions, Python measures the discount effect (regression), Power BI shows the results, and an Excel / Google Sheets workbook gives a second check.",
        "Association is not causation: discounts are the strongest suspect for the losses, not a proven cause.",
        "Sample data: the results illustrate a method, not a real company. Profit has no cost detail.",
        "Source: Tableau Superstore sample data (Kaggle copy).",
    ]),
]

# the top band on pages 1 and 2 starts at y=0 with the title; page 3 charts start below the band
BORDER ={"border": [{"properties": {"show": lit("true"), "color": lit("'#D6DEE6'"), "radius": lit("10D")}}],
          "background": [{"properties": {"show": lit("true"), "color": solid("#FFFFFF"), "transparency": lit("0D")}}]}
for pg, band_name in ((page1, "band1"), (page2, "band2"), (page3, "band3"), (page4, "band4")):
    pg.insert(0, band(band_name))
    for v in pg:
        if v["name"].startswith(("title", "subtitle")):
            v["visual"].setdefault("visualContainerObjects", {})["background"] = [{"properties": {"show": lit("false")}}]
        elif v["visual"]["visualType"] not in ("pageNavigator", "actionButton", "shape"):
            v["visual"].setdefault("visualContainerObjects", {}).update(BORDER)

# page 3 content starts under the band
for v in page3:
    if v["name"] in ("ch_subcat", "t_region", "t_losses"):
        v["position"]["y"] += 0

VERSION_AT_IMPORT = {"visual": "1.8.50", "report": "2.0.50", "page": "1.3.50"}
wj(PBI / f"{NAME}.pbip", {"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                          "settings": {"enableAutoRecovery": True}})
wj(RP / "definition.pbir", {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
wj(RP / "definition" / "version.json", {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
wj(RP / "StaticResources" / "RegisteredResources" / "SuperstoreTheme.json", {
    "name": "SuperstoreTheme",
    "dataColors": [TEAL, RED, NAVY, AMBER, GREY, "#4A78B5", "#6FBF8B", "#E8833A"],
    "background": "#FFFFFF", "foreground": "#1C2733", "tableAccent": NAVY})
wj(RP / "definition" / "report.json", {
    "$schema": f"{SCHEMA}/report/3.0.0/schema.json",
    "themeCollection": {
        "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": VERSION_AT_IMPORT, "type": "SharedResources"},
        "customTheme": {"name": "SuperstoreTheme.json", "reportVersionAtImport": VERSION_AT_IMPORT,
                        "type": "RegisteredResources"}},
    "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                          "items": [{"name": "SuperstoreTheme.json", "path": "SuperstoreTheme.json", "type": "CustomTheme"}]}],
    "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                 "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                 "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})
wj(RP / "definition" / "pages" / "pages.json", {"$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
                                                "pageOrder": ["page_overview", "page_discounts", "page_products", "page_about"],
                                                "activePageName": "page_overview"})
for pname, disp, visuals in (("page_overview", "Overview", page1), ("page_discounts", "Discounts", page2),
                             ("page_products", "Products & Regions", page3), ("page_about", "About", page4)):
    wj(RP / "definition" / "pages" / pname / "page.json",
       {"$schema": f"{SCHEMA}/page/2.0.0/schema.json", "name": pname, "displayName": disp,
        "displayOption": "FitToPage", "height": 720, "width": 1280,
        "objects": {"background": [{"properties": {"color": solid("#F2F5F7"), "transparency": lit("0D")}}]}})
    for v in visuals:
        wj(RP / "definition" / "pages" / pname / "visuals" / v["name"] / "visual.json", v)

w(PBI / ".gitignore", ".pbi/\n*.pbix.bak\n")
print("Built", PBI / f"{NAME}.pbip")
