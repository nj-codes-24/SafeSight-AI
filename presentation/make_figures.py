"""Presentation figures, drawn only from saved results. Runs no model.

Sources: reports/pr_curves.json, reports/common_val.json, reports/unseen_compare/summary.json.
Writes presentation/figures/*.png.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation" / "figures"
INK, MUTED, GRID, BG = "#1c2127", "#5b636e", "#e3e1da", "#fbfaf6"
COLOUR = {"m2": "#3b6fb6", "m3": "#c8641f", "m5": "#1e8a68"}
LABEL = {"m2": "M2", "m3": "M3", "m5": "M5"}
WORKSITE = ["c00.webm", "c01.webm", "c02.webm", "c03.ogv", "c09.ogv", "c10.ogv", "c12.ogv"]
# Judged by eye from the evidence sheets (reports/unseen_compare/*_evidence.jpg); see final_report.md.
ALERTS = {"M2 (0.65)": (0, 0), "M3 (0.50)": (1, 3), "M5 (0.50)": (2, 0), "M5 (0.60), app": (2, 0)}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": BG, "axes.facecolor": BG,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "axes.axisbelow": True})


def thresholds(pr):
    fig, ax = plt.subplots(figsize=(9, 6))
    for m in ("m2", "m3", "m5"):
        c = pr[m]["sh17_val"]
        ax.plot([c[t]["recall"] for t in c], [c[t]["precision"] for t in c], lw=2, color=COLOUR[m], label=LABEL[m],
                alpha=1 if m == "m5" else 0.45)
        t = str(pr[m]["threshold"]["value"])
        ax.plot(c[t]["recall"], c[t]["precision"], "o", ms=9, color=COLOUR[m], markeredgecolor=BG, markeredgewidth=2)
        if m != "m5":
            ax.annotate(f"{LABEL[m]} comparison {float(t):.2f}", (c[t]["recall"], c[t]["precision"]), textcoords="offset points",
                        xytext=(8, -18), color=MUTED, fontsize=11)
    c = pr["m5"]["sh17_val"]
    for t, text, dx, dy in (("0.5", "M5 comparison threshold 0.50\nP {p:.3f}  R {r:.3f}", 14, -48),
                            ("0.6", "M5 application threshold 0.60\nP {p:.3f}  R {r:.3f}", -250, 22)):
        p, r = c[t]["precision"], c[t]["recall"]
        ax.plot(r, p, "D" if t == "0.6" else "o", ms=10, color=COLOUR["m5"], markeredgecolor=INK, markeredgewidth=1.5)
        ax.annotate(text.format(p=p, r=r), (r, p), textcoords="offset points", xytext=(dx, dy), color=INK, fontsize=11,
                    arrowprops=dict(arrowstyle="-", color=MUTED))
    ax.axhline(0.95, color=MUTED, lw=1, ls="--")
    ax.text(0.22, 0.935, "rule: precision 0.95", color=MUTED, fontsize=10)
    ax.set_xlim(0, 0.9)
    ax.set_ylim(0.3, 1.1)
    ax.set_yticks([0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("no_helmet on SH17 validation, confidence 0.05 to 0.95", loc="left", color=INK)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "thresholds_sh17.png", dpi=160)
    plt.close(fig)


def benchmark_vs_site(cv):
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5))
    ms = ["m2", "m3", "m5"]
    vals = [cv[m]["sh17_val"]["per_class"]["no_helmet"]["AP50"] for m in ms]
    a.grid(axis="x", visible=False)
    b.grid(axis="x", visible=False)
    bars = a.bar([LABEL[m] for m in ms], vals, color=[COLOUR[m] for m in ms], width=0.55)
    a.bar_label(bars, fmt="%.2f", color=INK, padding=4)
    a.set_ylim(0, 1)
    a.set_title("Benchmark: SH17 val no_helmet AP50\n(all confidences, no threshold)", loc="left", color=INK, fontsize=12)
    names = list(ALERTS)
    x = range(len(names))
    tp = [ALERTS[n][0] for n in names]
    fp = [ALERTS[n][1] for n in names]
    b1 = b.bar([i - 0.18 for i in x], tp, width=0.34, color=INK, label="true alerts")
    # M3's count is a range (2 certain, 1 ambiguous), drawn as a solid bar to 2 and a faint bar from 2 to 3.
    b2 = b.bar([i + 0.18 for i in x], [min(v, 2) for v in fp], width=0.34, color="#d9a441", hatch="//", edgecolor=BG,
               label="false alerts")
    b3 = b.bar([i + 0.18 for i in x], [v - min(v, 2) for v in fp], bottom=[min(v, 2) for v in fp], width=0.34,
               color="#d9a441", alpha=0.35, edgecolor=BG)
    b.bar_label(b1, color=INK, padding=3)
    b.bar_label(b3, labels=["0", "2–3", "0", "0"], color=INK, padding=3)
    b2.set_label("false alerts (faint = uncertain)")
    b.set_xticks(list(x), names, fontsize=10)
    b.set_ylim(0, 4)
    b.set_yticks(range(5))
    b.set_title("Unseen worksite clips: full-pipeline alerts\n(threshold in brackets)", loc="left", color=INK, fontsize=12)
    b.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "benchmark_vs_site.png", dpi=160)
    plt.close(fig)


def tracking(uc):
    runs = {"M2 (0.65)": "m2", "M3 (0.50)": "m3", "M5 (0.50)": "m5", "M5 (0.60), app": "m5_at_0.6"}
    ids = [sum(v["track_ids"] for k, v in uc[r].items() if k != "no_helmet_conf") for r in runs.values()]
    short = [sum(v["short_ids"] for k, v in uc[r].items() if k != "no_helmet_conf") for r in runs.values()]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.grid(axis="x", visible=False)
    x = range(len(runs))
    b1 = ax.bar([i - 0.18 for i in x], ids, width=0.34, color=MUTED, label="track IDs issued")
    b2 = ax.bar([i + 0.18 for i in x], short, width=0.34, color="#d9a441", hatch="//", edgecolor=BG, label="IDs lasting under 1 s")
    ax.bar_label(b1, color=INK, padding=3)
    ax.bar_label(b2, color=INK, padding=3)
    ax.set_xticks(list(x), list(runs), fontsize=10)
    ax.set_title("Tracking on ten unseen clips (lower is steadier)", loc="left", color=INK)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "tracking_unseen.png", dpi=160)
    plt.close(fig)


def false_dets(uc):
    runs = {"M2 (0.65)": "m2", "M3 (0.50)": "m3", "M5 (0.50)": "m5", "M5 (0.60), app": "m5_at_0.6"}
    nh = [uc[r]["c02.webm"]["false_no_helmet_dets_per_100_frames"] for r in runs.values()]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.grid(axis="x", visible=False)
    bars = ax.bar(list(runs), nh, color=[COLOUR["m2"], COLOUR["m3"], COLOUR["m5"], COLOUR["m5"]], width=0.55)
    ax.bar_label(bars, fmt="%.1f", color=INK, padding=3)
    ax.set_title("False no_helmet detections per 100 frames, helmet-only clip c02", loc="left", color=INK)
    ax.tick_params(axis="x", labelsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "false_no_helmet_c02.png", dpi=160)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pr = json.loads((ROOT / "reports/pr_curves.json").read_text())
    cv = json.loads((ROOT / "reports/common_val.json").read_text())
    uc = json.loads((ROOT / "reports/unseen_compare/summary.json").read_text())
    thresholds(pr)
    benchmark_vs_site(cv)
    tracking(uc)
    false_dets(uc)
    print(sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
