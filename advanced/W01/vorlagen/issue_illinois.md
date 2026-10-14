# Weekly report: wrong weeks flagged for high scrap

Reported by the plant management in Illinois:

> The weekly report flags week 35 for high scrap, but our scrap peak was in week 36.
> Week 27 looks too low, too.

**Where:** the weekly report from `kennzahlen.py` (written by Lena Brandt, Controlling),
computed from `schichten.csv` as produced by `nordwerk import`, with the default limit of 3.0 %
scrap per plant and week.

**Expected:** The report flags exactly the weeks in which a plant's scrap rate was above the
limit, and the rates match the plant's own numbers.
