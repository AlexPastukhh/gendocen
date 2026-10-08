"""Author-selected bounds, not a general Markdown section parser."""
START = '<a id="reuse-policy"></a>'
END = '<a id="review-process"></a>'

def build(ctx):
    text = ctx.read("file://canonical/policy.md")
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("Reuse policy needs exactly one start and one end bound")
    first, last = text.index(START), text.index(END)
    if last <= first:
        raise ValueError("Reuse policy bounds are inverted")
    return {"reuse": text[first:last]}

def register(registry):
    registry.register("resource://source/policy", build)
