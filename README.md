# FastBox Mystery Delivery System

A Python solution to the "Mystery Delivery System" assignment. It simulates one day
of logistics operations for a fictional company **FastBox**: warehouses hold
packages, delivery agents pick them up and drive them to destinations, and the
program produces a report saying who did how much and who was most efficient.

This README is the long-form explainer — read it top to bottom and you should
be able to answer any question about the project, from "what does this script
do" to "why did you pick that tie-breaker."

---

## 1. The problem in plain English

You are given:

- A **map** with warehouses at fixed `(x, y)` coordinates.
- A set of **delivery agents** with starting `(x, y)` positions.
- A list of **packages**. Each package lives at one warehouse and must be
  delivered to a destination `(x, y)`.

The program must:

1. **Read and parse the input JSON.**
2. **Assign each package to the closest agent** — measuring straight-line
   (Euclidean) distance from each agent's starting location to the package's
   warehouse.
3. **Simulate delivery:** each agent travels `current_location → warehouse →
   destination` for each of their packages, with their location updating to the
   destination after each drop-off.
4. **Build a report** showing per-agent package count, total distance, and
   efficiency, plus a single `best_agent` field naming the most efficient one.
5. **Save the report to `report.json`.**

The assessment grades these five tasks plus optional bonus features.

---

## 2. Files in this project

| File | Purpose |
|------|---------|
| [delivery_system.py](delivery_system.py) | The main script (core tasks + 4 bonuses). |
| [base_case.json](base_case.json) | A small input matching the example in the PDF (but in list-of-objects format). |
| [base_case_with_new_agent.json](base_case_with_new_agent.json) | Same as `base_case.json` plus a `new_agent` block — demonstrates the mid-day-join bonus. |
| [Python Assignment(Delivery System Test Cases)/](Python%20Assignment%28Delivery%20System%20Test%20Cases%29/) | 10 official test cases (`test_case_1.json` … `test_case_10.json`). |
| [Python Assignment(Delivery System).pdf](Python%20Assignment%28Delivery%20System%29.pdf) | The original assignment PDF. |
| `report.json` *(generated)* | The output report — overwritten each run. |
| `top_performer.csv` *(generated)* | Bonus CSV summarising the best agent. |

---

## 3. Input formats — two shapes, one parser

The assignment files use two different JSON shapes. The script handles **both**.

### 3a. Spec / test-cases format (dict-style)
```json
{
  "warehouses": { "W1": [0, 0], "W2": [50, 75] },
  "agents":     { "A1": [5, 5], "A2": [60, 60] },
  "packages":   [ { "id": "P1", "warehouse": "W1", "destination": [30, 40] } ]
}
```

### 3b. `base_case.json` format (list-style)
```json
{
  "warehouses": [ { "id": "W1", "location": [0, 0] } ],
  "agents":     [ { "id": "A1", "location": [5, 5] } ],
  "packages":   [ { "id": "P1", "warehouse_id": "W1", "destination": [30, 40] } ]
}
```

`load_data()` normalises both into the same internal form
(`{"W1": (0, 0), ...}`), so the rest of the pipeline never has to care which
shape arrived on disk.

### Optional bonus field
```json
"new_agent": { "id": "A4", "location": [45, 70], "joins_after": 2 }
```
If present, the first `joins_after` packages go to the original pool and the
remaining packages are reassigned with the new agent included.

---

## 4. How to run it

```bash
# Default — reads base_case.json, writes report.json + top_performer.csv
python3 delivery_system.py

# Custom input
python3 delivery_system.py base_case.json

# Custom input + custom output path
python3 delivery_system.py path/to/input.json path/to/output.json

# A test case
python3 delivery_system.py "Python Assignment(Delivery System Test Cases)/test_case_5.json"

# Just see the ASCII route map, skip the JSON
python3 delivery_system.py base_case.json | sed -n '/Route map:/,$p'

# Run all 10 test cases and confirm each one picks a best_agent
for i in 1 2 3 4 5 6 7 8 9 10; do
  printf "test_case_%-2s -> " "$i"
  python3 delivery_system.py "Python Assignment(Delivery System Test Cases)/test_case_$i.json" "/tmp/tc${i}.json" \
    | grep best_agent
done
```

---

## 5. What the script does, step by step

The script flows through five functions in this order. Each one is self-contained
so you can talk about it on its own.

### Step 1 — `load_data(path)`  (JSON parsing)

- Opens the file with `json.load`.
- Calls `_normalise_locations()` on both `warehouses` and `agents`. That helper
  accepts either a dict (`{"W1": [0,0]}`) or a list of `{"id", "location"}`
  objects and returns a plain dict keyed by id with `(x, y)` tuples.
- Walks every package and accepts either `"warehouse"` or `"warehouse_id"` as
  the key naming the source warehouse.
- Reads an optional `new_agent` block (used only by the mid-day bonus).
- Returns `(warehouses, agents, packages, new_agent)`.

**Why tuples and not lists?** Tuples are immutable, so we can't accidentally
mutate a warehouse's coordinates while looping. Small thing, but it removes a
whole class of bug.

### Step 2 — `distance(a, b)`  (Euclidean distance)

```python
math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
```

Plain Pythagoras. We don't use any shortcut like Manhattan distance because the
assignment explicitly says **Euclidean**.

### Step 3 — `assign_packages(agents, warehouses, packages)`  (assignment)

For each package, find the agent whose **starting location** is closest to the
package's warehouse:

```python
nearest = min(
    agents.items(),
    key=lambda item: (distance(item[1], wh_loc), item[0]),
)[0]
```

Two important details:

- **Initial position, not current.** The spec describes assignment as a
  separate step that happens before simulation, so it uses the agent's initial
  coordinates. Using "current" position would essentially merge tasks 2 and 3
  into a greedy online assignment, which is a different algorithm.
- **Tie-breaker by agent id.** If two agents are equidistant, the alphabetically
  earlier id wins. This makes the output deterministic — same input, same
  output, every run.

Result: a dict like `{"A1": [pkg1, pkg4], "A2": [pkg2, pkg5], "A3": [pkg3]}`.

### Step 4 — `simulate(agents, warehouses, assignments)`  (simulate + delays)

For each agent, walk through their list of packages in input order:

```
current = agents[agent_id]            # agent's starting position
for each package:
    total += distance(current, warehouse)
    total += distance(warehouse, destination)
    current = destination             # agent is now at the drop-off point
    delay += random.randint(0, 30)    # bonus
```

So the per-package distance is the distance **to** the warehouse plus the
distance **from** the warehouse to the destination. The agent's position is
carried forward, so the next package's pickup leg starts from wherever the
previous one ended.

Returns `(totals, delays)` — `totals[agent_id]` is total km/units, `delays[agent_id]` is total minutes of bonus random delay.

**Why `random.seed(42)` at the top of the file?** So the "random" delays are
reproducible. Re-running the script gives the same delay numbers, which makes
testing and grading easier. Drop the seed if you want true randomness.

### Step 5 — `build_report(assignments, totals, delays)`  (report)

For every agent (even ones who got nothing assigned) write a small dict:

```python
{
  "packages_delivered": count,
  "total_distance":     round(dist, 2),
  "efficiency":         round(dist / count, 2) if count else 0.0,
  "total_delay_minutes": delays[agent_id],
}
```

Then choose `best_agent` = the agent with **lowest efficiency** (= least
distance per package).

**Why lowest, not highest?** Because efficiency here is *cost per package*,
not *packages per km*. The PDF's example confirms this: it picks A1 (42.66) as
best over A2 (60.06) and A3 (50.00). Less is better.

Agents who delivered zero packages are listed in the report (for transparency)
but are excluded from the `best_agent` contest — otherwise an agent with 0
packages and 0 distance would tie for "infinity efficiency", which doesn't make
sense.

### Step 6 — `run(input_path, output_path)`  (the driver)

- Calls all of the above in order.
- Has an `assert` that the total `packages_delivered` across all agents equals
  the input package count. The assignment's *Notes* section requires this
  invariant — if assignment ever drops a package, the program loudly fails.
- Writes `report.json` with `json.dump(..., indent=2)`.
- Writes `top_performer.csv` next to it (bonus).
- Prints the route map at the end (bonus).

---

## 6. The output report — every field explained

Sample output (from `python3 delivery_system.py base_case.json`):

```json
{
  "A1": { "packages_delivered": 2, "total_distance": 121.21, "efficiency": 60.61, "total_delay_minutes": 23 },
  "A2": { "packages_delivered": 2, "total_distance":  79.21, "efficiency": 39.60, "total_delay_minutes": 23 },
  "A3": { "packages_delivered": 1, "total_distance":  14.14, "efficiency": 14.14, "total_delay_minutes":  8 },
  "best_agent": "A3"
}
```

| Field | Meaning |
|-------|---------|
| `packages_delivered` | How many packages this agent was assigned (== delivered). |
| `total_distance`     | Sum of Euclidean distances they travelled across all legs. Rounded to 2 dp. |
| `efficiency`         | `total_distance / packages_delivered`. Lower is better. |
| `total_delay_minutes`| Bonus — sum of random delays incurred. Has no effect on distance. |
| `best_agent`         | Top-level field, one of the agent ids. Lowest efficiency wins; agents with 0 packages are skipped. |

---

## 7. The bonus features (and how they're implemented)

### Bonus 1 — Random delivery delays
Each delivery gets a `random.randint(0, 30)` minute delay added to the agent's
running total. Distance is unaffected. Reported as `total_delay_minutes`.
Seeded at the top of the file so runs are reproducible.

### Bonus 2 — ASCII route visualisation (`render_ascii_map`)
1. Collect every `(x, y)` in the data and compute the bounding box.
2. Build a 60×20 character grid.
3. For each agent, walk their route (`agent → warehouse → dest → next warehouse → next dest → …`) and drop 9 evenly-spaced `*` characters per leg.
4. Stamp `W` (warehouse), `A` (agent start), `D` (destination) **after** the
   stars so the markers always sit on top of the route lines.
5. Flip the y-axis when printing so larger y appears at the top (normal map
   intuition).
6. Footer shows the coordinate range and the legend.

The grid auto-scales: tiny inputs and large inputs both fill the same box.
To change the size, call `render_ascii_map(..., width=120, height=40)`.

### Bonus 3 — Mid-day agent join
Triggered by an optional `new_agent` field in the input JSON:

```json
"new_agent": { "id": "A4", "location": [45, 70], "joins_after": 2 }
```

When present, `run()` splits the packages list at index `joins_after`:
- First half is assigned among the **original** agents.
- Second half is assigned among the **original + new** agents.
- The two assignment dicts are then merged.

The simulator gets the new agent's starting position so distance is computed
correctly. Try it with [base_case_with_new_agent.json](base_case_with_new_agent.json).

### Bonus 4 — Top performer CSV
After the JSON report is written, `export_top_performer()` writes a tiny CSV
to `top_performer.csv` containing:

- The best agent's id, package count, distance, efficiency, delay.
- A blank row.
- A header (`package_id, warehouse, destination_x, destination_y`) followed by
  one row per package they delivered.

Easy to hand to non-technical stakeholders or open in Excel.

---

## 8. The math, made concrete

Using `base_case.json`:
- A1 starts at `(5, 5)`. They're assigned **P1** (W1→[30,40]) and **P4** (W1→[10,10]) because W1 is closest to A1.
- Their route is: `(5,5) → W1(0,0) → (30,40) → W1(0,0) → (10,10)`.
- Distances:
  - `(5,5) → (0,0)`  = √(25+25)  ≈ 7.07
  - `(0,0) → (30,40)` = √(900+1600) = 50.00
  - `(30,40) → (0,0)` = √(900+1600) = 50.00
  - `(0,0) → (10,10)` = √(100+100) ≈ 14.14
  - **Total ≈ 121.21**, matching the report.
- Efficiency = 121.21 / 2 ≈ 60.61.

A3 only handles P3 (W3 → (105,20)) starting from (95,30):
- `(95,30) → (100,25) → (105,20)` ≈ 7.07 + 7.07 = 14.14. Same as the report.

That's why A3 wins `best_agent` — one short leg, no zig-zag.

---

## 9. Things to be ready to defend

Likely questions, with crisp answers:

**Q. Why Euclidean distance? Roads aren't straight.**
A. The spec asks for Euclidean explicitly. In a real system you'd use a
routing engine (OSRM, Google Maps) but this is a simulation. Replacing the
`distance()` function is the only change needed to swap in a different metric.

**Q. What if two agents are exactly tied for closest?**
A. Tie-break by agent id alphabetically — see the `key=lambda item:
(distance, item[0])` tuple in `assign_packages()`. Output stays deterministic.

**Q. What if an agent ends up with zero packages?**
A. Still appears in the report (with zeros), but is excluded from the
`best_agent` decision so they don't unfairly win.

**Q. What if all agents have zero packages (empty input)?**
A. `best_agent` is `null`. The script doesn't crash.

**Q. Why initial agent positions, not updated?**
A. The spec lists assignment (task 2) and simulation (task 3) as separate
steps. Doing assignment with current positions would couple them and produce
a different (greedy online) algorithm.

**Q. Why is the assertion (`delivered == total packages`) important?**
A. The PDF's *Notes* section explicitly says "Make sure total packages
delivered matches total packages." The assertion makes a mistake loud
instead of silent.

**Q. Why round to 2 dp?**
A. To match the sample report in the spec.

**Q. Why a fixed random seed?**
A. So "random" delays are reproducible. Remove `random.seed(42)` for truly
random output.

**Q. Could I extend this to non-Euclidean routing?**
A. Yes — replace `distance(a, b)` with a call to a routing API. The function
is the only place the metric lives.

**Q. Could I optimise globally (e.g. minimise total fleet distance)?**
A. That's the classic assignment / vehicle-routing problem, NP-hard in
general. The spec asks for nearest-agent (a simple greedy), so we stop
there. An obvious next step would be the Hungarian algorithm, or an
OR-Tools VRP solver for larger instances.

---

## 10. Evaluation criteria coverage

| Criteria | Weight | Where it's met |
|----------|--------|----------------|
| JSON parsing | 10% | `load_data` + `_normalise_locations` handle both formats. |
| Distance calculation | 20% | `distance()` uses correct Euclidean math (`math.sqrt`). |
| Agent-package assignment | 25% | `assign_packages` picks nearest agent by initial position, deterministic ties. |
| Simulation & report | 25% | `simulate` + `build_report` produce the exact shape from the spec, plus invariant assertion. |
| Code clarity & comments | 10% | Functions are small, named, and each carries a docstring; helpers documented. |
| Bonus creativity | 10% | All 4 bonuses implemented: delays, ASCII map, mid-day agent, CSV export. |

---

## 11. Quick reference — function map

```
delivery_system.py
├── load_data(path)              # Step 1 — parse + normalise JSON
├── _normalise_locations(obj)    # helper: dict-style or list-style → dict
├── distance(a, b)               # Step 2 — Euclidean
├── assign_packages(...)         # Step 3 — nearest-agent assignment
├── simulate(...)                # Step 4 — walk routes, sum distance, roll delays
├── build_report(...)            # Step 5 — per-agent stats + best_agent
├── render_ascii_map(...)        # Bonus 2 — print the route map
├── export_top_performer(...)    # Bonus 4 — write CSV
└── run(input_path, output_path) # orchestrator — also handles Bonus 3 (mid-day)
```

That's the whole thing. Open the script alongside this README and you can
trace any question back to the line that answers it.
