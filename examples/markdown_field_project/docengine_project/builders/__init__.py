def register(registry):
    from .source.policy import register as register_policy
    from .views.guide import register as register_guide
    register_policy(registry)
    register_guide(registry)
