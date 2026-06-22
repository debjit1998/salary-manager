"""Idempotent seed script for the salary manager database.

Run with:  python -m scripts.seed

What it inserts:
  - 1 HR user (hr@acme.org) with the bcrypted HR_USER_PASSWORD
  - 8 departments, 7 levels (L1-L7), 3 currencies (USD/GBP/INR with fixed FX)
  - 21 comp_bands (one per level x country)
  - SEED_SIZE employees with a realistic country/level/employment-type mix
  - 1-4 salary_changes per employee (a coherent career arc: hire + raises/promos)
  - Equity grants for ~30-90% of employees at L4+, scaled by level

Idempotency:
  If the employees table already has any rows, the script is a no-op
  except for the HR user (which uses ON CONFLICT DO NOTHING). To reseed
  from scratch, downgrade the migration and re-upgrade.

Determinism:
  random.seed(42) at the top of main() — every run produces the same
  dataset modulo UUIDs (which come from os.urandom and aren't seeded).
"""

from __future__ import annotations

import os
import random
import sys
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import bcrypt
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db import engine
from app.settings import settings

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    "Engineering",
    "Product",
    "Design",
    "Sales",
    "Marketing",
    "Customer Success",
    "Finance",
    "People Ops",
]

LEVELS = [(f"L{i}", i) for i in range(1, 8)]  # L1..L7, rank 1..7

CURRENCIES: list[tuple[str, str, str]] = [
    # (code, name, ratio_to_usd) — captured 2026-06-21, see docs/ARCHITECTURE.md
    ("USD", "US Dollar", "1.000000"),
    ("GBP", "Pound Sterling", "0.755800"),
    ("INR", "Indian Rupee", "94.460000"),
]

COUNTRY_TO_CURRENCY = {"US": "USD", "UK": "GBP", "IN": "INR"}

# Comp bands: (rank, country) -> (band_min, band_mid, band_max) in native currency.
# Numbers are realistic-ish for a global tech org. Native currency only —
# USD-equivalents are derived at query time via the currencies table.
COMP_BANDS: dict[tuple[int, str], tuple[int, int, int]] = {
    (1, "US"): (60_000, 70_000, 80_000),
    (2, "US"): (80_000, 95_000, 110_000),
    (3, "US"): (110_000, 130_000, 150_000),
    (4, "US"): (150_000, 175_000, 200_000),
    (5, "US"): (200_000, 240_000, 280_000),
    (6, "US"): (280_000, 340_000, 400_000),
    (7, "US"): (400_000, 500_000, 600_000),
    (1, "UK"): (40_000, 47_500, 55_000),
    (2, "UK"): (55_000, 65_000, 75_000),
    (3, "UK"): (75_000, 87_500, 100_000),
    (4, "UK"): (100_000, 117_500, 135_000),
    (5, "UK"): (135_000, 157_500, 180_000),
    (6, "UK"): (180_000, 220_000, 260_000),
    (7, "UK"): (260_000, 330_000, 400_000),
    (1, "IN"): (600_000, 800_000, 1_000_000),
    (2, "IN"): (1_000_000, 1_300_000, 1_600_000),
    (3, "IN"): (1_600_000, 2_000_000, 2_500_000),
    (4, "IN"): (2_500_000, 3_200_000, 4_000_000),
    (5, "IN"): (4_000_000, 5_000_000, 6_000_000),
    (6, "IN"): (6_000_000, 8_000_000, 10_000_000),
    (7, "IN"): (10_000_000, 14_000_000, 18_000_000),
}

COUNTRY_WEIGHTS = [("US", 60), ("IN", 25), ("UK", 15)]
LEVEL_WEIGHTS = [(1, 6), (2, 16), (3, 28), (4, 24), (5, 16), (6, 8), (7, 2)]
EMPLOYMENT_TYPE_WEIGHTS = [("full_time", 85), ("part_time", 5), ("contractor", 10)]

# Curated name lists. Small but varied enough that 10k employees + a numeric
# suffix on the email keeps things unique without external dependencies.
FIRST_NAMES = [
    "Aanya",
    "Aarav",
    "Aisha",
    "Akira",
    "Alex",
    "Amelia",
    "Ananya",
    "Ankit",
    "Arjun",
    "Asha",
    "Avery",
    "Ben",
    "Cameron",
    "Carlos",
    "Chen",
    "Chloe",
    "Daniel",
    "Deepak",
    "Eli",
    "Emma",
    "Ethan",
    "Fatima",
    "Gabriel",
    "Grace",
    "Hannah",
    "Hari",
    "Hassan",
    "Imani",
    "Isabella",
    "Ishan",
    "Jack",
    "James",
    "Jasmine",
    "Kai",
    "Karthik",
    "Kavya",
    "Kiran",
    "Lakshmi",
    "Leo",
    "Liam",
    "Mei",
    "Meera",
    "Mia",
    "Mohammed",
    "Nadia",
    "Naman",
    "Naomi",
    "Neha",
    "Noah",
    "Olivia",
    "Oscar",
    "Pooja",
    "Priya",
    "Rahul",
    "Raj",
    "Riya",
    "Sara",
    "Shreya",
    "Sofia",
    "Sophia",
    "Tara",
    "Uma",
    "Vikram",
    "Wei",
    "William",
    "Yara",
    "Yuki",
    "Zara",
]

LAST_NAMES = [
    "Adams",
    "Agarwal",
    "Ahmed",
    "Allen",
    "Anand",
    "Andrews",
    "Bhatt",
    "Brown",
    "Chakraborty",
    "Chen",
    "Clark",
    "Cooper",
    "Das",
    "Davies",
    "Davis",
    "Desai",
    "Edwards",
    "Evans",
    "Foster",
    "Garcia",
    "Ghosh",
    "Gupta",
    "Harris",
    "Hassan",
    "Iyer",
    "Jain",
    "Johnson",
    "Jones",
    "Kapoor",
    "Kaur",
    "Khan",
    "Kim",
    "Krishnan",
    "Kumar",
    "Kim",
    "Lee",
    "Li",
    "Lewis",
    "Liu",
    "Lopez",
    "Malhotra",
    "Martin",
    "Mehta",
    "Miller",
    "Mitra",
    "Mohan",
    "Nair",
    "Nakamura",
    "Nguyen",
    "OBrien",
    "Park",
    "Patel",
    "Peters",
    "Pillai",
    "Prasad",
    "Rao",
    "Reddy",
    "Rodriguez",
    "Sen",
    "Shah",
    "Sharma",
    "Singh",
    "Smith",
    "Sundaram",
    "Sutton",
    "Taylor",
    "Thomas",
    "Verma",
    "Walker",
    "Wang",
    "Williams",
    "Wilson",
    "Wright",
    "Yamamoto",
    "Young",
    "Zhang",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def weighted_choice(weighted: list[tuple[Any, int]]) -> Any:
    items, weights = zip(*weighted, strict=True)
    return random.choices(items, weights=weights, k=1)[0]


def already_seeded(conn: Connection) -> bool:
    return (conn.execute(text("SELECT count(*) FROM employees")).scalar_one() or 0) > 0


# ---------------------------------------------------------------------------
# Per-table seeders
# ---------------------------------------------------------------------------


def seed_hr_user(conn: Connection) -> str:
    """Create the HR user (idempotent). Returns the user's UUID."""
    hashed = bcrypt.hashpw(
        settings.hr_user_password.encode(),
        bcrypt.gensalt(rounds=12),
    ).decode()
    conn.execute(
        text(
            """
            INSERT INTO users (email, password_hash)
            VALUES (:email, :password_hash)
            ON CONFLICT (email) DO NOTHING
            """
        ),
        {"email": settings.hr_user_email, "password_hash": hashed},
    )
    return conn.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": settings.hr_user_email},
    ).scalar_one()


def seed_departments(conn: Connection) -> dict[str, int]:
    for name in DEPARTMENTS:
        conn.execute(
            text("INSERT INTO departments (name) VALUES (:name) ON CONFLICT DO NOTHING"),
            {"name": name},
        )
    rows = conn.execute(text("SELECT id, name FROM departments")).all()
    return {name: id_ for id_, name in rows}


def seed_levels(conn: Connection) -> dict[int, int]:
    for code, rank in LEVELS:
        conn.execute(
            text("INSERT INTO levels (code, rank) VALUES (:code, :rank) " "ON CONFLICT DO NOTHING"),
            {"code": code, "rank": rank},
        )
    rows = conn.execute(text("SELECT id, rank FROM levels")).all()
    return {rank: id_ for id_, rank in rows}


def seed_currencies(conn: Connection) -> None:
    for code, name, ratio in CURRENCIES:
        conn.execute(
            text(
                """
                INSERT INTO currencies (code, name, ratio_to_usd)
                VALUES (:code, :name, :ratio)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"code": code, "name": name, "ratio": ratio},
        )


def seed_comp_bands(conn: Connection, level_id_by_rank: dict[int, int]) -> None:
    for (rank, country), (lo, mid, hi) in COMP_BANDS.items():
        conn.execute(
            text(
                """
                INSERT INTO comp_bands
                    (level_id, country, currency_code, band_min, band_mid, band_max)
                VALUES (:level_id, :country, :currency, :lo, :mid, :hi)
                ON CONFLICT (level_id, country) DO NOTHING
                """
            ),
            {
                "level_id": level_id_by_rank[rank],
                "country": country,
                "currency": COUNTRY_TO_CURRENCY[country],
                "lo": lo,
                "mid": mid,
                "hi": hi,
            },
        )


# ---------------------------------------------------------------------------
# Employee generation (the meat of the script)
# ---------------------------------------------------------------------------


def generate_career(
    country: str,
) -> tuple[int, date, list[dict[str, Any]]]:
    """Simulate one employee's career arc.

    Returns (final_level_rank, hire_date, list_of_salary_change_rows).
    The list is in chronological order and includes a 'hire' row.
    """
    # Starting level at hire: skewed toward L2-L3 for individual contributors.
    starting_rank = weighted_choice([(1, 15), (2, 30), (3, 30), (4, 15), (5, 7), (6, 3)])

    # Hire date in the last 5 years; biased toward more recent (org grew over time).
    days_ago = int(random.triangular(0, 5 * 365, 365))
    hire_date = date.today() - timedelta(days=days_ago)

    current_rank = starting_rank
    currency = COUNTRY_TO_CURRENCY[country]
    band_lo, band_mid, _ = COMP_BANDS[(current_rank, country)]
    # Start somewhere in the lower half of the band.
    current_amount = random.uniform(band_lo, band_mid)

    rows: list[dict[str, Any]] = [
        {
            "effective_date": hire_date,
            "amount": round(current_amount, 2),
            "currency_code": currency,
            "reason": "hire",
            "note": None,
        }
    ]

    current_date = hire_date
    today = date.today()
    while True:
        # 9-21 months between changes (clamped so we don't loop forever).
        days_later = random.randint(270, 630)
        next_date = current_date + timedelta(days=days_later)
        if next_date >= today:
            break

        reason = random.choices(
            ["raise", "promo", "adjustment"],
            weights=[65, 25, 10],
            k=1,
        )[0]

        if reason == "promo" and current_rank < 7:
            current_rank += 1
            new_lo, _, _ = COMP_BANDS[(current_rank, country)]
            current_amount = max(
                current_amount * random.uniform(1.15, 1.30),
                new_lo,
            )
        elif reason == "raise":
            current_amount *= random.uniform(1.03, 1.10)
        else:  # adjustment
            current_amount *= random.uniform(0.97, 1.05)

        rows.append(
            {
                "effective_date": next_date,
                "amount": round(current_amount, 2),
                "currency_code": currency,
                "reason": reason,
                "note": None,
            }
        )
        current_date = next_date

    return current_rank, hire_date, rows


def seed_employees_and_history(
    conn: Connection,
    size: int,
    hr_user_id: str,
    dept_id_by_name: dict[str, int],
    level_id_by_rank: dict[int, int],
) -> None:
    employees: list[dict[str, Any]] = []
    salary_changes: list[dict[str, Any]] = []
    equity_grants: list[dict[str, Any]] = []

    # Pass 1: generate all employees + their salary/equity histories.
    # Track each employee's final rank for the manager-assignment pass.
    by_rank: dict[int, list[str]] = defaultdict(list)
    rank_by_emp_id: dict[str, int] = {}

    for i in range(1, size + 1):
        country = weighted_choice(COUNTRY_WEIGHTS)
        final_rank, hire_date, salary_rows = generate_career(country)

        emp_id = str(uuid.uuid4())
        by_rank[final_rank].append(emp_id)
        rank_by_emp_id[emp_id] = final_rank

        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        employees.append(
            {
                "id": emp_id,
                "employee_no": f"ACM-{i:05d}",
                "first_name": first,
                "last_name": last,
                "email": f"{first.lower()}.{last.lower()}{i}@acme.org",
                "country": country,
                "department_id": dept_id_by_name[random.choice(DEPARTMENTS)],
                "level_id": level_id_by_rank[final_rank],
                "manager_id": None,  # filled in pass 2
                "employment_type": weighted_choice(EMPLOYMENT_TYPE_WEIGHTS),
                "hire_date": hire_date,
                "status": "active",
            }
        )
        for row in salary_rows:
            salary_changes.append(
                {
                    "id": str(uuid.uuid4()),
                    "employee_id": emp_id,
                    "created_by": hr_user_id,
                    **row,
                }
            )

        # Equity grants for L4+, scaled by level. Probability of having any
        # grant climbs from 30% (L4) to 90% (L7). Grant size scales too.
        if final_rank >= 4:
            grant_prob = {4: 0.30, 5: 0.55, 6: 0.75, 7: 0.90}[final_rank]
            if random.random() < grant_prob:
                num_grants = random.choices([1, 2, 3], weights=[60, 30, 10], k=1)[0]
                base_shares = {4: 500, 5: 1500, 6: 4000, 7: 10000}[final_rank]
                for _ in range(num_grants):
                    days_after_hire = random.randint(30, max(31, (date.today() - hire_date).days))
                    grant_date = hire_date + timedelta(days=days_after_hire)
                    equity_grants.append(
                        {
                            "id": str(uuid.uuid4()),
                            "employee_id": emp_id,
                            "grant_date": grant_date,
                            "shares": int(base_shares * random.uniform(0.5, 2.0)),
                            "created_by": hr_user_id,
                        }
                    )

    # Pass 2: assign each employee a manager from 1-2 ranks above. L6 and L7
    # may end up with no manager (no one's above them). O(N) using the
    # rank_by_emp_id map we built above.
    manager_updates: list[dict[str, Any]] = []
    for emp in employees:
        emp_rank = rank_by_emp_id[emp["id"]]
        candidates: list[str] = []
        for higher_rank in (emp_rank + 1, emp_rank + 2):
            if higher_rank in by_rank:
                candidates.extend(by_rank[higher_rank])
        if candidates:
            manager_id = random.choice(candidates)
            manager_updates.append({"id": emp["id"], "manager_id": manager_id})

    # Pass 3: bulk insert. employees go in with manager_id = NULL because
    # the FK to employees(id) is checked row-by-row inside executemany —
    # filling it in a second statement is simpler than topological sorting.
    print(f"  inserting {len(employees):,} employees (manager_id NULL)...")
    _batched_insert(
        conn,
        """
        INSERT INTO employees
            (id, employee_no, first_name, last_name, email, country,
             department_id, level_id, manager_id, employment_type,
             hire_date, status)
        VALUES
            (:id, :employee_no, :first_name, :last_name, :email, :country,
             :department_id, :level_id, :manager_id, :employment_type,
             :hire_date, :status)
        """,
        employees,
    )

    if manager_updates:
        print(f"  linking {len(manager_updates):,} manager relationships...")
        _batched_insert(
            conn,
            "UPDATE employees SET manager_id = :manager_id WHERE id = :id",
            manager_updates,
        )

    print(f"  inserting {len(salary_changes):,} salary_changes...")
    _batched_insert(
        conn,
        """
        INSERT INTO salary_changes
            (id, employee_id, effective_date, amount, currency_code,
             reason, note, created_by)
        VALUES
            (:id, :employee_id, :effective_date, :amount, :currency_code,
             :reason, :note, :created_by)
        """,
        salary_changes,
    )

    print(f"  inserting {len(equity_grants):,} equity_grants...")
    _batched_insert(
        conn,
        """
        INSERT INTO equity_grants
            (id, employee_id, grant_date, shares, created_by)
        VALUES
            (:id, :employee_id, :grant_date, :shares, :created_by)
        """,
        equity_grants,
    )


def _batched_insert(
    conn: Connection,
    statement: str,
    rows: list[dict[str, Any]],
    batch_size: int = 1000,
) -> None:
    if not rows:
        return
    stmt = text(statement)
    for i in range(0, len(rows), batch_size):
        conn.execute(stmt, rows[i : i + batch_size])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    random.seed(42)
    size = int(os.getenv("SEED_SIZE", "10000"))

    with engine.begin() as conn:
        hr_user_id = seed_hr_user(conn)
        print(f"  HR user: {settings.hr_user_email} ({hr_user_id})")

        if already_seeded(conn):
            print("employees table already populated — skipping bulk seed.")
            print(
                "  to reseed: psql ... -c 'TRUNCATE employees, comp_bands, "
                "departments, levels, currencies, users, nl_query_log "
                "RESTART IDENTITY CASCADE;' && python -m scripts.seed"
            )
            return 0

        dept_id_by_name = seed_departments(conn)
        print(f"  {len(dept_id_by_name)} departments")

        level_id_by_rank = seed_levels(conn)
        print(f"  {len(level_id_by_rank)} levels")

        seed_currencies(conn)
        print(f"  {len(CURRENCIES)} currencies")

        seed_comp_bands(conn, level_id_by_rank)
        print(f"  {len(COMP_BANDS)} comp_bands")

        print(f"generating {size:,} employees...")
        seed_employees_and_history(
            conn,
            size,
            hr_user_id=hr_user_id,
            dept_id_by_name=dept_id_by_name,
            level_id_by_rank=level_id_by_rank,
        )

    print("seed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
