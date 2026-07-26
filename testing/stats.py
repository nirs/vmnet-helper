# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

import json
import re

COUNTER_FIELDS = ["packets", "bytes", "drops", "fast", "slow"]

_STATS_RE = re.compile(r"\[stats\] (\{.*\})")


def parse(logfile):
    """
    Yield parsed stats entries from a vmnet-helper log file.
    """
    with open(logfile) as f:
        for line in f:
            m = _STATS_RE.search(line)
            if m:
                yield json.loads(m.group(1))


def compute_delta(prev, curr):
    """
    Compute the difference between two stats entries.
    """
    delta = {}
    for endpoint in ("host", "vm"):
        delta[endpoint] = {
            field: curr[endpoint][field] - prev[endpoint][field]
            for field in COUNTER_FIELDS
        }
    return delta
