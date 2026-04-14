from django.db import migrations

def migrate_verification_data(apps, schema_editor):
    SellerProfile = apps.get_model('marketplace', 'SellerProfile')
    SellerIDVerification = apps.get_model('sellers', 'SellerIDVerification')
    SellerBusinessVerification = apps.get_model('sellers', 'SellerBusinessVerification')
    UserVerification = apps.get_model('trust', 'UserVerification')
    
    # Map SellerVerificationStatus to UserVerificationStatus
    status_map = {
        'pending': 'pending', 
        'approved': 'verified',
        'rejected': 'rejected'
    }

    # 1. Migrate Identity Verifications
    for idv in SellerIDVerification.objects.select_related('seller', 'seller__user').all():
        try:
            profile = idv.seller
            user = profile.user
        except SellerProfile.DoesNotExist:
            continue

        uv, _ = UserVerification.objects.get_or_create(user=user)
        uv.id_type = idv.id_type
        uv.id_number = idv.id_number
        if idv.id_front_image:
            uv.national_id_front = idv.id_front_image
        if idv.selfie_with_id:
            uv.selfie_with_id = idv.selfie_with_id
        
        if profile.verification_status == 'verified':
            uv.id_status = 'verified'
        elif profile.verification_status == 'under_review':
            uv.id_status = 'pending'
        elif profile.verification_status == 'rejected':
            uv.id_status = 'rejected'
        
        uv.save()

    # 2. Migrate Business Verifications
    for bv in SellerBusinessVerification.objects.select_related('seller', 'seller__user').all():
        try:
            profile = bv.seller
            user = profile.user
        except SellerProfile.DoesNotExist:
            continue

        uv, _ = UserVerification.objects.get_or_create(user=user)
        uv.tin_number = bv.tin_number
        if bv.business_certificate:
            uv.tin_certificate = bv.business_certificate
        
        st = status_map.get(bv.status, 'pending')
        uv.tin_status = st
        uv.business_license_status = st
        uv.save()

def reverse_migrate(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('sellers', '0003_alter_sellerpayoutaccount_account_type'),
        ('trust', '0002_userverification_id_number_userverification_id_type_and_more'),
        ('marketplace', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(migrate_verification_data, reverse_migrate),
    ]
