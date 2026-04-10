# marketplace/schemas.py

VEHICLE_FIELDS = [
    "brand",
    "model",
    "year",
    "mileage",
    "fuel_type",
    "transmission",
    "condition",
    "capacity",
    "engine_size",
    "color"
]

ELECTRONICS_FIELDS = [
    "brand",
    "model",
    "ram",
    "storage",
    "condition",
    "warranty",
    "screen_size",
    "processor"
]

CLOTHES_FIELDS = [
    "size",
    "gender",
    "color",
    "material",
    "brand",
    "condition"
]

# Mapping category names to their respective fields
CATEGORY_SCHEMAS = {
    'vehicle': VEHICLE_FIELDS,
    'electronics': ELECTRONICS_FIELDS,
    'fashion': CLOTHES_FIELDS,
    'property': [], # Properties use model fields, but could have extra JSON attrs
}
