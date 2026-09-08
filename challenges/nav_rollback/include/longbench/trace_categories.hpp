#pragma once

#if LONGBENCH_ENABLE_PERFETTO
#include <perfetto.h>

PERFETTO_DEFINE_CATEGORIES(
    perfetto::Category("longbench.frame")
        .SetDescription("Top-level deterministic game-loop frames"),
    perfetto::Category("longbench.system")
        .SetDescription("Coarse systems and agent-added diagnostic zones"),
    perfetto::Category("longbench.counter")
        .SetDescription("Deterministic workload counters"));
#endif
