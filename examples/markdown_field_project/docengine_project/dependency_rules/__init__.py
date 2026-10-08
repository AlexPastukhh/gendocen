def register(registry):
    from .decisions.reuse import register as register_reuse
    from .decisions.full_policy import register as register_full
    register_reuse(registry)
    register_full(registry)
