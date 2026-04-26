# Daily Command Center

A polished, mobile-first personal dashboard built with plain HTML, CSS, and JavaScript.

## What this app is
Daily Command Center is a static utility app designed to feel like a small iPhone-friendly command center for everyday planning. It has no backend and stores your data in your browser.

## Features
- **Today Panel**
  - Live date and time
  - Daily focus input with local save
  - Status card on Home
- **Leave-Time Calculator**
  - Arrival, drive, prep, and optional shower timing
  - Calculates ready time + leave time
  - Saves drive/prep defaults
- **Money Snapshot**
  - Balance, bills, safety buffer, gas/food estimate inputs
  - Shows safe-to-spend and do-not-touch values
  - Saves recent values
- **Grocery Wizard**
  - 3/5/7 day selector
  - Tight/normal/flexible budget modes
  - Suggested meals, snacks, drinks, basics list
  - Copy list button
- **Quick Notes**
  - Add short notes
  - Newest notes first
  - Clear notes action
- **Navigation**
  - Home cards and persistent bottom nav
  - Active section highlighting
  - Back-to-home buttons in each module

## How to open it
1. Clone or download this repository.
2. Open `index.html` in your browser.

## GitHub Pages compatibility
This project is fully static and GitHub Pages compatible. You can deploy it directly from the repository without a build step.

## Local data storage
This app uses `localStorage` in your browser to save focus text, defaults, money inputs, grocery choices, and notes. Data stays on the device/browser where you use it.
