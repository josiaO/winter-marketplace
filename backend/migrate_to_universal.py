import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from core.models.category import Category as OldCategory
from catalog.models import Category as NewCategory
from core.models.media import Media as OldMedia
from media_app.models import Media as NewMedia
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

@transaction.atomic
def migrate_data():
    print("🚀 Starting data migration...")

    # 1. Migrate Categories
    print("📚 Migrating Categories...")
    category_map = {}
    
    # First pass: Create categories without parents
    old_categories = OldCategory.objects.all().order_by('id')
    for old in old_categories:
        new_cat = NewCategory.objects.create(
            id=old.id,
            name=old.name,
            slug=old.slug,
            description=old.description,
            icon=old.icon,
            vertical=old.vertical,
            is_active=old.is_active,
            order=old.order,
            created_at=old.created_at,
            updated_at=old.updated_at
        )
        category_map[old.id] = new_cat

    # Second pass: Set parents
    for old in old_categories:
        if old.parent_id:
            new_cat = category_map[old.id]
            new_cat.parent = category_map[old.parent_id]
            new_cat.save()

    print(f"✅ Migrated {len(category_map)} categories.")

    # 2. Migrate Media
    print("📸 Migrating Media...")
    old_media = OldMedia.objects.all()
    media_count = 0
    for old in old_media:
        # We need to preserve the generic relation
        NewMedia.objects.create(
            content_type=old.content_type,
            object_id=old.object_id,
            file=old.file,
            media_type=old.media_type,
            is_main=old.is_main,
            order=old.order,
            caption=old.caption,
            created_at=old.created_at,
            updated_at=old.updated_at
        )
        media_count += 1
    
    print(f"✅ Migrated {media_count} media items.")
    print("🏁 Migration complete!")

if __name__ == "__main__":
    migrate_data()
