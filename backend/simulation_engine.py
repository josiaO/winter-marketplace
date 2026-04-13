import asyncio
import random
import logging
import io
import json
from datetime import datetime
from faker import Faker
import httpx

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
BASE_URL = "http://localhost:8000/api/v1"
fake = Faker()

TOTAL_USERS = 20
CONCURRENT_USERS = 2
REQUEST_TIMEOUT = 120.0

# Dummy 1x1 transparent PNG pixels for uploads
DUMMY_IMAGE = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\xda\x63\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xdc\x44\x74\x78\x00\x00\x00\x00IEND\xaeB`\x82'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("SimEngine")

# -----------------------------------------------------------------------------
# GLOBAL STATE
# -----------------------------------------------------------------------------
class SimulationState:
    def __init__(self):
        self.users = []      # List of SimUser objects
        self.listings = []   # List of listing IDs
        self.categories = [] # Cached category IDs (catalog)
        self.store_categories = ['electronics', 'fashion', 'home', 'food', 'auto_parts', 'beauty', 'sports']
        self.lock = asyncio.Lock()

    async def add_user(self, user):
        async with self.lock:
            self.users.append(user)

    async def add_listing(self, listing_id):
        async with self.lock:
            self.listings.append(listing_id)

    def get_random_listing(self):
        return random.choice(self.listings) if self.listings else None

    def get_random_seller_profile(self):
        sellers = [u for u in self.users if u.is_seller]
        return random.choice(sellers) if sellers else None

state = SimulationState()

# -----------------------------------------------------------------------------
# SIMULATED USER
# -----------------------------------------------------------------------------
class SimUser:
    def __init__(self, email=None, password="Test1234!", role="buyer"):
        self.email = email or fake.unique.email()
        self.password = password
        self.token = None
        self.user_id = None
        self.username = None
        self.role = role # "buyer" or "seller"
        self.is_seller = False
        self.seller_profile_id = None
        self.order_ids = []

    def headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def register(self, client):
        try:
            res = await client.post(
                f"{BASE_URL}/accounts/auth/register/",
                json={
                    "email": self.email,
                    "password": self.password,
                    "password_confirm": self.password,
                    "phone_number": f"0{random.randint(600000000, 799999999)}",
                    "username": self.email.split('@')[0].replace('.', '_') + f"_{random.randint(100, 999)}",
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name()
                }
            )
            if res.status_code in (200, 201):
                return True
            logger.error(f"Registration failed for {self.email}: {res.text}")
            return False
        except Exception as e:
            logger.error(f"Error registering {self.email}: {e}")
            return False

    async def login(self, client):
        try:
            res = await client.post(
                f"{BASE_URL}/accounts/auth/token/",
                json={"email": self.email, "password": self.password}
            )
            if res.status_code == 200:
                data = res.json()
                self.token = data.get("access")
                return True
            return False
        except Exception as e:
            logger.error(f"Login error for {self.email}: {e}")
            return False

    async def setup_profile(self, client):
        try:
            await client.patch(
                f"{BASE_URL}/accounts/me/",
                headers=self.headers(),
                json={
                    "phone_number": f"+255{random.randint(600000000, 799999999)}",
                    "address": fake.address()
                }
            )
        except Exception:
            pass

    async def become_seller(self, client):
        try:
            # 1. Upgrade role
            res = await client.post(f"{BASE_URL}/accounts/profile/become-seller/", headers=self.headers())
            if res.status_code != 200: return
            
            # 2. Setup store
            res = await client.post(
                f"{BASE_URL}/sellers/store/setup/",
                headers=self.headers(),
                json={
                    "store_name": f"{fake.company()} Store",
                    "store_category": random.choice(state.store_categories),
                    "store_location": fake.city(),
                    "store_description": fake.catch_phrase()
                }
            )
            if res.status_code not in (200, 201):
                logger.warning(f"Store setup failed for {self.email}: {res.text}")
            if res.status_code in (200, 201):
                self.is_seller = True
                
            # 3. Simulate Verification (ID)
            res = await client.post(
                f"{BASE_URL}/sellers/verification/identity/", 
                headers=self.headers(), 
                data={
                    'id_type': 'national_id', 
                    'id_number': f"ID{random.randint(100000, 999999)}"
                }, 
                files={
                    'id_front_image': ('id.png', DUMMY_IMAGE, 'image/png'),
                    'selfie_with_id': ('selfie.png', DUMMY_IMAGE, 'image/png')
                }
            )
            if res.status_code not in (200, 201):
                logger.warning(f"ID Verification failed for {self.email}: {res.text}")
        except Exception as e:
            logger.warning(f"Become seller failed for {self.email}: {e}")

    async def create_listing(self, client):
        if not self.is_seller: return
        try:
            cat_id = random.choice(state.categories) if state.categories else 1
            res = await client.post(
                f"{BASE_URL}/listings/",
                headers=self.headers(),
                data={
                    "title": f"Product {fake.word()} {random.randint(1, 100)}",
                    "description": fake.paragraph(),
                    "price": random.randint(5000, 500000),
                    "category": cat_id,
                    "city": fake.city(),
                    "address": fake.street_address(),
                    "listing_type": "sale",
                    "condition": random.choice(["new", "used"]),
                    "delivery_is_free": True,
                    "is_published": True
                },
                files={
                    "image": ("prod.png", DUMMY_IMAGE, "image/png")
                }
            )
            if res.status_code not in (200, 201):
                logger.warning(f"Create listing failed: {res.text}")
            if res.status_code in (200, 201):
                lid = res.json().get("id")
                await state.add_listing(lid)
                return lid
        except Exception as e:
            logger.debug(f"Create listing error: {e}")

    async def browse_and_interact(self, client):
        lid = state.get_random_listing()
        if not lid: return
        try:
            # View Listing
            res = await client.get(f"{BASE_URL}/listings/{lid}/", headers=self.headers())
            if res.status_code == 200:
                # Like it
                if random.random() < 0.3:
                    await client.post(f"{BASE_URL}/listings/{lid}/like/", headers=self.headers())
        except Exception:
            pass

    async def full_checkout_flow(self, client):
        lid = state.get_random_listing()
        if not lid: return
        try:
            # 1. Fetch listing to check owner (avoid self-purchase 400)
            res = await client.get(f"{BASE_URL}/listings/{lid}/", headers=self.headers())
            if res.status_code == 200:
                listing_data = res.json()
                owner_id = listing_data.get("owner", {}).get("id")
                if owner_id == self.user_id:
                    return # Avoid buying own item

            # 2. Add to cart
            await client.post(
                f"{BASE_URL}/commerce/cart/add_item/",
                headers=self.headers(),
                json={"listing_id": lid, "quantity": 1}
            )
            
            # 2. Checkout (Create Order)
            res = await client.post(
                f"{BASE_URL}/commerce/cart/checkout/",
                headers=self.headers(),
                json={
                    "shipping_address": fake.address(),
                    "shipping_method": "standard",
                    "payment_method": "mobile_money",
                    "city": fake.city(),
                    "shipping_phone": f"0{random.randint(600000000, 799999999)}"
                }
            )
            if res.status_code in (200, 201):
                data = res.json()
                order_id = data.get("id")
                self.order_ids.append(order_id)
                logger.info(f"User {self.email} placed order {order_id}")
        except Exception as e:
            logger.debug(f"Checkout error: {e}")

# -----------------------------------------------------------------------------
# SIMULATION ENGINE
# -----------------------------------------------------------------------------
async def simulate_user_life():
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        user = SimUser()
        
        # 1. Onboarding
        if not await user.register(client): return
        if not await user.login(client): return
        await user.setup_profile(client)
        await state.add_user(user)
        
        # 2. Role Specialization
        if random.random() < 0.3: # 30% are sellers
            await user.become_seller(client)
            # Sellers create a few listings
            for _ in range(random.randint(1, 3)):
                await user.create_listing(client)
                await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # 3. Activity Phase
        for _ in range(random.randint(5, 10)):
            choice = random.random()
            if choice < 0.7:
                await user.browse_and_interact(client)
            else:
                await user.full_checkout_flow(client)
            
            await asyncio.sleep(random.uniform(0.1, 0.5))

async def main():
    logger.info("Starting Simulation Engine...")
    
    # Pre-fetch categories
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            res = await client.get(f"{BASE_URL}/catalog/categories/")
            if res.status_code == 200:
                data = res.json()
                # Categories might be in 'results' or direct list
                results = data.get('results', data) if isinstance(data, dict) else data
                state.categories = [c['id'] for c in results if isinstance(c, dict) and 'id' in c]
                logger.info(f"Loaded {len(state.categories)} categories.")
        except Exception as e:
            logger.error(f"Failed to fetch categories: {e}")

    # Run simulation in batches
    tasks = []
    for i in range(TOTAL_USERS):
        tasks.append(simulate_user_life())
        
        if len(tasks) >= CONCURRENT_USERS:
            logger.info(f"Running batch... ({i+1}/{TOTAL_USERS})")
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = []
    
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Simulation Complete.")

if __name__ == "__main__":
    asyncio.run(main())