# Playbook: Newsletter

## Workflow

```yaml
id: newsletter
name: Multi-Genre Newsletter
total_steps: 4
steps:
  - step: 1
    name: plan
    agent: main
    description: >
      Parse the user request to extract the newsletter topic
      and list of genres/sections. Each genre gets its own researcher.
    instruction: >
      Read the user's request. Identify:
      - Newsletter topic/title
      - List of genres or sections (minimum 1)
      For each genre, you will spawn one genre-researcher.

  - step: 2
    name: research
    agent: genre-researcher (parallel × N)
    description: >
      Spawn one genre-researcher per genre in parallel.
      Each researcher web-searches their assigned genre and
      returns a structured summary with key findings and sources.
    instruction: >
      Call parallel_spawn() with N copies of the genre-researcher config.
      Pass each one a prompt like:
        "Research the genre '{genre}' in the context of '{topic}'.
         Return a structured summary with: key developments,
         notable sources, and 1-2 paragraph analysis."
    parallel: true
    fan_out_key: genre

  - step: 3
    name: stitch
    agent: main
    description: >
      Combine all genre-researcher outputs into a cohesive newsletter.
      Order sections logically. Add an intro and conclusion.
    instruction: >
      Collect all research segments from step 2.
      Write a newsletter with:
      - Title and date
      - Brief introductory paragraph
      - One section per genre (use the researcher's summary)
      - Concluding paragraph
      Output as HTML in a single document.

  - step: 4
    name: publish
    agent: main
    description: >
      Write the final HTML to /newsletter/<YYYY-MM-DD>-<topic>.html.
      Use write_file to persist the newsletter.
    instruction: >
      Call write_file with:
        path: "/newsletter/{date}-{slug}.html"
        content: the full HTML from step 3
      Confirm the file was written.
```

## Tools

| Step | Tool | Gated |
|------|------|-------|
| 2 | `web_search`, `web_fetch`, `summarize` | No |
| 4 | `write_file` | No |
