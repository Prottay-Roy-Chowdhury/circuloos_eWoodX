"""eWoodX entity configuration."""


TIMBER_ENTITY_TYPE = "timber"

TIMBER_ID_PREFIX = "T"

ENTITY_ID_SEQUENCE_MIN_WIDTH = 4
ENTITY_ID_SEQUENCE_MAX_VALUE = 999999

ENTITY_ID_RANDOM_LENGTH = 3
ENTITY_ID_RANDOM_ALPHABET = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


TIMBER_ENTITY_INDEX = {
    "color": "TEXT",
    "length_mm": "REAL",
    "width_mm": "REAL",
    "thickness_mm": "REAL",
    "area_mm2": "REAL",
}