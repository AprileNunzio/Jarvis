import io
import textwrap


def png(chart: dict, theme: dict, width_in: float = 6.4, height_in: float = 3.4) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    colors = [f"#{c}" for c in theme["chart"]]
    kind = chart["chart"]
    cats = [textwrap.fill(str(c), 16 if kind != "bar" else 28, max_lines=3, placeholder="…") for c in chart["categories"]]
    series = chart["series"]
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    if kind in ("pie", "doughnut"):
        values = series[0]["values"]
        wedges, _, labels = ax.pie(values, labels=cats, colors=colors[:len(values)] * 3, autopct="%1.0f%%", startangle=90,
                                   pctdistance=0.78 if kind == "doughnut" else 0.6,
                                   wedgeprops={"width": 0.42 if kind == "doughnut" else 1, "edgecolor": "white", "linewidth": 2},
                                   textprops={"fontsize": 8, "color": "#333333"})
        for label in labels:
            label.set_color("white" if kind == "pie" else "#333333")
        ax.axis("equal")
    else:
        positions = list(range(len(cats)))
        n = len(series)
        width = 0.8 / max(n, 1)
        for i, s in enumerate(series):
            color = colors[i % len(colors)]
            if kind in ("bar", "column"):
                offs = [p - 0.4 + width * (i + 0.5) for p in positions]
                if kind == "bar":
                    ax.barh(offs, s["values"], height=width, color=color, label=s["name"])
                else:
                    ax.bar(offs, s["values"], width=width, color=color, label=s["name"])
            elif kind == "area":
                ax.fill_between(positions, s["values"], alpha=0.35, color=color)
                ax.plot(positions, s["values"], color=color, linewidth=2, label=s["name"])
            elif kind == "scatter":
                ax.scatter(positions, s["values"], color=color, s=36, label=s["name"])
            else:
                ax.plot(positions, s["values"], color=color, linewidth=2.4, marker="o", markersize=4, label=s["name"])
        if kind == "bar":
            ax.set_yticks(positions, cats, fontsize=8)
            ax.invert_yaxis()
        else:
            ax.set_xticks(positions, cats, fontsize=8, rotation=30 if len(cats) > 6 else 0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#CCCCCC")
        ax.tick_params(colors="#555555", labelsize=8)
        ax.grid(axis="x" if kind == "bar" else "y", color="#EEEEEE", linewidth=0.8)
        ax.set_axisbelow(True)
        if chart.get("unit"):
            (ax.set_xlabel if kind == "bar" else ax.set_ylabel)(chart["unit"], fontsize=8, color="#555555")
        if n > 1:
            ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    if chart.get("title"):
        ax.set_title(chart["title"], fontsize=11, color=f"#{theme['dark']}", loc="left", pad=10, fontweight="bold")
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
