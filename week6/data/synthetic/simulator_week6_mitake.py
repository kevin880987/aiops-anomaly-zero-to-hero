"""Week 6 supplementary dataset: overlay the Week 6 teaching events on the shipped telemetry.

Why this file exists
--------------------
`simulator_rrd_metrics.ipynb` produces the course-wide dataset (events A to J).
Labs 00 to 02 depend on that file byte-for-byte, so it is read-only here.

Events A to J are all unscheduled steps or spikes with no precursor: the base
generator writes multipliers only inside `[start_time, end_time]` and nothing at
all outside, so there is no ramp for a forecaster to extrapolate.  They stay the
contrast set and are never modified.

Week 6 (Forecasting and RCA) needs shapes that A to J do not contain.  Each row
below has to buy a distinct teaching function, otherwise it is not worth the
extra data:

  K         night egress ramp that crosses the capacity threshold T
            -> the one shape where a forecast track beats residual SPC     7427
  K_BENIGN  the same shape at 0.63 x T, never crosses
            -> the control that proves the lead time is not self-praise    7427
  M         ramp of a different length and steepness, on a different port
            -> HELD-OUT generalisation test; never tune anything on it     7429
  N         benign multi-week trend growth, seasonal shape unchanged
            -> "the forecast saw it and still must not page anyone"        7430
  P         day-end batch whose peak grows and whose finish time slips
            -> time-to-threshold in DAYS: capacity planning, not paging    7431
  Q         recurring SCHEDULED market-open microburst, weekdays only
            -> the legitimate use of a known-in-advance regressor h(t)     7429
  R         traffic DROP with rising retransmissions
            -> any one-sided control limit misses it entirely              7428
  L         modest root + much louder downstream symptoms
            -> the loudest symptom is not the root cause             7427 root

This script reads the shipped CSVs, overlays ONLY the declared windows, and
writes three files next to them:

  synthetic_rrd_metrics_week6.csv       the metrics, same schema, same row count
  synthetic_event_catalog_week6.csv     A..J plus the new catalogued events
  synthetic_scheduled_calendar_week6.csv   the RECURRING, KNOWN-IN-ADVANCE jobs

The third file is the point of event Q.  Q is normal behaviour, not an anomaly,
so it must never appear in the event catalog: putting it there would repeat the
cell-32 leak (feeding the true label of an *unknown* event into
`add_regressor`).  A published schedule of a job that runs every trading day is
the one thing a regressor is allowed to know in advance, and this file is how a
lab loader gets it.

Conventions are inherited from `simulator_rrd_metrics.ipynb`:
  * 5-minute polling grid, 43,200 rows, sorted by device_id, port_id, timestamp
  * INOCTETS / OUTOCTETS are float rounded to 2 decimals; every other metric is
    a non-negative integer counter
  * multipliers are applied inside `[start_time, end_time]` and nowhere else
  * the catalog carries exactly: event_id, event_type, port_id, start_time,
    periods_5min, description, end_time

Invariants this script asserts on every run:
  * every row outside a declared window is byte-for-byte identical to the source
  * no NEW overlay touches a row that belongs to events A to J
  * no two catalogued windows share a (port, timestamp)
  * every port keeps at least MIN_CLEAN_PORT_DAYS event-free port-days

One thing the catalog cannot express
-----------------------------------
A catalog row carries exactly one `[start_time, end_time]` pair, so a RECURRING
event has to be summarised by a bounding box.  Event P is eleven nightly blocks
between 02-20 and 03-02, and its box therefore sweeps over event H (02-22) and
event L (02-28) on port 7431 even though it shares no 5-minute row with either.
`run()` reports both facts separately: `collisions` is the check that matters
(shared rows, must be empty) and `box_overlaps` is the warning that a naive
slice by catalog window on port 7431 would pull in a neighbour's rows.  Slicing
by `event_id` on the metrics file is always unambiguous: no row carries two.

Every port has an event on 02-19 and 02-22 (G and H are five-port events), so no
7-to-10 day window anywhere in the post-training period can avoid a box overlap.
This is a limit of the schema, not a placement mistake.

Everything tunable lives in the single `CONFIG` dict below, so shapes can be
swept without touching the code, and `run(config)` accepts an overridden copy.
Every event draws from its own `default_rng([seed, n])` stream, so adding an
event never perturbs the numbers of an event that already exists.

Run:
    uv run --no-project --python 3.11 --with "pandas>=2.2" \
        --with "numpy>=1.26,<2.1" python simulator_week6_mitake.py
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# CONFIG : the only thing a tuning sweep needs to touch
# --------------------------------------------------------------------------- #

CONFIG: dict = {
    # provenance ------------------------------------------------------------
    "seed": 20260821,
    "source_metrics": "synthetic_rrd_metrics.csv",
    "source_catalog": "synthetic_event_catalog.csv",
    "out_metrics": "synthetic_rrd_metrics_week6.csv",
    "out_catalog": "synthetic_event_catalog_week6.csv",
    "out_calendar": "synthetic_scheduled_calendar_week6.csv",
    "min_clean_port_days": 8,
    # capacity threshold T --------------------------------------------------
    # T = quantile(traffic_total on T_PORT before T_TRAIN_END) * T_MARGIN.
    # This is the same T the Lab 06 forecast rules compare against, so the
    # plateau heights below are expressed as multiples of it.
    "T_PORT": "port-id7427",
    "T_TRAIN_END": "2026-02-24",
    "T_QUANTILE": 0.97,
    "T_MARGIN": 1.05,
    "T_EXCLUDE_EVENT_ROWS": False,
    # A second, head-roomed capacity definition, reported alongside the
    # notebook one.  q97 x 1.05 is crossed by the NATURAL series on 20 to 22 of
    # the 30 days on every port, so it cannot carry a "never crosses T" claim.
    "T_HEADROOM_QUANTILE": 0.999,
    "T_HEADROOM_MARGIN": 1.10,
    # shared batch-ramp shape (K and K_BENIGN use the SAME shape on purpose) --
    # RAMP/PLATEAU were retuned 2026-08-08 from 150/210.  A 150 min ramp crosses T
    # only 125 min after it starts, which caps the achievable lead time below the
    # 60 to 90 min the Mitake response window needs; 330 min moves the crossing to
    # 305 min in and leaves the room the forecast horizon needs to spend.  PLATEAU
    # 180 keeps the whole batch inside 20:00 -> 05:00, clear of the morning ramp.
    "RAMP_MINUTES": 330,  # linear 0 -> plateau
    "PLATEAU_MINUTES": 180,  # flat top
    "DECAY_MINUTES": 30,  # linear plateau -> 0
    "BATCH_NOISE_SIGMA": 0.06,  # lognormal jitter on the injected load
    "PKT_OCTET_RATIO": 3.5,  # OUTUCASTPKTS-per-byte of the batch, relative to
    # the port's own natural packets-per-byte.
    # >1 means smaller packets (the SMS fingerprint).
    "IN_DIRECTION_FRACTION": 0.02,  # inbound ACK share of the injected load
    # event K : malignant month-end SMS batch --------------------------------
    "K_PORT": "port-id7427",
    "K_START": "2026-02-26 20:00",
    "K_PLATEAU_MULT_OF_T": 1.07,
    "K_DISCARD_LAG_MINUTES": 30,  # after traffic_total first crosses T
    "K_DISCARD_PEAK": 140.0,  # OUTDISCARDS lambda at full overshoot
    # event K_BENIGN : same shape, harmless height ---------------------------
    "KB_START": "2026-02-25 20:00",
    "KB_PLATEAU_MULT_OF_T": 0.63,
    # ----------------------------------------------------------------------- #
    # batch history and its queue-loading precursor
    # ----------------------------------------------------------------------- #
    # Why these exist.  K and K_BENIGN are the same shape and differ only in the
    # height the ramp finally reaches, so before the crossing nothing observable
    # separates them and no forecast can warn.  Warning early needs two things
    # the record did not have: earlier runs of the same batch family to learn
    # from, and something measurable BEFORE a run that says how large tonight's
    # will be.
    #
    # The mechanism is the queue.  A batch is loaded before it is drained: in the
    # 90 minutes before a run starts the work items are pushed in, which the port
    # sees as many small inbound packets and only a few extra bytes.  How large
    # that burst is scales with the volume about to go out.  The burst is shaped
    # as a hump that reaches zero at both ends; a flat block would step DOWN the
    # moment the batch starts and teach a model that a packet surge is followed
    # by a traffic fall, which is the opposite of what happens.
    #
    # The runs sit on 7428 and 7430.  The three ports left out are left out for
    # reasons that are not about results: 7427 is the demo port and its Prophet
    # fit has to stay comparable to the earlier round, 7429 carries M and putting
    # batch history on the held-out port removes the thing M tests, and 7431
    # already runs the 22:00 reconciliation batch.
    "BATCH_HISTORY_ENABLED": True,
    "BATCH_HISTORY_RAMP_MINUTES": 330.0,
    "BATCH_HISTORY_PLATEAU_MINUTES": 180.0,
    "BATCH_HISTORY_DECAY_MINUTES": 30.0,
    "BATCH_HISTORY_NOISE_SIGMA": 0.06,
    "BATCH_HISTORY_PKT_OCTET_RATIO": 3.5,
    "BATCH_HISTORY_OUT_SHARE": 0.98,
    "BATCH_HISTORY_T_TRAIN_END": "2026-02-24",
    # port, start, plateau as a multiple of that port's OWN capacity, kind, text.
    # Fourteen of the sixteen stay under 0.95 of their port's capacity, because
    # routine scheduled work that overloads its own link every week would have
    # been fixed long before it reached a training set.  Two are left over the
    # line on purpose: without a run that actually crossed, the record holds no
    # example of what a ramp going over looks like, and a model that has never
    # seen one cannot project one.
    "BATCH_HISTORY_RUNS": [
        ("port-id7430", "2026-02-01 18:50", 1.18, "desktop_backup", "桌面全量備份"),
        ("port-id7428", "2026-02-02 21:05", 0.60, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7430", "2026-02-03 19:20", 0.57, "desktop_backup", "桌面增量備份"),
        ("port-id7428", "2026-02-04 20:40", 0.88, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7428", "2026-02-05 21:20", 1.15, "partner_file_exchange", "月初對帳檔交換"),
        ("port-id7428", "2026-02-09 20:55", 0.66, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7428", "2026-02-11 21:15", 1.02, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7428", "2026-02-12 20:35", 0.58, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7428", "2026-02-16 21:00", 1.24, "partner_file_exchange", "季度申報檔交換 / 該次把出口推過容量"),
        ("port-id7428", "2026-02-17 20:45", 0.71, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7428", "2026-02-18 21:25", 0.94, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7430", "2026-02-19 19:05", 0.62, "desktop_backup", "桌面增量備份"),
        ("port-id7428", "2026-02-20 20:50", 0.63, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7430", "2026-02-21 18:40", 0.69, "desktop_backup", "桌面增量備份"),
        ("port-id7428", "2026-02-22 21:10", 1.10, "partner_file_exchange", "夥伴檔案交換"),
        ("port-id7430", "2026-02-22 19:15", 1.26, "desktop_backup", "桌面全量備份 / 該次把出口推過容量"),
    ],
    # the queue-loading burst that precedes every batch run, including K,
    # K_BENIGN and M.  It is written only OUTSIDE the run's own window, so every
    # catalogued event keeps the bytes it shipped with.
    "QUEUE_PRECURSOR_ENABLED": True,
    "QUEUE_PRECURSOR_LEAD_MINUTES": 90.0,
    "QUEUE_PRECURSOR_BYTE_FRACTION": 0.030,  # of the run's own per-interval height
    "QUEUE_PRECURSOR_ITEM_BYTES": 40.0,      # a work item is a small packet
    "QUEUE_PRECURSOR_NOISE_SIGMA": 0.12,
    "QUEUE_PRECURSOR_KIND": "batch_queue_loading",
    "QUEUE_PRECURSOR_DESCRIPTION": "派送前的工單入列 / 封包數上升而位元組僅微增",
    # ----------------------------------------------------------------------- #
    # event M : held-out generalisation test (NEVER tune anything on this)
    # ----------------------------------------------------------------------- #
    # Deliberately unlike K: different port, its OWN threshold, a shorter and
    # therefore steeper ramp, a higher plateau.  Still a ramp, not a staircase:
    # the 2026-08-08 sweep showed a 3-step staircase buys 12.5 min of lead and
    # misses 6 times out of 10, because slope extrapolation goes blind on a
    # step's flat top.  Making the held-out set a staircase would spend it on
    # testing something already known to fail.
    # Night, not mid-session: during trading hours the natural series already
    # crosses T on 22 of 30 days, so "crossing" carries no information there.
    "M_PORT": "port-id7429",
    "M_START": "2026-02-24 20:00",  # Tue night, first night after T_TRAIN_END
    "M_RAMP_MINUTES": 240,
    "M_PLATEAU_MINUTES": 180,
    "M_DECAY_MINUTES": 30,
    "M_PLATEAU_MULT_OF_T": 1.12,  # of port 7429's OWN T, not 7427's
    "M_T_TRAIN_END": "2026-02-24",
    "M_PKT_OCTET_RATIO": 2.6,
    "M_IN_DIRECTION_FRACTION": 0.35,  # quote feed comes in, fan-out goes out
    "M_NOISE_SIGMA": 0.06,
    "M_DISCARD_LAG_MINUTES": 25,
    "M_DISCARD_PEAK": 110.0,
    # ----------------------------------------------------------------------- #
    # event N : benign multi-week capacity growth
    # ----------------------------------------------------------------------- #
    # 02-05 to 02-18 is the only stretch on 7430 with no A..J rows in it
    # (A 02-04, G 02-19, H 02-22, I 02-25), and NEW overlays are not allowed to
    # touch A..J rows.  The window therefore has to start and end at zero
    # amplitude, otherwise the level would step at the boundary.
    "N_PORT": "port-id7430",
    "N_START": "2026-02-05 00:00",
    "N_PEAK_AT": "2026-02-16 00:00",  # smooth rise, 11 days
    "N_HOLD_UNTIL": "2026-02-16 12:00",
    "N_END": "2026-02-18 23:55",
    "N_AMPLITUDE": 0.22,  # +22% on the trend at the peak
    "N_NOISE_SIGMA": 0.015,
    # "never crosses T" needs a T with head-room.  q97 x 1.05 has none: the
    # NATURAL series is already over it on 20 to 22 of the 30 days on every
    # single port, so no whole-day event can be below it.  N is measured against
    # the port's own observed ceiling instead, and the q97 numbers are reported
    # next to it so the difference is visible rather than hidden.
    "N_CAPACITY_MARGIN": 1.15,  # x max(traffic_total) over that port's normal rows
    # ----------------------------------------------------------------------- #
    # event P : day-end reconciliation batch, drifting over DAYS
    # ----------------------------------------------------------------------- #
    # The batch has to already be in the training data, otherwise its first
    # appearance is a step and residual SPC fires on day one.  So the stable
    # batch runs every day of the record and is published in the schedule file
    # as normal behaviour; only the DRIFT is catalogued as event P.
    # 22:00 start keeps every block clear of event H (02-22 20:05 to 21:30) and
    # of event C (02-08 01:00 to 03:55).
    "P_PORT": "port-id7431",
    "P_BATCH_START_HHMM": "22:00",
    "P_RAMP_MINUTES": 30,
    "P_PLATEAU_MINUTES": 90,  # stable-phase flat top
    # A long, soft taper matters more than it looks.  A short decay turns the
    # duration slip into a cliff against the learnt per-slot baseline, and then
    # residual SPC fires on drift day one, which would destroy the contrast this
    # event exists to make.  90 min of taper keeps the slip gradual.
    "P_DECAY_MINUTES": 90,
    "P_BASE_HEIGHT": 40.0e6,  # added bytes / 5 min at the stable plateau
    "P_DRIFT_START": "2026-02-20",  # first day the batch grows
    "P_DRIFT_DAYS": 10,  # 02-20 .. 03-01, then held
    "P_HEIGHT_GROWTH_PER_DAY": 0.040,  # +4% / day, compounding
    "P_SLIP_MINUTES_PER_DAY": 8.0,  # plateau gets this much longer each day
    "P_OUT_SHARE": 0.18,  # a write-heavy batch: mostly ingress
    "P_PKT_OCTET_RATIO": 0.55,  # large frames -> avg_packet_size rises
    "P_NOISE_SIGMA": 0.10,  # day-to-day volume of a real batch is not constant
    "P_T_QUANTILE": 0.97,
    "P_T_MARGIN": 1.05,
    # ----------------------------------------------------------------------- #
    # event Q : recurring SCHEDULED market-open microburst (NOT an anomaly)
    # ----------------------------------------------------------------------- #
    # Present on every trading day, absent at weekends.  This is the one effect
    # a regressor is allowed to know about in advance, which is what makes it
    # the rehabilitation of add_regressor after the lab condemns the cell-32
    # usage.  It is written to the schedule file, never to the event catalog.
    "Q_PORT": "port-id7429",
    "Q_BURSTS": [
        # (label, HH:MM, [per-5-min multiplier profile])
        ("market_open_microburst", "09:00", [1.55, 1.42, 1.28, 1.16, 1.07, 1.02]),
        ("market_close_auction", "13:25", [1.20, 1.30, 1.16]),
    ],
    "Q_PKT_OCTET_RATIO": 1.9,  # quote messages are small
    "Q_MCAST_SHARE": 0.6,  # market data rides multicast
    "Q_NOISE_SIGMA": 0.05,
    # ----------------------------------------------------------------------- #
    # event R : partial upstream failure, traffic DROPS
    # ----------------------------------------------------------------------- #
    "R_PORT": "port-id7428",
    "R_START": "2026-03-02 09:30",  # Monday, inside the busy part of the day
    "R_PERIODS": 31,  # 09:30 -> 12:00
    "R_TRANSITION_MINUTES": 20,  # in and out
    "R_DEPTH": 0.72,  # keeps 28% of the seasonal baseline
    "R_ERROR_LAMBDA": 16.0,  # per direction / 5 min at full depth
    "R_DISCARD_LAMBDA": 22.0,
    "R_PKT_OCTET_RATIO": 1.35,  # what survives is retry-heavy, small frames
    # ----------------------------------------------------------------------- #
    # PHYSICAL COUPLING : upstream errors -> downstream retransmission
    # ----------------------------------------------------------------------- #
    # This is a mechanism, not an event.  Nothing in the lab topology says the
    # five ports are independent: 7427 and 7428 are the two WAN uplinks into
    # edge-fw-01, and 7429 / 7430 / 7431 hang off core-sw-01 behind it, so every
    # north-south flow that terminates on a downstream port has already crossed
    # an uplink.  When an uplink starts losing frames, those flows retransmit,
    # and the retransmitted bytes are counted AGAIN on the downstream port:
    #
    #     traffic_down(t) = base_down(t) * (1 + beta * err_rate_up(t - tau))
    #
    # `err_rate_up` is the notebook's own `error_rate` feature, i.e.
    # (INERRORS + OUTERRORS) / (INUCASTPKTS + OUTUCASTPKTS) on the upstream port.
    # It is identically 0 on 42,142 of the 43,200 shipped rows, so the bracket is
    # exactly 1.0 and the term is a bit-level no-op almost everywhere; it only
    # bites where an upstream port is actually erroring.
    #
    # Two refinements, both physical, both reported rather than hidden:
    #
    #  * err_rate is averaged over a trailing causal window before it is used.
    #    The frozen slow-phase generator emits errors per unit TIME (a Poisson
    #    rate per 5-minute bucket), not per packet, so a raw 5-minute err_rate
    #    tracks 1 / ucast and swings 7x across the day purely because the
    #    denominator does.  A 3-hour causal mean is the link's condition; a
    #    single bucket is mostly the diurnal packet count.  It also gives the
    #    downstream response a memory of hours, which is what makes the rise LAG
    #    the error rise instead of tracking it: measured on the written file, the
    #    cross-correlation of the root's err_rate against 7429's deseasonalised
    #    traffic peaks at +150 min, and against the uncoupled 7428 at r = 0.013.
    #  * beta is per EDGE, not global.  It is the share of the downstream port's
    #    traffic that actually transits that uplink, times the retransmission
    #    amplification.  port-id7428 is `wan-secondary`, a standby that carries
    #    no production north-south flows in this record, so its edges are 0.0.
    #    Turning them on would make event R (03-02 09:30, a 72% throughput
    #    collapse with 32 errors / 5 min on 7428) inject a large undesigned
    #    traffic rise on all three downstream ports on the same morning; the
    #    counterfactual is measured and printed by `run()` rather than assumed.
    "COUPLING_ENABLED": True,
    "COUPLING_START": "2026-02-21 00:00",   # == L_SLOW_START; nothing before it
    "COUPLING_END": None,                   # None = end of record
    "COUPLING_SMOOTH_MINUTES": 180,         # trailing causal mean on err_rate
    "COUPLING_PKT_RATIO": 1.25,             # retransmits skew small: avg_packet_size drifts down
    # A retransmission load is congestion, and congestion on this dataset already
    # means queue drops plus a few errors: event R (`upstream_partial_outage`,
    # 「流量驟降且重傳上升」) raises INERRORS/OUTERRORS and IN/OUTDISCARDS together
    # for exactly this scenario.  The coupling follows that established
    # vocabulary, scaled by the lift it just applied.
    #
    # This is also what makes the Lab 07 z matrix robust instead of lucky.  With
    # no downstream errors at all, `window_zscores` divides by a pre-window sd of
    # exactly 0 on every symptom port and returns 0.0 for error_rate, so the root
    # wins that column by default and gate G1 fails.  The shipped 02-28 placement
    # passed G1 only because ONE background error row happened to land in
    # port-id7429's pre-window (1 of 24 samples, sd 5.0e-6).  A physical error
    # floor on the downstream ports removes the coin flip.
    "COUPLING_ERROR_PER_LIFT": 3.0,     # Poisson errors / direction / 5 min, per unit lift
    "COUPLING_DISCARD_PER_LIFT": 6.0,   # same, for IN/OUTDISCARDS
    "COUPLING_EDGES": [
        # upstream, downstream, beta, tau (minutes).  tau grows with hop count:
        # 7429 / 7430 sit one hop behind core-sw-01, 7431 is one further behind
        # dist-sw-02, so its retransmission backlog builds later.
        {"up": "port-id7427", "down": "port-id7429", "beta": 300.0, "tau": 45},
        {"up": "port-id7427", "down": "port-id7431", "beta": 260.0, "tau": 90},
        {"up": "port-id7427", "down": "port-id7430", "beta": 45.0, "tau": 45},
        {"up": "port-id7428", "down": "port-id7429", "beta": 0.0, "tau": 45},
        {"up": "port-id7428", "down": "port-id7430", "beta": 0.0, "tau": 45},
        {"up": "port-id7428", "down": "port-id7431", "beta": 0.0, "tau": 90},
    ],
    # The coupling obeys the same invariant every other overlay in this file
    # obeys: it never writes into a row another declared event already owns.
    # A row inside K, K_BENIGN, M, N, P, Q, R or A..J is that event's own
    # generator's output and stays byte-for-byte as shipped.  `run()` measures
    # and prints what the coupling WOULD have done to those rows, so the size of
    # what is being withheld is on the record instead of being invisible.
    "COUPLING_RESPECT_DECLARED_EVENTS": True,
    # ----------------------------------------------------------------------- #
    # event L : optical degradation then protection switch (REDESIGNED)
    # ----------------------------------------------------------------------- #
    # Hard requirement: the root port must NOT be argmax(z) on ANY of the eight
    # metrics the notebook shows, yet must be earliest and most upstream.  The
    # first design failed this: a collapsing root is trivially argmax on
    # traffic_total, so `argmax(z)` already picked it and the hybrid had no work
    # to do.  Here the root moves modestly and the two downstream ports move a
    # lot, so every single-metric argmax points at a symptom.
    #
    # The slow phase's rng DRAW is frozen: same start, same window, same lambda,
    # same two `rng.poisson` calls as the 2026-08-08 shipped run.  It runs under
    # the K window on 7427, so changing any of them would change K's rows.  What
    # moved on 2026-08-08 is which rows the draw is APPLIED to: everything from
    # L_SLOW_FROZEN_CUT onwards is now written by the continuation stream below,
    # because the fast phase left 02-28.  The draw is still made over the whole
    # frozen array so the stream position, and therefore K's 109 rows, are
    # bit-identical; only the tail of the array is discarded.
    "L_ROOT_PORT": "port-id7427",
    "L_SECONDARY_PORT": "port-id7428",  # must stay QUIET: same edge-fw-01 parent
    "L_SLOW_START": "2026-02-21 00:00",
    "L_ERROR_BASE_PER_INTERVAL": 0.25,  # per direction, at slow-phase start
    "L_ERROR_DAILY_GROWTH": 1.20,  # +20% per day, relative
    "L_ERROR_FADE_IN_HOURS": 6.0,  # soften the onset step
    "L_SLOW_FROZEN_END": "2026-02-28 13:00",  # end of the frozen DRAW (do not move)
    "L_SLOW_FROZEN_CUT": "2026-02-28 09:05",  # last frozen row APPLIED (do not move)
    # The lambda multiplier the SHIPPED run put on the frozen array's tail.  It
    # is a literal, not a tunable: `rng.poisson` over an array consumes a
    # value-dependent number of uniforms, so changing lambda anywhere in the
    # array moves the stream position for the SECOND call and therefore changes
    # K's OUTERRORS, 109 rows that are supposed to be frozen.  The tail's drawn
    # values are discarded, but the draw itself has to happen exactly as it did.
    "L_SLOW_FROZEN_TAIL_MULT": 4.0,
    # ----------------------------------------------------------------------- #
    # RELOCATED 2026-08-08.  The fast phase used to sit on 2026-02-28, which is a
    # Saturday AND 和平紀念日, while the lecture scripts it as 盤中.  TWSE's own
    # 115 年市場開休市日期 closes 02-27 (和平紀念日 makeup for the 02-28 Saturday),
    # 02-28 and 03-01, so the only genuine trading day left in the record after
    # event K's window closes at 02-27 05:00 is 2026-03-02 (Mon).
    #
    # 14:00, not 09:05, and that is forced by two independent things:
    #  * event R owns 7428 from 09:30 to 12:00 on 03-02 and may not be moved.  A
    #    72% collapse on the port that shares edge-fw-01 with the root would put
    #    7428 in the affected set with exactly the root's reach, which is the one
    #    failure mode this event was redesigned to avoid.  The 2h pre-window has
    #    to clear R too, so t0 >= 14:00.
    #  * the flattest natural window of the day.  On the untouched source series
    #    the same z recipe over 09:00 -> 12:55 already returns |z| up to 4.5 from
    #    the morning ramp alone; over 14:00 -> 17:55 it returns 0.87.  Placing the
    #    event on the afternoon plateau means the z matrix measures the event and
    #    not the time of day.
    "L_LATE_START": "2026-02-28 09:05",  # degradation accelerates (knee)
    "L_LATE_GROWTH": 2.2,  # extra per-day factor from L_LATE_START
    "L_FAST_START": "2026-03-02 14:00",
    "L_FAST_PERIODS": 48,  # 14:00 -> 17:55
    "L_FAST_ERROR_MULT": 2.0,  # error burst at the switch (slow-phase lambda)
    # root, port 7427: modest, and FIRST.  The error step is immediate so the
    # onset lands in the very first bucket of the window; the traffic dip ramps.
    # ERROR_ADD is set so the root's error_rate z lands near 7: high enough to be
    # inside the |z| > 3 affected set (otherwise G(c) is 0 for the root and the
    # topology term cannot carry it), low enough that A(c) still openly favours
    # the symptom, which is what makes "the loudest is not the root" a real
    # demonstration rather than an artefact of A's clip at z = 8.
    "L_ROOT_ERROR_ADD": 0.0,  # extra Poisson errors / direction / 5 min
    "L_ROOT_TRAFFIC_DIP": 0.13,  # loses 13% of throughput
    "L_ROOT_DIP_RAMP_MINUTES": 45,
    # symptom 1, port 7429 (core-sw-01): loud, and LATER
    "L_SYM1_PORT": "port-id7429",
    "L_SYM1_LAG_MINUTES": 35,
    "L_SYM1_RAMP_MINUTES": 20,
    "L_SYM1_TRAFFIC_MULT": 2.6,
    "L_SYM1_PKT_OCTET_RATIO": 1.9,  # retransmit storm -> small frames
    "L_SYM1_ERROR_LAMBDA": 40.0,
    "L_SYM1_DISCARD_LAMBDA": 55.0,
    "L_SYM1_UNKNOWN_LAMBDA": 3.0,
    # symptom 2, port 7431 (dist-sw-02): loud, and LATEST
    "L_SYM2_PORT": "port-id7431",
    "L_SYM2_LAG_MINUTES": 50,
    "L_SYM2_RAMP_MINUTES": 20,
    "L_SYM2_TRAFFIC_MULT": 2.2,
    "L_SYM2_PKT_OCTET_RATIO": 0.6,  # bulk re-sync -> large frames
    "L_SYM2_ERROR_LAMBDA": 12.0,
    "L_SYM2_DISCARD_LAMBDA": 40.0,
    "L_SYM2_UNKNOWN_LAMBDA": 0.0,
    "L_NOISE_SIGMA": 0.05,
    # catalog text ------------------------------------------------------------
    "K_EVENT_TYPE": "batch_egress_saturation",
    "K_DESCRIPTION": "月結簡訊大量送出 / 出口飽和",
    "KB_EVENT_TYPE": "benign_batch_ramp",
    "KB_DESCRIPTION": "良性的簡訊大量送出 / 對照組 (不應告警)",
    "L_EVENT_TYPE": "optical_degradation_failover",
    # The catalog port_id is the ROOT, not "MULTI".  `_truth(ev)` in Lab 07 falls
    # back to "every port carrying this label" when it sees MULTI, which would
    # score a symptom port as a correct hit@1 and quietly destroy the one
    # measurement this event exists to make.
    "L_DESCRIPTION": "光路劣化引發下游重傳風暴與主備切換 / 慢相自 2026-02-21 起錯誤率逐日爬升 (未標記), 下游 port-id7429 與 port-id7431 的流量經重傳耦合落後跟漲, 根因 port-id7427, port-id7428 全程安靜",
    "M_EVENT_TYPE": "quote_push_batch_ramp",
    "M_DESCRIPTION": "除權息旺季行情推播預熱爬坡 / 保留測試集 (不得用於調參)",
    "N_EVENT_TYPE": "benign_capacity_growth",
    "N_DESCRIPTION": "多週良性容量成長 / 趨勢上移但季節形狀不變 (不應告警)",
    "P_EVENT_TYPE": "batch_window_overrun",
    "P_DESCRIPTION": "日終對帳逐日長大且結束時間後移 / 以天為單位逼近容量",
    "R_EVENT_TYPE": "upstream_partial_outage",
    "R_DESCRIPTION": "上游部分失效 / 流量驟降且重傳上升 (單邊上界看不到)",
    "Q_DESCRIPTION": "開盤與收盤集合競價微爆量 / 每個交易日固定發生的排程行為",
    "P_SCHEDULE_DESCRIPTION": "日終對帳 / 每日 22:00 起的排程作業",
}

# --------------------------------------------------------------------------- #
# Schema, copied from simulator_rrd_metrics.ipynb
# --------------------------------------------------------------------------- #

METRIC_COLUMNS = [
    "INOCTETS", "OUTOCTETS",
    "INERRORS", "OUTERRORS",
    "INUCASTPKTS", "OUTUCASTPKTS",
    "INNUCASTPKTS", "OUTNUCASTPKTS",
    "INDISCARDS", "OUTDISCARDS",
    "INUNKNOWNPROTOS",
    "INBROADCASTPKTS", "OUTBROADCASTPKTS",
    "INMULTICASTPKTS", "OUTMULTICASTPKTS",
]
OCTET_COLUMNS = ["INOCTETS", "OUTOCTETS"]
COUNTER_COLUMNS = [c for c in METRIC_COLUMNS if c not in OCTET_COLUMNS]
STRING_COLUMNS = ["timestamp", "device_id", "port_id", "port_role", "event_label", "event_id"]
CATALOG_COLUMNS = [
    "event_id", "event_type", "port_id", "start_time", "periods_5min", "description", "end_time",
]
CALENDAR_COLUMNS = [
    "schedule_id", "kind", "port_id", "start_time", "end_time", "periods_5min", "description",
]

# Columns that carry traffic, i.e. the ones a link failure or failover scales.
TRAFFIC_COLUMNS = [
    "INOCTETS", "OUTOCTETS",
    "INUCASTPKTS", "OUTUCASTPKTS",
    "INNUCASTPKTS", "OUTNUCASTPKTS",
    "INBROADCASTPKTS", "OUTBROADCASTPKTS",
    "INMULTICASTPKTS", "OUTMULTICASTPKTS",
]

# The eight metrics Lab 07 cell 6 shows in the z matrix.  Gate G1 is stated on
# exactly this list.
RCA_METRICS = [
    "traffic_total", "error_rate", "discard_rate", "broadcast_total",
    "multicast_total", "unknown_total", "ucast_total", "avg_packet_size",
]

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _load_metrics(path: Path) -> tuple[pd.DataFrame, pd.Series]:
    """Read the shipped CSV, verify the on-disk schema, return a parsed timestamp.

    Counters are held as float64 while the overlay runs so partial packets can be
    accumulated; `_finalise` puts them back to int64 exactly the way the original
    generator does.
    """
    dtypes = {c: "string" for c in STRING_COLUMNS}
    dtypes.update({c: "float64" for c in OCTET_COLUMNS})
    dtypes.update({c: "int64" for c in COUNTER_COLUMNS})
    df = pd.read_csv(path, dtype=dtypes, keep_default_na=False)
    expected = STRING_COLUMNS[:4] + METRIC_COLUMNS + STRING_COLUMNS[4:]
    if list(df.columns) != expected:
        raise ValueError(f"unexpected metrics schema: {list(df.columns)}")
    # every overlay below indexes with positional integers via .loc, which is only
    # the same thing as label indexing while the index is a clean 0..n-1 range.
    if not df.index.equals(pd.RangeIndex(len(df))):
        raise ValueError("expected a 0..n-1 RangeIndex on the source frame")
    ts = pd.to_datetime(df["timestamp"])
    df[COUNTER_COLUMNS] = df[COUNTER_COLUMNS].astype("float64")
    return df, ts


def _batch_shape(minutes: np.ndarray, ramp: float, plateau: float, decay: float) -> np.ndarray:
    """Trapezoid in [0, 1]: linear ramp, flat plateau, linear decay."""
    frac = np.zeros_like(minutes, dtype=float)
    up = (minutes >= 0) & (minutes < ramp)
    frac[up] = minutes[up] / ramp
    flat = (minutes >= ramp) & (minutes < ramp + plateau)
    frac[flat] = 1.0
    start_decay = ramp + plateau
    down = (minutes >= start_decay) & (minutes <= start_decay + decay)
    frac[down] = 1.0 - (minutes[down] - start_decay) / decay
    return np.clip(frac, 0.0, 1.0)


def _causal_mean(x: np.ndarray, window: int) -> np.ndarray:
    """Trailing mean of `x` over `window` samples, current sample included.

    Causal on purpose: the coupling below feeds this into a physical response, so
    it may never see the future.  Short prefixes average over what exists rather
    than being dropped, which keeps the output the same length as the input.
    """
    window = max(int(window), 1)
    cum = np.concatenate([[0.0], np.cumsum(np.asarray(x, dtype=float))])
    hi = np.arange(1, x.size + 1)
    lo = np.maximum(hi - window, 0)
    return (cum[hi] - cum[lo]) / (hi - lo)


def _smoothstep(u: np.ndarray) -> np.ndarray:
    """Raised cosine 0 -> 1 on u in [0, 1], flat derivative at both ends."""
    u = np.clip(u, 0.0, 1.0)
    return 0.5 * (1.0 - np.cos(np.pi * u))


def _capacity_threshold(df: pd.DataFrame, ts: pd.Series, cfg: dict) -> float:
    port = df["port_id"].to_numpy() == cfg["T_PORT"]
    before = ts.to_numpy() < np.datetime64(pd.Timestamp(cfg["T_TRAIN_END"]))
    sel = port & before
    if cfg["T_EXCLUDE_EVENT_ROWS"]:
        sel = sel & (df["event_label"].to_numpy() == "normal")
    total = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[sel]
    return float(np.quantile(total, cfg["T_QUANTILE"]) * cfg["T_MARGIN"])


def _port_threshold(df: pd.DataFrame, ts: pd.Series, port: str, train_end: str | None,
                    quantile: float, margin: float, *, normal_only: bool = False) -> float:
    """The same rule as `_capacity_threshold`, for any port and any cut date."""
    sel = df["port_id"].to_numpy() == port
    if train_end is not None:
        sel = sel & (ts.to_numpy() < np.datetime64(pd.Timestamp(train_end)))
    if normal_only:
        sel = sel & (df["event_label"].to_numpy() == "normal")
    total = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[sel]
    return float(np.quantile(total, quantile) * margin)


def _free_rows(df: pd.DataFrame, mask: np.ndarray, base_event_id: np.ndarray) -> np.ndarray:
    """Row indices selected by `mask` that do NOT belong to events A to J.

    New overlays are forbidden from touching A..J rows: labs 00 to 02 and every
    round-1 number depend on those rows passing through untouched.
    """
    return np.flatnonzero(mask & (base_event_id == ""))


def _inject_load(df: pd.DataFrame, idx: np.ndarray, add_total: np.ndarray,
                 *, out_share: float, pkt_ratio: float) -> None:
    """Add `add_total` bytes / 5 min on `idx`, split by direction, with a packet
    fingerprint.

    Additive, not multiplicative, so the natural lognormal texture of the base
    series survives underneath, which is what makes an injected window look
    native next to events A to J.  `pkt_ratio` is packets-per-byte of the
    injected load relative to the port's own natural packets-per-byte: > 1 means
    smaller packets, < 1 means larger ones.
    """
    in_src = df["INOCTETS"].to_numpy()[idx]
    out_src = df["OUTOCTETS"].to_numpy()[idx]
    in_pkt = df["INUCASTPKTS"].to_numpy()[idx].astype(float)
    out_pkt = df["OUTUCASTPKTS"].to_numpy()[idx].astype(float)

    add_out = add_total * out_share
    add_in = add_total * (1.0 - out_share)

    ps_out = np.divide(out_src, out_pkt, out=np.full(idx.size, 900.0), where=out_pkt > 0)
    ps_in = np.divide(in_src, in_pkt, out=np.full(idx.size, 900.0), where=in_pkt > 0)

    df.loc[idx, "OUTOCTETS"] = out_src + add_out
    df.loc[idx, "INOCTETS"] = in_src + add_in
    df.loc[idx, "OUTUCASTPKTS"] = out_pkt + pkt_ratio * add_out / ps_out
    df.loc[idx, "INUCASTPKTS"] = in_pkt + pkt_ratio * add_in / ps_in


def _scale_traffic(df: pd.DataFrame, idx: np.ndarray, factor: np.ndarray,
                   *, pkt_ratio: float = 1.0, columns: list[str] | None = None) -> None:
    """Multiply the traffic counters on `idx` by a per-row `factor`.

    `pkt_ratio` applies an extra factor to the unicast packet counters only, so
    the injected share of the traffic can carry a different average frame size
    than the underlying series.  factor == 1 rows are left exactly alone.
    """
    cols = TRAFFIC_COLUMNS if columns is None else columns
    for col in cols:
        vals = df[col].to_numpy()[idx]
        f = factor
        if pkt_ratio != 1.0 and col in ("INUCASTPKTS", "OUTUCASTPKTS"):
            f = 1.0 + (factor - 1.0) * pkt_ratio
        df.loc[idx, col] = vals * f


def _add_counter(df: pd.DataFrame, idx: np.ndarray, column: str, lam: np.ndarray,
                 rng: np.random.Generator) -> np.ndarray:
    """Add Poisson(lam) counts to `column` on `idx`; returns what was added."""
    drops = rng.poisson(np.clip(lam, 0.0, None))
    df.loc[idx, column] = df[column].to_numpy()[idx] + drops
    return drops


def _label(df: pd.DataFrame, idx: np.ndarray, event_id: str, event_type: str) -> None:
    df.loc[idx, "event_label"] = event_type
    df.loc[idx, "event_id"] = event_id


# --------------------------------------------------------------------------- #
# Overlays : K and K_BENIGN (FROZEN, byte-identical to the 2026-08-08 run)
# --------------------------------------------------------------------------- #

def _overlay_batch_ramp(
    df: pd.DataFrame,
    ts: pd.Series,
    cfg: dict,
    *,
    event_id: str,
    event_type: str,
    description: str,
    port_id: str,
    start: str,
    plateau_mult: float,
    threshold: float,
    with_discards: bool,
    rng: np.random.Generator,
) -> dict:
    """Additive out-direction batch load: linear ramp, plateau, decay.

    Additive (not multiplicative) so the natural lognormal texture of the base
    series survives underneath, which is what makes the injected window look
    native next to events A to J.
    """
    ramp = float(cfg["RAMP_MINUTES"])
    plateau = float(cfg["PLATEAU_MINUTES"])
    decay = float(cfg["DECAY_MINUTES"])
    total_minutes = ramp + plateau + decay

    start_ts = pd.Timestamp(start)
    port_mask = df["port_id"].to_numpy() == port_id
    minutes_all = (ts.to_numpy() - np.datetime64(start_ts)) / np.timedelta64(1, "m")
    win = port_mask & (minutes_all >= 0) & (minutes_all <= total_minutes)
    idx = np.flatnonzero(win)
    if idx.size == 0:
        raise ValueError(f"event {event_id}: empty window at {start} on {port_id}")

    minutes = minutes_all[idx].astype(float)
    frac = _batch_shape(minutes, ramp, plateau, decay)

    in_src = df["INOCTETS"].to_numpy()[idx]
    out_src = df["OUTOCTETS"].to_numpy()[idx]
    in_pkt_src = df["INUCASTPKTS"].to_numpy()[idx].astype(float)
    out_pkt_src = df["OUTUCASTPKTS"].to_numpy()[idx].astype(float)

    # Height: put the flat top at `plateau_mult * T` of traffic_total.
    plateau_rows = frac >= 1.0
    natural_plateau_total = float((in_src + out_src)[plateau_rows].mean())
    in_frac = float(cfg["IN_DIRECTION_FRACTION"])
    batch_out = (plateau_mult * threshold - natural_plateau_total) / (1.0 + in_frac)
    if batch_out <= 0:
        raise ValueError(f"event {event_id}: plateau {plateau_mult} x T is below the natural floor")

    noise = rng.lognormal(mean=0.0, sigma=float(cfg["BATCH_NOISE_SIGMA"]), size=idx.size)
    add_out = batch_out * frac * noise
    add_in = in_frac * add_out

    # Small-packet fingerprint: the batch carries PKT_OCTET_RATIO times as many
    # packets per byte as the port normally does, so avg_packet_size collapses.
    ratio = float(cfg["PKT_OCTET_RATIO"])
    ps_out = np.divide(out_src, out_pkt_src, out=np.full(idx.size, 900.0), where=out_pkt_src > 0)
    ps_in = np.divide(in_src, in_pkt_src, out=np.full(idx.size, 900.0), where=in_pkt_src > 0)
    add_out_pkts = ratio * add_out / ps_out
    add_in_pkts = ratio * add_in / ps_in

    df.loc[idx, "OUTOCTETS"] = out_src + add_out
    df.loc[idx, "INOCTETS"] = in_src + add_in
    df.loc[idx, "OUTUCASTPKTS"] = out_pkt_src + add_out_pkts
    df.loc[idx, "INUCASTPKTS"] = in_pkt_src + add_in_pkts

    total_new = (in_src + add_in) + (out_src + add_out)

    # Secondary effect: OUTDISCARDS only lifts off some minutes AFTER the link
    # is actually over the threshold, and scales with the overshoot.
    discard_onset = None
    peak_discards = 0
    if with_discards:
        over = np.flatnonzero(total_new >= threshold)
        if over.size:
            cross_minute = minutes[over[0]]
            onset_minute = cross_minute + float(cfg["K_DISCARD_LAG_MINUTES"])
            headroom = max(plateau_mult - 1.0, 1e-9) * threshold
            severity = np.clip((total_new - threshold) / headroom, 0.0, 1.0)
            severity[minutes < onset_minute] = 0.0
            lam = float(cfg["K_DISCARD_PEAK"]) * severity
            drops = rng.poisson(lam)
            df.loc[idx, "OUTDISCARDS"] = df["OUTDISCARDS"].to_numpy()[idx] + drops
            live = np.flatnonzero(drops > 0)
            if live.size:
                discard_onset = pd.Timestamp(ts.to_numpy()[idx[live[0]]])
            peak_discards = int(drops.max())

    df.loc[idx, "event_label"] = event_type
    df.loc[idx, "event_id"] = event_id

    total_src = in_src + out_src
    crossed = np.flatnonzero(total_new >= threshold)
    return {
        "event_id": event_id,
        "event_type": event_type,
        "port_id": port_id,
        "description": description,
        "start_ts": pd.Timestamp(ts.to_numpy()[idx[0]]),
        "end_ts": pd.Timestamp(ts.to_numpy()[idx[-1]]),
        "periods": int(idx.size),
        "rows": idx,
        "ports": [port_id],
        "catalogued": True,
        "threshold": threshold,
        "metrics": "INOCTETS, OUTOCTETS, INUCASTPKTS, OUTUCASTPKTS"
                   + (", OUTDISCARDS" if with_discards else ""),
        "batch_out": float(batch_out),
        "peak_multiple": float((total_new / total_src).max()),
        "plateau_over_T": float(total_new[plateau_rows].mean() / threshold),
        "peak_over_T": float(total_new.max() / threshold),
        "crossed_T_at": pd.Timestamp(ts.to_numpy()[idx[crossed[0]]]) if crossed.size else None,
        "discard_onset": discard_onset,
        "peak_discards": peak_discards,
        "avg_pkt_plateau": float(total_new[plateau_rows].sum()
                                 / (in_pkt_src + add_in_pkts + out_pkt_src + add_out_pkts)[plateau_rows].sum()),
        # direction asymmetry: the whole point of K is that only the egress moves
        "out_multiple_plateau": float(((out_src + add_out) / out_src)[plateau_rows].mean()),
        "in_multiple_plateau": float(((in_src + add_in) / in_src)[plateau_rows].mean()),
    }


# --------------------------------------------------------------------------- #
# Overlay : event M, the held-out ramp
# --------------------------------------------------------------------------- #

def _overlay_holdout_ramp(df: pd.DataFrame, ts: pd.Series, cfg: dict, base_event_id: np.ndarray,
                          *, threshold: float, rng: np.random.Generator) -> dict:
    """Event M.  Same family as K, deliberately different numbers.

    Shorter ramp (steeper), higher plateau, its own port, its own threshold, and
    a more balanced direction split because a quote feed comes in and fans out.
    """
    ramp = float(cfg["M_RAMP_MINUTES"])
    plateau = float(cfg["M_PLATEAU_MINUTES"])
    decay = float(cfg["M_DECAY_MINUTES"])
    total_minutes = ramp + plateau + decay
    port_id = cfg["M_PORT"]

    start_ts = pd.Timestamp(cfg["M_START"])
    minutes_all = (ts.to_numpy() - np.datetime64(start_ts)) / np.timedelta64(1, "m")
    win = ((df["port_id"].to_numpy() == port_id)
           & (minutes_all >= 0) & (minutes_all <= total_minutes))
    idx = _free_rows(df, win, base_event_id)
    if idx.size == 0:
        raise ValueError("event M: empty window")

    minutes = minutes_all[idx].astype(float)
    frac = _batch_shape(minutes, ramp, plateau, decay)
    plateau_rows = frac >= 1.0

    total_src = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
    natural_plateau = float(total_src[plateau_rows].mean())
    height = float(cfg["M_PLATEAU_MULT_OF_T"]) * threshold - natural_plateau
    if height <= 0:
        raise ValueError("event M: plateau is below the natural floor")

    noise = rng.lognormal(0.0, float(cfg["M_NOISE_SIGMA"]), size=idx.size)
    add_total = height * frac * noise
    out_share = 1.0 - float(cfg["M_IN_DIRECTION_FRACTION"])
    _inject_load(df, idx, add_total, out_share=out_share,
                 pkt_ratio=float(cfg["M_PKT_OCTET_RATIO"]))

    total_new = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]

    discard_onset, peak_discards = None, 0
    over = np.flatnonzero(total_new >= threshold)
    if over.size:
        onset_minute = minutes[over[0]] + float(cfg["M_DISCARD_LAG_MINUTES"])
        headroom = max(float(cfg["M_PLATEAU_MULT_OF_T"]) - 1.0, 1e-9) * threshold
        severity = np.clip((total_new - threshold) / headroom, 0.0, 1.0)
        severity[minutes < onset_minute] = 0.0
        drops = _add_counter(df, idx, "OUTDISCARDS", float(cfg["M_DISCARD_PEAK"]) * severity, rng)
        live = np.flatnonzero(drops > 0)
        if live.size:
            discard_onset = pd.Timestamp(ts.to_numpy()[idx[live[0]]])
        peak_discards = int(drops.max())

    _label(df, idx, "M", cfg["M_EVENT_TYPE"])
    ucast_new = (df["INUCASTPKTS"].to_numpy() + df["OUTUCASTPKTS"].to_numpy())[idx]
    crossed = np.flatnonzero(total_new >= threshold)
    return {
        "event_id": "M", "event_type": cfg["M_EVENT_TYPE"], "port_id": port_id,
        "description": cfg["M_DESCRIPTION"],
        "start_ts": pd.Timestamp(ts.to_numpy()[idx[0]]),
        "end_ts": pd.Timestamp(ts.to_numpy()[idx[-1]]),
        "periods": int(idx.size), "rows": idx, "ports": [port_id], "catalogued": True,
        "threshold": threshold,
        "metrics": "INOCTETS, OUTOCTETS, INUCASTPKTS, OUTUCASTPKTS, OUTDISCARDS",
        "batch_out": float(height),
        "peak_multiple": float((total_new / total_src).max()),
        "plateau_over_T": float(total_new[plateau_rows].mean() / threshold),
        "peak_over_T": float(total_new.max() / threshold),
        "crossed_T_at": pd.Timestamp(ts.to_numpy()[idx[crossed[0]]]) if crossed.size else None,
        "minutes_ramp_to_cross": float(minutes[crossed[0]]) if crossed.size else None,
        "discard_onset": discard_onset, "peak_discards": peak_discards,
        "avg_pkt_plateau": float(total_new[plateau_rows].sum() / ucast_new[plateau_rows].sum()),
    }


# --------------------------------------------------------------------------- #
# Overlay : event N, benign multi-week growth
# --------------------------------------------------------------------------- #

def _overlay_trend_growth(df: pd.DataFrame, ts: pd.Series, cfg: dict, base_event_id: np.ndarray,
                          *, rng: np.random.Generator) -> dict:
    """Event N.  A multiplicative level shift that moves ONLY the trend.

    Multiplying every traffic counter by the same slowly varying factor leaves
    the shape of the day untouched, which is exactly what "g(t) moves, s(t) does
    not" means in a Prophet decomposition.
    """
    port_id = cfg["N_PORT"]
    t0, t_peak = pd.Timestamp(cfg["N_START"]), pd.Timestamp(cfg["N_PEAK_AT"])
    t_hold, t1 = pd.Timestamp(cfg["N_HOLD_UNTIL"]), pd.Timestamp(cfg["N_END"])
    ts_np = ts.to_numpy()
    win = ((df["port_id"].to_numpy() == port_id)
           & (ts_np >= np.datetime64(t0)) & (ts_np <= np.datetime64(t1)))
    idx = _free_rows(df, win, base_event_id)

    t = pd.to_datetime(ts_np[idx])
    up = (t - t0) / (t_peak - t0)
    down = (t1 - t) / (t1 - t_hold)
    shape = np.where(t < t_peak, _smoothstep(np.asarray(up, dtype=float)),
                     np.where(t <= t_hold, 1.0, _smoothstep(np.asarray(down, dtype=float))))
    amp = float(cfg["N_AMPLITUDE"])
    jitter = rng.lognormal(0.0, float(cfg["N_NOISE_SIGMA"]), size=idx.size)
    factor = 1.0 + amp * shape * jitter

    total_src = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
    _scale_traffic(df, idx, factor)
    total_new = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
    _label(df, idx, "N", cfg["N_EVENT_TYPE"])

    daily = pd.DataFrame({"d": t.floor("D"), "src": total_src, "new": total_new})
    peaks = daily.groupby("d").max()
    return {
        "event_id": "N", "event_type": cfg["N_EVENT_TYPE"], "port_id": port_id,
        "description": cfg["N_DESCRIPTION"],
        "start_ts": pd.Timestamp(ts_np[idx[0]]), "end_ts": pd.Timestamp(ts_np[idx[-1]]),
        "periods": int(idx.size), "rows": idx, "ports": [port_id], "catalogued": True,
        "metrics": "all traffic counters, multiplicative",
        "peak_multiple": float((total_new / total_src).max()),
        "max_factor": float(factor.max()),
        "window_max": float(total_new.max()),
        "daily_peaks_src": peaks["src"].to_numpy(),
        "daily_peaks_new": peaks["new"].to_numpy(),
        "daily_index": [pd.Timestamp(d) for d in peaks.index],
    }


# --------------------------------------------------------------------------- #
# Overlay : event P, the day-end batch that grows and slips
# --------------------------------------------------------------------------- #

def _overlay_nightly_batch(df: pd.DataFrame, ts: pd.Series, cfg: dict, base_event_id: np.ndarray,
                           *, rng: np.random.Generator) -> tuple[dict, dict]:
    """The 22:00 reconciliation batch (background) and its drift (event P).

    The batch runs every day of the record.  Days before P_DRIFT_START are the
    stable phase: they are normal behaviour, published in the schedule file and
    NOT catalogued, because a batch that first appears mid-record would be a step
    and residual SPC would fire on day one, which would destroy the very contrast
    the event exists to teach.
    """
    port_id = cfg["P_PORT"]
    ts_np = ts.to_numpy()
    port_mask = df["port_id"].to_numpy() == port_id
    hh, mm = (int(x) for x in str(cfg["P_BATCH_START_HHMM"]).split(":"))

    ramp = float(cfg["P_RAMP_MINUTES"])
    plateau0 = float(cfg["P_PLATEAU_MINUTES"])
    decay = float(cfg["P_DECAY_MINUTES"])
    h0 = float(cfg["P_BASE_HEIGHT"])
    growth = float(cfg["P_HEIGHT_GROWTH_PER_DAY"])
    slip = float(cfg["P_SLIP_MINUTES_PER_DAY"])
    drift_start = pd.Timestamp(cfg["P_DRIFT_START"])
    drift_days = int(cfg["P_DRIFT_DAYS"])

    days = pd.date_range(pd.Timestamp(ts_np.min()).normalize(),
                         pd.Timestamp(ts_np.max()).normalize(), freq="D")

    stable_rows, drift_rows = [], []
    occurrences, daily = [], []
    for day in days:
        d = (day - drift_start).days
        if d < 0:
            k = 0.0
        else:
            k = float(min(d, drift_days - 1) + 1)   # day 1 of the drift is +1 step
        height = h0 * (1.0 + growth) ** k
        plateau = plateau0 + slip * k
        block_start = day + pd.Timedelta(hours=hh, minutes=mm)
        total_minutes = ramp + plateau + decay
        minutes_all = (ts_np - np.datetime64(block_start)) / np.timedelta64(1, "m")
        win = port_mask & (minutes_all >= 0) & (minutes_all <= total_minutes)
        idx = _free_rows(df, win, base_event_id)
        if idx.size == 0:
            continue
        minutes = minutes_all[idx].astype(float)
        frac = _batch_shape(minutes, ramp, plateau, decay)
        jitter = rng.lognormal(0.0, float(cfg["P_NOISE_SIGMA"]), size=idx.size)
        _inject_load(df, idx, height * frac * jitter,
                     out_share=float(cfg["P_OUT_SHARE"]),
                     pkt_ratio=float(cfg["P_PKT_OCTET_RATIO"]))
        total_new = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
        drifting = d >= 0
        (drift_rows if drifting else stable_rows).append(idx)
        daily.append({
            "day": day, "drift_step": k, "height": height,
            "plateau_minutes": plateau,
            "block_start": pd.Timestamp(ts_np[idx[0]]),
            "block_end": pd.Timestamp(ts_np[idx[-1]]),
            "block_peak": float(total_new.max()),
            "drifting": drifting,
            "rows": idx,
            "slot_minutes": minutes,
            "plateau_rows": idx[frac >= 1.0],
            "clipped": int(np.flatnonzero(win).size - idx.size),   # A..J rows skipped
            "truncated": int(int(total_minutes // 5) + 1 - np.flatnonzero(win).size),
        })
        occurrences.append({
            "schedule_id": "P_BATCH", "kind": "nightly_reconciliation_batch",
            "port_id": port_id,
            "start_time": pd.Timestamp(ts_np[idx[0]]),
            "end_time": pd.Timestamp(ts_np[idx[-1]]),
            "periods_5min": int(idx.size),
            "description": cfg["P_SCHEDULE_DESCRIPTION"]
                           + (f" (drift day {int(k)})" if drifting else " (stable)"),
        })
        if drifting:
            _label(df, idx, "P", cfg["P_EVENT_TYPE"])

    stable = np.concatenate(stable_rows) if stable_rows else np.array([], dtype=int)
    drift = np.concatenate(drift_rows) if drift_rows else np.array([], dtype=int)
    daily_df = pd.DataFrame(daily)

    background = {
        "event_id": "P_BATCH", "kind": "nightly_reconciliation_batch", "port_id": port_id,
        "rows": stable, "ports": [port_id], "catalogued": False,
        "occurrences": [o for o in occurrences if "(stable)" in o["description"]],
        "description": cfg["P_SCHEDULE_DESCRIPTION"],
    }
    event = {
        "event_id": "P", "event_type": cfg["P_EVENT_TYPE"], "port_id": port_id,
        "description": cfg["P_DESCRIPTION"],
        "start_ts": pd.Timestamp(daily_df.loc[daily_df.drifting, "block_start"].min()),
        "end_ts": pd.Timestamp(daily_df.loc[daily_df.drifting, "block_end"].max()),
        "periods": int(drift.size), "rows": drift, "ports": [port_id], "catalogued": True,
        "metrics": "INOCTETS, OUTOCTETS, INUCASTPKTS, OUTUCASTPKTS",
        "peak_multiple": float("nan"),
        "daily": daily_df,
        "all_occurrences": occurrences,
    }
    return event, background


# --------------------------------------------------------------------------- #
# Overlay : event Q, the scheduled market-open microburst
# --------------------------------------------------------------------------- #

def _overlay_scheduled_bursts(df: pd.DataFrame, ts: pd.Series, cfg: dict, base_event_id: np.ndarray,
                              *, rng: np.random.Generator) -> dict:
    """Event Q.  Recurring, known in advance, and NOT an anomaly.

    Rows keep `event_label == "normal"` and no `event_id`: the whole teaching
    point is that this belongs in h(t) as a published schedule, not in the event
    catalog as a label the model is not supposed to have.
    """
    port_id = cfg["Q_PORT"]
    ts_np = ts.to_numpy()
    port_mask = df["port_id"].to_numpy() == port_id
    days = pd.date_range(pd.Timestamp(ts_np.min()).normalize(),
                         pd.Timestamp(ts_np.max()).normalize(), freq="D")

    rows, occurrences = [], []
    for day in days:
        if day.dayofweek >= 5:                       # weekends: the exchange is shut
            continue
        for label, hhmm, profile in cfg["Q_BURSTS"]:
            hh, mm = (int(x) for x in str(hhmm).split(":"))
            start = day + pd.Timedelta(hours=hh, minutes=mm)
            offsets = np.arange(len(profile)) * 5
            stamps = np.array([np.datetime64(start + pd.Timedelta(minutes=int(o)))
                               for o in offsets])
            win = port_mask & np.isin(ts_np, stamps)
            idx = _free_rows(df, win, base_event_id)
            if idx.size != len(profile):
                continue                             # clipped by an A..J row or the record end
            mult = np.asarray(profile, dtype=float)
            jitter = rng.lognormal(0.0, float(cfg["Q_NOISE_SIGMA"]), size=idx.size)
            factor = 1.0 + (mult - 1.0) * jitter
            mcast_factor = 1.0 + (factor - 1.0) * float(cfg["Q_MCAST_SHARE"])
            _scale_traffic(df, idx, factor, pkt_ratio=float(cfg["Q_PKT_OCTET_RATIO"]),
                           columns=["INOCTETS", "OUTOCTETS", "INUCASTPKTS", "OUTUCASTPKTS"])
            _scale_traffic(df, idx, mcast_factor,
                           columns=["INMULTICASTPKTS", "OUTMULTICASTPKTS"])
            rows.append(idx)
            occurrences.append({
                "schedule_id": "Q", "kind": label, "port_id": port_id,
                "start_time": pd.Timestamp(ts_np[idx[0]]),
                "end_time": pd.Timestamp(ts_np[idx[-1]]),
                "periods_5min": int(idx.size),
                "description": cfg["Q_DESCRIPTION"],
            })

    all_rows = np.concatenate(rows) if rows else np.array([], dtype=int)
    return {
        "event_id": "Q", "kind": "scheduled_market_bursts", "port_id": port_id,
        "rows": all_rows, "ports": [port_id], "catalogued": False,
        "occurrences": occurrences, "description": cfg["Q_DESCRIPTION"],
        "trading_days": len({o["start_time"].date() for o in occurrences}),
    }


# --------------------------------------------------------------------------- #
# Overlay : event R, the traffic drop
# --------------------------------------------------------------------------- #

def _overlay_traffic_drop(df: pd.DataFrame, ts: pd.Series, cfg: dict, base_event_id: np.ndarray,
                          *, rng: np.random.Generator) -> dict:
    """Event R.  Throughput falls well under the seasonal baseline; errors rise.

    Every control limit in the labs so far is one-sided (`> UCL`, `yhat_upper >=
    T`).  None of them can see this, which is the entire point.
    """
    port_id = cfg["R_PORT"]
    start = pd.Timestamp(cfg["R_START"])
    periods = int(cfg["R_PERIODS"])
    end = start + pd.Timedelta(minutes=5 * (periods - 1))
    ts_np = ts.to_numpy()
    win = ((df["port_id"].to_numpy() == port_id)
           & (ts_np >= np.datetime64(start)) & (ts_np <= np.datetime64(end)))
    idx = _free_rows(df, win, base_event_id)
    if idx.size == 0:
        raise ValueError("event R: empty window")

    minutes = (ts_np[idx] - np.datetime64(start)) / np.timedelta64(1, "m")
    span = float(minutes.max())
    trans = float(cfg["R_TRANSITION_MINUTES"])
    severity = np.minimum(_smoothstep(minutes / max(trans, 1e-9)),
                          _smoothstep((span - minutes) / max(trans, 1e-9)))

    depth = float(cfg["R_DEPTH"])
    total_src = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
    factor = 1.0 - depth * severity
    _scale_traffic(df, idx, factor, pkt_ratio=1.0 / float(cfg["R_PKT_OCTET_RATIO"]))
    total_new = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]

    for col, key in (("INERRORS", "R_ERROR_LAMBDA"), ("OUTERRORS", "R_ERROR_LAMBDA"),
                     ("INDISCARDS", "R_DISCARD_LAMBDA"), ("OUTDISCARDS", "R_DISCARD_LAMBDA")):
        _add_counter(df, idx, col, float(cfg[key]) * severity, rng)

    _label(df, idx, "R", cfg["R_EVENT_TYPE"])
    return {
        "event_id": "R", "event_type": cfg["R_EVENT_TYPE"], "port_id": port_id,
        "description": cfg["R_DESCRIPTION"],
        "start_ts": pd.Timestamp(ts_np[idx[0]]), "end_ts": pd.Timestamp(ts_np[idx[-1]]),
        "periods": int(idx.size), "rows": idx, "ports": [port_id], "catalogued": True,
        "metrics": "all traffic counters (down), INERRORS/OUTERRORS, IN/OUTDISCARDS (up)",
        "peak_multiple": float((total_new / total_src).min()),
        "trough_fraction": float((total_new / total_src).min()),
        "mean_fraction": float((total_new / total_src).mean()),
    }


# --------------------------------------------------------------------------- #
# Overlay : batch history, and the queue loading that precedes every batch run
# --------------------------------------------------------------------------- #

def _overlay_batch_history(df: pd.DataFrame, ts: pd.Series, cfg: dict,
                           *, protected: np.ndarray,
                           rng: np.random.Generator) -> tuple[dict, list[dict]]:
    """Earlier runs of the same batch family, on ports the demo port does not use.

    A forecast can only warn about a saturation it has seen the shape of before.
    Without these runs the record holds exactly two sustained ramps, K and
    K_BENIGN, and both of them are the thing being tested, so a residual model
    has nothing to learn the ramp-to-plateau relationship from.

    These are scheduled work, published in the calendar file and NOT catalogued,
    the same standing as the 22:00 reconciliation batch.  They are the answer to
    "has this port ever done this before", not "is this an incident".

    Returns the background record and, for each run, what the precursor needs:
    the port, the start, and the run's own per-interval byte height.
    """
    ramp = float(cfg["BATCH_HISTORY_RAMP_MINUTES"])
    plateau = float(cfg["BATCH_HISTORY_PLATEAU_MINUTES"])
    decay = float(cfg["BATCH_HISTORY_DECAY_MINUTES"])
    total_minutes = ramp + plateau + decay
    out_share = float(cfg["BATCH_HISTORY_OUT_SHARE"])
    pkt_ratio = float(cfg["BATCH_HISTORY_PKT_OCTET_RATIO"])
    sigma = float(cfg["BATCH_HISTORY_NOISE_SIGMA"])
    train_end = cfg["BATCH_HISTORY_T_TRAIN_END"]

    ts_np = ts.to_numpy()
    port_arr = df["port_id"].to_numpy()
    thresholds: dict[str, float] = {}
    rows, occurrences, runs = [], [], []

    for port_id, start, plateau_mult, kind, text in cfg["BATCH_HISTORY_RUNS"]:
        if port_id not in thresholds:
            thresholds[port_id] = _port_threshold(df, ts, port_id, train_end,
                                                  float(cfg["T_QUANTILE"]),
                                                  float(cfg["T_MARGIN"]))
        start_ts = pd.Timestamp(start)
        minutes_all = (ts_np - np.datetime64(start_ts)) / np.timedelta64(1, "m")
        win = (port_arr == port_id) & (minutes_all >= 0) & (minutes_all <= total_minutes)
        idx = np.flatnonzero(win & ~protected)
        if idx.size == 0:
            continue
        minutes = minutes_all[idx].astype(float)
        frac = _batch_shape(minutes, ramp, plateau, decay)
        plateau_rows = frac >= 1.0
        if not plateau_rows.any():
            continue
        total_src = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
        height = plateau_mult * thresholds[port_id] - float(total_src[plateau_rows].mean())
        if height <= 0:
            continue
        noise = rng.lognormal(0.0, sigma, size=idx.size)
        _inject_load(df, idx, height * frac * noise, out_share=out_share, pkt_ratio=pkt_ratio)
        rows.append(idx)
        runs.append({"port_id": port_id, "start_ts": start_ts, "height": float(height)})
        occurrences.append({
            "schedule_id": "S", "kind": kind, "port_id": port_id,
            "start_time": pd.Timestamp(ts_np[idx[0]]),
            "end_time": pd.Timestamp(ts_np[idx[-1]]),
            "periods_5min": int(idx.size),
            "description": f"{text} / 夜間大量傳檔，量隨當日累積工作量變動",
        })

    all_rows = np.concatenate(rows) if rows else np.array([], dtype=int)
    return {
        "event_id": "S", "kind": "batch_history", "port_id": "MULTI",
        "rows": all_rows, "ports": sorted({r["port_id"] for r in runs}),
        "catalogued": False, "occurrences": occurrences,
        "description": "已發布的排程作業歷史紀錄",
        "runs": len(runs),
        "thresholds": thresholds,
    }, runs


def _overlay_queue_precursor(df: pd.DataFrame, ts: pd.Series, cfg: dict,
                             *, runs: list[dict], protected: np.ndarray,
                             rng: np.random.Generator) -> dict:
    """The work items are pushed into the queue before the batch drains it.

    Many small inbound packets, few bytes, sized in proportion to the run that is
    about to start.  This is the only thing in the record that says, before a
    ramp has gone anywhere, how far it will go.

    Two properties matter and both are deliberate.  It is written only in the
    window BEFORE a run, never inside one, so every catalogued event keeps the
    bytes it shipped with.  And it is shaped as a half sine that reaches zero at
    both ends: a flat block would drop back to zero exactly when the batch starts
    from zero, which reads as "a packet surge is followed by a traffic fall" and
    is the opposite of the relationship being taught.
    """
    lead = float(cfg["QUEUE_PRECURSOR_LEAD_MINUTES"])
    byte_frac = float(cfg["QUEUE_PRECURSOR_BYTE_FRACTION"])
    item_bytes = float(cfg["QUEUE_PRECURSOR_ITEM_BYTES"])
    sigma = float(cfg["QUEUE_PRECURSOR_NOISE_SIGMA"])

    ts_np = ts.to_numpy()
    port_arr = df["port_id"].to_numpy()
    rows, occurrences = [], []
    for run in runs:
        minutes_all = (ts_np - np.datetime64(run["start_ts"])) / np.timedelta64(1, "m")
        win = (port_arr == run["port_id"]) & (minutes_all >= -lead) & (minutes_all < 0)
        idx = np.flatnonzero(win & ~protected)
        if idx.size == 0:
            continue
        u = (minutes_all[idx].astype(float) + lead) / lead
        lift = (byte_frac * run["height"] * np.sin(np.pi * u)
                * rng.lognormal(0.0, sigma, size=idx.size))
        df.loc[idx, "INOCTETS"] = df["INOCTETS"].to_numpy()[idx] + lift
        df.loc[idx, "INUCASTPKTS"] = df["INUCASTPKTS"].to_numpy()[idx].astype(float) \
            + lift / item_bytes
        rows.append(idx)
        occurrences.append({
            "schedule_id": "W", "kind": cfg["QUEUE_PRECURSOR_KIND"],
            "port_id": run["port_id"],
            "start_time": pd.Timestamp(ts_np[idx[0]]),
            "end_time": pd.Timestamp(ts_np[idx[-1]]),
            "periods_5min": int(idx.size),
            "description": cfg["QUEUE_PRECURSOR_DESCRIPTION"],
        })
    all_rows = np.concatenate(rows) if rows else np.array([], dtype=int)
    return {
        "event_id": "W", "kind": cfg["QUEUE_PRECURSOR_KIND"], "port_id": "MULTI",
        "rows": all_rows, "ports": sorted({r["port_id"] for r in runs}),
        "catalogued": False, "occurrences": occurrences,
        "description": cfg["QUEUE_PRECURSOR_DESCRIPTION"],
        "windows": len(occurrences),
    }


# --------------------------------------------------------------------------- #
# Mechanism : upstream errors -> downstream retransmission (NOT an event)
# --------------------------------------------------------------------------- #

def _error_rate_series(df: pd.DataFrame, ts_np: np.ndarray, port_arr: np.ndarray,
                       port_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(row indices in time order, their timestamps, the notebook's error_rate)."""
    idx = np.flatnonzero(port_arr == port_id)
    idx = idx[np.argsort(ts_np[idx], kind="stable")]
    errs = (df["INERRORS"].to_numpy()[idx] + df["OUTERRORS"].to_numpy()[idx]).astype(float)
    ucast = (df["INUCASTPKTS"].to_numpy()[idx] + df["OUTUCASTPKTS"].to_numpy()[idx]).astype(float)
    rate = np.divide(errs, ucast, out=np.zeros_like(errs), where=ucast > 0)
    return idx, ts_np[idx], rate


def _overlay_retransmission_coupling(df: pd.DataFrame, ts: pd.Series, cfg: dict,
                                     base_event_id: np.ndarray, *,
                                     protected: np.ndarray,
                                     rng: np.random.Generator) -> dict:
    """traffic_down(t) *= 1 + beta * errbar_up(t - tau), for every declared edge.

    Runs LAST, so `df` already carries every event's own output and the upstream
    error series it reads is the final one.  `protected` is the row set owned by
    a declared event other than L; those rows are skipped, and the size of what
    was skipped is measured and returned so it can be printed rather than
    assumed.
    """
    ts_np = ts.to_numpy()
    port_arr = df["port_id"].to_numpy()
    lo = np.datetime64(pd.Timestamp(cfg["COUPLING_START"]))
    hi = (np.datetime64(pd.Timestamp(cfg["COUPLING_END"])) if cfg.get("COUPLING_END")
          else ts_np.max())
    window = int(round(float(cfg["COUPLING_SMOOTH_MINUTES"]) / 5.0))
    pkt_ratio = float(cfg["COUPLING_PKT_RATIO"])
    respect = bool(cfg.get("COUPLING_RESPECT_DECLARED_EVENTS", True))

    # smoothed upstream error rate, one series per upstream port
    errbar: dict[str, pd.Series] = {}
    raw_peak: dict[str, float] = {}
    for up in sorted({e["up"] for e in cfg["COUPLING_EDGES"]}):
        _, uts, rate = _error_rate_series(df, ts_np, port_arr, up)
        errbar[up] = pd.Series(_causal_mean(rate, window), index=pd.DatetimeIndex(uts))
        raw_peak[up] = float(rate.max())

    rows, edges = [], []
    for edge in cfg["COUPLING_EDGES"]:
        up, down = edge["up"], edge["down"]
        beta, tau = float(edge["beta"]), float(edge["tau"])
        didx = np.flatnonzero(port_arr == down)
        didx = didx[np.argsort(ts_np[didx], kind="stable")]
        lagged = errbar[up].reindex(
            pd.DatetimeIndex(ts_np[didx]) - pd.Timedelta(minutes=tau)
        ).to_numpy()
        lagged = np.nan_to_num(lagged, nan=0.0)          # before the record starts

        in_span = (ts_np[didx] >= lo) & (ts_np[didx] <= hi)
        free = base_event_id[didx] == ""
        if respect:
            free = free & ~protected[didx]
        live = in_span & free
        lift = beta * lagged

        sel = didx[live]
        factor = 1.0 + lift[live]
        moved = int((factor != 1.0).sum())
        if beta > 0.0 and sel.size:
            _scale_traffic(df, sel, factor, pkt_ratio=pkt_ratio)
            for col, key in (("INERRORS", "COUPLING_ERROR_PER_LIFT"),
                             ("OUTERRORS", "COUPLING_ERROR_PER_LIFT"),
                             ("INDISCARDS", "COUPLING_DISCARD_PER_LIFT"),
                             ("OUTDISCARDS", "COUPLING_DISCARD_PER_LIFT")):
                _add_counter(df, sel, col, float(cfg[key]) * lift[live], rng)
            rows.append(sel[factor != 1.0])

        # what was withheld, so the size of the exclusion is on the record
        held = in_span & ~free          # positional masks into `lift`, not row ids
        outside = ~in_span
        edges.append({
            "up": up, "down": down, "beta": beta, "tau": tau,
            "rows_written": moved,
            "max_lift": float(lift[live].max()) if live.any() else 0.0,
            "mean_lift": float(lift[live].mean()) if live.any() else 0.0,
            "p50_lift": float(np.median(lift[live])) if live.any() else 0.0,
            "held_rows": int((lift[held] != 0.0).sum()),
            "held_max_lift": float(lift[held].max()) if held.any() else 0.0,
            "held_mean_lift": float(lift[held][lift[held] > 0].mean())
                              if held.any() and (lift[held] > 0).any() else 0.0,
            "outside_span_rows": int((lift[outside] != 0.0).sum()),
            "outside_span_max_lift": float(lift[outside].max()) if outside.any() else 0.0,
        })

    all_rows = np.unique(np.concatenate(rows)) if rows else np.array([], dtype=int)
    return {
        "event_id": "COUPLING", "kind": "retransmission_coupling",
        "port_id": "MULTI", "rows": all_rows,
        "ports": sorted({e["down"] for e in cfg["COUPLING_EDGES"]}),
        "catalogued": False, "edges": edges,
        "window_minutes": float(cfg["COUPLING_SMOOTH_MINUTES"]),
        "raw_err_rate_peak": raw_peak,
        "errbar": errbar,
        "description": "上游錯誤率驅動下游重傳 (物理耦合, 非事件)",
    }


# --------------------------------------------------------------------------- #
# Overlay : event L, redesigned
# --------------------------------------------------------------------------- #

def _overlay_optical_failover(
    df: pd.DataFrame,
    ts: pd.Series,
    cfg: dict,
    base_event_id: np.ndarray,
    *,
    rng: np.random.Generator,
    fast_rng: np.random.Generator,
    cont_rng: np.random.Generator,
) -> dict:
    """Event L: a day-scale error ramp on the root, then a mid-session incident.

    Two phases, and they are frozen for different reasons.

    Slow phase (FROZEN).  Errors only, on the root port, from 2026-02-21, left
    unlabelled.  It runs underneath the K window, so its rng draws are part of
    K's shipped bytes: the draw order, the row set and the lambda are all exactly
    what the 2026-08-08 run used, and changing any of them would move K.

    Fast phase (REDESIGNED 2026-08-08).  The first version collapsed the root
    port to 2% of its traffic and tripled the secondary, which made `argmax(z)`
    on traffic_total pick the true root by itself; the hybrid had nothing to do
    and "the method beats the eye" could not be shown.  Now the root moves
    modestly (a 13% throughput dip plus a moderate error rise) and starts FIRST,
    while two downstream ports move a lot and start LATER.  Port 7428 is left
    completely alone: it hangs off the same edge-fw-01 as the root, so a large
    anomaly there would tie the topology term and kill G(c).
    """
    root = cfg["L_ROOT_PORT"]
    sym1, sym2 = cfg["L_SYM1_PORT"], cfg["L_SYM2_PORT"]
    quiet = cfg["L_SECONDARY_PORT"]

    ts_np = ts.to_numpy()
    port = df["port_id"].to_numpy()

    fast_start = pd.Timestamp(cfg["L_FAST_START"])
    fast_end = fast_start + pd.Timedelta(minutes=5 * (int(cfg["L_FAST_PERIODS"]) - 1))
    slow_start = pd.Timestamp(cfg["L_SLOW_START"])

    # ---- slow phase, FROZEN DRAW.  Do not touch: K's bytes depend on it ------
    # The array, the lambda and both `rng.poisson` calls are exactly the shipped
    # 2026-08-08 ones, including the old fast-phase multiplier on the tail, so
    # the stream position at every index is unchanged and K's 109 rows come out
    # bit-identical.  Only the tail of the RESULT is discarded: rows at or after
    # L_SLOW_FROZEN_CUT are written by the continuation below instead, because
    # the fast phase no longer sits on 02-28.
    frozen_end = pd.Timestamp(cfg["L_SLOW_FROZEN_END"])
    frozen_cut = pd.Timestamp(cfg["L_SLOW_FROZEN_CUT"])
    slow = (port == root) & (ts_np >= np.datetime64(slow_start)) & (ts_np <= np.datetime64(frozen_end))
    slow_idx = np.flatnonzero(slow)
    days = (ts_np[slow_idx] - np.datetime64(slow_start)) / np.timedelta64(1, "D")
    lam = float(cfg["L_ERROR_BASE_PER_INTERVAL"]) * float(cfg["L_ERROR_DAILY_GROWTH"]) ** days
    fade_days = float(cfg["L_ERROR_FADE_IN_HOURS"]) / 24.0
    if fade_days > 0:
        lam = lam * np.clip(days / fade_days, 0.0, 1.0)

    frozen_tail = ts_np[slow_idx] >= np.datetime64(frozen_cut)
    lam = np.where(frozen_tail, lam * float(cfg["L_SLOW_FROZEN_TAIL_MULT"]), lam)

    add_in_err = rng.poisson(lam)
    add_out_err = rng.poisson(lam)
    kept = slow_idx[~frozen_tail]
    df.loc[kept, "INERRORS"] = df["INERRORS"].to_numpy()[kept] + add_in_err[~frozen_tail]
    df.loc[kept, "OUTERRORS"] = df["OUTERRORS"].to_numpy()[kept] + add_out_err[~frozen_tail]

    # ---- slow phase, CONTINUATION (new stream) ------------------------------
    # Same exponential, plus a knee: an optical path that is already shedding
    # frames degrades faster, not linearly.  This is the segment the coupling
    # actually rides on, and it runs right up to the protection switch.
    late_start = pd.Timestamp(cfg["L_LATE_START"])
    cont = (port == root) & (ts_np >= np.datetime64(frozen_cut)) & (ts_np <= np.datetime64(fast_end))
    cont_idx = np.flatnonzero(cont)
    cdays = (ts_np[cont_idx] - np.datetime64(slow_start)) / np.timedelta64(1, "D")
    clam = float(cfg["L_ERROR_BASE_PER_INTERVAL"]) * float(cfg["L_ERROR_DAILY_GROWTH"]) ** cdays
    late = np.clip((ts_np[cont_idx] - np.datetime64(late_start)) / np.timedelta64(1, "D"), 0.0, None)
    clam = clam * float(cfg["L_LATE_GROWTH"]) ** late
    cont_fast = ts_np[cont_idx] >= np.datetime64(fast_start)
    clam = np.where(cont_fast, clam * float(cfg["L_FAST_ERROR_MULT"]), clam)
    df.loc[cont_idx, "INERRORS"] = df["INERRORS"].to_numpy()[cont_idx] + cont_rng.poisson(clam)
    df.loc[cont_idx, "OUTERRORS"] = df["OUTERRORS"].to_numpy()[cont_idx] + cont_rng.poisson(clam)

    ramp_idx = np.concatenate([kept, cont_idx])
    ramp_lam = np.concatenate([lam[~frozen_tail], clam])

    # ---- fast phase ---------------------------------------------------------
    in_fast = (ts_np >= np.datetime64(fast_start)) & (ts_np <= np.datetime64(fast_end))

    def _window(port_id: str, lag_minutes: float) -> tuple[np.ndarray, np.ndarray]:
        idx = _free_rows(df, (port == port_id) & in_fast, base_event_id)
        minutes = (ts_np[idx] - np.datetime64(fast_start)) / np.timedelta64(1, "m")
        return idx, minutes.astype(float)

    # root: an immediate error step (so the onset lands in the first bucket) and
    # a throughput dip that ramps in.
    root_idx, root_min = _window(root, 0.0)
    root_src = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[root_idx]
    dip_sev = _smoothstep(root_min / max(float(cfg["L_ROOT_DIP_RAMP_MINUTES"]), 1e-9))
    _scale_traffic(df, root_idx, 1.0 - float(cfg["L_ROOT_TRAFFIC_DIP"]) * dip_sev)
    _add_counter(df, root_idx, "INERRORS",
                 np.full(root_idx.size, float(cfg["L_ROOT_ERROR_ADD"])), fast_rng)
    _add_counter(df, root_idx, "OUTERRORS",
                 np.full(root_idx.size, float(cfg["L_ROOT_ERROR_ADD"])), fast_rng)
    root_new = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[root_idx]

    sym_stats = {}
    for tag, port_id, lag_key, ramp_key, mult_key, pkt_key, err_key, dis_key, unk_key in (
        ("sym1", sym1, "L_SYM1_LAG_MINUTES", "L_SYM1_RAMP_MINUTES", "L_SYM1_TRAFFIC_MULT",
         "L_SYM1_PKT_OCTET_RATIO", "L_SYM1_ERROR_LAMBDA", "L_SYM1_DISCARD_LAMBDA",
         "L_SYM1_UNKNOWN_LAMBDA"),
        ("sym2", sym2, "L_SYM2_LAG_MINUTES", "L_SYM2_RAMP_MINUTES", "L_SYM2_TRAFFIC_MULT",
         "L_SYM2_PKT_OCTET_RATIO", "L_SYM2_ERROR_LAMBDA", "L_SYM2_DISCARD_LAMBDA",
         "L_SYM2_UNKNOWN_LAMBDA"),
    ):
        idx, minutes = _window(port_id, 0.0)
        lag = float(cfg[lag_key])
        sev = _smoothstep((minutes - lag) / max(float(cfg[ramp_key]), 1e-9))
        jitter = fast_rng.lognormal(0.0, float(cfg["L_NOISE_SIGMA"]), size=idx.size)
        src = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
        factor = 1.0 + (float(cfg[mult_key]) - 1.0) * sev * jitter
        _scale_traffic(df, idx, factor, pkt_ratio=float(cfg[pkt_key]))
        _add_counter(df, idx, "INERRORS", float(cfg[err_key]) * sev, fast_rng)
        _add_counter(df, idx, "OUTERRORS", float(cfg[err_key]) * sev, fast_rng)
        _add_counter(df, idx, "INDISCARDS", float(cfg[dis_key]) * sev, fast_rng)
        _add_counter(df, idx, "OUTDISCARDS", float(cfg[dis_key]) * sev, fast_rng)
        if float(cfg[unk_key]) > 0:
            _add_counter(df, idx, "INUNKNOWNPROTOS", float(cfg[unk_key]) * sev, fast_rng)
        new = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[idx]
        first = np.flatnonzero(sev > 0.05)
        sym_stats[tag] = {
            "port_id": port_id, "rows": idx,
            "mean_multiple": float(new.mean() / src.mean()),
            "peak_multiple": float((new / src).max()),
            "onset_ts": pd.Timestamp(ts_np[idx[first[0]]]) if first.size else None,
            "lag_minutes": lag,
        }

    labelled = np.concatenate([root_idx] + [s["rows"] for s in sym_stats.values()])
    _label(df, labelled, "L", cfg["L_EVENT_TYPE"])

    # error_rate diagnostics on the slow phase (pre-switch rows only)
    pre_mask = ts_np[ramp_idx] < np.datetime64(fast_start)
    pre = ramp_idx[pre_mask]
    pkts = (df["INUCASTPKTS"].to_numpy() + df["OUTUCASTPKTS"].to_numpy())[pre].astype(float)
    errs = (df["INERRORS"].to_numpy() + df["OUTERRORS"].to_numpy())[pre].astype(float)
    daily = pd.DataFrame({"d": pd.to_datetime(ts_np[pre]).floor("D"), "e": errs, "p": pkts})
    daily = daily.groupby("d").sum()
    daily_rate = (daily["e"] / daily["p"]).to_numpy()

    quiet_idx = np.flatnonzero((port == quiet) & in_fast)
    return {
        "event_id": "L",
        "event_type": cfg["L_EVENT_TYPE"],
        "port_id": root,          # the ROOT, deliberately not "MULTI": see CONFIG
        "description": cfg["L_DESCRIPTION"],
        "start_ts": fast_start,
        "end_ts": fast_end,
        "periods": int(cfg["L_FAST_PERIODS"]),
        "rows": np.concatenate([ramp_idx, labelled]),
        "labelled_rows": labelled,
        "ramp_rows": ramp_idx,
        "ports": [root, sym1, sym2],
        "catalogued": True,
        "quiet_port": quiet,
        "quiet_rows": quiet_idx,
        "metrics": "INERRORS, OUTERRORS (slow) + traffic / errors / discards / unknown (fast)",
        "peak_multiple": max(s["peak_multiple"] for s in sym_stats.values()),
        "root_mean_multiple": float(root_new.mean() / root_src.mean()),
        "sym": sym_stats,
        "slow_start": slow_start,
        "frozen_rows_applied": int(kept.size),
        "frozen_rows_discarded": int(int(frozen_tail.sum())),
        "continuation_rows": int(cont_idx.size),
        "slow_lam_after_fade": float(
            lam[np.searchsorted(days, float(cfg["L_ERROR_FADE_IN_HOURS"]) / 24.0)]
        ),
        "slow_lam_last_pre_switch": float(ramp_lam[pre_mask][-1]),
        "slow_lam_fast": float(ramp_lam[~pre_mask].max()) if (~pre_mask).any() else 0.0,
        "slow_daily_rate_min": float(daily_rate[daily_rate > 0].min()),
        "slow_daily_rate_max": float(daily_rate.max()),
    }


def _finalise(df: pd.DataFrame) -> None:
    """Re-apply the generator's own clipping and rounding. Idempotent."""
    df[METRIC_COLUMNS] = df[METRIC_COLUMNS].clip(lower=0)
    df[COUNTER_COLUMNS] = df[COUNTER_COLUMNS].round().astype("int64")
    df[OCTET_COLUMNS] = df[OCTET_COLUMNS].round(2)


def _build_catalog(src_path: Path, events: list[dict]) -> pd.DataFrame:
    cat = pd.read_csv(src_path, dtype="string", keep_default_na=False)
    if list(cat.columns) != CATALOG_COLUMNS:
        raise ValueError(f"unexpected catalog schema: {list(cat.columns)}")
    rows = [
        {
            "event_id": e["event_id"],
            "event_type": e["event_type"],
            "port_id": e["port_id"],
            "start_time": e["start_ts"].strftime("%Y-%m-%d %H:%M"),
            "periods_5min": str(e["periods"]),
            "description": e["description"],
            "end_time": e["end_ts"].strftime("%Y-%m-%d %H:%M:%S"),
        }
        for e in events if e.get("catalogued", True)
    ]
    return pd.concat([cat, pd.DataFrame(rows, dtype="string")], ignore_index=True)


def _build_calendar(backgrounds: list[dict], events: list[dict]) -> pd.DataFrame:
    rows = []
    for b in backgrounds:
        for o in b.get("occurrences", []):
            rows.append({
                "schedule_id": o["schedule_id"], "kind": o["kind"], "port_id": o["port_id"],
                "start_time": o["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": o["end_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "periods_5min": str(o["periods_5min"]), "description": o["description"],
            })
    # the drifting blocks of the reconciliation batch are still the same
    # scheduled job, so the schedule stays complete; the event catalog is what
    # says those days are also an incident.
    for e in events:
        for o in e.get("all_occurrences", []):
            if "(stable)" in o["description"]:
                continue
            rows.append({
                "schedule_id": o["schedule_id"], "kind": o["kind"], "port_id": o["port_id"],
                "start_time": o["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": o["end_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "periods_5min": str(o["periods_5min"]), "description": o["description"],
            })
    out = pd.DataFrame(rows, dtype="string")
    if len(out):
        out = out.sort_values(["port_id", "start_time"]).reset_index(drop=True)
        out = out[CALENDAR_COLUMNS]
    return out


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #

def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """The Lab 01 / Lab 07 feature engineering, copied verbatim."""
    sdiv = lambda a, b: np.where(b > 0, a / b, 0.0)
    out = pd.DataFrame(index=df.index)
    out["traffic_total"] = df["INOCTETS"] + df["OUTOCTETS"]
    out["ucast_total"] = df["INUCASTPKTS"] + df["OUTUCASTPKTS"]
    out["broadcast_total"] = df["INBROADCASTPKTS"] + df["OUTBROADCASTPKTS"]
    out["multicast_total"] = df["INMULTICASTPKTS"] + df["OUTMULTICASTPKTS"]
    errors_total = df["INERRORS"] + df["OUTERRORS"]
    discards_total = df["INDISCARDS"] + df["OUTDISCARDS"]
    out["error_rate"] = sdiv(errors_total, out["ucast_total"])
    out["discard_rate"] = sdiv(discards_total, out["ucast_total"])
    out["unknown_total"] = df["INUNKNOWNPROTOS"]
    out["avg_packet_size"] = sdiv(out["traffic_total"], out["ucast_total"])
    return out


def window_zscores(df: pd.DataFrame, ts: pd.Series, t0, t1, pre: str = "2h") -> pd.DataFrame:
    """Lab 07 cell 6, reproduced exactly, so gate G1 is measured the notebook way."""
    feats = _build_features(df)
    feats["port_id"] = df["port_id"].to_numpy()
    feats.index = pd.DatetimeIndex(ts)
    pre_td = pd.Timedelta(pre)
    rows = []
    for p in sorted(df["port_id"].unique()):
        g = feats[feats.port_id == p]
        pre_w = g.loc[t0 - pre_td: t0 - pd.Timedelta("5min")]
        dur = g.loc[t0:t1]
        if pre_w.empty or dur.empty:
            continue
        rec = {"port_id": p}
        for m in RCA_METRICS:
            mu, sd = pre_w[m].mean(), pre_w[m].std()
            rec[m] = float((dur[m].mean() - mu) / sd) if sd and sd > 1e-9 else 0.0
        rows.append(rec)
    return pd.DataFrame(rows).set_index("port_id")


def anomaly_onset(df: pd.DataFrame, ts: pd.Series, port: str, metric: str, t0, t1,
                  pre: str = "2h", k: float = 3.0):
    """Lab 07 cell 14, reproduced (one-sided, as shipped)."""
    feats = _build_features(df)
    feats["port_id"] = df["port_id"].to_numpy()
    feats.index = pd.DatetimeIndex(ts)
    g = feats[feats.port_id == port]
    pre_w = g.loc[t0 - pd.Timedelta(pre): t0 - pd.Timedelta("5min")][metric]
    mu, sd = pre_w.mean(), max(pre_w.std(), 1e-9)
    dur = g.loc[t0:t1][metric]
    crossed = dur[(dur - mu) / sd > k]
    return crossed.index[0] if len(crossed) else None


def _exceedance(df: pd.DataFrame, ts: pd.Series, port: str, threshold: float,
                lo=None, hi=None) -> tuple[int, int]:
    """(samples over `threshold`, distinct days with at least one) on one port."""
    sel = df["port_id"].to_numpy() == port
    if lo is not None:
        sel = sel & (ts.to_numpy() >= np.datetime64(pd.Timestamp(lo)))
    if hi is not None:
        sel = sel & (ts.to_numpy() <= np.datetime64(pd.Timestamp(hi)))
    total = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())[sel]
    over = total > threshold
    days = pd.DatetimeIndex(ts[sel][over]).normalize().nunique() if over.any() else 0
    return int(over.sum()), int(days)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def run(config: dict | None = None, *, write: bool = True) -> dict:
    cfg = copy.deepcopy(CONFIG)
    if config:
        cfg.update(config)

    src_metrics = HERE / cfg["source_metrics"]
    src_catalog = HERE / cfg["source_catalog"]
    out_metrics = HERE / cfg["out_metrics"]
    out_catalog = HERE / cfg["out_catalog"]
    out_calendar = HERE / cfg["out_calendar"]

    src_bytes = src_metrics.read_bytes()
    df, ts = _load_metrics(src_metrics)
    before = df[METRIC_COLUMNS].to_numpy(dtype="float64", copy=True)
    base_event_id = df["event_id"].to_numpy(dtype=object).astype(str)   # A..J membership

    threshold = _capacity_threshold(df, ts, cfg)
    seed = int(cfg["seed"])

    # ---- FROZEN block: K_BENIGN, K, and L's slow phase ----------------------
    # Order and rng streams are exactly the 2026-08-08 run.  L's slow phase adds
    # errors underneath the K window, so it is part of K's shipped bytes.
    kb = _overlay_batch_ramp(
        df, ts, cfg,
        event_id="K_BENIGN", event_type=cfg["KB_EVENT_TYPE"], description=cfg["KB_DESCRIPTION"],
        port_id=cfg["K_PORT"], start=cfg["KB_START"],
        plateau_mult=float(cfg["KB_PLATEAU_MULT_OF_T"]), threshold=threshold,
        with_discards=True, rng=np.random.default_rng([seed, 2]),
    )
    k = _overlay_batch_ramp(
        df, ts, cfg,
        event_id="K", event_type=cfg["K_EVENT_TYPE"], description=cfg["K_DESCRIPTION"],
        port_id=cfg["K_PORT"], start=cfg["K_START"],
        plateau_mult=float(cfg["K_PLATEAU_MULT_OF_T"]), threshold=threshold,
        with_discards=True, rng=np.random.default_rng([seed, 1]),
    )
    l = _overlay_optical_failover(
        df, ts, cfg, base_event_id,
        rng=np.random.default_rng([seed, 3]),        # frozen: slow-phase draw
        fast_rng=np.random.default_rng([seed, 13]),  # fast phase
        cont_rng=np.random.default_rng([seed, 14]),  # new: slow-phase continuation
    )

    # ---- new events, each on its own derived stream -------------------------
    q = _overlay_scheduled_bursts(df, ts, cfg, base_event_id,
                                  rng=np.random.default_rng([seed, 20]))
    p, p_bg = _overlay_nightly_batch(df, ts, cfg, base_event_id,
                                     rng=np.random.default_rng([seed, 21]))
    n = _overlay_trend_growth(df, ts, cfg, base_event_id,
                              rng=np.random.default_rng([seed, 22]))
    # M's threshold is 7429's OWN T, measured after Q, because the market-open
    # burst is part of that port's normal profile and a capacity number has to
    # sit above the routine peak.
    threshold_m = _port_threshold(df, ts, cfg["M_PORT"], cfg["M_T_TRAIN_END"],
                                  float(cfg["T_QUANTILE"]), float(cfg["T_MARGIN"]))
    m = _overlay_holdout_ramp(df, ts, cfg, base_event_id,
                              threshold=threshold_m, rng=np.random.default_rng([seed, 23]))
    r = _overlay_traffic_drop(df, ts, cfg, base_event_id,
                              rng=np.random.default_rng([seed, 24]))

    # ---- batch history and queue loading ------------------------------------
    # After every catalogued event, so each event's own numbers -- the capacity
    # threshold, M's threshold, M's plateau, P's capacity -- were all measured on
    # the untouched frame and come out unchanged.  `declared` is every row a
    # catalogued event or a published background already owns, so neither overlay
    # can write into one.
    # Only rows that are actually LABELLED are off limits.  L's row set spans its
    # slow phase too, which starts 2026-02-21 on 7427 and would blanket the
    # evenings before K and K_BENIGN; that phase is deliberately unlabelled and
    # only adds error counts, so a queue-loading burst can sit inside it without
    # touching L's mechanism.
    declared = np.zeros(len(df), dtype=bool)
    declared[base_event_id != ""] = True                            # events A..J
    declared[df["event_label"].to_numpy() != "normal"] = True       # labelled rows
    for e in (q, p_bg):
        declared[e["rows"]] = True                                  # published backgrounds

    history, history_runs = None, []
    if cfg.get("BATCH_HISTORY_ENABLED", True):
        history, history_runs = _overlay_batch_history(
            df, ts, cfg, protected=declared, rng=np.random.default_rng([seed, 40]))

    precursor = None
    if cfg.get("QUEUE_PRECURSOR_ENABLED", True):
        # K, K_BENIGN and M are batch runs of the same family, so each carries the
        # same queue loading, sized by its own injected height and written only in
        # the 90 min before it starts.
        runs = list(history_runs) + [
            {"port_id": cfg["K_PORT"], "start_ts": pd.Timestamp(cfg["KB_START"]),
             "height": kb["batch_out"]},
            {"port_id": cfg["K_PORT"], "start_ts": pd.Timestamp(cfg["K_START"]),
             "height": k["batch_out"]},
            {"port_id": cfg["M_PORT"], "start_ts": m["start_ts"],
             "height": m["batch_out"]},
        ]
        precursor = _overlay_queue_precursor(
            df, ts, cfg, runs=runs, protected=declared,
            rng=np.random.default_rng([seed, 41]))

    # ---- physical coupling, LAST -------------------------------------------
    # Last on purpose.  It reads the FINAL upstream error series (L's ramp plus
    # anything else that erred), and running it after every event means every
    # other event's own numbers -- M's threshold, M's plateau height, P's
    # capacity, Q's multipliers -- were computed on the untouched frame and come
    # out byte-identical.  `protected` is every row a declared event owns except
    # L's, because the coupling IS L's mechanism.
    protected = np.zeros(len(df), dtype=bool)
    for e in (k, kb, m, n, p, r):
        protected[e["rows"]] = True
    protected[q["rows"]] = True
    protected[p_bg["rows"]] = True
    # The batch history and the queue loading are deliberately NOT protected.
    # The coupling filters its row set with `~protected` before drawing, so any
    # row added here shortens the Poisson draw and shifts the stream for every
    # later edge, which would change L's shipped error counts and with them
    # Lab 07's root-cause numbers.  Leaving them exposed is also the physical
    # answer: retransmission coupling acts on whatever traffic is on the port,
    # regardless of which job put it there.
    coupling = None
    if cfg.get("COUPLING_ENABLED", True):
        coupling = _overlay_retransmission_coupling(df, ts, cfg, base_event_id,
                                                    protected=protected,
                                                    rng=np.random.default_rng([seed, 30]))

    events = [k, kb, m, n, p, r, l]
    backgrounds = ([q, p_bg]
                   + [b for b in (history, precursor) if b is not None]
                   + ([coupling] if coupling is not None else []))

    _finalise(df)

    # clean reference: avg packet size on the ramp port over untouched normal rows
    col = {c: i for i, c in enumerate(METRIC_COLUMNS)}
    ref = (df["port_id"].to_numpy() == cfg["K_PORT"]) & (df["event_label"].to_numpy() == "normal")
    ref = ref & (ts.to_numpy() < np.datetime64(pd.Timestamp(cfg["T_TRAIN_END"])))
    avg_pkt_ref = float(
        (before[ref, col["INOCTETS"]] + before[ref, col["OUTOCTETS"]]).sum()
        / (before[ref, col["INUCASTPKTS"]] + before[ref, col["OUTUCASTPKTS"]]).sum()
    )
    for e in (k, kb):
        e["avg_pkt_before"] = avg_pkt_ref

    total_final = (df["INOCTETS"].to_numpy() + df["OUTOCTETS"].to_numpy())

    # ---- N : is the benign growth really benign? ---------------------------
    n_normal = ((df["port_id"].to_numpy() == cfg["N_PORT"])
                & (base_event_id == "") & (df["event_id"].to_numpy() == ""))
    n_cap = float(total_final[n_normal].max() * float(cfg["N_CAPACITY_MARGIN"]))
    n_T97 = _port_threshold(df, ts, cfg["N_PORT"], cfg["T_TRAIN_END"],
                            float(cfg["T_QUANTILE"]), float(cfg["T_MARGIN"]))
    n["capacity"] = n_cap
    n["window_max"] = float(total_final[n["rows"]].max())
    n["window_max_over_capacity"] = n["window_max"] / n_cap
    n["T97"] = n_T97
    n["over_T97_in_window"] = _exceedance(df, ts, cfg["N_PORT"], n_T97,
                                          cfg["N_START"], cfg["N_END"])
    n["crosses_capacity"] = bool(n["window_max"] > n_cap)
    # the same count on the SOURCE series, so "N pushed it over" can be checked
    # rather than assumed
    n_src_total = before[:, 0] + before[:, 1]
    n_win = np.zeros(len(df), dtype=bool)
    n_win[n["rows"]] = True
    n["over_T97_in_window_source"] = (
        int((n_src_total[n_win] > n_T97).sum()),
        int(pd.DatetimeIndex(ts[n_win][n_src_total[n_win] > n_T97]).normalize().nunique()),
    )
    n["source_window_max"] = float(n_src_total[n_win].max())

    # ---- P : where the day-scale trend crosses, and what SPC would see -----
    p_daily = p["daily"]
    p_cap = _port_threshold(df, ts, cfg["P_PORT"], cfg["P_DRIFT_START"],
                            float(cfg["P_T_QUANTILE"]), float(cfg["P_T_MARGIN"]))
    # The tracked series is a FIXED slot window, the stable batch's own flat top.
    # Averaging over the whole (lengthening) plateau would dilute the number with
    # the small hours, where the natural baseline is lower, and hide the growth.
    lo_slot = float(cfg["P_RAMP_MINUTES"])
    hi_slot = lo_slot + float(cfg["P_PLATEAU_MINUTES"])
    peak_mean, block_peak = [], []
    for _, row in p_daily.iterrows():
        sel = (row["slot_minutes"] >= lo_slot) & (row["slot_minutes"] <= hi_slot)
        peak_mean.append(float(total_final[row["rows"][sel]].mean()) if sel.any() else float("nan"))
        block_peak.append(float(total_final[row["rows"]].max()))
    p_daily = p_daily.assign(plateau_mean=peak_mean, block_peak=block_peak)
    # SPC surrogate: per-slot baseline built from the STABLE days only, which is
    # what a model trained before the drift would have learnt.
    stable = p_daily[~p_daily.drifting]
    slot_vals: dict[float, list[float]] = {}
    for _, row in stable.iterrows():
        for s, i in zip(row["slot_minutes"], row["rows"]):
            slot_vals.setdefault(float(s), []).append(float(total_final[i]))
    slot_mu = {s: float(np.mean(v)) for s, v in slot_vals.items()}
    sigma = float(np.median([np.std(v, ddof=1) for v in slot_vals.values() if len(v) > 2]))
    spc_max, spc_hits = [], []
    for _, row in p_daily.iterrows():
        zs = [(float(total_final[i]) - slot_mu[float(s)]) / sigma
              for s, i in zip(row["slot_minutes"], row["rows"]) if float(s) in slot_mu]
        spc_max.append(max(zs) if zs else float("nan"))
        spc_hits.append(int(sum(1 for v in zs if v > 3.0)))
    p_daily = p_daily.assign(spc_max_sigma=spc_max, spc_hits=spc_hits)
    # A bare "> 3 sigma somewhere today" fires on stable days too, because each
    # day contributes ~40 slots and the max of 40 draws routinely clears 3.
    # The honest comparison is against the stable days themselves, which is the
    # same control-group discipline the K_BENIGN ramp exists to enforce.
    stable_hits = int(p_daily.loc[~p_daily.drifting, "spc_hits"].max())
    drift = p_daily[p_daily.drifting].reset_index(drop=True)
    over = drift.index[drift.plateau_mean > p_cap]
    spc_hit = drift.index[drift.spc_hits > stable_hits]
    p["spc_stable_max_hits"] = stable_hits
    p["batch_rows_clipped_by_AJ"] = int(p_daily["clipped"].sum())
    p["daily"] = p_daily
    p["capacity"] = p_cap
    p["spc_sigma"] = sigma
    p["cross_day"] = pd.Timestamp(drift.loc[over[0], "day"]) if len(over) else None
    p["cross_drift_step"] = float(drift.loc[over[0], "drift_step"]) if len(over) else None
    p["spc_first_day"] = pd.Timestamp(drift.loc[spc_hit[0], "day"]) if len(spc_hit) else None
    p["spc_first_step"] = float(drift.loc[spc_hit[0], "drift_step"]) if len(spc_hit) else None
    # the literal claim in the design note: the DAY-OVER-DAY increment, not the
    # cumulative deviation, is what stays inside the control limits
    inc = np.diff(drift.plateau_mean.to_numpy())
    p["max_day_over_day_sigma"] = float(np.max(np.abs(inc)) / sigma) if inc.size else 0.0
    p["peak_multiple"] = float(drift.plateau_mean.max() / stable.plateau_mean.mean()) \
        if len(stable) else float("nan")
    p["finish_slip_minutes"] = float(drift.plateau_minutes.max() - stable.plateau_minutes.max())

    # ---- R : what a one-sided limit sees -----------------------------------
    r_T97 = _port_threshold(df, ts, cfg["R_PORT"], None,
                            float(cfg["T_QUANTILE"]), float(cfg["T_MARGIN"]))
    r_win = total_final[r["rows"]]
    r["T97"] = r_T97
    r["window_max_over_T97"] = float(r_win.max() / r_T97)
    r["over_T97_samples"] = int((r_win > r_T97).sum())

    # ---- context : how often each port crosses the notebook's own T --------
    exceed = []
    for pid in sorted(df["port_id"].unique()):
        t97 = _port_threshold(df, ts, pid, cfg["T_TRAIN_END"],
                              float(cfg["T_QUANTILE"]), float(cfg["T_MARGIN"]))
        s, d = _exceedance(df, ts, pid, t97)
        exceed.append({"port_id": pid, "T_q97x1.05": t97, "samples_over": s, "days_over": d})
    exceed = pd.DataFrame(exceed).set_index("port_id")

    # cross-event diagnostic: L's slow error ramp runs underneath the K window
    k_rows = k["rows"]
    k["errors_in_window_mean"] = float(df["OUTERRORS"].to_numpy()[k_rows].mean())
    k["errors_in_window_drift"] = float(
        df["OUTERRORS"].to_numpy()[k_rows][-12:].mean() - df["OUTERRORS"].to_numpy()[k_rows][:12].mean()
    )

    # ---- G4 : byte identity of every non-overlaid row ----------------------
    touched = np.zeros(len(df), dtype=bool)
    for e in events + backgrounds:
        touched[e["rows"]] = True
    changed = np.any(df[METRIC_COLUMNS].to_numpy(dtype="float64") != before, axis=1)
    stray = np.flatnonzero(changed & ~touched)

    out_text = df.to_csv(index=False, lineterminator="\n")
    out_bytes = out_text.encode("utf-8")
    src_lines = src_bytes.split(b"\n")
    dst_lines = out_bytes.split(b"\n")
    assert len(src_lines) == len(dst_lines), (
        f"line count changed: {len(src_lines)} -> {len(dst_lines)}"
    )
    assert src_lines[0] == dst_lines[0], "header changed"
    mismatched = [i for i in np.flatnonzero(~touched) if src_lines[i + 1] != dst_lines[i + 1]]
    assert not mismatched, (
        f"{len(mismatched)} non-overlaid rows differ from the source, first at row {mismatched[0]}"
    )
    assert stray.size == 0, f"{stray.size} rows changed outside a declared event window"

    # NEW overlays must never reach an A..J row.  The one exception is the eight
    # event-H rows on 7427 that L's FROZEN slow phase has always written to.
    ajl = np.flatnonzero(base_event_id != "")
    aj_changed = [i for i in ajl if src_lines[i + 1] != dst_lines[i + 1]]

    identity = {
        "total_rows": len(df),
        "overlaid_rows": int(touched.sum()),
        "untouched_rows": int((~touched).sum()),
        "byte_mismatches": len(mismatched),
        "stray_value_changes": int(stray.size),
        "aj_rows_touched": len(aj_changed),
        "aj_rows_touched_index": aj_changed,
    }

    # ---- G2 : no two CATALOGUED windows share a (port, timestamp) ----------
    collisions = []
    cat_events = [e for e in events if e.get("catalogued", True)]
    for i in range(len(cat_events)):
        for j in range(i + 1, len(cat_events)):
            a = cat_events[i]["labelled_rows"] if "labelled_rows" in cat_events[i] else cat_events[i]["rows"]
            b = cat_events[j]["labelled_rows"] if "labelled_rows" in cat_events[j] else cat_events[j]["rows"]
            shared = np.intersect1d(a, b)
            if shared.size:
                collisions.append((cat_events[i]["event_id"], cat_events[j]["event_id"], int(shared.size)))
    # and against the A..J windows, which are rows carrying a source event_id
    for e in cat_events:
        rows = e["labelled_rows"] if "labelled_rows" in e else e["rows"]
        hit = rows[base_event_id[rows] != ""]
        if hit.size:
            collisions.append((e["event_id"], "A..J", int(hit.size)))

    # Separate and weaker check: catalog rows carry ONE [start, end] pair, so a
    # nightly recurring event is summarised by a bounding box that necessarily
    # sweeps over anything else on the same port in between.  No row is shared
    # (that is the check above); this only warns that a naive slice by catalog
    # window would pull in a neighbour's rows.
    all_ports = sorted(df["port_id"].unique())
    src_cat = pd.read_csv(src_catalog, parse_dates=["start_time", "end_time"], dtype={"port_id": str})
    boxes = []
    for row in src_cat.itertuples():
        if row.port_id != "MULTI":
            touched_ports = {row.port_id}
        else:
            m = (base_event_id == row.event_id)
            touched_ports = set(df["port_id"].to_numpy()[m])
        boxes.append((row.event_id, touched_ports, row.start_time, row.end_time))
    boxes += [(e["event_id"], set(e["ports"]), e["start_ts"], e["end_ts"]) for e in cat_events]
    box_overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            shared = a[1] & b[1]
            if shared and a[2] <= b[3] and b[2] <= a[3]:
                box_overlaps.append((a[0], b[0], sorted(shared)))

    # ---- G3 : clean (event-free) port-days ---------------------------------
    day = pd.DatetimeIndex(ts).normalize()
    all_days = pd.DatetimeIndex(sorted(set(day)))
    port_arr = df["port_id"].to_numpy()
    ports = sorted(df["port_id"].unique())
    before_id = base_event_id
    after_id = df["event_id"].to_numpy(dtype=object).astype(str)
    clean_rows = []
    for pid in ports:
        pm = port_arr == pid
        b_days = set(day[pm & (before_id != "")])
        a_days = set(day[pm & (after_id != "")])
        strict = set(day[pm & (touched | (before_id != ""))])
        clean_rows.append({
            "port_id": pid,
            "clean_before": len(all_days) - len(b_days),
            "clean_after": len(all_days) - len(a_days),
            "clean_after_strict": len(all_days) - len(strict),
        })
    clean = pd.DataFrame(clean_rows).set_index("port_id")
    floor = int(cfg["min_clean_port_days"])
    short = clean.index[clean["clean_after"] < floor].tolist()
    assert not short, (
        f"{short} keep fewer than {floor} event-free port-days; move an event, "
        f"do not lower the floor"
    )

    catalog = _build_catalog(src_catalog, events)
    calendar = _build_calendar(backgrounds, events)

    if write:
        out_metrics.write_bytes(out_bytes)
        catalog.to_csv(out_catalog, index=False, lineterminator="\n")
        calendar.to_csv(out_calendar, index=False, lineterminator="\n")

    return {
        "config": cfg,
        "threshold": threshold,
        "threshold_m": threshold_m,
        "events": events,
        "backgrounds": backgrounds,
        "coupling": coupling,
        "identity": identity,
        "collisions": collisions,
        "box_overlaps": box_overlaps,
        "clean_days": clean,
        "exceedance": exceed,
        "catalog": catalog,
        "calendar": calendar,
        "metrics": df,
        "timestamps": ts,
        "out_metrics": out_metrics,
        "out_catalog": out_catalog,
        "out_calendar": out_calendar,
    }


def _fmt(ts_val) -> str:
    return "-" if ts_val is None else pd.Timestamp(ts_val).strftime("%m-%d %H:%M")


def main() -> None:
    res = run()
    cfg, T, evs, ident = res["config"], res["threshold"], res["events"], res["identity"]
    by_id = {e["event_id"]: e for e in evs}
    k, kb, l = by_id["K"], by_id["K_BENIGN"], by_id["L"]
    m, n, p, r = by_id["M"], by_id["N"], by_id["P"], by_id["R"]
    q = res["backgrounds"][0]

    print("=" * 96)
    print("Week 6 supplementary dataset : simulator_week6_mitake.py")
    print("=" * 96)
    print(f"source   : {cfg['source_metrics']}  +  {cfg['source_catalog']}")
    print(f"written  : {res['out_metrics'].name}  ({len(res['metrics']):,} rows)")
    print(f"           {res['out_catalog'].name}  ({len(res['catalog'])} events)")
    print(f"           {res['out_calendar'].name}  ({len(res['calendar'])} scheduled occurrences)")
    print(f"seed     : {cfg['seed']}")
    print(f"T(7427)  : {T:,.0f} bytes / 5 min   T(7429) : {res['threshold_m']:,.0f}")
    print()

    print("-" * 96)
    print(f"{'event':<10}{'window':<30}{'n':>5}  {'ports':<26}{'peak x':>8}")
    print("-" * 96)
    for e in evs:
        ports = "/".join(x[-4:] for x in e["ports"])
        window = f"{_fmt(e['start_ts'])} -> {_fmt(e['end_ts'])}"
        print(f"{e['event_id']:<10}{window:<30}{e['periods']:>5}  {ports:<26}{e['peak_multiple']:>8.2f}")
    print(f"{'Q (sched)':<10}{'every trading day 09:00/13:25':<30}"
          f"{len(q['rows']):>5}  {q['port_id']:<26}{'-':>8}")
    print("-" * 96)
    print()

    print("K  (Lab 06 headline, malignant)")
    print(f"   plateau {k['plateau_over_T']:.3f} x T, crosses T at {_fmt(k['crossed_T_at'])}, "
          f"avg pkt {k['avg_pkt_before']:.0f} -> {k['avg_pkt_plateau']:.0f} B")
    print("K_BENIGN  (Lab 06 control, must not alert)")
    print(f"   plateau {kb['plateau_over_T']:.3f} x T, crosses T at {_fmt(kb['crossed_T_at'])}")
    print()
    print("M  (HELD-OUT: report on it, never tune on it)")
    print(f"   plateau {m['plateau_over_T']:.3f} x T(7429), crosses T at {_fmt(m['crossed_T_at'])} "
          f"({m['minutes_ramp_to_cross']:.0f} min into a {cfg['M_RAMP_MINUTES']} min ramp)")
    print(f"   peak {m['peak_over_T']:.3f} x T, {m['peak_multiple']:.2f} x own baseline, "
          f"OUTDISCARDS peak {m['peak_discards']}")
    print()
    print("N  (benign multi-week growth)")
    print(f"   trend factor 1.000 -> {n['max_factor']:.3f}, window max {n['window_max']:,.0f} "
          f"= {n['window_max_over_capacity']:.2f} x capacity  -> crosses capacity: "
          f"{n['crosses_capacity']}")
    print(f"   capacity {n['capacity']:,.0f} (max normal x {cfg['N_CAPACITY_MARGIN']}); "
          f"source window max was {n['source_window_max']:,.0f}")
    print(f"   caveat: the notebook's own T (q97 x 1.05) is only {n['T97']:,.0f}, and this "
          f"window is over it on {n['over_T97_in_window'][0]} samples / "
          f"{n['over_T97_in_window'][1]} days vs {n['over_T97_in_window_source'][0]} / "
          f"{n['over_T97_in_window_source'][1]} before N was added")
    print()
    print("P  (day-scale batch overrun)")
    print(f"   capacity {p['capacity']:,.0f} (q97 x 1.05 on the pre-drift period, batch included)")
    print(f"   flat-top mean crosses capacity on {_fmt(p['cross_day'])} = drift day "
          f"{p['cross_drift_step']}")
    print(f"   per-slot SPC (sigma={p['spc_sigma']:,.0f}): stable days already produce up to "
          f"{p['spc_stable_max_hits']} slots over 3 sigma, so the first drift day that beats "
          f"the control group is {_fmt(p['spc_first_day'])} = drift day {p['spc_first_step']}")
    print(f"   largest day-over-day increment {p['max_day_over_day_sigma']:.2f} sigma "
          f"(inside the limits, which is the claim); batch rows clipped by A..J: "
          f"{p['batch_rows_clipped_by_AJ']}")
    print(f"   finish time slips +{p['finish_slip_minutes']:.0f} min, flat top grows "
          f"x{p['peak_multiple']:.2f}")
    print(p["daily"][["day", "drift_step", "plateau_minutes", "plateau_mean", "block_peak",
                      "spc_max_sigma", "spc_hits", "drifting"]].tail(16).to_string(index=False))
    print()
    print("R  (traffic drop)")
    print(f"   trough {r['trough_fraction']:.3f} x baseline, window mean {r['mean_fraction']:.3f} x")
    print(f"   the window's own max is {r['window_max_over_T97']:.2f} x T(q97 x 1.05) and "
          f"{r['over_T97_samples']} samples are over it: every upper limit is silent")
    print()
    print("L  (Lab 07 headline)")
    print(f"   fast phase {_fmt(l['start_ts'])} -> {_fmt(l['end_ts'])} "
          f"({pd.Timestamp(cfg['L_FAST_START']).strftime('%Y-%m-%d %a')}, a TWSE trading day)")
    print(f"   root {cfg['L_ROOT_PORT']} mean traffic x{l['root_mean_multiple']:.3f}")
    for tag, s in l["sym"].items():
        print(f"   {tag} {s['port_id']} mean x{s['mean_multiple']:.2f}, "
              f"peak x{s['peak_multiple']:.2f}, onset {_fmt(s['onset_ts'])}")
    print(f"   error ramp: frozen draw {l['frozen_rows_applied']} rows applied / "
          f"{l['frozen_rows_discarded']} discarded, continuation {l['continuation_rows']} rows; "
          f"lambda {l['slow_lam_after_fade']:.3f} -> {l['slow_lam_last_pre_switch']:.2f} "
          f"-> {l['slow_lam_fast']:.2f} (fast)")
    print(f"   daily error_rate over the slow phase {l['slow_daily_rate_min']:.2e} -> "
          f"{l['slow_daily_rate_max']:.2e}")
    print()

    cp = res["coupling"]
    if cp is not None:
        print("COUPLING  traffic_down(t) *= 1 + beta * errbar_up(t - tau)   "
              f"(errbar = {cp['window_minutes']:.0f} min trailing causal mean of error_rate)")
        print(f"{'edge':<30}{'beta':>8}{'tau':>6}{'rows':>8}{'max lift':>10}{'p50':>9}"
              f"{'  | withheld rows':>18}{'their max lift':>16}")
        for e in cp["edges"]:
            name = f"{e['up'][-4:]} -> {e['down'][-4:]}"
            print(f"{name:<30}{e['beta']:>8.1f}{e['tau']:>6.0f}{e['rows_written']:>8}"
                  f"{e['max_lift']*100:>9.2f}%{e['p50_lift']*100:>8.3f}%"
                  f"{e['held_rows']:>18}{e['held_max_lift']*100:>15.2f}%")
        print(f"   rows the coupling actually moved: {len(cp['rows']):,}  "
              f"(all on {', '.join(p[-4:] for p in cp['ports'])}, none inside another event)")
        print()

    print("-" * 96)
    print("G4  non-overlaid row identity")
    print(f"   total {ident['total_rows']:,}  overlaid {ident['overlaid_rows']:,}  "
          f"untouched {ident['untouched_rows']:,}")
    print(f"   byte mismatches {ident['byte_mismatches']}   off-window value changes "
          f"{ident['stray_value_changes']}   A..J rows touched {ident['aj_rows_touched']}")
    print("G2  row-level collisions between catalogued events :", res["collisions"] or "none")
    print("    catalog bounding-box interval overlaps (no shared rows, see docstring) :")
    for a, b, sp in res["box_overlaps"]:
        print(f"       {a} vs {b} on {', '.join(sp)}")
    print("G3  clean port-days  (clean_after = no CATALOGUED event that day;")
    print("    clean_after_strict also counts scheduled background Q / P_BATCH as dirty)")
    print(res["clean_days"].to_string())
    print()
    print("context: how often the NATURAL series already crosses the notebook's own T")
    print(res["exceedance"].to_string())
    print("-" * 96)
    print()
    print(res["catalog"].tail(7).to_string(index=False))


if __name__ == "__main__":
    main()
