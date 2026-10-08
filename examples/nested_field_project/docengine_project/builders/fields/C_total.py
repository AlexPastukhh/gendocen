def produce(ctx, fields):
    return fields.read_path(ctx, "A", "/plan/deadline") * fields.read(ctx, "C", "rate")
