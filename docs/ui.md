# Counter companion

Run `python -m stories_promo serve` and open `http://127.0.0.1:8000/`.

## Staff workflow

1. Enter the customer's product and choose branch, time, day and order type. Time and weekday initially follow the browser's local clock.
2. Find up to three add-ons and select one. “Out of stock” excludes that item and fetches replacement suggestions. Exclusions last for this page session and reset on branch change or reload.
3. Optionally apply a discount: 0% (none), 10%, 20%, 30%, 40% or 50%. Each option shows the customer price and rounded-up additional purchases per 1,000 matching orders needed to break even. A suggested customer-facing phrase updates with the selection.
4. “Why this pairing?” opens a short explanation of past purchases, the lower-selling selection, and the limits of the evidence. “How is this calculated?” explains costs, the exact threshold and assumptions separately.
5. “New order” clears the product and results while retaining branch, context and session stock exclusions.

Desktop uses three adjacent panels. Narrow screens use three navigable steps so the normal workflow fits the viewport instead of stacking panels down the page. Short screens omit decorative headings. Dialogs can scroll when necessary; content is never forcibly clipped, preserving access with larger accessibility text or unusually small windows.

No discount (0%) is selected by default and resets for each new request. Discount choices are comparison scenarios, not learned optimal discounts. Offers are not sent to a POS or recorded as sales. Recorded USD prices and costs are historical. Live inventory and pricing still need integration before operational use.

## Architecture and scope

Buildless HTML, CSS and JavaScript in `src/stories_promo/web/`, served by FastAPI at `/` and `/assets`. No frontend dependencies or external assets. `/options` supplies menus; `/recommend` supplies every recommendation and financial value. The browser formats returned values only. Training, artifact and evaluation reports are unchanged.

The staff interface deliberately omits model selection, raw probability/lift dashboards, exports, popularity thresholds and advanced financial assumptions. These capabilities remain available through the API and Python service. Default assumptions: no existing discount, no campaign costs or substitution loss, one add-on per opportunity.

## State and accessibility

Native labeled inputs, keyboard-operable buttons, visible focus, native modal focus containment and Escape dismissal. Context edits immediately clear results to prevent stale offers. Request sequence checks prevent older requests replacing newer selections. Network errors and timeouts are visible; submission can be retried. Unknown products are rejected; no qualifying candidates produces an explicit empty state. Nonviable discounts are labeled instead of showing a misleading break-even number.

## Verification

All 32 backend tests pass. Browser verification covers the order flow, evidence dialog, offer comparison and financial values, stock exclusion, new-order reset, and responsive document dimensions. See `reports/ui_verification.json` for the checked viewports. The screen adapts to available space; exceptionally small windows and accessibility zoom retain natural overflow rather than hiding controls.
