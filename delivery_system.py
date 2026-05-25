"""
FastBox Mystery Delivery System
--------------------------------
Simulates one day of operations for a logistics company:
  1. Parse the input JSON (warehouses, agents, packages).
  2. Assign every package to the nearest agent (Euclidean distance
     from the agent's starting location to the package's warehouse).
  3. Simulate each agent picking packages up and delivering them,
     tracking the total distance travelled.
  4. Build a per-agent report (packages_delivered, total_distance,
     efficiency) and pick the best (most distance-efficient) agent.
  5. Save the report to report.json.

Usage:
    python delivery_system.py                       # input=base_case.json, output=report.json
    python delivery_system.py input.json            # custom input
    python delivery_system.py input.json out.json   # custom input + output
"""

import csv
import json
import math
import random
import sys
from pathlib import Path

# Fixed seed so "random" delays are reproducible run-to-run.
random.seed(42)


# ---------- 1. JSON parsing -------------------------------------------------

def load_data(path):
    with open(path, "r") as f:
        raw = json.load(f)

    warehouses = _normalise_locations(raw["warehouses"])
    agents = _normalise_locations(raw["agents"])

    packages = []
    for p in raw["packages"]:
        wh_id = p.get("warehouse", p.get("warehouse_id"))
        packages.append({
            "id": p["id"],
            "warehouse": wh_id,
            "destination": tuple(p["destination"]),
        })

    new_agent = raw.get("new_agent")

    return warehouses, agents, packages, new_agent


def _normalise_locations(obj):
    result = {}
    if isinstance(obj, dict):
        for key, loc in obj.items():
            result[key] = tuple(loc)
    else: 
        for item in obj:
            result[item["id"]] = tuple(item["location"])
    return result


# ---------- 2. Distance + assignment ---------------------------------------

def distance(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def assign_packages(agents, warehouses, packages):
    assignments = {agent_id: [] for agent_id in agents}

    for pkg in packages:
        wh_loc = warehouses[pkg["warehouse"]]
        nearest = min(
            agents.items(),
            key=lambda item: (distance(item[1], wh_loc), item[0]),
        )[0]
        assignments[nearest].append(pkg)

    return assignments

def simulate(agents, warehouses, assignments):
    totals = {}
    delays = {}
    for agent_id, packages in assignments.items():
        current = agents[agent_id]
        total = 0.0
        delay_total = 0
        for pkg in packages:
            wh_loc = warehouses[pkg["warehouse"]]
            dest = pkg["destination"]
            total += distance(current, wh_loc) + distance(wh_loc, dest)
            delay_total += random.randint(0, 30)
            current = dest
        totals[agent_id] = total
        delays[agent_id] = delay_total
    return totals, delays


# ---------- 4. Report -------------------------------------------------------

def build_report(assignments, totals, delays):
    report = {}
    for agent_id, packages in assignments.items():
        count = len(packages)
        dist = totals[agent_id]
        efficiency = (dist / count) if count else 0.0
        report[agent_id] = {
            "packages_delivered": count,
            "total_distance": round(dist, 2),
            "efficiency": round(efficiency, 2),
            "total_delay_minutes": delays[agent_id],
        }

    eligible = {a: r for a, r in report.items() if r["packages_delivered"] > 0}
    if eligible:
        best = min(eligible, key=lambda a: eligible[a]["efficiency"])
        report["best_agent"] = best
    else:
        report["best_agent"] = None

    return report


# ---------- Bonus: ASCII route visualization -------------------------------

def render_ascii_map(warehouses, agents, assignments, width=60, height=20):
    points = list(warehouses.values()) + list(agents.values())
    for pkgs in assignments.values():
        for p in pkgs:
            points.append(p["destination"])
    if not points:
        return "(empty map)"

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    grid = [[" "] * width for _ in range(height)]

    def to_grid(pt):
        gx = int((pt[0] - min_x) / span_x * (width - 1))
        gy = int((pt[1] - min_y) / span_y * (height - 1))
        return gx, (height - 1) - gy

    def place(pt, ch):
        gx, gy = to_grid(pt)
        if grid[gy][gx] == " " or ch in "WAD":
            grid[gy][gx] = ch
    def stroke(a, b):
        for i in range(1, 10):
            t = i / 10
            place((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), "*")

    for agent_id, pkgs in assignments.items():
        current = agents[agent_id]
        for p in pkgs:
            wh = warehouses[p["warehouse"]]
            stroke(current, wh)
            stroke(wh, p["destination"])
            current = p["destination"]

    for loc in warehouses.values():
        place(loc, "W")
    for loc in agents.values():
        place(loc, "A")
    for pkgs in assignments.values():
        for p in pkgs:
            place(p["destination"], "D")

    border = "+" + "-" * width + "+"
    lines = [border] + ["|" + "".join(row) + "|" for row in grid] + [border]
    lines.append(f"  x:[{min_x},{max_x}]  y:[{min_y},{max_y}]   W=warehouse  A=agent  D=destination  *=route")
    return "\n".join(lines)


# ---------- Bonus: top performer CSV ---------------------------------------

def export_top_performer(report, assignments, csv_path):
    best = report.get("best_agent")
    if not best:
        return None

    stats = report[best]
    rows = [
        ["agent_id", best],
        ["packages_delivered", stats["packages_delivered"]],
        ["total_distance", stats["total_distance"]],
        ["efficiency", stats["efficiency"]],
        ["total_delay_minutes", stats.get("total_delay_minutes", 0)],
        [],
        ["package_id", "warehouse", "destination_x", "destination_y"],
    ]
    for pkg in assignments.get(best, []):
        rows.append([pkg["id"], pkg["warehouse"], pkg["destination"][0], pkg["destination"][1]])

    with open(csv_path, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    return csv_path


def run(input_path, output_path):
    warehouses, agents, packages, new_agent = load_data(input_path)

    if new_agent:
        cutoff = new_agent.get("joins_after", len(packages) // 2)
        early, late = packages[:cutoff], packages[cutoff:]

        early_assign = assign_packages(agents, warehouses, early)

        extended_agents = dict(agents)
        extended_agents[new_agent["id"]] = tuple(new_agent["location"])
        late_assign = assign_packages(extended_agents, warehouses, late)

        assignments = {a: list(early_assign.get(a, [])) for a in extended_agents}
        for a, pkgs in late_assign.items():
            assignments[a].extend(pkgs)

        agents = extended_agents
        print(f"(mid-day join: {new_agent['id']} arrived after {cutoff} packages)")
    else:
        assignments = assign_packages(agents, warehouses, packages)

    totals, delays = simulate(agents, warehouses, assignments)
    report = build_report(assignments, totals, delays)

    delivered = sum(r["packages_delivered"] for k, r in report.items()
                    if k != "best_agent")
    assert delivered == len(packages), (
        f"Package count mismatch: delivered={delivered}, expected={len(packages)}"
    )

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    csv_path = Path(output_path).with_name("top_performer.csv")
    export_top_performer(report, assignments, csv_path)

    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print(f"CSV   : {csv_path}")
    print(json.dumps(report, indent=2))
    print("\nRoute map:")
    print(render_ascii_map(warehouses, agents, assignments))
    return report


if __name__ == "__main__":
    args = sys.argv[1:]
    in_path = Path(args[0]) if len(args) >= 1 else Path(r"E:\Nexgensis Technologies Assignment\Python Assignment -2026\base_case.json")
    out_path = Path(args[1]) if len(args) >= 2 else Path(r"E:\Nexgensis Technologies Assignment\Python Assignment -2026\report.json")
    run(in_path, out_path)
