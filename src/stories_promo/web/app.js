/* Presentation only. Recommendations and all offer economics come from the API. */
"use strict";
const $ = (id) => document.getElementById(id);
const state = { options: null, result: null, selected: null, discount: 0, excluded: new Set(), sequence: 0 };
const money = (n) => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD'}).format(n);
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const option = (value) => { const o = document.createElement('option'); o.value = value; o.textContent = value[0].toUpperCase() + value.slice(1); return o; };
function notice(message = '') { $('notice').textContent = message; $('notice').hidden = !message; }
function step(name) {
  document.querySelector('.workspace').dataset.active = name;
  document.querySelectorAll('[data-step]').forEach(b => { if (b.dataset.step === name) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current'); });
}
function products() { $('products').replaceChildren(...state.options.branches[$('branch').value].map(option)); }
function clearResults() {
  ++state.sequence;
  state.result = null; state.selected = null; state.discount = 0;
  $('recommendations').replaceChildren();
  $('addon-actions').hidden = $('continue-button').hidden = $('offer-content').hidden = true;
  $('empty').hidden = $('offer-empty').hidden = false;
  $('empty').innerHTML = 'Ready when you are.<small>Choose a product to find a suitable add-on.</small>';
  $('pairing-context').textContent = 'Your next pairing starts with an order.';
  document.querySelectorAll('[data-step]').forEach(b => b.disabled = b.dataset.step !== 'order');
  $('find-button').disabled = false;
  $('find-button').innerHTML = 'Find an add-on <span>→</span>';
  notice(); step('order');
}
async function json(url, body) {
  const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, {signal:controller.signal, ...(body ? {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {})});
    if (!response.ok) throw new Error('Couldn’t load suggestions. Please try again.');
    return await response.json();
  } catch (error) { throw new Error(error.name === 'AbortError' ? 'This is taking too long. Please try again.' : 'Couldn’t reach the service. Please try again.'); }
  finally { clearTimeout(timeout); }
}
async function find() {
  const known = state.options.branches[$('branch').value];
  const anchor = known.find(p => p.toLowerCase() === $('anchor').value.trim().toLowerCase());
  $('anchor').setCustomValidity(anchor ? '' : 'Choose a product from this branch’s menu.');
  if (!$('context-form').reportValidity()) return;
  $('anchor').value = anchor;
  clearResults();
  const sequence = ++state.sequence;
  $('find-button').disabled = true; $('find-button').textContent = 'Finding a pairing…';
  try {
    const result = await json('/recommend', {anchor, branch:$('branch').value, daypart:$('daypart').value, weekday:$('weekday').value, order_type:$('order-type').value, top_k:3, discounts:[0,.1,.2,.3,.4,.5], available_products:known.filter(p => !state.excluded.has(p))});
    if (sequence !== state.sequence) return;
    state.result = result; state.selected = result.recommendations[0]?.product;
    $('pairing-context').textContent = `To go with ${anchor}`;
    if (!state.selected) {
      $('empty').innerHTML = 'No suitable pairing.<small>Try another product or check availability.</small>';
      document.querySelector('[data-step=addons]').disabled = false; step('addons'); return;
    }
    document.querySelectorAll('[data-step]').forEach(b => b.disabled = false);
    render(); step('addons');
  } catch(error) { if (sequence === state.sequence) notice(error.message); }
  finally { if (sequence === state.sequence) { $('find-button').disabled = false; $('find-button').innerHTML = 'Find an add-on <span>→</span>'; } }
}
function selected() { return state.result.recommendations.find(r => r.product === state.selected); }
function render() {
  $('empty').hidden = $('offer-empty').hidden = true;
  $('addon-actions').hidden = $('continue-button').hidden = $('offer-content').hidden = false;
  $('recommendations').innerHTML = state.result.recommendations.map(r => `<button class="recommendation" data-product="${esc(r.product)}" aria-pressed="${r.product === state.selected}"><strong>${esc(r.product)}</strong><small>${esc(r.category)}</small><span class="price">${money(r.offers[0].regular_price_usd)}</span></button>`).join('');
  const item = selected(); const offer = item.offers.find(o => o.requested_discount === state.discount);
  $('offer-product').textContent = item.product;
  $('offer-pitch').textContent = offer.status === 'feasible' ? `“Would you like to add ${item.product} for ${money(offer.offer_price_usd)}?”` : 'Choose a smaller discount before suggesting this offer.';
  $('offers').innerHTML = item.offers.map(o => `<button class="offer" data-discount="${o.requested_discount}" aria-pressed="${o.requested_discount === state.discount}">${o.requested_discount ? `${o.requested_discount * 100}% off` : '0% · None'}<strong>${money(o.offer_price_usd)}</strong><small>${o.status === 'feasible' ? `${o.whole_additional_purchases_per_1000} extra / 1,000` : 'Not viable'}</small></button>`).join('');
  $('break-number').textContent = offer.status === 'feasible' ? offer.whole_additional_purchases_per_1000 : '—';
  $('break-copy').textContent = offer.status !== 'feasible' ? 'This discount cannot break even. Choose a smaller offer.' : offer.whole_additional_purchases_per_1000 === 0 ? 'extra purchases needed: no discount cost at full price.' : 'extra add-on purchases needed to cover this discount.';
}
function detail(title, content) { $('detail-title').textContent = title; $('detail-content').innerHTML = content; $('detail-dialog').showModal(); }
$('context-form').addEventListener('submit', e => { e.preventDefault(); find(); });
$('context-form').addEventListener('input', () => { $('anchor').setCustomValidity(''); clearResults(); });
$('context-form').addEventListener('change', clearResults);
$('branch').addEventListener('change', () => { state.excluded.clear(); products(); $('anchor').value = ''; });
$('new-order').addEventListener('click', () => { clearResults(); $('anchor').value = ''; $('anchor').focus(); });
document.querySelector('.steps').addEventListener('click', e => { const b = e.target.closest('[data-step]'); if (b && !b.disabled) step(b.dataset.step); });
$('continue-button').addEventListener('click', () => step('offer'));
$('recommendations').addEventListener('click', e => { const b = e.target.closest('[data-product]'); if (!b) return; state.selected = b.dataset.product; render(); document.querySelector(`[data-product="${CSS.escape(state.selected)}"]`).focus(); });
$('offers').addEventListener('click', e => { const b = e.target.closest('[data-discount]'); if (!b) return; state.discount = Number(b.dataset.discount); render(); document.querySelector(`[data-discount="${state.discount}"]`).focus(); });
$('unavailable-button').addEventListener('click', () => { state.excluded.add(state.selected); find(); });
$('evidence-button').addEventListener('click', () => {
  const item = selected(), e = item.evidence;
  detail('Why this pairing?', `<h3>Customers have bought them together</h3><p>${esc(item.product)} and ${esc(state.result.context.anchor)} appeared together in ${e.training_pair_baskets} past orders across branches.</p><h3>Give a quieter menu item a chance</h3><p>This add-on is among the less frequently purchased items in its category at ${esc(state.result.context.branch)}.</p><h3>A suggestion worth testing</h3><p>${e.raw_basket_lift < 1 ? 'This pair was not bought together unusually often. Treat it as a possible pairing, not a proven favourite.' : 'These products appeared together more often than the add-on’s overall purchase frequency would suggest. That supports trying the pairing.'}</p><p class="detail-note">Past orders help us suggest a match. They do not prove that an offer will generate extra sales. Confirm stock before suggesting it.</p>`);
});
$('calculation-button').addEventListener('click', () => {
  const item = selected(), o = item.offers.find(o => o.requested_discount === state.discount);
  detail('What does break-even mean?', `<p>The discount also goes to customers who would have bought the add-on at full price. Extra purchases need to cover that cost.</p><h3>For this offer</h3><p>Customer pays <strong>${money(o.offer_price_usd)}</strong>. Each extra sale leaves <strong>${money(o.contribution_per_additional_unit_usd)}</strong> after the recorded product cost.</p><p>Estimated discount cost on existing demand: <strong>${money(o.discount_exposure_per_1000_usd)}</strong> per 1,000 matching orders.</p><p>${o.status === 'feasible' ? `Break-even is ${o.additional_purchases_per_1000.toFixed(2)} extra purchases, rounded up to <strong>${o.whole_additional_purchases_per_1000} whole purchases</strong>.` : 'This offer cannot cover its cost under these assumptions.'}</p><p class="detail-note">Uses historical purchase estimates, recorded USD prices and unit costs. Assumes one add-on per order, no existing discount and no extra campaign or substitution costs. This is a planning estimate; confirm an offer with your manager.</p>`);
});
$('close-dialog').addEventListener('click', () => $('detail-dialog').close());
$('done-button').addEventListener('click', () => $('detail-dialog').close());
async function init() {
  try {
    state.options = await json('/options');
    $('branch').replaceChildren(...Object.keys(state.options.branches).map(option));
    $('branch').value = state.options.branches.Garden ? 'Garden' : Object.keys(state.options.branches)[0];
    $('weekday').replaceChildren(...state.options.weekdays.map(option));
    $('daypart').replaceChildren(...state.options.dayparts.map(option));
    const now = new Date(); const hour = now.getHours();
    $('weekday').value = new Intl.DateTimeFormat('en-US', {weekday:'long'}).format(now);
    $('daypart').value = hour < 6 ? 'overnight' : hour < 11 ? 'morning' : hour < 14 ? 'midday' : hour < 18 ? 'afternoon' : 'evening';
    products(); $('context-fields').disabled = false;
  } catch(error) { notice(`${error.message} Refresh the page to reconnect.`); }
}
init();
