"""Frozen pre-change kernels for this diagnostic Project, never production defaults."""
import hashlib
from blackbase.context import snapshot_store as module


def memory_preparation(data, schema, owner):
    if not isinstance(data, module.Mapping):
        raise TypeError("Snapshot payload must be a Mapping")
    for key in data:
        if not isinstance(key, str) or not key:
            raise ValueError("Snapshot payload keys must be non-empty strings")
    profile = module._SnapshotWireProfile()
    module._validate_lossless_snapshot_value(data, _wire_profile=profile)
    if not profile.stable or profile.max_depth > 126 or profile.normalizing_array:
        return None
    codec = module.RedisValueCodec(serializer="safe", max_payload_bytes=1_073_741_824,
                                  envelope_scope="snapshot-detach")
    if profile.nodes > codec.max_nodes:
        raise module.RedisValueCodecError("safe Redis value exceeds node limit")
    try:
        frozen = module.freeze_snapshot_value(data, owner, source=data)
    except module.UnsupportedSnapshotValue:
        return None
    wire = module._safe_codec_module._to_safe_wire(frozen, path="value", depth=0,
        max_depth=codec.max_depth, active=set())
    codec._dumps_safe_wire(wire)
    tag = module._VALUE_TAG
    digest_wire = {tag: "mapping", "items": [
        ["digest_codec", module.SNAPSHOT_DIGEST_CODEC],
        ["value", {tag: "mapping", "items": [["schema", schema], ["data", wire]]}]]}
    raw = module._canonical_safe_wire_bytes(digest_wire)
    return frozen, "sha256:" + hashlib.sha256(raw).hexdigest(), raw
