# Playbook: Territory Report

## Workflow

```yaml
id: territory-report
name: Territory Sales Report
total_steps: 6
steps:
  - step: 1
    name: define-territory
    agent: main
    description: >
      Identify the territory (region/country) and time period
      from the user request.
    instruction: >
      Ask the user which territory and time period (month/quarter/year)
      the report should cover.

  - step: 2
    name: pull-data
    agent: chinook-analyst
    description: >
      Query the Chinook database for sales data in the specified
      territory: total revenue, top customers, top products, trends.
    instruction: >
      Run the following queries:
      1. Total revenue for the territory in the period
      2. Top 10 customers by revenue
      3. Top 5 products by units sold
      4. Month-over-month revenue trend
      Use customer country/region to filter by territory.

  - step: 3
    name: analyze
    agent: main
    description: >
      Analyze the data from step 2. Identify key patterns,
      growth areas, and concerns. Prepare text for the report.
    instruction: >
      Review the query results. Identify:
      - Revenue total and trend (up/down/flat)
      - Top customer concentration risk
      - Best-selling product categories
      - Any notable anomalies
      Write analysis paragraphs for the report.

  - step: 4
    name: chart
    agent: main (optional: code_interpreter sandbox)
    description: >
      Generate charts: revenue trend line, top customers bar,
      product mix pie. Use Python with matplotlib if sandbox
      is available, or describe charts in text.
    instruction: >
      If code_interpreter middleware is available:
        Write and execute Python to generate charts.
        Save chart images to /territory/charts/.
      Otherwise:
        Describe the data visually in markdown tables.

  - step: 5
    name: write-report
    agent: main
    description: >
      Compose the full territory report in markdown.
      Include: executive summary, data tables, analysis,
      charts (as references), and recommendations.
    instruction: >
      Write the report as markdown with sections:
      1. Executive Summary
      2. Territory Overview (data from step 2)
      3. Analysis (from step 3)
      4. Visualizations (chart references from step 4)
      5. Recommendations (actionable next steps)
      6. Appendix: raw query results

  - step: 6
    name: save-report
    agent: main
    description: >
      Write the report to /territory/<YYYY-MM>-<territory>.md.
    instruction: >
      Call write_file with:
        path: "/territory/{year}-{month}-{territory-slug}.md"
        content: the full report markdown from step 5
```

## Tools

| Step | Tool | Gated |
|------|------|-------|
| 2 | `read_query`, `list_tables` | No |
| 4 | Python (via code_interpreter) | No |
| 6 | `write_file` | No |
