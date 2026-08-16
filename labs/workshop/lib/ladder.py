"""Bookkeeping and display for a notebook that works by trial and error. No statistics here.

Lab 08 runs one trial per step and decides the next step from what the trial measured. Keeping
that record is presentation rather than analysis, so it lives here; every number the record holds
is computed by a cell the cadet can read and change.
"""
import numpy as np
import pandas as pd


class Ladder:
    """The running record of every trial, and what each one decided.

    A lab that prints one table per method teaches that the methods exist. A lab that keeps the
    score across every attempt teaches how the choice was reached, which is the part nobody can
    reconstruct afterwards from a pile of separate outputs.

    `next_step` is required rather than optional. A trial whose result does not change what
    happens next did not need running, and being forced to write the sentence is what catches
    that before the work is done rather than after.
    """

    def __init__(self):
        self.rows = []

    def record(self, step, trial, metric, value, verdict, next_step):
        self.rows.append({"step": step, "trial": trial, "metric": metric,
                          "value": round(float(value), 4), "verdict": verdict,
                          "next_step": next_step})
        return self.rows[-1]

    def table(self, since=None, metric=None):
        out = pd.DataFrame(self.rows)
        if since is not None:
            out = out[out["step"] >= since]
        if metric is not None:
            out = out[out["metric"] == metric]
        return out.reset_index(drop=True)

    def show(self, since=None, metric=None):
        return self.table(since, metric)[["step", "trial", "metric", "value", "verdict"]]

    def plot(self, metric, ax=None, colour="#7A5AC7", title=None, floor=None, xlim=(0, 1.05)):
        """Every trial that recorded this metric, in the order they were run."""
        import matplotlib.pyplot as plt
        table = self.table(metric=metric)
        if table.empty:
            raise ValueError(f"no trial recorded the metric {metric!r}; "
                             f"recorded so far: {sorted(set(r['metric'] for r in self.rows))}")
        ax = ax or plt.gca()
        y = np.arange(len(table))
        ax.barh(y, table["value"], color=colour)
        for n, row in enumerate(table.itertuples()):
            ax.text(row.value + 0.012, n, f"{row.value:.3f}", va="center", fontsize=11)
        if floor is not None:
            ax.axvline(floor, color="#D6455D", ls="--", lw=1.0)
            ax.text(floor + 0.012, -0.62, f"chance {floor}", color="#D6455D", fontsize=10)
        ax.set_yticks(y, [f"{r.step}. {r.trial}" for r in table.itertuples()])
        ax.invert_yaxis()
        ax.set(xlim=xlim, xlabel=metric, title=title or f"{metric}, every trial in order")
        return ax


def show_prompt(text, title="COPY EVERYTHING BETWEEN THE LINES INTO YOUR LLM"):
    """Print a prompt with hard delimiters, so a cadet can select it without catching output."""
    rule = "=" * 78
    print(f"{rule}\n{title}\n{rule}\n{text}\n{rule}\nEND OF PROMPT\n{rule}")
