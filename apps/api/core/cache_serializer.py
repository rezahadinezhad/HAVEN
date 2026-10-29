"""Redis is a coordination service, never a trusted Python object source."""

import json


class JSONCacheSerializer:
    def dumps(self, value):
        if type(value) is int:
            return value  # Preserve Redis atomic INCR semantics.
        result = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
        if len(result) > 65536:
            raise ValueError("Cache value exceeds local coordination budget")
        return result

    def loads(self, value):
        if len(value) > 65536:
            raise ValueError("Cache value exceeds local coordination budget")
        try:
            return int(value)
        except ValueError:
            return json.loads(value)  # No pickle/object hooks or executable decoding.
