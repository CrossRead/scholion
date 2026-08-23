"""`ingest-garmin`, kept as a name — the work lives in `wearables`.

This module used to be the Garmin ingest: it found the export, loaded the reader,
merged the fresh build with the previous file and wrote the trends. When a second
device arrived none of that could stay device-specific — a Garmin and a WHOOP
report the same measurements and do not measure them the same way, so a
measurement is now stored together with the device that made it. The discovery
rules, the merge that stops an incomplete export erasing history, and the backup
all moved to `wearables.py` and were generalised there.

What did not move is the NAME. `ingest-garmin` is in the public contract, and the
contract may grow and may not shrink. So the command survives as one line that
asks for the Garmin watch BY NAME — which is also the only thing here worth
having: without the name a WHOOP export handed to `ingest-garmin` would be filed
under the wrong watch, and nothing downstream could tell.

Until 23.08.2026 the superseded implementation was still sitting underneath it —
six functions, a hundred and forty-three of this file's hundred and eighty-five
lines, with no caller anywhere. It was kept «until the next release cleans it
out» and then read as live code twice: once by a test suite that measured its
coverage, and once by a boundary test that checked the search rule on the copy
that no longer runs. A duplicate that outlives its purpose does not sit quietly;
it collects the attention meant for the original.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def reingest(folder: Optional[str] = None) -> Dict[str, Any]:
    """Rebuild the Garmin part of the lifestyle layer.

    Asks for the Garmin watch by name, so the old command cannot be handed a
    WHOOP export and quietly file it under the wrong device.
    """
    from . import wearables
    return wearables.reingest(folder, source="garmin")
