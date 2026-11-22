"""Phase 11: render the report figures from results/*.csv.

Reads only the committed CSVs (no database needed), so anyone cloning the repo can
regenerate every figure. Output goes to docs/figures/ so GitHub Pages and the README
share one copy: PNG at 200 dpi plus a matching SVG.

Visual language is borrowed from clinical-trial reporting, which is where
pre-registration, forest plots, and minimum-detectable-effect all come from:
  one signal colour, used only where something is significant or alarming
  filled marker means the interval excludes zero, hollow means it does not
  no chartjunk: no top or right spines, no boxes, hairline reference rules only

Run:  python scripts/make_figures.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
# Figures live under docs/ so GitHub Pages can serve them directly and the README can
# embed the same single copy. No duplication between results/ and the site.
FIGDIR = REPO / "docs" / "figures"

# ---- design tokens -------------------------------------------------------------
# Same palette as docs/css/tokens.css: red marks wrong answers and overstatement,
# neutral greys carry everything else. Plates stay white so they read on light and
# dark pages alike.
INK      = "#17191c"
MID      = "#4a4f56"
RULE     = "#dcd9d1"
FAINT    = "#efede8"
PAPER    = "#ffffff"
SIGNAL   = "#c0392b"   # the site's red
SLATE    = "#4a4f56"   # secondary encoding: dark neutral
LIGHT    = "#c9c6bc"   # the lighter neutral, paired with SLATE

# The site's own fonts (docs/fonts, SIL OFL), converted from woff2 once per run so the
# figures and the pages share one set of files.
from matplotlib import font_manager
from fontTools.ttLib import TTFont
import tempfile

_FONTDIR = Path(tempfile.mkdtemp(prefix="yardstick-fonts-"))
for _w in ["source-serif-4-600", "ibm-plex-mono-400", "ibm-plex-mono-500", "ibm-plex-sans-400"]:
    _f = TTFont(REPO / "docs" / "fonts" / f"{_w}.woff2")
    _f.flavor = None
    _f.save(_FONTDIR / f"{_w}.ttf")
    font_manager.fontManager.addfont(str(_FONTDIR / f"{_w}.ttf"))

SERIF = ["Source Serif 4", "Georgia", "serif"]
MONO  = ["IBM Plex Mono", "Menlo", "monospace"]
SANSF = ["IBM Plex Sans", "Helvetica", "sans-serif"]

plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER,
    "font.family": "sans-serif", "font.sans-serif": SANSF, "font.serif": SERIF, "font.size": 11,
    "text.color": INK, "axes.labelcolor": INK,
    "axes.edgecolor": RULE, "axes.linewidth": 0.8,
    "xtick.color": MID, "ytick.color": MID,
    "xtick.labelsize": 10, "ytick.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False, "figure.dpi": 200, "savefig.dpi": 200,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.28,
})

VLABEL = {"V1": "V1  8B · zero-shot", "V2": "V2  8B · few-shot",
          "V3": "V3  70B · zero-shot", "V4": "V4  70B · few-shot"}


def read(name: str) -> list[dict]:
    with (RESULTS / name).open() as f:
        return list(csv.DictReader(f))


def save(fig, stem: str):
    FIGDIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(FIGDIR / f"{stem}.{ext}")
    plt.close(fig)
    print(f"  {stem}.png / .svg")


def caption(ax, text: str, y: float = -0.30):
    """Technical source note, left-aligned to the plot area (axes-relative, never drifts)."""
    ax.text(0, y, text, transform=ax.transAxes, ha="left", va="top",
            fontsize=8.5, color=MID, fontfamily=MONO, linespacing=1.5)


def plainbox(ax, text: str, y: float = -0.28):
    """One boxed sentence in everyday language: what a non-specialist should take away.
    Sits between the chart and the technical note so the figure reads without the paper."""
    ax.text(0, y, text, transform=ax.transAxes, ha="left", va="top",
            fontsize=10, color=INK, fontfamily=SANSF, linespacing=1.45,
            bbox=dict(boxstyle="round,pad=0.55", facecolor="#f7f6f2",
                      edgecolor=RULE, linewidth=0.8))


# ---- Figure 1: the headline ---------------------------------------------------
def fig_silent():
    rows = {r["variant"]: r for r in read("variant_summary.csv")}
    order = sorted(rows, key=lambda v: float(rows[v]["accuracy"]))
    share = [float(rows[v]["silent_share_of_errors"]) * 100 for v in order]
    acc = [float(rows[v]["accuracy"]) * 100 for v in order]
    nerr = [int(rows[v]["n_errors"]) for v in order]

    fig, ax = plt.subplots(figsize=(8.4, 3.5))
    y = range(len(order))
    # Colour encodes MODEL FAMILY, not alarm. The 70B variants are the accurate ones,
    # so painting them red would imply the opposite of the finding.
    fam = {"V1": "8B", "V2": "8B", "V3": "70B", "V4": "70B"}
    ax.barh(list(y), share, height=0.52,
            color=[SLATE if fam[v] == "70B" else LIGHT for v in order], zorder=3)
    for i, (s, a, ne) in enumerate(zip(share, acc, nerr)):
        ax.text(s - 1.6, i, f"{s:.0f}%", va="center", ha="right",
                color=PAPER if fam[order[i]] == "70B" else INK,
                fontsize=11.5, fontfamily=MONO, zorder=4)
        ax.text(101.5, i, f"{a:.0f}% accurate · {ne} errors", va="center", ha="left",
                fontsize=9.5, color=MID, fontfamily=MONO)
    ax.set_yticks(list(y))
    ax.set_yticklabels([VLABEL[v] for v in order], fontfamily=MONO, fontsize=10)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"], fontfamily=MONO)
    ax.set_xlabel("share of that variant's errors that were SILENT", fontsize=10, color=MID,
                  labelpad=9)
    for xt in (25, 50, 75, 100):
        ax.axvline(xt, color=FAINT, lw=0.8, zorder=1)
    ax.spines["left"].set_color(RULE)
    ax.tick_params(length=0)
    ax.invert_yaxis()
    ax.set_title(fontfamily=SERIF, label="Most mistakes ran without any error", loc="left", fontsize=15.5,
                 color=INK, pad=14)
    ax.legend(handles=[
        Line2D([], [], marker="s", ls="none", ms=9, color=LIGHT, label="8B (cheap model)"),
        Line2D([], [], marker="s", ls="none", ms=9, color=SLATE, label="70B (strong model)")],
        loc="upper left", bbox_to_anchor=(0.0, -0.22), ncol=2, frameon=False,
        fontsize=9, handletextpad=.5, columnspacing=2.2)
    plainbox(ax, "In plain terms: when the AI was wrong, the query almost always still ran. 93 of 104 mistakes\n" "gave no error. Both large-model setups sit above both small ones, a gap that could be chance (p = 0.09).", y=-0.42)
    caption(ax, "Silent = the query ran without error but returned the WRONG rows. Ordered by accuracy.\n"
                "n = 150 per variant.", y=-0.76)
    save(fig, "fig1_silent_failures")


# ---- Figure 2: forest plot ----------------------------------------------------
def fig_forest():
    prim = {r["tier"]: r for r in read("primary_analysis.csv")}
    me = read("model_effect.csv")

    rows = []   # (label, diff, lo, hi, p, group)
    for tier in ("simple", "moderate", "complex"):
        r = prim[tier]
        rows.append((tier, float(r["diff_pts"]), float(r["ci_low_pts"]),
                     float(r["ci_high_pts"]), float(r["bh_adj_p"]), "prompt"))
    for tier in ("simple", "moderate", "complex"):
        for r in me:
            if r["tier"] == tier and r["comparison"] == "model_zeroshot":
                rows.append((tier, float(r["diff_pts"]), float(r["ci_low_pts"]),
                             float(r["ci_high_pts"]), float(r["mcnemar_p"]), "model"))

    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    # y decreases down the page; leave a gap between the two blocks and a slot above
    # each for its section heading.
    ypos, y = [], 0.0
    for i in range(len(rows)):
        if i == 3:
            y -= 1.55                     # gap + heading slot for the second block
        ypos.append(y)
        y -= 1.0

    right = ax.get_yaxis_transform()      # x in axes fraction, y in data coords
    for (label, d, lo, hi, p, grp), yy in zip(rows, ypos):
        ci_excl = lo > 0 or hi < 0     # marker fill encodes the interval
        p_sig = p < 0.05               # text colour encodes the pre-specified test
        col = SIGNAL if ci_excl else MID
        ax.plot([lo, hi], [yy, yy], color=col, lw=1.5, zorder=3)
        for cap in (lo, hi):
            ax.plot([cap, cap], [yy - .15, yy + .15], color=col, lw=1.5, zorder=3)
        ax.plot([d], [yy], marker="s", ms=8, mfc=col if ci_excl else PAPER,
                mec=col, mew=1.5, zorder=4)
        ax.text(1.03, yy, f"{d:+.0f}  [{lo:+.0f}, {hi:+.0f}]   p {p:.3f}",
                transform=right, va="center", ha="left", fontsize=9.5,
                fontfamily=MONO, color=SIGNAL if p_sig else MID, clip_on=False)

    ax.axvline(0, color=INK, lw=1, zorder=2)
    ax.set_yticks(ypos)
    ax.set_yticklabels([r[0] for r in rows], fontfamily=MONO, fontsize=10)
    ax.set_xlim(-34, 46)
    ax.set_xticks([-30, -20, -10, 0, 10, 20, 30, 40])
    ax.set_xticklabels(["−30", "−20", "−10", "0", "+10", "+20", "+30", "+40"], fontfamily=MONO)
    ax.set_xlabel("accuracy difference (percentage points), 95% bootstrap CI",
                  fontsize=10, color=MID, labelpad=9)
    ax.set_ylim(min(ypos) - .7, max(ypos) + 1.0)
    ax.spines["left"].set_visible(False)
    ax.tick_params(length=0)

    for slot, text in ((ypos[0] + .72, "PRIMARY   few-shot − zero-shot (8B) · BH-adjusted"),
                       (ypos[3] + .72, "EXPLORATORY   70B − 8B (zero-shot) · uncorrected")):
        ax.text(-34, slot, text, fontsize=9, color=INK, fontfamily=MONO, va="center")

    ax.set_title(fontfamily=SERIF, label="Only the larger model moved the needle, on hard questions", loc="left", fontsize=15.5,
                 color=INK, pad=18)
    ax.legend(handles=[
        Line2D([], [], marker="s", ls="none", ms=8, mfc=SIGNAL, mec=SIGNAL, label="CI excludes 0"),
        Line2D([], [], marker="s", ls="none", ms=8, mfc=PAPER, mec=MID, label="CI includes 0")],
        loc="upper left", bbox_to_anchor=(0.0, -0.16), ncol=2, frameon=False,
        fontsize=9, handletextpad=.5, columnspacing=1.8)
    plainbox(ax, "In plain terms: if a bar crosses the middle line, that change did nothing we can prove.\n"
                 "Only one thing clearly worked: the larger, newer model on the hardest questions.", y=-0.30)
    caption(ax, "Filled marker = interval excludes zero. Red text = the pre-specified test is significant.\n"
                "These disagree on exploratory 'simple', where McNemar is conservative with few discordant\n"
                "pairs; the pre-specified test governs. Minimum detectable effect at n = 50 is 14 to 27 pts.",
            y=-0.62)
    save(fig, "fig2_forest")


# ---- Figure 3: calibration ----------------------------------------------------
def fig_calibration():
    rows = {r["variant"]: r for r in read("variant_summary.csv")}
    # Sorted by overconfidence gap (largest first) so the shrinking gap reads at a glance.
    gap = {v: (float(r["mean_confidence"]) - float(r["accuracy"])) * 100
           for v, r in rows.items()}
    order = sorted(rows, key=lambda v: -gap[v])
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    for i, v in enumerate(order):
        stated = float(rows[v]["mean_confidence"]) * 100
        actual = float(rows[v]["accuracy"]) * 100
        ax.plot([actual, stated], [i, i], color=RULE, lw=6, solid_capstyle="round", zorder=2)
        ax.plot([actual], [i], marker="o", ms=9, color=SLATE, zorder=4)
        ax.plot([stated], [i], marker="o", ms=9, color=SIGNAL, zorder=4)
        # y axis is inverted, so +0.30 places the note BELOW its dumbbell (clear of the title)
        ax.text((actual + stated) / 2, i + .30, f"gap {stated-actual:.0f} pts",
                ha="center", va="center", fontsize=8.5, color=MID, fontfamily=MONO)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([VLABEL[v] for v in order], fontfamily=MONO, fontsize=10)
    ax.set_xlim(70, 103)
    ax.set_xticks([70, 80, 90, 100])
    ax.set_xticklabels(["70", "80", "90", "100%"], fontfamily=MONO)
    for xt in (80, 90, 100):
        ax.axvline(xt, color=FAINT, lw=0.8, zorder=1)
    ax.set_ylim(3.62, -0.55)     # inverted, with room for the last gap note
    ax.tick_params(length=0)
    ax.spines["left"].set_color(RULE)
    ax.set_xlabel("percent", fontsize=10, color=MID, labelpad=9)
    ax.set_title(fontfamily=SERIF, label="Every variant is overconfident", loc="left", fontsize=15.5,
                 color=INK, pad=14)
    ax.legend(handles=[
        Line2D([], [], marker="o", ls="none", ms=9, color=SLATE, label="measured accuracy"),
        Line2D([], [], marker="o", ls="none", ms=9, color=SIGNAL, label="stated confidence")],
        loc="upper left", bbox_to_anchor=(0.0, -0.20), ncol=2, frameon=False,
        fontsize=9, handletextpad=.5, columnspacing=2.2)
    plainbox(ax, "In plain terms: every model claims to be surer than it actually is. The gap is smaller for the\n" "larger model but never closes, so a model's own confidence score is a weak safety check.", y=-0.34)
    caption(ax, "Sorted by the size of the overconfidence gap. All four stay 87 to 96% confident even on\n"
                "the answers they get wrong.", y=-0.70)
    save(fig, "fig3_calibration")


# ---- Figure 4: routing frontier -----------------------------------------------
def fig_routing():
    rows = read("routing_comparison.csv")
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    nice = {"always_cheap": "always cheap", "always_expensive": "always expensive",
            "random": "random", "length_only": "length-only baseline",
            "difficulty_routed": "difficulty routed", "oracle": "oracle (upper bound)"}
    offs = {"always_cheap": (9, -4), "always_expensive": (-4, -16), "random": (7, 7),
            "length_only": (9, -13), "difficulty_routed": (-6, -17), "oracle": (-4, 11)}
    for r in rows:
        pol = r["policy"]
        x = float(r["total_cost_usd"]) * 1000
        yv = float(r["accuracy"]) * 100
        hero = pol in ("difficulty_routed", "oracle")
        ax.plot([x], [yv], marker="o", ms=10 if hero else 7,
                color=SIGNAL if pol == "difficulty_routed" else (INK if pol == "oracle" else MID),
                mfc=SIGNAL if pol == "difficulty_routed" else (INK if pol == "oracle" else PAPER),
                mec=SIGNAL if pol == "difficulty_routed" else (INK if pol == "oracle" else MID),
                mew=1.5, zorder=4)
        dx, dy = offs[pol]
        ax.annotate(nice[pol], (x, yv), textcoords="offset points", xytext=(dx, dy),
                    fontsize=9.5, fontfamily=MONO,
                    color=SIGNAL if pol == "difficulty_routed" else (INK if hero else MID))
    for yt in (70, 75, 80, 85, 90):
        ax.axhline(yt, color=FAINT, lw=0.8, zorder=1)
    ax.set_xlabel("total cost for 60 questions (thousandths of a US cent, list price)",
                  fontsize=10, color=MID, labelpad=9)
    ax.set_ylabel("execution accuracy (%)", fontsize=10, color=MID, labelpad=9)
    # explicit ticks: letting matplotlib auto-pick gave 72.5/77.5, which round to
    # misleading "72"/"78" labels.
    ax.set_xticks([2, 5, 8, 11, 14, 17, 20])
    ax.set_xticklabels(["2", "5", "8", "11", "14", "17", "20"], fontfamily=MONO)
    ax.set_yticks([70, 75, 80, 85, 90])
    ax.set_yticklabels(["70", "75", "80", "85", "90"], fontfamily=MONO)
    ax.set_ylim(68, 92)
    ax.set_title(fontfamily=SERIF, label="Difficulty routing did not reliably beat random", loc="left", fontsize=15.5,
                 color=INK, pad=14)
    plainbox(ax, "In plain terms: our way of guessing which questions need the expensive model tied one random\n" "draw at the same budget, and beat random by only about 3 points on average.", y=-0.22)
    caption(ax, "One random draw also scored 78.3%; over 100,000 draws random averages 75.5%. The oracle (perfect foresight) beats\n"
                "always expensive at 63% less cost, so real headroom exists. These features could not reach it.",
            y=-0.46)
    save(fig, "fig4_routing")


# ---- Figure 5: error taxonomy -------------------------------------------------
def fig_taxonomy():
    rows = read("error_taxonomy.csv")
    fams = {"V1": "8B", "V2": "8B", "V3": "70B", "V4": "70B"}
    types = ["wrong_join", "wrong_filter", "wrong_projection", "wrong_aggregation",
             "schema_error"]
    counts = {"8B": dict.fromkeys(types, 0), "70B": dict.fromkeys(types, 0)}
    for r in rows:
        et = r["error_type"]
        if et in counts[fams[r["variant"]]]:
            counts[fams[r["variant"]]][et] += int(r["count"])

    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    n = len(types)
    h = 0.36
    ys = list(range(n))
    # 70B is drawn as the upper bar of each pair, so it is listed first in the legend.
    b70 = ax.barh([y - h/2 for y in ys], [counts["70B"][t] for t in types], height=h,
                  color=SLATE, label="70B (strong model)", zorder=3)
    b8 = ax.barh([y + h/2 for y in ys], [counts["8B"][t] for t in types], height=h,
                 color=LIGHT, label="8B (cheap model)", zorder=3)
    for i, t in enumerate(types):
        ax.text(counts["8B"][t] + .6, i + h/2, str(counts["8B"][t]), va="center",
                fontsize=9.5, color=MID, fontfamily=MONO)
        ax.text(counts["70B"][t] + .6, i - h/2, str(counts["70B"][t]), va="center",
                fontsize=9.5, color=SLATE, fontfamily=MONO)
    ax.set_yticks(ys)
    ax.set_yticklabels([t.replace("_", " ") for t in types], fontfamily=MONO, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("errors (both variants of each model size combined)", fontsize=10,
                  color=MID, labelpad=9)
    ax.set_xticks([0, 10, 20, 30])
    ax.set_xticklabels(["0", "10", "20", "30"], fontfamily=MONO)
    ax.set_xlim(0, 37)
    ax.tick_params(length=0)
    ax.spines["left"].set_color(RULE)
    ax.legend(handles=[b70, b8], loc="upper left", bbox_to_anchor=(0.0, -0.18),
              ncol=2, frameon=False, fontsize=9, handletextpad=.6, columnspacing=2.2)
    ax.set_title(fontfamily=SERIF, label="Where the model upgrade actually pays: joins", loc="left",
                 fontsize=15.5, color=INK, pad=14)
    plainbox(ax, "In plain terms: the most common mistake is joining the wrong tables (46 of 104).\n" "The larger model made it less often: 13 times against 33.", y=-0.34)
    caption(ax, "Wrong joins fall from 33 to 13 with the larger model. Invented tables or columns, 10 to 1.\n"
                "Only schema error fails loudly. Every other category returns wrong results silently.",
            y=-0.68)
    save(fig, "fig5_taxonomy")


# ---- Share card: what link previews actually show ------------------------------
def fig_sharecard():
    """1200x630 open-graph card, matched to the first screen of the page: same headline,
    same two numbers, same fonts and colours. Link scrapers render it at thumbnail
    size, so only big type is on it.

    The filename is versioned on purpose: scrapers cache og:image by URL and keep
    serving a stale card long after the file changed. Bump it if the card changes.

    The numbers are counted from docs/data/runs.json with the same rules as
    docs/js/facts.js, so the card cannot drift from the page."""
    import json
    runs = json.loads((REPO / "docs" / "data" / "runs.json").read_text())["runs"]
    wrong = [r for r in runs if not r["ok"]]
    nowarn = [r for r in wrong if r["ran"] and r["conf"] is not None and r["conf"] >= 0.9]
    caught = [r for r in nowarn if r["flagged"]]

    BG, PANEL, LINE = "#f7f6f2", "#ffffff", "#dcd9d1"
    C_INK, C_MID, C_ACC, C_BAD, C_GOOD = "#17191c", "#4a4f56", "#1d5ea8", "#c0392b", "#1f7a4d"
    SANS = ["IBM Plex Sans", "Helvetica", "sans-serif"]

    # Rendered at 2x (2400x1260): scrapers downscale hard and thin text turns to mush.
    fig = plt.figure(figsize=(12.0, 6.3), dpi=200)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.set_xlim(0, 1200); ax.set_ylim(0, 630)
    ax.add_patch(plt.Rectangle((40, 40), 1120, 550, facecolor=PANEL, edgecolor=LINE, lw=2, zorder=1))

    ax.text(84, 536, "YARDSTICK  ·  AAKASH MEHTA", fontsize=15, color=C_MID,
            fontfamily=MONO, va="baseline", zorder=3)
    ax.text(84, 452, "In my test, most of the AI's", fontsize=46, color=C_INK,
            fontfamily=SERIF, va="baseline", zorder=3)
    ax.text(84, 388, "mistakes came with no warning.", fontsize=46, color=C_INK,
            fontfamily=SERIF, va="baseline", zorder=3)

    ax.plot([84, 1116], [330, 330], color=LINE, lw=2, zorder=2)
    ax.text(84, 230, f"{len(nowarn)} of {len(wrong)}", fontsize=58, color=C_BAD,
            fontfamily=SERIF, va="baseline", zorder=3)
    ax.text(84, 186, "wrong answers: no error,", fontsize=20, color=C_INK, fontfamily=SANS, va="baseline", zorder=3)
    ax.text(84, 156, "and 90%+ self-rated confidence", fontsize=20, color=C_INK, fontfamily=SANS, va="baseline", zorder=3)
    ax.text(620, 230, f"{len(caught)} of {len(nowarn)}", fontsize=58, color=C_GOOD,
            fontfamily=SERIF, va="baseline", zorder=3)
    ax.text(620, 186, "of those caught by comparing", fontsize=20, color=C_INK, fontfamily=SANS, va="baseline", zorder=3)
    ax.text(620, 156, "four answers to each question", fontsize=20, color=C_INK, fontfamily=SANS, va="baseline", zorder=3)

    ax.text(84, 78, "a28-2001.github.io/yardstick", fontsize=19, color=C_ACC,
            fontfamily=MONO, va="baseline", zorder=3)

    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGDIR / "card-v5.png", dpi=200, facecolor=BG, bbox_inches=None, pad_inches=0)
    plt.close(fig)
    print("  card-v5.png")


if __name__ == "__main__":
    print("Rendering figures ->", FIGDIR)
    fig_silent(); fig_forest(); fig_calibration(); fig_routing(); fig_taxonomy()
    fig_sharecard()
    print("Done.")
