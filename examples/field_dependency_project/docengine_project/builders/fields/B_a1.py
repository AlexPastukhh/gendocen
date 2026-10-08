def produce(ctx, fields):
    return fields.read(ctx, "C", "x") * 2
