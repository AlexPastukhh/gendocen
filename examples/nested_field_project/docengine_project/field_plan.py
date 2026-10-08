from .fields import FieldPlan
from .builders.fields.A_deadline import produce as deadline
from .builders.fields.C_total import produce as total
from .builders.fields.A_budget import produce as budget

FIELDS = FieldPlan()
FIELDS.document("A", "resource://inputs/A")
FIELDS.document("C", "resource://inputs/C")
FIELDS.input("C", "rate", "resource://inputs/C#/rate")

FIELDS.computed_path("A", "/plan/deadline", "resource://fields/A_deadline", deadline)
FIELDS.computed("C", "total", "resource://fields/C_total", total)
FIELDS.computed_path("A", "/plan/budget", "resource://fields/A_budget", budget,
                     raw_override="resource://inputs/A#/plan/budget")
