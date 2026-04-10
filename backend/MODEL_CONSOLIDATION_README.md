# Model Consolidation - README

## What Changed

We've consolidated duplicate model logic across the platform:

### 1. ✅ Media System Consolidated
**Before:** Two systems (`media_app.Media` + `listings.ListingMedia`)  
**After:** Single system (`listings.ListingMedia`)

- ❌ **DEPRECATED**: `media_app.Media`
- ✅ **USE**: `listings.ListingMedia`

### 2. ✅ Payment System Consolidated
**Before:** Two systems (`properties.Payment` + `transactions.Transaction`)  
**After:** Single system (`transactions.Transaction` + `transactions.Order`)

- ❌ **DEPRECATED**: `properties.Payment`
- ✅ **USE**: `transactions.Transaction`

---

## Migration Required?

### If you have existing data:

Run the migration script:

```bash
cd /home/josiamosses/SmartDalali/backend
python migrate_consolidated_models.py
```

This will:
1. Copy `media_app.Media` → `listings.ListingMedia`
2. Copy `properties.Payment` → `transactions.Transaction`
3. Create corresponding `Order` records

### If this is a new installation:
No migration needed! Just use the new models.

---

## Code Changes Required

### For Media:

**Old Code:**
```python
from media_app.models import Media
from django.contrib.contenttypes.models import ContentType

ct = ContentType.objects.get_for_model(listing)
media = Media.objects.filter(content_type=ct, object_id=listing.id)
```

**New Code:**
```python
from listings.models import ListingMedia

media = ListingMedia.objects.filter(listing=listing)
```

### For Payments:

**Old Code:**
```python
from properties.models import Payment

payment = Payment.objects.create(
    user=user,
    property=property,
    method='mpesa',
    amount=100000
)
```

**New Code:**
```python
from transactions.models import Order, Transaction
from django.contrib.contenttypes.models import ContentType

# 1. Create Order
order = Order.objects.create(
    buyer=user,
    seller=property.owner,
    listing_id=property.id,
    content_type=ContentType.objects.get_for_model(property),
    amount=100000
)

# 2. Create Transaction
transaction = Transaction.objects.create(
    order=order,
    method='mpesa',
    amount=100000
)
```

---

## What's Been Updated

### ✅ Updated Files:
- `media_app/models.py` - Marked `Media` as deprecated
- `properties/models.py` - Marked `Payment` as deprecated
- `core/services/marketplace.py` - Now uses `ListingMedia`
- `listings/serializers.py` - Already uses `ListingMedia` ✅
- `migrate_consolidated_models.py` - New data migration script

### ⚠️ Files That May Need Updates:
Check these files if you have custom code:
- `properties/tests/test_models.py` - May reference old `Media`
- `properties/tests/test_views.py` - May reference old `Payment`
- Any custom views/serializers using deprecated models

---

## Deprecated Models (Keep for Backward Compatibility)

These models still exist but are marked DEPRECATED:
- `media_app.models.Media`
- `properties.models.Payment`

They will be removed in a future version after all data is migrated.

---

## Benefits

✅ **Simpler**: One way to handle media, one way to handle payments  
✅ **Faster**: Direct FK queries instead of GenericForeignKey lookups  
✅ **Clearer**: No confusion about which model to use  
✅ **Universal**: Works across all listing types (properties, vehicles, electronics)

---

## Questions?

- **Q: Can I still use the old models?**  
  A: Yes, temporarily. But please migrate to new models.

- **Q: Will my existing data be lost?**  
  A: No. Run the migration script to preserve all data.

- **Q: What if the migration fails?**  
  A: Old models still work. You can retry migration or ask for help.

---

## Next Steps

1. ✅ Run migration script (if you have existing data)
2. ✅ Update any custom code to use new models
3. ✅ Test your application
4. ✅ Remove old model imports from your code
