I need you to build a complete seller onboarding and verification system 
from scratch. I will describe exactly how it should work, what every model 
looks like, what every API endpoint does, and what every UI screen shows. 
Do not make assumptions — follow this specification exactly.

My stack is:
- Backend: Django + Django REST Framework
- Frontend: Next.js (App Router)
- Database: PostgreSQL
- File storage: [your storage e.g. AWS S3 or Cloudflare R2]
- Notifications: Firebase Cloud Messaging
- Background tasks: Celery + Redis
- Auth: JWT via djangorestframework-simplejwt

═══════════════════════════════════════════════════════════════════
PART 1 — DATABASE MODELS (Django)
═══════════════════════════════════════════════════════════════════

Create these models exactly as described. Do not add extra fields 
unless I say so.

──────────────────────────────────────────
MODEL 1: SellerProfile
──────────────────────────────────────────
This model is created automatically when a user selects the "Seller" 
role during registration. It is separate from the main User model.

Fields:
- user              → OneToOneField to User, on_delete=CASCADE
- store_name        → CharField, max_length=100, blank=True
- store_category    → CharField, max_length=50, choices (see below), blank=True
- store_location    → CharField, max_length=100, blank=True
- store_description → TextField, blank=True
- store_logo        → ImageField, upload_to='store_logos/', blank=True, null=True
- verification_status → CharField, max_length=20, choices, default='incomplete'
- is_active         → BooleanField, default=False
  (False means store is not visible to buyers yet)
- products_limit    → IntegerField, default=50
  (max products they can list — increases on business upgrade)
- payout_limit      → DecimalField, max_digits=12, decimal_places=2, default=500000.00
  (monthly payout limit in TZS — removed on business upgrade)
- total_sales       → DecimalField, max_digits=14, decimal_places=2, default=0.00
- completed_orders  → IntegerField, default=0
- created_at        → DateTimeField, auto_now_add=True
- updated_at        → DateTimeField, auto_now=True

verification_status choices:
  'incomplete'  → User registered but has not started any verification
  'pending_id'  → Waiting for identity documents to be uploaded
  'under_review'→ Documents uploaded, admin is reviewing
  'verified'    → Identity verified, store is active
  'rejected'    → Documents rejected, reason provided
  'suspended'   → Store was active but has been suspended by admin

store_category choices:
  'electronics', 'fashion', 'home', 'food', 'auto_parts',
  'books', 'beauty', 'sports', 'other'

──────────────────────────────────────────
MODEL 2: SellerIDVerification
──────────────────────────────────────────
Stores the identity verification documents uploaded by the seller.
One seller has one verification record. If rejected and resubmitted,
update the existing record — do not create a new one.

Fields:
- seller            → OneToOneField to SellerProfile, on_delete=CASCADE
- id_type           → CharField, max_length=30, choices:
                       'national_id', 'passport', 'voters_card', 'driving_license'
- id_number         → CharField, max_length=50
- id_front_image    → ImageField, upload_to='verifications/id/'
- selfie_with_id    → ImageField, upload_to='verifications/selfies/'
- submitted_at      → DateTimeField, auto_now_add=True
- reviewed_at       → DateTimeField, blank=True, null=True
- reviewed_by       → ForeignKey to User, null=True, blank=True, on_delete=SET_NULL
                       (the admin who reviewed this)
- rejection_reason  → TextField, blank=True
  (filled by admin when rejecting — shown to seller)
- notes             → TextField, blank=True
  (internal admin notes — never shown to seller)

──────────────────────────────────────────
MODEL 3: SellerPayoutAccount
──────────────────────────────────────────
Stores the mobile money number where the seller receives payments.
A seller can have multiple payout accounts but only one can be 
primary (is_primary=True) at a time.

Fields:
- seller            → ForeignKey to SellerProfile, on_delete=CASCADE
- account_type      → CharField, max_length=20, choices:
                       'mpesa', 'tigo_pesa', 'airtel_money', 'bank'
- account_number    → CharField, max_length=50
  (phone number for mobile money, account number for bank)
- account_name      → CharField, max_length=100
  (name on the account — must match seller's verified name)
- is_primary        → BooleanField, default=False
- is_verified       → BooleanField, default=False
  (True after the TZS 1 test transaction succeeds)
- verification_code → CharField, max_length=10, blank=True
  (random code sent in the test transaction for seller to confirm)
- created_at        → DateTimeField, auto_now_add=True

──────────────────────────────────────────
MODEL 4: SellerOnboardingProgress
──────────────────────────────────────────
Tracks which onboarding steps the seller has completed.
This is used to show the progress bar and know which step 
to show next.

Fields:
- seller              → OneToOneField to SellerProfile, on_delete=CASCADE
- step_registration   → BooleanField, default=False
  (True immediately after account creation)
- step_store_setup    → BooleanField, default=False
  (True after store name, category, location saved)
- step_id_submitted   → BooleanField, default=False
  (True after ID documents uploaded)
- step_id_approved    → BooleanField, default=False
  (True after admin approves the documents)
- step_payout_added   → BooleanField, default=False
  (True after mobile money number added and verified)
- step_first_product  → BooleanField, default=False
  (True after seller lists their first product — even as draft)
- step_business_upgraded → BooleanField, default=False
  (True after optional business upgrade — may never be True)

──────────────────────────────────────────
MODEL 5: SellerBusinessVerification
──────────────────────────────────────────
OPTIONAL step — only relevant once seller reaches 
TZS 500,000 total sales OR 20 completed orders.
This is completely separate from identity verification.

Fields:
- seller                   → OneToOneField to SellerProfile, on_delete=CASCADE
- business_name            → CharField, max_length=200
- business_registration_no → CharField, max_length=100, blank=True
- tin_number               → CharField, max_length=50, blank=True
- business_certificate     → FileField, upload_to='verifications/business/', blank=True, null=True
- bank_account_number      → CharField, max_length=50, blank=True
- bank_name                → CharField, max_length=100, blank=True
- bank_account_name        → CharField, max_length=100, blank=True
- status                   → CharField, choices: 'pending','approved','rejected', default='pending'
- submitted_at             → DateTimeField, auto_now_add=True
- reviewed_at              → DateTimeField, null=True, blank=True
- reviewed_by              → ForeignKey to User, null=True, blank=True, on_delete=SET_NULL
- rejection_reason         → TextField, blank=True

──────────────────────────────────────────
SIGNALS — Create these automatically
──────────────────────────────────────────
In sellers/signals.py, create post_save signals:

1. When a User is created with role='seller':
   - Create a SellerProfile linked to the user
   - Create a SellerOnboardingProgress linked to the SellerProfile
   - Set step_registration = True on the progress record

2. When SellerIDVerification is saved with the seller's 
   SellerProfile.verification_status changing to 'verified':
   - Set SellerProfile.is_active = True
   - Set SellerOnboardingProgress.step_id_approved = True
   - Send a Firebase push notification to the seller:
     Title: "Hongera! Akaunti yako imeidhinishwa"
     Body: "Duka lako sasa linaonekana kwa wanunuzi Tanzania nzima."
   - Trigger Celery task: send_seller_approval_email(seller_id)

3. When SellerProfile.total_sales >= 500000 
   OR completed_orders >= 20, 
   AND step_business_upgraded = False:
   - Trigger Celery task: send_business_upgrade_prompt(seller_id)

═══════════════════════════════════════════════════════════════════
PART 2 — API ENDPOINTS (Django REST Framework)
═══════════════════════════════════════════════════════════════════

Create all endpoints inside the 'sellers' Django app.
Use /api/sellers/ as the base URL prefix.

All endpoints except registration require IsAuthenticated permission.
Endpoints marked [SELLER ONLY] also require a custom permission 
IsSeller that checks request.user has a SellerProfile.
Endpoints marked [ADMIN ONLY] require IsAdminUser.

──────────────────────────────────────────
ENDPOINT 1: POST /api/auth/register/
──────────────────────────────────────────
This endpoint already exists for general registration.
Modify it to accept a 'role' field: 'buyer', 'seller', or 'both'.

If role is 'seller' or 'both':
- Create the User
- Create the SellerProfile (via signal)
- Return the JWT tokens + user data + seller_profile id

──────────────────────────────────────────
ENDPOINT 2: GET /api/sellers/onboarding/progress/
──────────────────────────────────────────
[SELLER ONLY]
Returns the current onboarding progress for the logged-in seller.

Response shape:
{
  "steps": {
    "registration":       true,
    "store_setup":        false,
    "id_submitted":       false,
    "id_approved":        false,
    "payout_added":       false,
    "first_product":      false,
    "business_upgraded":  false
  },
  "completion_percentage": 14,
  "verification_status": "incomplete",
  "store_is_active": false,
  "rejection_reason": null
}

completion_percentage is calculated as:
  (number of True steps / 6) * 100
  Note: step_business_upgraded is not counted — it is optional.

──────────────────────────────────────────
ENDPOINT 3: POST /api/sellers/store/setup/
──────────────────────────────────────────
[SELLER ONLY]
Saves the basic store information.

Request body:
{
  "store_name":     "Duka la Amina",
  "store_category": "fashion",
  "store_location": "Dar es Salaam",
  "store_description": "..." (optional)
}

On success:
- Update SellerProfile with these fields
- Set SellerOnboardingProgress.step_store_setup = True
- Return updated SellerProfile data

Validation:
- store_name: required, min 3 chars, max 100 chars
- store_name must be unique across all SellerProfiles
- store_category: required, must be one of the defined choices
- store_location: required

──────────────────────────────────────────
ENDPOINT 4: POST /api/sellers/verification/identity/
──────────────────────────────────────────
[SELLER ONLY]
Uploads identity verification documents.
This is a multipart/form-data request (file uploads).

Request fields:
- id_type:        string (one of the choices)
- id_number:      string
- id_front_image: file (image, max 5MB, jpg/png/pdf only)
- selfie_with_id: file (image, max 5MB, jpg/png only)

On success:
- Create or update SellerIDVerification record
- Set SellerProfile.verification_status = 'under_review'
- Set SellerOnboardingProgress.step_id_submitted = True
- Send internal notification to all admin users:
  "New seller verification request from [store_name]"
- Trigger Celery task: notify_admin_new_verification(seller_id)
- Return:
  {
    "message": "Documents submitted successfully. 
                We will review within 24 hours.",
    "submitted_at": "2025-01-15T10:30:00Z"
  }

Validation:
- Seller must have completed store_setup first.
  If not, return 400: 
  {"error": "Please complete your store setup first."}
- File size max 5MB each
- Image files only for selfie (no PDF)
- All fields required

──────────────────────────────────────────
ENDPOINT 5: GET /api/sellers/verification/identity/status/
──────────────────────────────────────────
[SELLER ONLY]
Returns the current status of their identity verification.

Response:
{
  "status": "under_review",
  "submitted_at": "2025-01-15T10:30:00Z",
  "reviewed_at": null,
  "rejection_reason": null
}

If status is 'rejected', include rejection_reason so the seller
knows exactly what to fix before resubmitting.

──────────────────────────────────────────
ENDPOINT 6: POST /api/sellers/payout/add/
──────────────────────────────────────────
[SELLER ONLY]
Adds a mobile money payout account.
Only available after verification_status = 'verified'.

If called before verified, return 403:
{"error": "Your identity must be verified before adding 
           a payout account."}

Request body:
{
  "account_type":   "mpesa",
  "account_number": "0712345678",
  "account_name":   "Amina Mbwana"
}

On success:
- Create SellerPayoutAccount record
- Generate a random 6-digit verification_code
- Store the code on the record
- Trigger Celery task: send_payout_verification(payout_account_id)
  This task simulates sending TZS 1 to the number with the 
  verification code in the transaction description.
  (In development, just log the code. In production, use 
  Selcom API to send real test transaction.)
- Return:
  {
    "message": "We sent TZS 1 to 0712345678. 
                Check the transaction description for your 
                6-digit code and enter it below.",
    "payout_account_id": 123
  }

──────────────────────────────────────────
ENDPOINT 7: POST /api/sellers/payout/verify/
──────────────────────────────────────────
[SELLER ONLY]
Confirms the payout account using the code from the test transaction.

Request body:
{
  "payout_account_id": 123,
  "verification_code": "847291"
}

On success (code matches):
- Set SellerPayoutAccount.is_verified = True
- Set SellerPayoutAccount.is_primary = True 
  (and set all other accounts for this seller to is_primary=False)
- Set SellerOnboardingProgress.step_payout_added = True
- Return: {"message": "Payout account verified successfully."}

On failure (code does not match):
- Return 400: {"error": "Incorrect code. Please try again."}

──────────────────────────────────────────
ENDPOINT 8: GET /api/sellers/profile/
──────────────────────────────────────────
[SELLER ONLY]
Returns the full seller profile for the dashboard.

Response includes:
- All SellerProfile fields
- Onboarding progress
- Payout accounts (is_verified ones only)
- verification_status
- Whether business upgrade is available:
  (total_sales >= 500000 OR completed_orders >= 20) 
  AND step_business_upgraded = False

──────────────────────────────────────────
ENDPOINT 9: POST /api/sellers/verification/business/
──────────────────────────────────────────
[SELLER ONLY]
Optional business upgrade. Only available if seller has 
total_sales >= 500000 OR completed_orders >= 20.

Request fields (all optional except business_name):
- business_name
- business_registration_no
- tin_number
- business_certificate (file)
- bank_account_number
- bank_name
- bank_account_name

On success:
- Create SellerBusinessVerification record
- Trigger Celery task: notify_admin_business_verification(seller_id)
- Return: {"message": "Business verification submitted for review."}


═══════════════════════════════════════════════════════════════════
PART 3 — ADMIN ENDPOINTS (Django REST Framework)
═══════════════════════════════════════════════════════════════════

These are the endpoints used by admin users to manage 
seller verifications. All require IsAdminUser permission.

──────────────────────────────────────────
ENDPOINT A1: GET /api/admin/sellers/verifications/
──────────────────────────────────────────
[ADMIN ONLY]
Returns a paginated list of all pending seller verifications.
Default: show 'under_review' status first, then others.

Query params:
- status: filter by verification_status
  (incomplete, pending_id, under_review, verified, rejected, suspended)
- search: search by store_name or user email
- page: pagination

Response per item:
{
  "seller_id": 45,
  "store_name": "Duka la Amina",
  "seller_email": "amina@example.com",
  "seller_phone": "0712345678",
  "verification_status": "under_review",
  "submitted_at": "2025-01-15T10:30:00Z",
  "id_type": "national_id",
  "id_number": "12345678",
  "id_front_image_url": "https://...",
  "selfie_with_id_url": "https://..."
}

──────────────────────────────────────────
ENDPOINT A2: GET /api/admin/sellers/verifications/{seller_id}/
──────────────────────────────────────────
[ADMIN ONLY]
Returns full detail of one seller's verification request.
Shows everything: store info, ID documents, 
payout accounts, onboarding progress, 
any previous rejection reasons.

──────────────────────────────────────────
ENDPOINT A3: POST /api/admin/sellers/verifications/{seller_id}/approve/
──────────────────────────────────────────
[ADMIN ONLY]
Approves an identity verification.

Request body:
{
  "notes": "Documents verified. National ID matches selfie." 
  (optional internal note)
}

On success:
- Set SellerIDVerification.reviewed_at = now()
- Set SellerIDVerification.reviewed_by = request.user
- Set SellerIDVerification.notes = notes
- Set SellerProfile.verification_status = 'verified'
- Set SellerProfile.is_active = True
- Set SellerOnboardingProgress.step_id_approved = True
- Signal fires → sends FCM notification + email to seller
- Return: {"message": "Seller approved successfully."}

──────────────────────────────────────────
ENDPOINT A4: POST /api/admin/sellers/verifications/{seller_id}/reject/
──────────────────────────────────────────
[ADMIN ONLY]
Rejects an identity verification. rejection_reason is required
and will be shown directly to the seller.

Request body:
{
  "rejection_reason": "The selfie image is too blurry. 
                       Please retake your photo in good lighting 
                       holding your ID clearly visible.",
  "notes": "Internal: tried whatsapp-quality image" (optional)
}

Validation: rejection_reason is required. 
If empty, return 400: 
{"error": "You must provide a rejection reason."}

On success:
- Set SellerIDVerification.rejection_reason = rejection_reason
- Set SellerIDVerification.reviewed_at = now()
- Set SellerIDVerification.reviewed_by = request.user
- Set SellerProfile.verification_status = 'rejected'
- Set SellerProfile.is_active = False
- Trigger Celery task: send_seller_rejection_email(seller_id, rejection_reason)
- Send FCM notification to seller:
  Title: "Tatizo na nyaraka zako"
  Body: First 100 chars of rejection_reason + "..."
- Return: {"message": "Seller rejected. Reason sent to seller."}

──────────────────────────────────────────
ENDPOINT A5: POST /api/admin/sellers/{seller_id}/suspend/
──────────────────────────────────────────
[ADMIN ONLY]
Suspends an active seller.

Request body:
{
  "reason": "Multiple buyer complaints about undelivered orders."
}

On success:
- Set SellerProfile.verification_status = 'suspended'
- Set SellerProfile.is_active = False
  (products become invisible to buyers immediately)
- Trigger Celery task: send_seller_suspension_email(seller_id, reason)
- Return: {"message": "Seller suspended."}

──────────────────────────────────────────
ENDPOINT A6: POST /api/admin/sellers/{seller_id}/reinstate/
──────────────────────────────────────────
[ADMIN ONLY]
Reinstates a suspended seller.

On success:
- Set SellerProfile.verification_status = 'verified'
- Set SellerProfile.is_active = True
- Return: {"message": "Seller reinstated."}

──────────────────────────────────────────
ENDPOINT A7: POST /api/admin/sellers/business/{seller_id}/approve/
──────────────────────────────────────────
[ADMIN ONLY]
Approves a business verification upgrade.

On success:
- Set SellerBusinessVerification.status = 'approved'
- Set SellerProfile.products_limit = 500
- Set SellerProfile.payout_limit = 0 (0 means unlimited)
- Set SellerOnboardingProgress.step_business_upgraded = True
- Add "Verified Business" badge to seller profile
  (add a boolean field: SellerProfile.is_business_verified = True)
- Send FCM notification + email to seller
- Return: {"message": "Business verification approved."}


═══════════════════════════════════════════════════════════════════
PART 4 — CELERY TASKS
═══════════════════════════════════════════════════════════════════

Create these tasks in sellers/tasks.py.
All tasks use @shared_task with max_retries=3, countdown=60.

1. send_seller_approval_email(seller_id)
   Send email to seller: "Your store is now live!"
   Include their store name and a link to their seller dashboard.

2. send_seller_rejection_email(seller_id, rejection_reason)
   Send email to seller explaining what was wrong and 
   how to fix it and resubmit.

3. send_seller_suspension_email(seller_id, reason)
   Send email to seller explaining the suspension.

4. notify_admin_new_verification(seller_id)
   Send email to all admin users that a new verification 
   request is waiting for review.
   Subject: "New seller verification: [store_name]"

5. send_payout_verification(payout_account_id)
   In development: log the verification code to console.
   In production: call Selcom API to send TZS 1 test transaction.
   (Add a TODO comment for the Selcom integration point.)

6. send_business_upgrade_prompt(seller_id)
   Send push notification + email to seller telling them 
   they qualify for a business account upgrade.
   Only send this ONCE — check if already sent before sending.
   Add a field to SellerOnboardingProgress: 
   upgrade_prompt_sent = BooleanField, default=False
   Set it to True after sending.


═══════════════════════════════════════════════════════════════════
PART 5 — FRONTEND: SELLER ONBOARDING FLOW (Next.js)
═══════════════════════════════════════════════════════════════════

All seller onboarding pages live under:
  /seller/onboarding/

These pages are protected routes — redirect to /login 
if not authenticated.

The seller should never be forced through these steps 
linearly unless they try to access something that requires 
a previous step. The dashboard always shows what is 
available and what is not, with clear reasons.

──────────────────────────────────────────
PAGE 1: /seller/onboarding/store-setup
──────────────────────────────────────────
Simple form with 3 fields:
1. Store name (text input)
2. What will you mainly sell? 
   (icon grid of categories — not a dropdown, show icons 
    for each category so it feels like a product, not a form)
3. Where are you based? (dropdown of Tanzanian regions)

Below the form, a small text:
"You can change these details later from your settings."

Submit button: "Tengeneza Duka Langu →"

On success: redirect to /seller/dashboard
Show a toast: "Duka lako limeundwa! Anza kuongeza bidhaa."

──────────────────────────────────────────
PAGE 2: /seller/onboarding/verify-identity
──────────────────────────────────────────
This page is only shown when the seller clicks 
"Publish Product" for the first time and their 
verification_status is not 'verified'.

Do NOT show this page unprompted. Only show it at the 
moment they try to go live.

Layout:
- Top: Progress indicator showing "Step 2 of 4: Verify Identity"
- Brief explanation (2 sentences max):
  "We need to confirm who you are so buyers can trust your store.
   This takes about 5 minutes and we review within 24 hours."
- What you need (checklist style, not a paragraph):
  ✓ Your National ID, Passport, Voter's Card, or Driving License
  ✓ A clear photo of yourself holding the ID

Form fields:
1. ID Type (radio buttons with icons, not a dropdown):
   [ National ID ] [ Passport ] [ Voter's Card ] [ Driving License ]

2. ID Number (text input)
   Label: "Number shown on your ID"

3. Photo of your ID (file upload)
   Label: "Front of your ID"
   Helper text: "Clear photo, good lighting, all corners visible"
   Show a small example image of what "good" looks like.

4. Selfie holding your ID (file upload)
   Label: "You holding your ID"
   Helper text: "Hold your ID next to your face, both must be clear"
   Show a small example image.

Below uploads: 
"🔒 Your documents are encrypted and only seen by our 
    verification team. We never share them."

Submit button: "Tuma Nyaraka →"
Below button: "Do this later" link (returns to dashboard)

After submission: show a success screen (not a redirect):
- Big checkmark
- "Asante! Tunapiitia nyaraka zako."
- "Tutakujulisha ndani ya masaa 24 kwa SMS na barua pepe."
- Button: "Rudi kwenye Dashibodi"

──────────────────────────────────────────
PAGE 3: /seller/onboarding/add-payout
──────────────────────────────────────────
Only accessible after verification_status = 'verified'.
Shown automatically after approval (redirect from 
the approval notification deep link).

Layout:
- Celebration header: "🎉 Hongera! Duka lako limeidhinishwa."
- Sub: "Hatua moja tu kubaki — tuambie tulipe wapi."

Form:
1. Payment method (large icon buttons, not a dropdown):
   [ 💚 M-Pesa ] [ 🔵 Tigo Pesa ] [ 🔴 Airtel Money ] [ 🏦 Bank ]

2. Phone number (if mobile money selected)
   or Bank details (if bank selected — show account number, 
   bank name, account name as three separate fields)

3. Account name
   Helper: "Must match your verified name: [seller's legal name]"

Submit: "Ongeza Akaunti →"

After submit: show inline message (do not redirect):
"Tumetuma TZS 1 kwa [number]. Angalia ujumbe wa malipo 
 na uingize nambari ya tarakimu 6 uliyopata."

Show a 6-digit code input (individual boxes, like an OTP input).
Below: "Hukupata? Tuma tena" link (calls the endpoint again).

After code verified: redirect to /seller/dashboard
Show toast: "Akaunti ya malipo imethibitishwa. 
             Uko tayari kupokea malipo!"

──────────────────────────────────────────
PAGE 4: /seller/dashboard
──────────────────────────────────────────
This is the main seller dashboard. It looks different
depending on the seller's onboarding stage.

STATE A — Store just created, not yet verified:
Show a prominent onboarding progress card at the top.
Below it: their product drafts (if any).
No earnings, no order metrics yet.

Progress card layout:
┌──────────────────────────────────────────────────┐
│  Duka lako liko 40% tayari                       │
│  ████████░░░░░░░░░░░░  40%                       │
│                                                  │
│  ✅ Akaunti imeundwa                             │
│  ✅ Duka limewekwa                               │
│  ⏳ Uthibitisho wa utambulisho — Inapitiwa       │
│  ○  Ongeza akaunti ya malipo                     │
│  ○  Orodhesha bidhaa yako ya kwanza             │
└──────────────────────────────────────────────────┘

Rules for the progress card:
- ✅ = completed step
- ⏳ = in progress / waiting
- ○  = not started yet
- Each incomplete step has a small action button 
  next to it: "Fanya Sasa →"
- If verification_status = 'rejected': show the 
  rejection reason in a red box with a 
  "Jaribu Tena →" button

STATE B — Fully verified, payout added, active:
Hide the progress card entirely.
Show normal seller dashboard:
  - Today's orders
  - Earnings this month
  - Escrow balance (held) vs available
  - Recent order list
  - Quick actions: Add Product, View Store, Withdraw

STATE C — Business upgrade available:
Show a non-intrusive upgrade banner at the top 
(can be dismissed):
"🚀 Unakua haraka! Boresha akaunti yako ya biashara 
    na uondoe mipaka."
[ Boresha Sasa ] [ Labadaye ]


═══════════════════════════════════════════════════════════════════
PART 6 — FRONTEND: ADMIN VERIFICATION PANEL (Next.js)
═══════════════════════════════════════════════════════════════════

All admin pages live under /admin/ and require 
role = 'admin' in the JWT token. 
Redirect to /login if not admin.

──────────────────────────────────────────
PAGE: /admin/sellers/verifications
──────────────────────────────────────────
Main verification queue page.

Layout:
- Top: 4 stat cards showing count of sellers in each status:
  [ Under Review: 12 ] [ Verified: 340 ] 
  [ Rejected: 8 ] [ Suspended: 3 ]

- Filter tabs: All | Under Review | Verified | Rejected | Suspended
  "Under Review" tab is selected by default.

- Search bar: search by store name or email

- Table with columns:
  Store Name | Seller Email | ID Type | Submitted | Status | Actions

- Actions column shows:
  [ Review ] button for 'under_review' items
  [ View ] button for others

──────────────────────────────────────────
PAGE: /admin/sellers/verifications/[seller_id]
──────────────────────────────────────────
Detailed review page for one seller.

Layout (two columns):
LEFT column — Document viewer:
  - Large image display for id_front_image
  - Large image display for selfie_with_id
  - Click to enlarge (full screen modal)
  - ID Type and ID Number shown as text below images

RIGHT column — Seller information + actions:
  - Store name
  - Seller's full name (from User model)
  - Email and phone
  - Location
  - Store category
  - Submitted at (relative time: "2 hours ago")

  Action section:
  ┌─────────────────────────────────────────┐
  │  Internal notes (textarea)              │
  │  (only visible to admins)               │
  │                                         │
  │  [ ✅ Approve ]   [ ❌ Reject ]         │
  └─────────────────────────────────────────┘

  When admin clicks Reject:
  - Show a modal with a required textarea:
    "Rejection reason (this will be shown to the seller):"
  - Placeholder: "e.g. The selfie is too blurry. 
                      Please retake in good lighting..."
  - Confirm button: "Send Rejection"

  After approve or reject:
  - Show success toast
  - Redirect back to /admin/sellers/verifications
  - The seller disappears from the "Under Review" tab


═══════════════════════════════════════════════════════════════════
PART 7 — IMPORTANT RULES FOR IMPLEMENTATION
═══════════════════════════════════════════════════════════════════

Follow these rules throughout the entire implementation:

1. NEVER delete a SellerIDVerification record when rejecting.
   Always update the existing one. The rejection history must 
   be preserved.

2. NEVER allow a seller's is_active to be set to True unless 
   verification_status = 'verified'. Enforce this in both the 
   model's save() method AND the API.

3. ALL file uploads must be validated:
   - Max size: 5MB
   - Allowed types: jpg, jpeg, png for images; 
                    jpg, jpeg, png, pdf for documents
   - Validate on both frontend (before upload) and 
     backend (in the serializer)

4. ALL admin actions (approve, reject, suspend, reinstate) 
   must be logged. Create a simple SellerActionLog model:
   - seller → ForeignKey to SellerProfile
   - action → CharField (approve/reject/suspend/reinstate)
   - performed_by → ForeignKey to User
   - reason → TextField, blank=True
   - timestamp → DateTimeField, auto_now_add=True

5. The rejection_reason field in SellerIDVerification is 
   shown directly to the seller exactly as the admin types it.
   Make this clear in the admin UI with a label:
   "⚠️ This text will be sent directly to the seller."

6. When a seller is suspended, all their products must be 
   set to is_active=False immediately. Do this in the 
   suspend endpoint, not in a background task.

7. A seller can resubmit verification documents after 
   rejection. When they do, set verification_status back 
   to 'under_review' and clear the rejection_reason field.

8. Never show the seller's raw file storage URLs directly. 
   Always generate signed/temporary URLs so document links 
   expire after 1 hour.

9. The progress percentage shown to the seller counts only 
   these 6 steps (business upgrade is excluded):
   registration, store_setup, id_submitted, id_approved, 
   payout_added, first_product.

10. Every API response that returns a status the seller 
    needs to understand must include a human-readable 
    message in both Swahili and English:
    {
      "status": "under_review",
      "message_sw": "Nyaraka zako zinapitiwa. Subiri masaa 24.",
      "message_en": "Your documents are under review. 
                     Please wait up to 24 hours."
    }