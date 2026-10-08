def register(registry):
    from .views.A import register as register_a
    from .views.C import register as register_c
    register_a(registry)
    register_c(registry)
