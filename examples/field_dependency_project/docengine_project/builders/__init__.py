def register(registry):
    from .views.A import register as register_a
    from .views.B import register as register_b

    register_a(registry)
    register_b(registry)
