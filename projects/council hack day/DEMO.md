# Council Receipts — 2-minute demo script

**One-liner:** Council Receipts turns raw council minutes into answers to three questions —
what is my council talking about, what is it deciding, and does the talk match the money?

## Flow (localhost:8599)

1. **Open on Sheffield (Council overview).**
   - Election banner: "Southey ward by-election in 5 days" — this is who the tool is for:
     a campaigner or journalist walking into that ward needs to know what the council's
     been doing, in five minutes not five hours.
   - Metrics row: meetings, cancellation rate, key decisions, docs analysed, population.
   - Scroll: topic share chart, then the auto-generated briefing with source links —
     every claim clicks through to the original PDF.

2. **Topic trends.** What all 10 councils are talking about, week by week, as shares.
   Point at a mover. "This is a national issue-tracker built from local paperwork."

3. **Talk vs Spend — Tower Hamlets.** The punchline chart: Housing dominates its
   discussion, but education is 59% of its money (schools duty). Talk is a choice;
   spend is mostly statutory. The gap is where politics actually happens. The third
   bar is the England-average spend share (from MHCLG's own England total) — every
   council reads against the national benchmark.

4. **Close on the pipeline, not the app.** One script harvests any of the 320 councils
   in the API into tidy CSVs (topics, meetings, decisions), joined to official MHCLG
   finance, ONS population, and Democracy Club elections. The dashboard is one consumer;
   the CSVs are the reusable deliverable.

## If asked

- **Topics method?** Deterministic keyword taxonomy (10 topics, regex) — free,
  reproducible, no LLM in the metrics. LLM writes only the briefing prose, grounded in
  the CSV rows.
- **Data quality?** We found and reported: stale party control labels, empty /people
  corpus-wide, Bradford's 2,808 statutory traffic notices masquerading as committees
  (was 48% of all Transport hits — filtered), hallucinated AI toplines on decisions,
  B&D zero documents.
- **Scale?** Curated 10 councils for party/size mix; v2 ranks all 320 by population ×
  document coverage. Wales/Scotland need separate finance sources.

## Numbers to have ready

- 10 councils, ~7,000 documents, 680 meetings, 1,261 decisions, 4-month window, 10 topics.
- Lancashire (Reform-run, new May 2025): 660 decisions in 4 months — more than the other
  nine councils combined.
- England average spend: Education 54.7%, Social Care 23.0% — the benchmark bars.
- Sheffield agenda: Licensing #1. Bristol: Transport #1. Tower Hamlets: Housing #1.
  Bradford: Finance #1. Kent: Children & Education #1.
- Education is 49–76% of net service spend in every upper-tier council.
