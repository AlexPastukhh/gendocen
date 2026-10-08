def produce(ctx, fields):
    return fields.read(ctx, "C", "total")
