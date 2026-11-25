"""
eWoodX sensing and projection synchronization configuration.
"""

# ============================================================
# SYNCHRONIZATION
# ============================================================

ENABLE_SYNCHRONIZATION = False


# ============================================================
# TIMING
# ============================================================

# Settling time after projector blanking acknowledgment.
SYNC_SETTLING_TIME_MS = 100

# Number of potentially buffered camera frames to discard.
SYNC_DISCARD_FRAMES = 2

# Minimum projection visibility between capture cycles.
SYNC_MIN_PROJECTION_TIME_MS = 200

# Timeout for individual projector command acknowledgments.
SYNC_COMMAND_TIMEOUT_MS = 1000