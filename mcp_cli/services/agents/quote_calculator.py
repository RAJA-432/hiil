from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from mcp_cli.services.agents.middleware import AgentMiddleware
from mcp_cli.services.agents.models import register_middleware

_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "calculate_quote",
        "description": (
            "Compute exact line-item totals, subtotal, volume discount, "
            "and grand total for a quote. Always use this tool instead of "
            "guessing math. The discount is applied ONCE to the subtotal."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "line_items": {
                    "type": "array",
                    "description": "List of line items in the quote",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Item name or SKU",
                            },
                            "quantity": {
                                "type": "number",
                                "description": "Number of units",
                                "minimum": 0,
                            },
                            "unit_price": {
                                "type": "number",
                                "description": "Price per unit in USD",
                                "minimum": 0,
                            },
                        },
                        "required": ["description", "quantity", "unit_price"],
                    },
                },
            },
            "required": ["line_items"],
        },
    },
}

# Volume discount tiers: (threshold_subtotal, discount_rate)
_DISCOUNT_TIERS: list[tuple[Decimal, Decimal]] = [
    (Decimal("100000"), Decimal("0.15")),   # > $100k → 15%
    (Decimal("50000"), Decimal("0.10")),    # > $50k  → 10%
    (Decimal("10000"), Decimal("0.05")),    # > $10k  → 5%
]


def _apply_discount(subtotal: Decimal) -> tuple[Decimal, Decimal]:
    for threshold, rate in sorted(_DISCOUNT_TIERS, key=lambda x: x[0], reverse=True):
        if subtotal > threshold:
            return rate, (subtotal * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0"), Decimal("0")


@register_middleware
class QuoteCalculatorMiddleware(AgentMiddleware):
    """Exact quote math middleware.

    Registers a ``calculate_quote`` tool that computes line-item totals,
    applies volume discounts, and returns structured JSON output.

    Usage in agent config::

        middleware=[QuoteCalculatorMiddleware()]
    """

    def get_extra_tools(self) -> list[dict[str, Any]]:
        return [_TOOL_DEFINITION]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, str | None]:
        if name != "calculate_quote":
            return False, None

        items = args.get("line_items", [])
        if not items:
            return True, json.dumps({"error": "No line items provided"}, indent=2)

        line_results: list[dict[str, Any]] = []
        subtotal = Decimal("0")

        for i, item in enumerate(items):
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("unit_price", 0)))
            line_total = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += line_total
            line_results.append({
                "line": i + 1,
                "description": item.get("description", ""),
                "quantity": float(qty),
                "unit_price": float(price),
                "line_total": float(line_total),
            })

        subtotal_rounded = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        discount_rate, discount_amount = _apply_discount(subtotal_rounded)
        grand_total = (subtotal_rounded - discount_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        result = {
            "line_items": line_results,
            "subtotal": float(subtotal_rounded),
            "discount_rate": float(discount_rate),
            "discount_amount": float(discount_amount),
            "grand_total": float(grand_total),
            "summary": (
                f"Subtotal: ${float(subtotal_rounded):,.2f} | "
                f"Discount: {float(discount_rate)*100:.0f}% (${float(discount_amount):,.2f}) | "
                f"Grand Total: ${float(grand_total):,.2f}"
            ),
        }
        return True, json.dumps(result, indent=2)
