def produce(ctx, fields):
    return fields.read(ctx, "A", "g") + 1
