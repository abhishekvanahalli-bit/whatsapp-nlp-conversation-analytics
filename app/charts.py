"""
Plotly figure builders for the dashboard. Pure functions: tables in, figure out.
Nothing here reads files or knows about any particular chat.

Colours follow one fixed mapping so a row kind means the same colour on every
chart (categorical slots used in order: text, media, deleted, system). Marks are
thin with a 2px surface gap between fills; grid and axes are recessive; identity
never relies on colour alone (legends plus hover tooltips on every mark).
"""

import plotly.graph_objects as go

SURFACE = "#ffffff"          # chart panel colour (matches the white cards)
INK = "#172033"
INK_SECONDARY = "#5b6678"
GRID = "#e1e7f0"
ON_DARK, ON_LIGHT = "#ffffff", "#172033"   # bar-label colours, chosen per bar by contrast

# row kind -> colour (validated categorical slots 1-4, fixed order)
KIND_COLOURS = {
    "text": "#2563eb",      # blue
    "media": "#d9611e",     # orange
    "deleted": "#0f9d73",   # green
    "system": "#b98300",    # amber
    "header": "#7a869a",    # neutral
    "user": "#64748b",      # neutral slate (parent of text/media/deleted)
}
SERIES_ALL, SERIES_UNIQUE = "#2563eb", "#d9611e"
SCRIPT_COLOURS = {"latin": "#2563eb", "devanagari": "#d9611e", "other": "#7a869a"}


def _luminance(hex_colour):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(hex_colour[i:i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def label_colour(bar_hex):
    """White or dark text, whichever contrasts more with the bar it sits on."""
    lum = _luminance(bar_hex)
    return ON_DARK if (1.05 / (lum + 0.05)) >= ((lum + 0.05) / (_luminance(ON_LIGHT) + 0.05)) else ON_LIGHT


def _base(fig, height, title=None):
    fig.update_layout(
        height=height, title=dict(text=title, x=0, font=dict(size=15, color=INK)) if title else None,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",   # follow the (possibly tinted) panel
        font=dict(family="Source Sans Pro, Segoe UI, Arial, sans-serif", size=14, color=INK_SECONDARY),
        margin=dict(l=10, r=16, t=44 if title else 28, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=INK_SECONDARY)),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#c3ccd9", font=dict(color=INK)),
    )
    fig.update_xaxes(automargin=True, gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=INK_SECONDARY),
                     title_font=dict(size=13, color=INK_SECONDARY))
    fig.update_yaxes(automargin=True, gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=INK_SECONDARY),
                     title_font=dict(size=13, color=INK_SECONDARY))
    return fig


def _empty(message, height=220):
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=14, color=INK_SECONDARY))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base(fig, height)


# ---------------------------------------------------------------- composition ---
def composition_figure(composition):
    """Two stacked horizontal bars from analytics_row_composition: parsed rows
    (header/system/user) and user rows (text/media/deleted)."""
    if composition.empty:
        return _empty("No rows to show.")
    fig = go.Figure()
    order = {"parsed_rows": ("header", "system", "user"), "user_rows": ("text", "media", "deleted")}
    labels = {"parsed_rows": "Parsed rows", "user_rows": "User rows"}
    seen = set()
    for group, cats in order.items():
        sub = composition[composition["group"] == group].set_index("category")
        for cat in cats:
            if cat not in sub.index:
                continue
            count, denom = int(sub.loc[cat, "count"]), int(sub.loc[cat, "denominator"])
            fig.add_trace(go.Bar(
                y=[labels[group]], x=[count], name=cat, orientation="h",
                marker=dict(color=KIND_COLOURS[cat], line=dict(color=SURFACE, width=2)),
                legendgroup=cat, showlegend=cat not in seen,
                text=[str(count)] if count else None, textposition="inside",
                textfont=dict(color=label_colour(KIND_COLOURS[cat])),
                hovertemplate=f"{labels[group]}: {cat}<br>%{{x}} of {denom}<extra></extra>"))
            seen.add(cat)
    fig.update_layout(barmode="stack", bargap=0.45)
    fig.update_xaxes(title_text="Rows")
    fig.update_yaxes(autorange="reversed")
    return _base(fig, 230)


# ------------------------------------------------------------------- timeline ---
def daily_timeline_figure(daily):
    """Stacked bars per calendar date (zero-filled, so empty dates are visible)."""
    if daily.empty:
        return _empty("No dated rows to show a timeline.")
    fig = go.Figure()
    for column, kind in (("text_messages", "text"), ("media_rows", "media"),
                         ("deleted_rows", "deleted"), ("system_rows", "system")):
        fig.add_trace(go.Bar(
            x=daily["date"], y=daily[column], name=kind,
            marker=dict(color=KIND_COLOURS[kind], line=dict(color=SURFACE, width=1.5)),
            hovertemplate=f"%{{x}}<br>{kind}: %{{y}}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.25, hovermode="x unified")
    fig.update_xaxes(type="category", tickangle=-45)
    fig.update_yaxes(title_text="Rows per date")
    return _base(fig, 330)


# ------------------------------------------------------------------ repetition ---
def unique_vs_repeated_figure(summary):
    """Text messages = unique texts + repeat messages (one stacked bar)."""
    s = summary.set_index("metric")["count"] if not summary.empty else {}
    total = int(s.get("text_messages", 0)) if len(s) else 0
    if total == 0:
        return _empty("No text messages to compare.", 160)
    repeats = int(s["repeat_messages_after_masking"])
    unique = int(s["unique_texts_after_masking"])
    fig = go.Figure()
    for name, value, colour in (("Unique texts", unique, KIND_COLOURS["text"]),
                                ("Repeat messages", repeats, KIND_COLOURS["media"])):
        fig.add_trace(go.Bar(
            y=["Text messages"], x=[value], name=name, orientation="h",
            marker=dict(color=colour, line=dict(color=SURFACE, width=2)),
            text=[str(value)] if value else None, textposition="inside", textfont=dict(color=label_colour(colour)),
            hovertemplate=f"{name}: %{{x}} of {total} text messages<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.5)
    fig.update_xaxes(title_text="Text messages")
    return _base(fig, 190)


def template_groups_figure(groups):
    if groups.empty:
        return _empty("No repeated templates found.", 160)
    fig = go.Figure(go.Bar(
        y="Template " + groups["template_id"].astype(str), x=groups["occurrences"], orientation="h",
        marker=dict(color=KIND_COLOURS["text"], line=dict(color=SURFACE, width=2)),
        text=groups["occurrences"], textposition="outside", cliponaxis=False,
        customdata=groups[["repeat_messages", "distinct_raw_texts", "first_date", "last_date"]],
        hovertemplate=("%{y}: %{x} messages<br>%{customdata[0]} repeats, %{customdata[1]} distinct raw "
                       "texts<br>%{customdata[2]} to %{customdata[3]}<extra></extra>")))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Messages using the template")
    fig.update_layout(bargap=0.4, showlegend=False)
    return _base(fig, max(160, 60 + 40 * len(groups)))


# -------------------------------------------------------------------- terms ---
def ngram_bars_figure(table, top_k, rank_by="all"):
    """Grouped horizontal bars: occurrences across all messages vs across
    unique texts. rank_by: 'all' or 'unique'."""
    if table.empty:
        return _empty("Nothing to show (no terms above the display threshold).")
    key = "count_all" if rank_by == "all" else "count_unique"
    top = table.sort_values([key, "ngram"], ascending=[False, True]).head(top_k)
    fig = go.Figure()
    for column, name, colour in (("count_all", "All messages", SERIES_ALL),
                                 ("count_unique", "Unique texts only", SERIES_UNIQUE)):
        fig.add_trace(go.Bar(
            y=top["ngram"], x=top[column], name=name, orientation="h",
            marker=dict(color=colour, line=dict(color=SURFACE, width=1.5)),
            customdata=top[["msgs_all"]],
            hovertemplate="%{y}<br>" + name + ": %{x}<br>in %{customdata[0]} messages<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Occurrences")
    return _base(fig, max(260, 46 * len(top) + 90))


def tfidf_bars_figure(top_terms, variant, metric, top_k):
    """Top terms of one variant by a TF-IDF metric, coloured by script."""
    sub = top_terms[top_terms["variant"] == variant] if not top_terms.empty else top_terms
    if sub.empty:
        return _empty("Nothing to show (no terms above the display threshold).")
    top = sub.sort_values([metric, "term"], ascending=[False, True]).head(top_k)
    fig = go.Figure()
    for script in ("latin", "devanagari", "other"):
        part = top[top["script"] == script]
        if part.empty:
            continue
        fig.add_trace(go.Bar(
            y=part["term"], x=part[metric], name=script, orientation="h",
            marker=dict(color=SCRIPT_COLOURS[script], line=dict(color=SURFACE, width=1.5)),
            customdata=part[["df", "idf"]],
            hovertemplate=("%{y}<br>" + metric + ": %{x:.3f}<br>in %{customdata[0]} messages, "
                           "IDF %{customdata[1]:.2f}<extra></extra>")))
    fig.update_layout(barmode="stack", bargap=0.3)
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=list(top["term"]))
    fig.update_xaxes(title_text=metric.replace("_", " "))
    return _base(fig, max(260, 40 * len(top) + 90))


# --------------------------------------------------------------------- hours ---
def hour_histogram_figure(hours, height=260):
    if hours.empty or int(hours[["user_rows", "system_rows"]].to_numpy().sum()) == 0:
        return _empty("No timestamped rows.", 200)
    fig = go.Figure()
    for column, kind in (("user_rows", "user"), ("system_rows", "system")):
        fig.add_trace(go.Bar(
            x=hours["hour_as_exported"], y=hours[column], name=kind,
            marker=dict(color=KIND_COLOURS[kind], line=dict(color=SURFACE, width=1.5)),
            hovertemplate=f"hour %{{x}}: {kind} rows %{{y}}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.2)
    fig.update_xaxes(title_text="Hour as recorded in the export (time zone unverified)", dtick=1)
    fig.update_yaxes(title_text="Rows")
    return _base(fig, height)


# ---------------------------------------------------------------- script mix ---
SCRIPT_CLASS_LABELS = {"latin_only": "Latin-only", "mixed_script": "Mixed-script",
                       "devanagari_only": "Devanagari-only", "no_alphabetic": "No alphabetic text",
                       "other_script_only": "Other script only"}
SCRIPT_CLASS_COLOURS = {"latin_only": "#2563eb", "devanagari_only": "#d9611e", "mixed_script": "#0f9d73",
                        "no_alphabetic": "#7a869a", "other_script_only": "#b98300"}
SCRIPT_CLASS_ORDER = ("latin_only", "mixed_script", "devanagari_only", "no_alphabetic", "other_script_only")


def script_mix_figure(summary, variant="all"):
    """Messages per script class (from script_mix_summary). Script composition, not language."""
    sub = summary[summary["variant"] == variant] if not summary.empty else summary
    if sub.empty or int(sub["denominator"].iloc[0]) == 0:
        return _empty("No text messages to classify.", 200)
    sub = sub.set_index("message_class")
    classes = [c for c in SCRIPT_CLASS_ORDER if c in sub.index and (c != "other_script_only" or int(sub.loc[c, "messages"]) > 0)]
    total = int(sub["denominator"].iloc[0])
    fig = go.Figure(go.Bar(
        y=[SCRIPT_CLASS_LABELS[c] for c in classes], x=[int(sub.loc[c, "messages"]) for c in classes],
        orientation="h", marker=dict(color=[SCRIPT_CLASS_COLOURS[c] for c in classes], line=dict(color=SURFACE, width=2)),
        text=[str(int(sub.loc[c, "messages"])) for c in classes], textposition="outside", cliponaxis=False,
        customdata=[[int(sub.loc[c, "short_messages"])] for c in classes],
        hovertemplate="%{y}: %{x} of " + str(total) + " text messages<br>%{customdata[0]} very short (3 words or fewer)<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Text messages")
    fig.update_layout(showlegend=False, bargap=0.4)
    fig = _base(fig, 120 + 46 * len(classes))
    fig.update_layout(margin=dict(l=10, r=46, t=28, b=10))     # room for the outside value labels
    return fig


# ----------------------------------------------------------------- weekday ---
def weekday_figure(table):
    """Rows per weekday (user + system) from analytics_weekday_table; coverage of the export, not a habit."""
    if table.empty or int(table[["user_rows", "system_rows"]].to_numpy().sum()) == 0:
        return _empty("No timestamped rows.", 200)
    fig = go.Figure()
    for column, kind in (("user_rows", "user"), ("system_rows", "system")):
        fig.add_trace(go.Bar(
            x=table["weekday"].str.slice(0, 3), y=table[column], name=kind,
            marker=dict(color=KIND_COLOURS[kind], line=dict(color=SURFACE, width=1.5)),
            hovertemplate=f"%{{x}}: {kind} rows %{{y}}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_yaxes(title_text="Rows")
    return _base(fig, 240)


def key_terms_compact_figure(table, top_k=6):
    """Single-series coverage bars (distinct messages containing each term) for narrow overview cards."""
    if table.empty:
        return _empty("Nothing to show (no terms above the display threshold).", 240)
    top = table.sort_values(["unique_texts_containing", "term"], ascending=[False, True]).head(top_k)
    fig = go.Figure(go.Bar(
        y=top["term"], x=top["unique_texts_containing"].astype(int), orientation="h",
        marker=dict(color=SERIES_ALL, line=dict(color=SURFACE, width=1.5)),
        text=top["unique_texts_containing"].astype(int), textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: in %{x} distinct messages<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Distinct messages (coverage)")
    fig.update_layout(showlegend=False, bargap=0.35)
    return _base(fig, 280)


# ----------------------------------------------------------------- key terms ---
def key_terms_figure(table, top_k):
    """Distinct messages containing each term (coverage) next to total occurrences (frequency)."""
    if table.empty:
        return _empty("Nothing to show (no terms above the display threshold).")
    top = table.sort_values(["unique_texts_containing", "term"], ascending=[False, True]).head(top_k)
    fig = go.Figure()
    for column, name, colour in (("unique_texts_containing", "Distinct messages containing the term (coverage)", SERIES_ALL),
                                 ("occurrences_all", "Total occurrences (frequency)", SERIES_UNIQUE)):
        fig.add_trace(go.Bar(
            y=top["term"], x=top[column].astype(int), name=name, orientation="h",
            marker=dict(color=colour, line=dict(color=SURFACE, width=1.5)),
            hovertemplate="%{y}<br>" + name + ": %{x}<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Count")
    return _base(fig, max(280, 46 * len(top) + 110))
