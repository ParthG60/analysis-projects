"""Generate high-polish effort.news dark-mode figures for legislative AI prevalence.

Uses isotonic calibration (expected-value method).
Generates smoothed and non-smoothed versions of the bills chart.
Prints CIs to terminal but does not plot them.
"""
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parents[1]
DATA = HERE / "data"
V = HERE / "data" / "validation"
FIG = HERE / "figures"
FIG.mkdir(parents=True, exist_ok=True)

BG_COLOR = "#000000"
SURFACE_COLOR = "#0a0a0a"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#94a3b8"
TEXT_DIM = "#64748b"
HAIRLINE = "#777777"
WHITE = "#ffffff"
DEM_BLUE = "#3b82f6"
REP_RED = "#ef4444"

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Georgia", "DejaVu Serif", "Times New Roman"]
plt.rcParams["axes.edgecolor"] = HAIRLINE
plt.rcParams["axes.linewidth"] = 0.8

BINS_6 = ["[0.00, 0.20)", "[0.20, 0.35)", "[0.35, 0.50)", "[0.50, 0.65)", "[0.65, 0.80)", "[0.80, 1.00]"]
MIDS = np.array([0.10, 0.275, 0.425, 0.575, 0.725, 0.90])
RNG = np.random.default_rng(73)


def load_isotonic_calibration(corpus="federal_bills"):
    """Load corrected calibration, return (emp_rates, bootstrap_rates)."""
    calib = pd.read_csv(V / "joint_calibration_tables_corrected.csv")
    sub = calib[calib.corpus == corpus]
    k = np.array([int(sub[sub.score_bin == b]["pangram_ai_hits"].values[0]) for b in BINS_6])
    n = np.array([int(sub[sub.score_bin == b]["n_sampled"].values[0]) for b in BINS_6])
    emp = np.array([float(sub[sub.score_bin == b]["empirical_rate"].values[0]) for b in BINS_6])
    for i in range(1, len(emp)):
        if emp[i] < emp[i-1]:
            emp[i] = emp[i-1]
    B = 10000
    boot = RNG.beta(k + 1, n - k + 1, size=(B, len(BINS_6)))
    # Fix anchor bin at 0 (zero-FPR floor)
    boot[:, 0] = 0.0
    for b in range(B):
        for i in range(2, len(boot[b])):
            if boot[b][i] < boot[b][i-1]:
                boot[b][i] = boot[b][i-1]
    return emp, boot


def p_ai(score, rates):
    return np.interp(score, MIDS, rates, left=0.0, right=float(rates[-1]))


def build_series():
    """Build all quarterly series and bootstrap CIs.
    
    Returns: (quarters, comb, p_piv, comb_boot, dem_boot, rep_boot, ctrl)
    """
    scores = pd.read_csv(DATA / "block_scores_3b.csv", low_memory=False)
    scores["action_date"] = pd.to_datetime(scores["action_date"], errors="coerce")
    scores = scores.dropna(subset=["action_date"])
    scores["quarter"] = scores["action_date"].dt.to_period("Q")

    emp_rates, boot = load_isotonic_calibration("federal_bills")

    fb = scores[scores.block_type.isin(["findings", "preamble"])].groupby(
        ["congress", "bill_type", "bill_num", "quarter", "sponsor_party"]
    ).agg(max_score=("score", "max")).reset_index()
    fb["p_ai"] = p_ai(fb["max_score"].values, emp_rates)
    fb = fb[(fb.quarter >= "2023Q1") & (fb.quarter <= "2026Q2")]

    comb = fb.groupby("quarter").agg(
        n_bills=("p_ai", "count"), n_ai_expected=("p_ai", "sum")
    ).reset_index()
    comb["pct_ai"] = (comb["n_ai_expected"] / comb["n_bills"]) * 100

    # --- Non-content (control-only) bills ---
    content_ids = set(scores[scores.block_type.isin(["findings","preamble"])].package_id.unique())
    ctrl_only = scores[~scores.package_id.isin(content_ids) & (scores.block_type == "control")].copy()
    ctrl_bills = ctrl_only.groupby(
        ["package_id", "quarter"]
    ).agg(max_score=("score", "max")).reset_index()
    ctrl_bills = ctrl_bills[(ctrl_bills.quarter >= "2023Q1") & (ctrl_bills.quarter <= "2026Q2")]
    ctrl_bills["p_ai"] = p_ai(ctrl_bills["max_score"].values, emp_rates)
    ctrl = ctrl_bills.groupby("quarter").agg(
        n_bills=("p_ai", "count"), n_ai_expected=("p_ai", "sum")
    ).reset_index()
    ctrl["pct_ai"] = (ctrl["n_ai_expected"] / ctrl["n_bills"]) * 100
    ctrl = ctrl.set_index("quarter").reindex(comb["quarter"]).fillna(0).reset_index()
    # ---

    quarters = sorted(list(fb["quarter"].unique()))
    q_idx = {q: i for i, q in enumerate(quarters)}
    q_arr = np.array([q_idx[q] for q in fb["quarter"].values])
    p_arr = fb["sponsor_party"].values
    s_arr = fb["max_score"].values

    # Party series
    p_df = fb[fb.sponsor_party.isin(["D", "R"])].copy()
    p_pt = p_df.groupby(["quarter", "sponsor_party"]).agg(
        n_bills=("p_ai", "count"), n_ai_expected=("p_ai", "sum")
    ).reset_index()
    p_pt["pct_ai"] = (p_pt["n_ai_expected"] / p_pt["n_bills"]) * 100
    p_piv = p_pt.pivot(index="quarter", columns="sponsor_party", values="pct_ai").fillna(0)

    # Bootstrap
    B = boot.shape[0]
    comb_boot = np.zeros((B, len(quarters)))
    dem_boot = np.zeros((B, len(quarters)))
    rep_boot = np.zeros((B, len(quarters)))
    for b in range(B):
        pv = p_ai(s_arr, boot[b])
        for q in range(len(quarters)):
            m = q_arr == q
            if m.sum() == 0: continue
            comb_boot[b, q] = pv[m].sum() / m.sum() * 100
            md = m & (p_arr == "D")
            mr = m & (p_arr == "R")
            if md.sum() > 0: dem_boot[b, q] = pv[md].sum() / md.sum() * 100
            if mr.sum() > 0: rep_boot[b, q] = pv[mr].sum() / mr.sum() * 100

    return quarters, comb, p_piv, comb_boot, dem_boot, rep_boot, ctrl


def plot_figure(quarters, comb, p_piv, ctrl, smoothing=True, suffix="", show_legend=True):
    """Plot a single 2-panel figure. If smoothing=True, 2Q rolling mean."""
    q_str = [str(q) for q in quarters]
    x = np.arange(len(quarters))

    comb_v = comb["pct_ai"].rolling(2, min_periods=1).mean().values if smoothing else comb["pct_ai"].values
    ctrl_v = ctrl["pct_ai"].rolling(2, min_periods=1).mean().values if smoothing else ctrl["pct_ai"].values
    dem_v = p_piv["D"].rolling(2, min_periods=1).mean().values if smoothing else p_piv["D"].values
    rep_v = p_piv["R"].rolling(2, min_periods=1).mean().values if smoothing else p_piv["R"].values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.8), facecolor=BG_COLOR,
                                   gridspec_kw={'width_ratios': [1.2, 1]})

    # Panel 1: Congress Aggregate
    ax1.set_facecolor(BG_COLOR)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.25, color=HAIRLINE, zorder=1)
    ax1.plot(x, comb_v, color=WHITE, linewidth=2.8, label="Findings & Preambles", zorder=5)
    ax1.plot(x, ctrl_v, color=HAIRLINE, linewidth=1.8, linestyle="--", label="Statutory text only", zorder=3)
    ax1.text(x[-1] + 0.15, comb_v[-1], f"{comb_v[-1]:.1f}%", color=WHITE,
             fontsize=9.5, fontweight="bold", va="center")
    ax1.set_title("A. Congress Aggregate", fontsize=12.5,
                  fontweight="bold", color=TEXT_MAIN, loc="left", pad=12)
    ax1.set_ylabel("Expected AI %", fontsize=9.5, color=TEXT_MUTED, labelpad=8)
    ax1.set_ylim(-0.2, 8.2)
    ax1.set_xlim(-0.3, len(x) + 0.8)
    ax1.set_xticks(x)
    ax1.set_xticklabels(q_str, fontsize=8.5, color=TEXT_MUTED, rotation=30)
    ax1.tick_params(colors=TEXT_MUTED, labelsize=9)
    for s in ("top", "right"): ax1.spines[s].set_visible(False)
    if show_legend:
        ax1.legend(loc="upper left", frameon=False, fontsize=8.0, labelcolor=TEXT_MAIN)

    # Panel 2: Party Comparisons
    ax2.set_facecolor(BG_COLOR)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.25, color=HAIRLINE, zorder=1)
    ax2.plot(x, dem_v, color=DEM_BLUE, linewidth=2.4, label="Democratic Staff", zorder=4)
    ax2.plot(x, rep_v, color=REP_RED, linewidth=2.4, label="Republican Staff", zorder=5)

    # Smart label placement: avoid overlap when values are close
    gap = abs(dem_v[-1] - rep_v[-1])
    if gap < 1.2:
        # Stagger vertically — D above, R further below
        d_off = 0.6 if dem_v[-1] >= rep_v[-1] else -0.4
        r_off = -0.4 if rep_v[-1] >= dem_v[-1] else 0.6
        d_va = "bottom" if d_off > 0 else "top"
        r_va = "top" if r_off < 0 else "bottom"
        ax2.text(x[-1] + 0.15, dem_v[-1] + d_off, f"D: {dem_v[-1]:.1f}%", color=DEM_BLUE,
                 fontsize=9, fontweight="bold", va=d_va)
        ax2.text(x[-1] + 0.15, rep_v[-1] + r_off, f"R: {rep_v[-1]:.1f}%", color=REP_RED,
                 fontsize=9, fontweight="bold", va=r_va)
    else:
        ax2.text(x[-1] + 0.15, dem_v[-1] + 0.3, f"D: {dem_v[-1]:.1f}%", color=DEM_BLUE,
                 fontsize=9, fontweight="bold", va="center")
        ax2.text(x[-1] + 0.15, rep_v[-1] - 0.3, f"R: {rep_v[-1]:.1f}%", color=REP_RED,
                 fontsize=9, fontweight="bold", va="center")

    ax2.set_title("B. Party Comparisons", fontsize=12.5,
                  fontweight="bold", color=TEXT_MAIN, loc="left", pad=12)
    # y-axis label only on panel A (shared scale)
    ax2.set_ylim(-0.2, 8.2)
    ax2.set_xlim(-0.3, len(x) + 1.2)
    ax2.set_xticks(x)
    ax2.set_xticklabels(q_str, fontsize=8.5, color=TEXT_MUTED, rotation=30)
    ax2.tick_params(colors=TEXT_MUTED, labelsize=9)
    for s in ("top", "right"): ax2.spines[s].set_visible(False)
    if show_legend:
        ax2.legend(loc="upper left", frameon=False, fontsize=8.2, labelcolor=TEXT_MAIN)

    fig.suptitle("AI in Congressional Bills",
                 fontsize=15, fontweight="bold", color=TEXT_MAIN, x=0.06, y=0.97,
                 ha="left")
    fig.text(0.06, 0.02,
             "Data: GPO govinfo 116th–119th Congress. EditLens 3B calibrated using Pangram 3.3.2.",
             fontsize=7.5, color=TEXT_DIM, fontfamily="monospace")

    out_name = f"prevalence_quarterly{suffix}.png"
    out_path = FIG / out_name
    plt.tight_layout(rect=[0.04, 0.05, 0.98, 0.94])
    plt.savefig(out_path, dpi=300, facecolor=BG_COLOR, bbox_inches="tight")
    print(f"Saved -> {out_path}")


def generate_bills_figure():
    quarters, comb, p_piv, comb_boot, dem_boot, rep_boot, ctrl = build_series()

    # Print CI table
    print("=" * 95)
    print(f"{'Quarter':<10} {'N':>5} {'Overall':>8} {'95% CI':>18} | {'Dem':>8} {'95% CI':>18} | {'Rep':>8} {'95% CI':>18}")
    print("=" * 95)
    for i, q in enumerate(quarters):
        r = comb.iloc[i]
        cl = np.percentile(comb_boot[:, i], 2.5)
        ch = np.percentile(comb_boot[:, i], 97.5)
        dl = np.percentile(dem_boot[:, i], 2.5)
        dh = np.percentile(dem_boot[:, i], 97.5)
        rl = np.percentile(rep_boot[:, i], 2.5)
        rh = np.percentile(rep_boot[:, i], 97.5)
        print(f"{str(q):<10} {int(r['n_bills']):>5} {r['pct_ai']:>6.2f}%  [{cl:>5.2f}%, {ch:>5.2f}%]   {p_piv.loc[q,'D']:>6.2f}%  [{dl:>5.2f}%, {dh:>5.2f}%]   {p_piv.loc[q,'R']:>6.2f}%  [{rl:>5.2f}%, {rh:>5.2f}%]")

    # Plot smoothed version
    plot_figure(quarters, comb, p_piv, ctrl, smoothing=True, suffix="")
    # Plot raw version (no legend)
    plot_figure(quarters, comb, p_piv, ctrl, smoothing=False, suffix="_raw", show_legend=False)


def plot_crec_figure(quarters, pt, smoothing, suffix, show_legend=True):
    """Plot a single CREC prevalence figure. If smoothing=True, 2Q rolling mean."""
    q_str = [str(q) for q in quarters]
    x = np.arange(len(quarters))
    if smoothing and len(pt) > 1:
        y = pd.Series(pt).rolling(2, min_periods=1).mean().values
    else:
        y = pt

    fig, ax = plt.subplots(figsize=(10.5, 5.4), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.grid(True, axis="y", linestyle="--", alpha=0.25, color=HAIRLINE, zorder=1)
    label = "Calibrated AI Share (2Q smoothed)" if smoothing else "Calibrated AI Share"
    ax.plot(x, y, color=WHITE, linewidth=2.8, label=label, zorder=4)
    ax.text(x[-1] + 0.15, y[-1], f"{y[-1]:.1f}%", color=WHITE,
            fontsize=9.5, fontweight="bold", va="center")
    ax.set_title("AI in Congressional Record Extensions of Remarks",
                 fontsize=15, fontweight="bold", color=TEXT_MAIN, loc="left", pad=16)
    ax.set_ylabel("Expected AI %", fontsize=10, color=TEXT_MUTED, labelpad=10)
    ax.set_ylim(-0.5, 20.0)
    ax.set_xlim(-0.3, len(x) + 0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(q_str, fontsize=8.5, color=TEXT_MUTED, rotation=30)
    ax.tick_params(colors=TEXT_MUTED, labelsize=9)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    if show_legend:
        ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=TEXT_MAIN)
    fig.text(0.08, 0.02,
             "Data: GPO govinfo CREC (2023–2026). EditLens 3B calibrated using Pangram 3.3.2.",
             fontsize=7.8, color=TEXT_DIM, fontfamily="monospace")

    out_name = f"crec_prevalence_calibrated_{suffix}.png" if suffix else "crec_prevalence_calibrated.png"
    out_path = FIG / out_name
    plt.tight_layout(rect=[0.04, 0.05, 0.98, 0.94])
    plt.savefig(out_path, dpi=300, facecolor=BG_COLOR, bbox_inches="tight")
    plt.close()
    print(f"Saved -> {out_path}")


def generate_crec_figure():
    print("Generating CREC figures...")

    cal = pd.read_csv(DATA / "crec_prevalence_calibrated.csv")
    cal = cal[(cal.quarter >= "2023Q1") & (cal.quarter <= "2026Q2")]

    quarters = list(cal["quarter"])
    pt = cal["point"].values * 100

    # Print CI table
    print("\n" + "=" * 75)
    print(f"{'Quarter':<10} {'N':>6} {'Prevalence':>12} {'95% CI':>18}")
    print("=" * 75)
    for i, q in enumerate(quarters):
        lo = cal.iloc[i]["lo"] * 100
        hi = cal.iloc[i]["hi"] * 100
        n = cal.iloc[i]["n_sampled"] if "n_sampled" in cal else 0
        print(f"{str(q):<10} {n:>6} {pt[i]:>8.2f}%  [{lo:>5.2f}%, {hi:>5.2f}%]")

    # Smoothed version (default)
    plot_crec_figure(quarters, pt, smoothing=True, suffix="")
    # Raw version (no legend)
    plot_crec_figure(quarters, pt, smoothing=False, suffix="raw", show_legend=False)


def main():
    print("Building series and computing CIs...")
    generate_bills_figure()
    generate_crec_figure()


if __name__ == "__main__":
    main()