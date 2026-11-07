// Klicky Mart: the shop plus the study flow (set-up, three tasks, effort rating, NASA-TLX, SUS).
// Every click is logged with its time; results are sent to the local study server (server.py).
"use strict";

const AISLES = {
  fruit: "Fruit", dairy: "Dairy", bakery: "Bakery", vegetables: "Vegetables",
};
const ITEMS = [
  { id: "apples", name: "Apples", face: "🍎", price: 60, unit: "each", aisle: "fruit" },
  { id: "bananas", name: "Bananas", face: "🍌", price: 15, unit: "each", aisle: "fruit" },
  { id: "mangoes", name: "Mangoes", face: "🥭", price: 120, unit: "each", aisle: "fruit" },
  { id: "oranges", name: "Oranges", face: "🍊", price: 40, unit: "each", aisle: "fruit" },
  { id: "milk", name: "Milk", face: "🥛", price: 280, unit: "a carton", aisle: "dairy" },
  { id: "yoghurt", name: "Yoghurt", face: "🥣", price: 220, unit: "a cup", aisle: "dairy" },
  { id: "eggs", name: "Eggs", face: "🥚", price: 450, unit: "a dozen", aisle: "dairy" },
  { id: "cheese", name: "Cheese", face: "🧀", price: 900, unit: "a block", aisle: "dairy" },
  { id: "bread", name: "Bread", face: "🍞", price: 180, unit: "a loaf", aisle: "bakery" },
  { id: "rusk", name: "Rusk", face: "🥖", price: 250, unit: "a pack", aisle: "bakery" },
  { id: "buns", name: "Buns", face: "🥯", price: 120, unit: "a pack of 4", aisle: "bakery" },
  { id: "tomatoes", name: "Tomatoes", face: "🍅", price: 160, unit: "a kilo", aisle: "vegetables" },
  { id: "potatoes", name: "Potatoes", face: "🥔", price: 120, unit: "a kilo", aisle: "vegetables" },
  { id: "onions", name: "Onions", face: "🧅", price: 140, unit: "a kilo", aisle: "vegetables" },
  { id: "carrots", name: "Carrots", face: "🥕", price: 100, unit: "a kilo", aisle: "vegetables" },
];
const item = (id) => ITEMS.find((i) => i.id === id);

// Matched task sets: same aisles, same number of steps. "target" is what counts as a wrong action otherwise.
const TASKS = {
  A: [
    { text: "Add 2 apples to your cart", target: ["apples"], seed: {}, done: (s) => s.cart.apples === 2 },
    { text: "Add a carton of milk to your cart", target: ["milk"], seed: {}, done: (s) => (s.cart.milk || 0) >= 1 },
    { text: "Remove the bread from your cart, then check out", target: ["bread"], seed: { bread: 1, rusk: 1 },
      done: (s) => s.order && !s.order.bread && s.order.rusk === 1 },
  ],
  B: [
    { text: "Add 3 bananas to your cart", target: ["bananas"], seed: {}, done: (s) => s.cart.bananas === 3 },
    { text: "Add a cup of yoghurt to your cart", target: ["yoghurt"], seed: {}, done: (s) => (s.cart.yoghurt || 0) >= 1 },
    { text: "Remove the eggs from your cart, then check out", target: ["eggs"], seed: { eggs: 1, buns: 1 },
      done: (s) => s.order && !s.order.eggs && s.order.buns === 1 },
  ],
};

const PAAS = ["Very, very low", "Very low", "Low", "Rather low", "Neither low nor high", "Rather high", "High", "Very high", "Very, very high"];
const TLX = [
  { id: "mental", q: "Mental demand", ask: "How mentally demanding were the tasks?", low: "Very low", high: "Very high" },
  { id: "physical", q: "Physical demand", ask: "How physically demanding were the tasks?", low: "Very low", high: "Very high" },
  { id: "temporal", q: "Hurry", ask: "How hurried or rushed was the pace?", low: "Very low", high: "Very high" },
  { id: "performance", q: "Performance", ask: "How successful were you in doing what you were asked?", low: "Perfect", high: "Failure" },
  { id: "effort", q: "Effort", ask: "How hard did you have to work to do that well?", low: "Very low", high: "Very high" },
  { id: "frustration", q: "Frustration", ask: "How stressed, irritated or discouraged were you?", low: "Very low", high: "Very high" },
];
const SUS = [
  "I think that I would like to use this system frequently.",
  "I found the system unnecessarily complex.",
  "I thought the system was easy to use.",
  "I think that I would need the support of a technical person to be able to use this system.",
  "I found the various functions in this system were well integrated.",
  "I thought there was too much inconsistency in this system.",
  "I would imagine that most people would learn to use this system very quickly.",
  "I found the system very cumbersome to use.",
  "I felt very confident using the system.",
  "I needed to learn a lot of things before I could get going with this system.",
];
const AGREE = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"];

const $ = (id) => document.getElementById(id);
const state = { aisle: "vegetables", qty: {}, cart: {}, order: null };
const study = { round: null, index: -1, task: null };

// ---------------------------------------------------------------- the shop

function money(rs) { return `Rs ${rs.toLocaleString("en-PK")}`; }

function showAisle(aisle, focus) {
  state.aisle = aisle;
  document.querySelectorAll(".aisles a").forEach((a) => {
    if (a.dataset.aisle === aisle) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  $("aisleTitle").textContent = AISLES[aisle];
  const list = $("items");
  list.innerHTML = "";
  for (const it of ITEMS.filter((i) => i.aisle === aisle)) {
    const qty = state.qty[it.id] || 1;
    const li = document.createElement("li");
    li.className = "item";
    li.style.setProperty("--aisle", `var(--${aisle})`);
    li.innerHTML = `
      <span class="item-face" aria-hidden="true">${it.face}</span>
      <h2 class="item-name">${it.name}</h2>
      <p class="item-price">${money(it.price)} ${it.unit}</p>
      <div class="stepper">
        <button type="button" data-act="less" data-id="${it.id}" aria-label="Decrease quantity: ${it.name}" ${qty <= 1 ? "disabled" : ""}>−</button>
        <output aria-live="polite" aria-label="Quantity of ${it.name}">${qty}</output>
        <button type="button" data-act="more" data-id="${it.id}" aria-label="Increase quantity: ${it.name}" ${qty >= 9 ? "disabled" : ""}>+</button>      </div>
      <button type="button" class="btn btn-primary btn-wide" data-act="add" data-id="${it.id}" aria-label="Add to cart: ${it.name}">Add to cart</button>`;
    list.appendChild(li);
  }
  if (focus) $("shelf").focus();
}

function setQty(id, qty) {
  state.qty[id] = Math.max(1, Math.min(9, qty));
  const scroll = window.scrollY;
  showAisle(state.aisle);
  window.scrollTo(0, scroll);
}

function addToCart(id) {
  const qty = state.qty[id] || 1;
  state.cart[id] = (state.cart[id] || 0) + qty;
  state.qty[id] = 1;
  showAisle(state.aisle);
  updateCartCount(true);
  say(`Added ${qty} ${item(id).name.toLowerCase()} to your cart`);
  logAction("add", id);
}

function removeFromCart(id) {
  delete state.cart[id];
  updateCartCount(true);
  renderCart();
  say(`Removed ${item(id).name.toLowerCase()} from your cart`);
  logAction("remove", id);
}

function cartItems() { return Object.values(state.cart).reduce((a, b) => a + b, 0); }

function updateCartCount(bump) {
  const n = cartItems();
  $("cartCount").textContent = n;
  $("cartButton").setAttribute("aria-label", `Cart, ${n} ${n === 1 ? "item" : "items"}`);
  if (bump) {
    const c = $("cartCount");
    c.classList.remove("bump"); void c.offsetWidth; c.classList.add("bump");
  }
}

function renderCart() {
  const body = $("cartBody");
  if (state.order && !Object.keys(state.cart).length) {
    body.innerHTML = `<div class="placed"><span class="tick" aria-hidden="true">✓</span><h3>Your order is placed</h3>
      <p>Thank you for shopping at Klicky Mart.</p></div>`;
    return;
  }
  const ids = Object.keys(state.cart);
  if (!ids.length) {
    body.innerHTML = `<div class="empty"><p><strong>Your cart is empty.</strong></p><p>Choose an aisle and add something.</p></div>`;
    return;
  }
  const total = ids.reduce((sum, id) => sum + item(id).price * state.cart[id], 0);
  body.innerHTML = `<ul class="cart-list">${ids.map((id) => `
      <li class="cart-row"><span class="face" aria-hidden="true">${item(id).face}</span>
        <span><span class="what">${item(id).name}</span><br><span class="how">${state.cart[id]} × ${money(item(id).price)}</span></span>
        <button type="button" class="btn btn-danger" data-act="remove" data-id="${id}" aria-label="Remove: ${item(id).name}">Remove</button></li>`).join("")}
    </ul>
    <p class="cart-total"><span>Total</span><span>${money(total)}</span></p>
    <button type="button" class="btn btn-primary btn-wide" data-act="checkout">Check out</button>`;
}

let lastFocus = null;
function openCart() {
  lastFocus = document.activeElement;
  renderCart();
  $("cartBackdrop").hidden = false;
  $("cartPanel").hidden = false;
  $("closeCart").focus();
  logAction("open-cart");
}
function closeCart() {
  $("cartBackdrop").hidden = true;
  $("cartPanel").hidden = true;
  (lastFocus && document.contains(lastFocus) ? lastFocus : $("cartButton")).focus();
}

function checkout() {
  state.order = { ...state.cart };
  state.cart = {};
  updateCartCount(false);
  renderCart();
  say("Your order is placed");
  logAction("checkout");
  $("closeCart").focus();
}

let toastTimer = 0;
function say(text) {
  $("status").textContent = text;
  const toast = $("toast");
  toast.textContent = text;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

// ---------------------------------------------------------------- logging

function now() { return Math.round(performance.now()); }

function logClick(event) {
  const t = study.task;
  if (!t || t.ended) return;
  const target = event.target.closest("button, a, input, label");
  if (!target || target.closest("#taskBand")) return;
  const name = target.getAttribute("aria-label") || (target.dataset.aisle && AISLES[target.dataset.aisle])
    || target.textContent.trim().replace(/\s+/g, " ").slice(0, 60);
  t.clicks += 1;
  if (t.firstClick === null) t.firstClick = now() - t.start;
  t.events.push({ t: now() - t.start, type: "click", name });
}

function logAction(kind, id) {
  const t = study.task;
  if (!t || t.ended) return;
  t.events.push({ t: now() - t.start, type: kind, item: id || null });
  if ((kind === "add" || kind === "remove") && !t.def.target.includes(id)) t.wrong += 1;
}

async function post(path, data) {
  try {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    return response.ok;
  } catch (error) {
    return false;
  }
}

// ---------------------------------------------------------------- study screens

function screen(html, focusSelector) {
  $("screenCard").innerHTML = html;
  $("screen").hidden = false;
  $("store").inert = true;
  document.querySelector(".topbar").inert = true;
  const first = $("screenCard").querySelector(focusSelector || "h2");
  if (first) { if (first.tagName === "H2") first.tabIndex = -1; first.focus(); }
}
function hideScreen() {
  $("screen").hidden = true;
  $("store").inert = false;
  document.querySelector(".topbar").inert = false;
}

function choices(name, labels, values) {
  return `<div class="choices">${labels.map((label, i) => `
    <label class="choice"><input type="radio" name="${name}" value="${values ? values[i] : label}" required><span>${label}</span></label>`).join("")}</div>`;
}

function setupScreen() {
  screen(`<h2 id="screenTitle">Set up a round</h2>
    <p class="lead">For the researcher. The participant starts after this screen.</p>
    <form id="setupForm">
      <div class="field"><label for="pid">Participant code</label><input id="pid" name="pid" type="text" autocomplete="off" placeholder="P01" required></div>
      <fieldset class="field"><legend>Group</legend>${choices("group", ["Deaf or hard of hearing", "Low vision or motor", "Comparison"], ["deaf", "speak", "comparison"])}</fieldset>
      <fieldset class="field"><legend>Task version</legend>${choices("version", ["A", "B"])}</fieldset>
      <fieldset class="field"><legend>This round</legend>${choices("klicky", ["With Klicky", "Without Klicky"], ["with", "without"])}</fieldset>
      <p id="setupError" class="error" role="alert" hidden></p>
      <div class="screen-actions"><button class="btn btn-primary" type="submit">Start the round</button></div>
    </form>`, "#pid");
  $("setupForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const pid = String(form.get("pid") || "").trim().toUpperCase();
    if (!/^[A-Z0-9_-]{1,12}$/.test(pid) || !form.get("group") || !form.get("version") || !form.get("klicky")) {
      const error = $("setupError");
      error.textContent = "Fill in a participant code (letters and numbers only) and pick one option in each row.";
      error.hidden = false;
      return;
    }
    study.round = { participant: pid, group: form.get("group"), version: form.get("version"), klicky: form.get("klicky"),
                    started: new Date().toISOString(), tasks: [] };
    study.index = -1;
    nextTask();
  });
}

function nextTask() {
  study.index += 1;
  const tasks = TASKS[study.round.version];
  if (study.index >= tasks.length) { tlxScreen(); return; }
  const def = tasks[study.index];
  screen(`<h2 id="screenTitle">Task ${study.index + 1} of ${tasks.length}</h2>
    <p class="task-big">${def.text}</p>
    <p class="lead">Take your time. Press "I'm done" at the top when you have finished.</p>
    <div class="screen-actions"><button id="startTask" class="btn btn-primary" type="button">Start task</button></div>`, "#startTask");
  $("startTask").addEventListener("click", () => startTask(def));
}

function startTask(def) {
  state.cart = { ...def.seed };
  state.qty = {};
  state.order = null;
  closeCart();
  updateCartCount(false);
  showAisle("vegetables");
  window.scrollTo(0, 0);
  study.task = { def, start: now(), firstClick: null, clicks: 0, wrong: 0, events: [], ended: false };
  $("taskStep").textContent = `Task ${study.index + 1} of ${TASKS[study.round.version].length}`;
  $("taskText").textContent = def.text;
  $("taskBand").hidden = false;
  hideScreen();
  $("taskText").tabIndex = -1;
  $("taskText").focus();
}

function endTask(skipped) {
  const t = study.task;
  if (!t || t.ended) return;
  t.ended = true;
  $("taskBand").hidden = true;
  closeCart();
  const result = {
    task: study.index + 1, text: t.def.text,
    success: !skipped && Boolean(t.def.done(state)), skipped,
    seconds: Math.round((now() - t.start) / 100) / 10,
    first_click_seconds: t.firstClick === null ? null : Math.round(t.firstClick / 100) / 10,
    clicks: t.clicks, wrong_actions: t.wrong, events: t.events,
  };
  effortScreen(result);
}

function effortScreen(result) {
  screen(`<h2 id="screenTitle">How much mental effort did that task take?</h2>
    <p class="lead">Pick one number from 1 (very, very low) to 9 (very, very high).</p>
    <form id="effortForm">
      <fieldset><legend class="sr-only">Mental effort, 1 to 9</legend>
        ${choices("paas", PAAS.map((_, i) => String(i + 1)), PAAS.map((_, i) => i + 1))}
        <div class="scale-ends" aria-hidden="true"><span>Very, very low</span><span>Very, very high</span></div>
      </fieldset>
      <p id="effortError" class="error" role="alert" hidden></p>
      <div class="screen-actions"><button class="btn btn-primary" type="submit">Next</button></div>
    </form>`);
  document.querySelectorAll('#effortForm input[name="paas"]').forEach((input, i) => input.setAttribute("aria-label", `${i + 1}, ${PAAS[i]}`));
  $("effortForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = new FormData(event.target).get("paas");
    if (!value) { const e = $("effortError"); e.textContent = "Pick a number from 1 to 9."; e.hidden = false; return; }
    result.paas = Number(value);
    study.round.tasks.push(result);
    await post("/api/task", { ...roundInfo(), ...result });
    nextTask();
  });
}

function roundInfo() {
  const r = study.round;
  return { participant: r.participant, group: r.group, version: r.version, klicky: r.klicky };
}

function tlxScreen() {
  screen(`<h2 id="screenTitle">About all three tasks</h2>
    <p class="lead">Move each slider. 0 is the lowest, 100 the highest.</p>
    <form id="tlxForm">
      ${TLX.map((s) => `<div class="tlx">
        <p class="q" id="q-${s.id}">${s.q}</p><p id="a-${s.id}">${s.ask}</p>
        <div class="row"><input type="range" id="tlx-${s.id}" name="${s.id}" min="0" max="100" step="5" value="50"
          aria-labelledby="q-${s.id}" aria-describedby="a-${s.id}"><output for="tlx-${s.id}" id="o-${s.id}">50</output></div>
        <div class="scale-ends" aria-hidden="true"><span>${s.low}</span><span>${s.high}</span></div></div>`).join("")}
      <div class="screen-actions"><button class="btn btn-primary" type="submit">Next</button></div>
    </form>`);
  for (const s of TLX) {
    const input = $(`tlx-${s.id}`);
    const show = () => { $(`o-${s.id}`).textContent = input.value; input.setAttribute("aria-valuetext", `${input.value}, ${s.low} to ${s.high}`); };
    input.addEventListener("input", show); show();
  }
  $("tlxForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    study.round.tlx = Object.fromEntries(TLX.map((s) => [s.id, Number(form.get(s.id))]));
    study.round.tlx.raw_tlx = Math.round(TLX.reduce((sum, s) => sum + study.round.tlx[s.id], 0) / TLX.length * 10) / 10;
    susScreen();
  });
}

function susScreen() {
  const system = study.round.klicky === "with" ? "Klicky Mart with Klicky" : "Klicky Mart";
  screen(`<h2 id="screenTitle">What did you think of ${system}?</h2>
    <p class="lead">"The system" below means ${system}. Pick one answer for each line.</p>
    <form id="susForm">
      ${SUS.map((q, i) => `<fieldset class="sus-item"><legend>${i + 1}. ${q}</legend>${choices(`sus${i + 1}`, AGREE, [1, 2, 3, 4, 5])}</fieldset>`).join("")}
      <p id="susError" class="error" role="alert" hidden></p>
      <div class="screen-actions"><button class="btn btn-primary" type="submit">Finish</button></div>
    </form>`);
  $("susForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const answers = SUS.map((_, i) => Number(form.get(`sus${i + 1}`)));
    const missing = answers.findIndex((a) => !a);
    if (missing >= 0) {
      const e = $("susError"); e.textContent = `Answer line ${missing + 1} too.`; e.hidden = false;
      document.querySelector(`input[name="sus${missing + 1}"]`).focus();
      return;
    }
    // SUS: odd items score (answer - 1), even items (5 - answer); the sum times 2.5 gives 0 to 100.
    const score = answers.reduce((sum, a, i) => sum + (i % 2 === 0 ? a - 1 : 5 - a), 0) * 2.5;
    study.round.sus = { answers, score };
    study.round.finished = new Date().toISOString();
    const saved = await post("/api/round", study.round);
    thanksScreen(saved);
  });
}

function thanksScreen(saved) {
  screen(`<h2 id="screenTitle">Thank you, that's the end of this round</h2>
    <p class="lead">${saved ? "Your answers are saved." : "The answers could not be saved: check that server.py is running, then press Save again."}</p>
    <div class="screen-actions">
      ${saved ? "" : '<button id="retrySave" class="btn btn-primary" type="button">Save again</button>'}
      <button id="newRound" class="btn btn-quiet" type="button">Set up another round</button>
    </div>`);
  if (!saved) $("retrySave").addEventListener("click", async () => thanksScreen(await post("/api/round", study.round)));
  $("newRound").addEventListener("click", setupScreen);
}

// ---------------------------------------------------------------- wiring

document.addEventListener("click", logClick, true);

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-act]");
  if (!button) return;
  const { act, id } = button.dataset;
  if (act === "more" || act === "less") {
    setQty(id, (state.qty[id] || 1) + (act === "more" ? 1 : -1));
    const again = document.querySelector(`[data-act="${act}"][data-id="${id}"]`);
    (again && !again.disabled ? again : document.querySelector(`[data-act="add"][data-id="${id}"]`)).focus();
    say(`${state.qty[id]} ${item(id).name.toLowerCase()}`);
  } else if (act === "add") {
    addToCart(id);
    document.querySelector(`[data-act="add"][data-id="${id}"]`).focus();
  } else if (act === "remove") {
    removeFromCart(id);
    const next = document.querySelector('#cartBody [data-act="remove"], #cartBody [data-act="checkout"]');
    (next || $("closeCart")).focus();
  } else if (act === "checkout") {
    checkout();
  }
});

document.querySelectorAll(".aisles a").forEach((a) => a.addEventListener("click", (event) => {
  event.preventDefault();
  showAisle(a.dataset.aisle, false);
  logAction("aisle", a.dataset.aisle);
}));

$("cartButton").addEventListener("click", openCart);
$("closeCart").addEventListener("click", closeCart);
$("cartBackdrop").addEventListener("click", closeCart);
$("doneButton").addEventListener("click", () => endTask(false));
$("skipButton").addEventListener("click", () => endTask(true));

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("cartPanel").hidden) { closeCart(); return; }
  if (event.key === "Tab" && !$("cartPanel").hidden) {  // keep focus inside the open cart
    const focusable = [...$("cartPanel").querySelectorAll("button")];
    const first = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { last.focus(); event.preventDefault(); }
    else if (!event.shiftKey && document.activeElement === last) { first.focus(); event.preventDefault(); }
  }
});

showAisle("vegetables");
updateCartCount(false);
if (new URLSearchParams(location.search).has("shop")) hideScreen(); else setupScreen();
