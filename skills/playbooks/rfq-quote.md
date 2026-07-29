# Playbook: RFQ Quote

## Workflow

```yaml
id: rfq-quote
name: Request for Quote
total_steps: 6
steps:
  - step: 1
    name: discovery
    agent: chinook-analyst
    description: >
      Identify the customer in the Chinook database.
      Get company name, contact info, and existing order history.
    instruction: "Run a query to find the customer by name or email. Retrieve their contact info and past order totals."

  - step: 2
    name: requirements
    agent: main
    description: >
      Collect line items from the user conversation.
      Confirm quantities, part numbers, and any special requirements.
    instruction: "Ask the user for each line item: description, quantity, and unit price. Confirm the list before proceeding."

  - step: 3
    name: pricing
    agent: main
    description: >
      Calculate exact quote using the calculate_quote tool.
      Pass all line items with quantities and unit prices.
    instruction: >
      Call calculate_quote with the complete list of line items.
      Each item must have: description, quantity, unit_price.
      The tool returns line totals, subtotal, discount, and grand total.

  - step: 4
    name: review
    agent: quote-reviewer
    description: >
      Sanity-check the quote. Verify every line total, the subtotal,
      the discount tier, and the grand total. Flag any discrepancy.
    instruction: >
      Read the quote output from step 3.
      Recalculate each line total (qty × unit_price).
      Verify the discount tier matches the subtotal.
      If all correct, mark step done. If not, report the error.

  - step: 5
    name: approval
    agent: main
    description: >
      Present the final quote to the user for approval.
      Include line items, subtotal, discount, and grand total.
    instruction: >
      Display the quote in a clear format.
      Ask the user to approve or request changes.
      If changes needed, go back to step 2.

  - step: 6
    name: deliver
    agent: inbox-manager
    description: >
      Save the approved quote as a mail draft addressed to the customer.
      Use save_draft with the quote details in the body.
    instruction: >
      Call save_draft with:
        to: customer email from step 1
        subject: "Quote #<id> — <company>"
        body: formatted quote with all line items and totals
```

## Tools

| Step | Tool | Gated |
|------|------|-------|
| 1 | `read_query` | No |
| 3 | `calculate_quote` | No |
| 4 | `calculate_quote` (read-only) | No |
| 6 | `save_draft` | Yes — requires human approval |
