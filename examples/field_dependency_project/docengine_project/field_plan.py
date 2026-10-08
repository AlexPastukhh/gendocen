"""The explicit logical-field/source map for this project."""

from .fields import FieldPlan
from .builders.fields.A_g import produce as produce_a_g
from .builders.fields.B_a1 import produce as produce_b_a1
from .builders.fields.B_g1 import produce as produce_b_g1

FIELDS = FieldPlan()
FIELDS.input("A", "a", "resource://inputs/A#/a")
FIELDS.input("B", "b1", "resource://inputs/B#/b1")
FIELDS.input("C", "x", "resource://inputs/C#/x")
FIELDS.computed("B", "a1", "resource://fields/B_a1", produce_b_a1,
                raw_override="resource://inputs/B#/a1")
FIELDS.computed("A", "g", "resource://fields/A_g", produce_a_g)
FIELDS.computed("B", "g1", "resource://fields/B_g1", produce_b_g1)
