"""
Django management command to generate test data for SmartDalali Marketplace.
Downloads images using the scraper and creates realistic marketplace listings with categories.

Usage: python manage.py generate_marketplace_data
"""
import os
import random
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files import File
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from listings.models import Listing, ListingMedia
from catalog.models import Category
from accounts.models import Profile
from marketplace.models import SellerProfile, Store
from datetime import timedelta
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Command(BaseCommand):
    help = 'Generate test data with real images for marketplace listings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=50,
            help='Number of seller users to create (default: 50)'
        )
        parser.add_argument(
            '--listings',
            type=int,
            default=150,
            help='Number of listings to create (default: 150, minimum: 100)'
        )

    def handle(self, *args, **options):
        num_users = options['users']
        num_listings = max(options['listings'], 100)  # Ensure at least 100

        self.stdout.write(self.style.SUCCESS('=== SmartDalali Marketplace Test Data Generator ===\n'))
        
        # Step 1: Download images
        self.stdout.write('Step 1: Downloading images...')
        product_images = self.download_images(
            'https://unsplash.com/s/photos/product',
            'products',
            num_listings * 3  # 3 images per listing average
        )
        accessory_images = self.download_images(
            'https://unsplash.com/s/photos/accessories',
            'accessories',
            num_listings * 2  # Additional images
        )
        all_images = product_images + accessory_images
        random.shuffle(all_images)  # Randomize image selection

        # Step 2: Create categories and subcategories
        self.stdout.write('\nStep 2: Creating categories and subcategories...')
        categories_map = self.create_categories()

        # Step 3: Create seller users
        self.stdout.write(f'\nStep 3: Creating {num_users} seller users...')
        sellers = self.create_sellers(num_users)

        # Step 4: Create listings
        self.stdout.write(f'\nStep 4: Creating {num_listings} marketplace listings...')
        listings = self.create_listings(num_listings, sellers, categories_map, all_images)

        self.stdout.write(self.style.SUCCESS(f'\n✓ Test data generation complete!'))
        self.stdout.write(self.style.SUCCESS(f'  - Created {len(categories_map)} categories'))
        self.stdout.write(self.style.SUCCESS(f'  - Created {len(sellers)} sellers'))
        self.stdout.write(self.style.SUCCESS(f'  - Created {len(listings)} listings'))

    def download_images(self, url, category, max_images):
        """Download images from Unsplash"""
        self.stdout.write(f'  Scraping {url}...')
        
        try:
            html = requests.get(url, timeout=10, verify=False).text
            soup = BeautifulSoup(html, 'html.parser')
            
            image_urls = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and 'images.unsplash.com' in src:
                    # Get full resolution image
                    if 'w=' in src:
                        src = src.split('w=')[0] + 'w=800'
                    image_urls.append(src)
                if len(image_urls) >= max_images:
                    break
            
            self.stdout.write(f'  Found {len(image_urls)} image URLs')
            
            # Download images
            save_dir = os.path.join(settings.MEDIA_ROOT, f'test_data/{category}')
            os.makedirs(save_dir, exist_ok=True)
            
            downloaded = []
            for i, img_url in enumerate(image_urls[:max_images]):
                try:
                    response = requests.get(img_url, timeout=10, verify=False)
                    if response.status_code == 200:
                        filename = f'{category}_{i+1}.jpg'
                        filepath = os.path.join(save_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        downloaded.append(filepath)
                        if (i + 1) % 20 == 0:
                            self.stdout.write(f'    Downloaded {i+1}/{max_images}...')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'    Failed to download image {i+1}: {e}'))
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Downloaded {len(downloaded)} images'))
            
            # Fallback if no images downloaded
            if not downloaded:
                self.stdout.write(self.style.WARNING("  ! No images downloaded. Generating placeholders..."))
                return self.generate_placeholders(save_dir, category, max_images)
                
            return downloaded
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Failed to scrape images: {e}'))
            return self.generate_placeholders(
                os.path.join(settings.MEDIA_ROOT, f'test_data/{category}'), 
                category, 
                max_images
            )

    def generate_placeholders(self, save_dir, category, count):
        """Generate placeholder images when download fails"""
        os.makedirs(save_dir, exist_ok=True)
        paths = []
        # 1x1 gray pixel JPEG
        placeholder_data = b'/9j/4AAQSkZJRgABAQEASABIAAD/2wBDCAgKCgoKCgsKCgoICgoKCAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AH8AL//Z'
        
        import base64
        data = base64.b64decode(placeholder_data)
        
        for i in range(count):
            filename = f'{category}_placeholder_{i+1}.jpg'
            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(data)
            paths.append(filepath)
            
        self.stdout.write(self.style.SUCCESS(f'  ✓ Generated {count} placeholder images'))
        return paths

    def create_categories(self):
        """Create categories and subcategories for marketplace"""
        categories_map = {}
        
        # Electronics category structure
        electronics = Category.objects.get_or_create(
            name='Electronics',
            slug='electronics',
            defaults={
                'description': 'Electronic devices and gadgets',
                'vertical': 'electronics',
                'is_active': True,
                'order': 1,
            }
        )[0]
        
        electronics_subcategories = [
            ('Smartphones', 'smartphones', 'Mobile phones and smartphones'),
            ('Laptops', 'laptops', 'Laptops and notebooks'),
            ('Tablets', 'tablets', 'Tablets and e-readers'),
            ('Headphones', 'headphones', 'Audio devices and headphones'),
            ('Cameras', 'cameras', 'Digital cameras and accessories'),
            ('Gaming', 'gaming', 'Gaming consoles and accessories'),
        ]
        
        for name, slug_name, desc in electronics_subcategories:
            subcat = Category.objects.get_or_create(
                name=name,
                slug=slug_name,
                parent=electronics,
                defaults={
                    'description': desc,
                    'vertical': 'electronics',
                    'is_active': True,
                }
            )[0]
            categories_map[slug_name] = subcat
            self.stdout.write(f'  ✓ Created category: Electronics > {name}')
        
        # Fashion category structure
        fashion = Category.objects.get_or_create(
            name='Fashion',
            slug='fashion',
            defaults={
                'description': 'Fashion and clothing items',
                'vertical': 'fashion',
                'is_active': True,
                'order': 2,
            }
        )[0]
        
        fashion_subcategories = [
            ('Clothing', 'clothing', 'Men and women clothing'),
            ('Shoes', 'shoes', 'Footwear and shoes'),
            ('Accessories', 'fashion-accessories', 'Fashion accessories and jewelry'),
            ('Bags', 'bags', 'Handbags and backpacks'),
            ('Watches', 'watches', 'Wristwatches and timepieces'),
        ]
        
        for name, slug_name, desc in fashion_subcategories:
            subcat = Category.objects.get_or_create(
                name=name,
                slug=slug_name,
                parent=fashion,
                defaults={
                    'description': desc,
                    'vertical': 'fashion',
                    'is_active': True,
                }
            )[0]
            categories_map[slug_name] = subcat
            self.stdout.write(f'  ✓ Created category: Fashion > {name}')
        
        # Home & Garden category structure
        home = Category.objects.get_or_create(
            name='Home & Garden',
            slug='home-garden',
            defaults={
                'description': 'Home and garden products',
                'vertical': 'other',
                'is_active': True,
                'order': 3,
            }
        )[0]
        
        home_subcategories = [
            ('Furniture', 'furniture', 'Home furniture and decor'),
            ('Kitchen', 'kitchen', 'Kitchen appliances and tools'),
            ('Garden', 'garden', 'Garden tools and plants'),
            ('Home Decor', 'home-decor', 'Home decoration items'),
        ]
        
        for name, slug_name, desc in home_subcategories:
            subcat = Category.objects.get_or_create(
                name=name,
                slug=slug_name,
                parent=home,
                defaults={
                    'description': desc,
                    'vertical': 'other',
                    'is_active': True,
                }
            )[0]
            categories_map[slug_name] = subcat
            self.stdout.write(f'  ✓ Created category: Home & Garden > {name}')
        
        # Sports & Outdoors
        sports = Category.objects.get_or_create(
            name='Sports & Outdoors',
            slug='sports-outdoors',
            defaults={
                'description': 'Sports equipment and outdoor gear',
                'vertical': 'other',
                'is_active': True,
                'order': 4,
            }
        )[0]
        
        sports_subcategories = [
            ('Fitness', 'fitness', 'Fitness equipment and accessories'),
            ('Outdoor Gear', 'outdoor-gear', 'Camping and outdoor equipment'),
            ('Sports Equipment', 'sports-equipment', 'Sports gear and equipment'),
        ]
        
        for name, slug_name, desc in sports_subcategories:
            subcat = Category.objects.get_or_create(
                name=name,
                slug=slug_name,
                parent=sports,
                defaults={
                    'description': desc,
                    'vertical': 'other',
                    'is_active': True,
                }
            )[0]
            categories_map[slug_name] = subcat
            self.stdout.write(f'  ✓ Created category: Sports & Outdoors > {name}')
        
        return categories_map

    def create_sellers(self, count):
        """Create seller user accounts"""
        sellers = []
        first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'James', 'Olivia', 'Robert', 'Sophia', 
                      'William', 'Ava', 'Joseph', 'Isabella', 'Charles', 'Mia', 'Daniel', 'Charlotte', 'Matthew', 'Amelia']
        last_names = ['Mwangi', 'Kamau', 'Ochieng', 'Moshi', 'Njoroge', 'Wanjiru', 'Kimani', 'Otieno', 'Mwamba', 
                     'Nyambura', 'Kariuki', 'Achieng', 'Mutua', 'Wambui', 'Omondi', 'Juma', 'Hassan', 'Mwalimu', 'Baraka', 'Salim']
        
        cities = ['Dar es Salaam', 'Arusha', 'Mwanza', 'Dodoma', 'Mbeya', 'Tanga', 'Morogoro', 'Zanzibar']
        
        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f'seller.{first_name.lower()}.{last_name.lower()}{i+1}'
            email = f'{username}@smartdalali.co.tz'
            
            # Create user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
                
                # Generate phone number
                phone_number = f'+255{random.randint(700000000, 799999999)}'
                address = f'{random.choice(cities)}, Tanzania'
                
                # Update or create profile
                profile, profile_created = Profile.objects.get_or_create(
                    user=user,
                    defaults={
                        'name': f'{first_name} {last_name}',
                        'phone_number': phone_number,
                        'address': address,
                    }
                )
                
                # Ensure profile has phone number even if it already existed
                if not profile_created and (not profile.phone_number or profile.phone_number == ''):
                    profile.phone_number = phone_number
                    profile.address = address
                    profile.name = f'{first_name} {last_name}'
                    profile.save()
                
                # Create seller profile
                business_name = f'{last_name} {random.choice(["Store", "Shop", "Trading", "Enterprises", "Ltd"])}'
                # Ensure we have a valid phone number (never None or empty)
                business_phone = profile.phone_number if (profile.phone_number and profile.phone_number.strip()) else phone_number
                business_address = profile.address if (profile.address and profile.address.strip()) else address
                
                # Ensure business_phone is never empty (database constraint)
                if not business_phone or not business_phone.strip():
                    business_phone = phone_number
                
                seller_profile, _ = SellerProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'business_name': business_name,
                        'business_type': random.choice(['individual', 'business', 'retailer']),
                        'business_phone': business_phone,  # Always has a value
                        'business_email': email,
                        'business_address': business_address,
                        'is_active': True,
                        'is_verified': random.choice([True, False]),  # Some verified sellers
                    }
                )
                
                # Create a store for the seller
                store_slug = slugify(business_name)
                # Ensure unique slug
                base_slug = store_slug
                counter = 1
                while Store.objects.filter(slug=store_slug).exists():
                    store_slug = f'{base_slug}-{counter}'
                    counter += 1
                
                store, _ = Store.objects.get_or_create(
                    seller=seller_profile,
                    slug=store_slug,
                    defaults={
                        'name': business_name,
                        'description': f'Quality products from {business_name}. We offer the best deals in Tanzania.',
                        'is_active': True,
                        'is_featured': random.choice([True, False]),  # Some featured stores
                    }
                )
                
                sellers.append({
                    'user': user,
                    'seller_profile': seller_profile,
                    'store': store
                })
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'  Created {i+1}/{count} sellers...')
        
        return sellers

    def create_listings(self, count, sellers, categories_map, image_paths):
        """Create marketplace listings with images"""
        listings = []
        
        # Product titles by category
        product_titles = {
            'smartphones': [
                'Premium Smartphone', 'Latest Model Phone', 'High-End Mobile Device',
                'Budget-Friendly Smartphone', 'Flagship Phone', '5G Enabled Device'
            ],
            'laptops': [
                'Gaming Laptop', 'Business Laptop', 'Ultrabook', 'Student Laptop',
                'Professional Workstation', 'Portable Notebook'
            ],
            'tablets': [
                'Tablet Computer', 'E-Reader Tablet', 'Drawing Tablet', 'Kids Tablet',
                'Professional Tablet', 'Entertainment Tablet'
            ],
            'headphones': [
                'Wireless Headphones', 'Noise-Cancelling Headphones', 'Gaming Headset',
                'Studio Headphones', 'Sports Earbuds', 'Premium Audio Headphones'
            ],
            'cameras': [
                'Digital Camera', 'DSLR Camera', 'Action Camera', 'Vlogging Camera',
                'Professional Camera', 'Compact Camera'
            ],
            'gaming': [
                'Gaming Console', 'Gaming Controller', 'Gaming Mouse', 'Gaming Keyboard',
                'Gaming Chair', 'Gaming Monitor'
            ],
            'clothing': [
                'Designer Shirt', 'Casual T-Shirt', 'Formal Dress', 'Jeans',
                'Jacket', 'Sweater', 'Dress Shirt'
            ],
            'shoes': [
                'Running Shoes', 'Casual Sneakers', 'Formal Shoes', 'Sports Shoes',
                'Boots', 'Sandals', 'High Heels'
            ],
            'fashion-accessories': [
                'Leather Belt', 'Sunglasses', 'Jewelry Set', 'Wallet',
                'Scarf', 'Hat', 'Necklace'
            ],
            'bags': [
                'Leather Handbag', 'Backpack', 'Travel Bag', 'Laptop Bag',
                'Crossbody Bag', 'Tote Bag'
            ],
            'watches': [
                'Smart Watch', 'Luxury Watch', 'Sports Watch', 'Classic Watch',
                'Digital Watch', 'Fashion Watch'
            ],
            'furniture': [
                'Modern Sofa', 'Dining Table', 'Office Chair', 'Bookshelf',
                'Coffee Table', 'Bed Frame'
            ],
            'kitchen': [
                'Coffee Maker', 'Blender', 'Cookware Set', 'Kitchen Knife Set',
                'Food Processor', 'Microwave Oven'
            ],
            'garden': [
                'Garden Tools Set', 'Plant Pots', 'Garden Hose', 'Lawn Mower',
                'Garden Furniture', 'Plant Seeds'
            ],
            'home-decor': [
                'Wall Art', 'Decorative Lamp', 'Throw Pillows', 'Curtains',
                'Rug', 'Vase Set'
            ],
            'fitness': [
                'Dumbbells Set', 'Yoga Mat', 'Resistance Bands', 'Treadmill',
                'Exercise Bike', 'Fitness Tracker'
            ],
            'outdoor-gear': [
                'Camping Tent', 'Sleeping Bag', 'Backpack', 'Hiking Boots',
                'Camping Stove', 'Water Bottle'
            ],
            'sports-equipment': [
                'Basketball', 'Football', 'Tennis Racket', 'Golf Clubs',
                'Bicycle', 'Skateboard'
            ],
        }
        
        # Product descriptions
        descriptions = [
            'High-quality product in excellent condition. Perfect for everyday use.',
            'Brand new item with original packaging. Great value for money.',
            'Premium quality product with modern design. Well-maintained and ready to use.',
            'Excellent condition product. Perfect for both personal and professional use.',
            'Top-quality item with all original accessories included.',
            'Like-new condition. Barely used and well cared for.',
            'Professional grade product suitable for various applications.',
            'Stylish and functional design. Great addition to any collection.',
        ]
        
        # Price ranges by category (in TZS)
        price_ranges = {
            'smartphones': (500000, 5000000),
            'laptops': (1000000, 10000000),
            'tablets': (300000, 3000000),
            'headphones': (50000, 500000),
            'cameras': (800000, 8000000),
            'gaming': (200000, 5000000),
            'clothing': (20000, 200000),
            'shoes': (50000, 500000),
            'fashion-accessories': (10000, 300000),
            'bags': (50000, 800000),
            'watches': (100000, 2000000),
            'furniture': (200000, 5000000),
            'kitchen': (50000, 1000000),
            'garden': (30000, 800000),
            'home-decor': (20000, 500000),
            'fitness': (50000, 2000000),
            'outdoor-gear': (100000, 3000000),
            'sports-equipment': (50000, 1500000),
        }
        
        cities = ['Dar es Salaam', 'Arusha', 'Mwanza', 'Dodoma', 'Mbeya', 'Tanga', 'Morogoro', 'Zanzibar']
        
        # Get all leaf categories (subcategories)
        leaf_categories = list(categories_map.values())
        
        for i in range(count):
            seller_data = random.choice(sellers)
            seller = seller_data['user']
            seller_profile = seller_data['seller_profile']
            store = seller_data['store']
            
            category = random.choice(leaf_categories)
            category_slug = None
            for slug, cat in categories_map.items():
                if cat.id == category.id:
                    category_slug = slug
                    break
            
            # Get title and price based on category
            titles = product_titles.get(category_slug, ['Product Item', 'Quality Item', 'Premium Product'])
            title = f'{random.choice(titles)} - {i+1}'
            price_range = price_ranges.get(category_slug, (10000, 1000000))
            price = random.randint(price_range[0], price_range[1])
            price = round(price / 1000) * 1000  # Round to nearest 1000
            
            # Create listing linked to seller profile and store
            city = random.choice(cities)
            listing = Listing.objects.create(
                owner=seller,
                store=store,  # Link to store
                category=category,
                title=title,
                description=random.choice(descriptions),
                price=price,
                currency='TZS',
                city=city,
                address=f'{random.randint(1, 999)} Street, {city}',
                status='active',
                is_published=True,
                listing_type='sale',
                condition=random.choice(['new', 'used', 'refurbished']),
                track_inventory=random.choice([True, False]),
                stock_quantity=random.randint(1, 50) if random.choice([True, False]) else 1,
                specs={}  # Empty specs for now, can be populated based on category fields
            )
            
            # Add 2-5 images per listing
            num_images = random.randint(2, 5)
            available_images = image_paths[i*5:(i+1)*5] if i*5 < len(image_paths) else random.sample(image_paths, min(num_images, len(image_paths)))
            
            for img_idx, img_path in enumerate(available_images[:num_images]):
                if os.path.exists(img_path):
                    try:
                        with open(img_path, 'rb') as img_file:
                            ListingMedia.objects.create(
                                listing=listing,
                                file=File(img_file, name=f'listing_{i+1}_img_{img_idx+1}.jpg'),
                                media_type='image',
                                order=img_idx
                            )
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'    Failed to add image {img_idx+1} to listing {i+1}: {e}'))
            
            listings.append(listing)
            if (i + 1) % 20 == 0:
                self.stdout.write(f'  Created {i+1}/{count} listings...')
        
        return listings
