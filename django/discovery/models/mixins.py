"""Behaviour shared by several discovery models."""

import zlib


class RangeFieldMixin:
    """``start_position`` / ``end_position`` / ``size_kb`` over the half-open int4range in ``range_field``."""

    range_field = "bgc_range"

    @property
    def start_position(self) -> int:
        return getattr(self, self.range_field).lower

    @property
    def end_position(self) -> int:
        return getattr(self, self.range_field).upper - 1

    @property
    def size_kb(self) -> float:
        rng = getattr(self, self.range_field)
        return (rng.upper - rng.lower) / 1000.0


class ZlibSequenceMixin:
    """``get_sequence`` / ``compress_sequence`` over a zlib-compressed ``data`` column."""

    def get_sequence(self) -> str:
        if self.data:
            return zlib.decompress(bytes(self.data)).decode("utf-8")
        return ""

    @staticmethod
    def compress_sequence(seq: str) -> bytes:
        return zlib.compress(seq.encode("utf-8"))
