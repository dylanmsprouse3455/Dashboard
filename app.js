// A1 - Helpers
const $ = (id) => document.getElementById(id);
const storage = {
  get(key, fallback) {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  },
  set(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }
};

function formatMoney(value) {
  return `$${Number(value).toFixed(2)}`;
}

function timeToMinutes(timeValue) {
  if (!timeValue) return null;
  const [hours, minutes] = timeValue.split(":").map(Number);
  return (hours * 60) + minutes;
}

function minutesToTime(totalMinutes) {
  const fullDay = 24 * 60;
  const safeMinutes = ((totalMinutes % fullDay) + fullDay) % fullDay;
  const hours = String(Math.floor(safeMinutes / 60)).padStart(2, "0");
  const minutes = String(safeMinutes % 60).padStart(2, "0");
  return `${hours}:${minutes}`;
}

// B1 - Navigation
const views = ["home", "today", "leave", "money", "grocery", "notes"];

function showView(viewId) {
  views.forEach((id) => {
    $(id).classList.toggle("active", id === viewId);
  });

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewId);
  });
}

function setupNavigation() {
  document.querySelectorAll(".nav-btn").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });

  document.querySelectorAll(".home-card").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.target));
  });

  document.querySelectorAll(".back-home").forEach((button) => {
    button.addEventListener("click", () => showView("home"));
  });
}

// C1 - Today Panel
function updateClock() {
  const now = new Date();
  const dateText = now.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric"
  });
  const timeText = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  $("statusDate").textContent = dateText;
  $("statusTime").textContent = timeText;
  $("todayDate").textContent = dateText;
  $("todayTime").textContent = timeText;
}

function setupTodayPanel() {
  const focusData = storage.get("dcc_focus", { text: "" });
  if (focusData.text) {
    $("dailyFocus").value = focusData.text;
    $("focusSavedText").textContent = `Saved focus: ${focusData.text}`;
    $("statusFocus").textContent = `Focus: ${focusData.text}`;
  }

  $("saveFocusBtn").addEventListener("click", () => {
    const text = $("dailyFocus").value.trim();
    storage.set("dcc_focus", { text });
    $("focusSavedText").textContent = text ? `Saved focus: ${text}` : "Focus cleared.";
    $("statusFocus").textContent = text ? `Focus: ${text}` : "No focus set yet.";
  });

  updateClock();
  setInterval(updateClock, 1000);
}

// D1 - Leave Time
function setupLeaveTime() {
  const defaults = storage.get("dcc_leave_defaults", { driveTime: 30, prepTime: 40 });
  $("driveTime").value = defaults.driveTime;
  $("prepTime").value = defaults.prepTime;

  $("calcLeaveBtn").addEventListener("click", () => {
    const arrival = timeToMinutes($("arrivalTime").value);
    const drive = Number($("driveTime").value || 0);
    const prep = Number($("prepTime").value || 0);
    const shower = $("showerNeeded").checked ? 20 : 0;

    if (arrival === null) return;

    const leaveMinutes = arrival - drive;
    const readyMinutes = leaveMinutes - prep - shower;

    $("leaveTimeOutput").textContent = minutesToTime(leaveMinutes);
    $("readyTimeOutput").textContent = minutesToTime(readyMinutes);

    storage.set("dcc_leave_defaults", { driveTime: drive, prepTime: prep });
  });
}

// E1 - Money Snapshot
function setupMoneySnapshot() {
  const saved = storage.get("dcc_money", {
    balance: 0,
    bills: 0,
    buffer: 0,
    gasFood: 0
  });

  $("balanceInput").value = saved.balance;
  $("billsInput").value = saved.bills;
  $("bufferInput").value = saved.buffer;
  $("gasFoodInput").value = saved.gasFood;

  function calculate() {
    const balance = Number($("balanceInput").value || 0);
    const bills = Number($("billsInput").value || 0);
    const buffer = Number($("bufferInput").value || 0);
    const gasFood = Number($("gasFoodInput").value || 0);

    const doNotTouch = bills + buffer + gasFood;
    const safeSpend = Math.max(0, balance - doNotTouch);

    $("dontTouchOutput").textContent = formatMoney(doNotTouch);
    $("safeSpendOutput").textContent = formatMoney(safeSpend);

    storage.set("dcc_money", { balance, bills, buffer, gasFood });
  }

  $("calcMoneyBtn").addEventListener("click", calculate);
  calculate();
}

// F1 - Grocery Wizard
const groceryPlans = {
  tight: {
    meals: ["Oatmeal + bananas", "Rice + beans + salsa bowls", "Pasta + frozen veggies", "Egg sandwiches"],
    snacks: ["Popcorn", "Peanut butter toast", "Carrots + hummus"],
    drinks: ["Tea bags", "Store-brand sparkling water"],
    basics: ["Bread", "Eggs", "Milk or oat milk", "Onions", "Garlic"]
  },
  normal: {
    meals: ["Chicken stir-fry", "Turkey tacos", "Greek yogurt parfaits", "Sheet-pan salmon + potatoes"],
    snacks: ["Trail mix", "Yogurt cups", "Apple slices + peanut butter"],
    drinks: ["Cold brew", "Electrolyte packets", "Seltzer"],
    basics: ["Olive oil", "Mixed greens", "Tortillas", "Rice", "Cheese"]
  },
  flexible: {
    meals: ["Shrimp bowls", "Steak + veggie night", "Avocado toast + eggs", "Chicken pesto pasta"],
    snacks: ["Protein bars", "Berries", "Cheese + crackers"],
    drinks: ["Fresh juice", "Kombucha", "Flavored sparkling water"],
    basics: ["Herbs", "Avocados", "Greek yogurt", "Granola", "Dark chocolate"]
  }
};

function scaleList(items, days) {
  if (days <= 3) return items.slice(0, 3);
  if (days <= 5) return items;
  return items.concat(items.slice(0, 2));
}

function renderGroceryList() {
  const days = Number($("daysSelect").value);
  const budget = $("budgetSelect").value;
  const plan = groceryPlans[budget];

  const sections = [
    ["Meals", scaleList(plan.meals, days)],
    ["Snacks", scaleList(plan.snacks, days)],
    ["Drinks", scaleList(plan.drinks, days)],
    ["Basics", scaleList(plan.basics, days)]
  ];

  const html = sections.map(([title, list]) => {
    const listItems = list.map((item) => `<li>${item}</li>`).join("");
    return `<h4>${title}</h4><ul>${listItems}</ul>`;
  }).join("");

  $("groceryOutput").innerHTML = html;
  storage.set("dcc_grocery", { days, budget });
}

function plainGroceryText() {
  return $("groceryOutput").innerText.trim();
}

function setupGroceryWizard() {
  const saved = storage.get("dcc_grocery", { days: 5, budget: "normal" });
  $("daysSelect").value = String(saved.days);
  $("budgetSelect").value = saved.budget;

  $("buildListBtn").addEventListener("click", () => {
    renderGroceryList();
    $("copyFeedback").textContent = "";
  });

  $("copyListBtn").addEventListener("click", async () => {
    const text = plainGroceryText();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      $("copyFeedback").textContent = "Copied list to clipboard.";
    } catch (error) {
      $("copyFeedback").textContent = "Copy failed. You can still select and copy manually.";
    }
  });

  renderGroceryList();
}

// G1 - Quick Notes
function renderNotes(notes) {
  const list = $("notesList");
  list.innerHTML = "";

  if (!notes.length) {
    list.innerHTML = "<li>No notes yet.</li>";
    return;
  }

  notes.forEach((note) => {
    const li = document.createElement("li");
    li.textContent = note;
    list.appendChild(li);
  });
}

function setupQuickNotes() {
  let notes = storage.get("dcc_notes", []);
  renderNotes(notes);

  $("addNoteBtn").addEventListener("click", () => {
    const text = $("noteInput").value.trim();
    if (!text) return;

    notes.unshift(text);
    notes = notes.slice(0, 30);
    storage.set("dcc_notes", notes);
    $("noteInput").value = "";
    renderNotes(notes);
  });

  $("clearNotesBtn").addEventListener("click", () => {
    notes = [];
    storage.set("dcc_notes", notes);
    renderNotes(notes);
  });
}

function initApp() {
  setupNavigation();
  setupTodayPanel();
  setupLeaveTime();
  setupMoneySnapshot();
  setupGroceryWizard();
  setupQuickNotes();
}

initApp();
