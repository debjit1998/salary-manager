"""Shared Literal types used across multiple domain modules.

These mirror the Postgres CHECK constraints in the schema. Keeping them
in one place avoids the "did someone add a new value here but not
there?" class of bug. If you add a value, update:

  1. The DB CHECK constraint (alembic migration)
  2. The Literal here
  3. The schema_hints.yaml entry for the relevant column (for the NL
     feature's system prompt)
"""

from __future__ import annotations

from typing import Literal

Country = Literal["US", "UK", "IN"]
Currency = Literal["USD", "GBP", "INR"]
EmploymentType = Literal["full_time", "part_time", "contractor"]
EmployeeStatus = Literal["active", "terminated"]
SalaryReason = Literal["hire", "raise", "promo", "adjustment"]
BandPosition = Literal["below", "within", "above"]
Dimension = Literal["department", "level", "country", "employment_type"]
