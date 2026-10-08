from .fields import FieldPlan
from .builders.fields.reuse_text import produce

FIELDS = FieldPlan()
FIELDS.document("Guide", "resource://inputs/guide")
FIELDS.computed_path("Guide", "/sections/reuse/text", "resource://fields/reuse_text", produce)
