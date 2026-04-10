# SmartDalali `accounts` app

Documentation for the Django app at `backend/accounts`: models, services, API routes, auth flows, and known issues.

## Purpose

This app owns **user identity extensions** (profiles, addresses, OTPs), **JWT login/refresh** (SimpleJWT with custom payloads), **registration and activation**, **Firebase token exchange**, **password reset** (link-based and OTP-related), **seller upgrade**, and **admin-facing user management**.

It is mounted at **`/api/v1/accounts/`** (see `backend/backend/urls.py`).

---

## Data models (`models.py`)

| Model | Role |
|--------|------|
| **Profile** | `OneToOne` to Django `User`: name, about, phone, address, image, referral-style `code`, `firebase_uid` (unique), `email_verified`, soft-delete `is_deleted`, notification toggles. |
| **UserAddress** | Multiple addresses per user; `is_default` enforced in `save()` (only one default per user). |
| **OTP** | Codes for `verify_email`, `password_reset`, `confirm_action`, `delete_account`; tracks `attempts`, `expires_at`, `is_used`. |

### User → Profile signal

A `@receiver(post_save, sender=User)` creates a `Profile` on user creation and calls `instance.profile.save()` on **every** user save. That assumes a profile always exists; unusual `User` creation paths could break this.

The standalone `post_save.connect(...)` line is commented out; the decorator is what runs.

---

## Roles (`roles.py`)

- **`get_user_role(user)`** → `'admin'` (superuser), `'seller'` (in group `seller`), else `'user'`.
- **`ROLE_AGENT`** is an alias of **`ROLE_SELLER`** (`is_agent` → `is_seller`).

### Management command mismatch

`management/commands/init_roles.py` ensures group **`agent`**, while role logic keys off **`seller`**. That is inconsistent unless both groups are kept in sync elsewhere.

---

## Service layer (`core/services/accounts.py` — `AccountService`)

- **`register_user`**: Creates inactive user (`is_active=False`), profile + phone, sends **`verify_email` OTP** via `send_otp`, optional **`send_welcome_email`**, and optionally adds **`seller`** group for `role` in `('seller', 'both')`.
- **`update_profile`**: Merges flat/nested payload for user + profile fields and image uploads.
- **`firebase_authenticate`**: Find/create user by email (`User.objects.filter(email=email).first()` — case sensitivity depends on DB), sync `Profile` (`firebase_uid`, name, phone).
- **`toggle_seller_role` / `downgrade_from_seller`**: Group `seller` + `marketplace.SellerProfile` create/update/deactivate.

---

## OTP subsystem (`otp.py`)

- **`send_otp`**: Invalidates prior active OTPs for that user+purpose, creates a new row, enqueues **`send_otp_delivery_task`** (Celery).
- **`verify_otp`**: Validates latest unused OTP; on success for **`verify_email`** sets **`user.is_active = True`** and **`profile.email_verified = True`**.

Configurable via settings (with defaults in `otp.py`): `OTP_EXPIRY_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_LENGTH`.

**Copy vs behavior:** Email body for `delete_account` describes permanent deletion, but the delete API **soft-deletes** (deactivates user, marks profile deleted).

---

## API surface (`urls.py` + `views.py`)

### Auth

| Method | Path (under `/api/v1/accounts/`) | Notes |
|--------|----------------------------------|--------|
| POST | `auth/token/` | Login; `username`+`password` or `email`+`password`. **Throttles disabled** on this view. |
| POST | `auth/token/refresh/` | Refresh; **throttles disabled**. |
| POST | `auth/logout/` | Blacklists refresh token if body includes `refresh`. |
| POST | `auth/register/` | JSON registration; **no tokens**; user inactive until OTP. |
| POST | `auth/signup/` | Server-rendered signup (`SignupForm`) — not the same as `auth/register/`. |
| GET | `auth/routes/` | Lists token URLs. |
| POST | `firebase-login/` | `firebase_token`, `firebase_uid`, `email`, optional `display_name`, `phone_number`. |
| POST | `auth/password-reset/` | Django-style reset; emails link via Celery (`FRONTEND_URL`). |
| POST | `auth/password-reset/confirm/` | `uid`, `token`, `new_password`, `re_new_password`. |

### OTP

| Method | Path | Notes |
|--------|------|--------|
| POST | `otp/request/` | Purposes: `verify_email`, `password_reset`, `confirm_action`, `delete_account`; optional `channel` `email` / `sms`. |
| POST | `otp/verify/` | Verifies code; for `password_reset` returns **`reset_token`** (cached, short TTL). |
| POST | `otp/change-password/` | See [Known issues](#known-issues--bugs). |

### Profile / account

| Method | Path | Notes |
|--------|------|--------|
| GET, PUT, PATCH | `me/`, `profile/` | Current user payload / `AccountService.update_profile`. |
| PUT, PATCH | `profile/update/` | Legacy alias to the same update handler. |
| POST | `profile/change-password/` | `old_password`, `new_password`, `confirm_password`. |
| DELETE | `profile/delete/` | Requires OTP `delete_account`; soft delete + optional token blacklist. |
| POST | `profile/become-seller/`, `profile/upgrade-to-agent/` | Seller upgrade + new JWTs with `role`. |

### Router (`DefaultRouter`)

- **`/users/`** — `UserManagementViewSet` (`IsAdmin`): user admin, `toggle_seller_status`, `toggle_active_status`, `stats`.
- **`/addresses/`** — `UserAddressViewSet` (owner-only).
- **`/profile/`** — `UserProfileViewSet`: superuser sees all; normal user `get_object` forces **own** profile.

### Template-based views

`signup`, `activate`, `profile_view` still render Django templates (`registration/`, `account/`).

---

## Serializers (`serializers.py`)

- **`MyTokenObtainPairSerializer`**: Adds `username` and **`role`** to JWT; `validate` attaches **`user`** via lazy import of `_serialize_current_user` from `views` (tight coupling).
- **`MyTokenRefreshSerializer`**: Adds **`role`** and **`username`** to the new **access** token after refresh.
- **`RegisterSerializer`**: Validation + `AccountService.register_user` in `create`.
- **`UserSerializer`**: Exposes nested profile including **`profile.code`** (activation code visible to whoever can call this API).

---

## DRF authentication (`authentication.py`)

**`FirebaseAuthentication`**: `Authorization: Bearer <firebase_id_token>`. Verifies with Firebase Admin, resolves user by `Profile.firebase_uid` or creates/links by email/uid.

Invalid token → `None` (JWT can run next). Expired → **401**.

This module **imports `firebase_admin` at import time**. The project pins `firebase-admin` in `requirements.txt`; removing it would break Django startup when loading this class.

---

## Project settings integration

- **`INSTALLED_APPS`**: `accounts`.
- **`REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`**: `FirebaseAuthentication`, then JWT, then session (if `DEBUG`).
- **SimpleJWT**: `TOKEN_OBTAIN_SERIALIZER` / `TOKEN_REFRESH_SERIALIZER` point at this app’s serializers.
- **`rest_framework_simplejwt.token_blacklist`**: Used for logout / rotation behavior.

---

## Admin (`admin.py`)

Custom `User` admin with `Profile` inline; separate `Profile` admin. **`OTP`** is not registered.

---

## Management commands

- **`init_roles`** — ensures group `agent` (see role mismatch above).
- **`check_social_providers`**, **`check_emails`** — operational helpers.

---

## System checks (`checks.py`)

When `allauth` and `SOCIALACCOUNT_PROVIDERS` are set, emits warnings for missing/misconfigured `SocialApp` / site attachment (`accounts.W001`–`W003`).

---

## Celery

- **`tasks.py`**: `send_welcome_email`, `send_activation_email_task`, `send_password_reset_email_task`.
- **`otp.py`**: `send_otp_delivery_task` for OTP delivery.

---

## Dependencies (conceptual)

- Django **`User`** / **`Group`**
- **DRF**, **SimpleJWT** (+ blacklist)
- **`commerce.Order`** in `_serialize_current_user`
- **`marketplace.SellerProfile`**
- **Celery**, **cache** (OTP password-reset confirmation)
- **Firebase Admin** (login + optional Bearer auth)

---

## Known issues & bugs

### 1. Duplicate view functions (`views.py`)

`verify_otp` and `change_password_with_otp` are each defined **twice**. Only the **last** definition is used. Earlier blocks are dead code and confuse readers.

### 2. OTP password reset vs authentication

Intended flow: request `password_reset` OTP → `otp/verify/` returns `reset_token` → `otp/change-password/`. But **`otp/change-password/`** requires **`IsAuthenticated`**, so a user who is **not** logged in typically **cannot** finish OTP-based password reset. The **link-based** `auth/password-reset/confirm/` path is the one that works without a session.

### 3. Broken or skipped `signals.py` registration

The `m2m_changed` receiver uses `sender=settings.AUTH_USER_MODEL.groups.through`. `AUTH_USER_MODEL` is usually a **string**, which has no `.groups`, so import may **fail**.

`AccountsConfig.ready()` catches exceptions when importing `accounts.signals`, so startup can **silently skip** signals — including `post_migrate` group creation and auto-`SellerProfile` on seller group add. Fix: use `get_user_model()` and `User.groups.through`.

### 4. Tests out of sync

- **`tests.py`**: Expects group **`agent`** and role **`agent`**; `get_user_role` does not treat `agent` as seller.
- **`tests_activation.py`**: Expects immediate `is_active` after register; registration keeps users inactive until OTP.
- **`tests_views.py` `test_register`**: Expects JWT in register response; current API returns no tokens.
- **`test_login_with_non_existent_email`**: Error shape/string likely does not match wrapped `{'error': ...}` responses.

`tests_views.py` references **`properties.models.AgentProfile`** — may not exist in all deployments.

### 5. Two password-reset mechanisms

Link-based (Django token + email) vs OTP + cache token. They are not unified; clients should follow one documented flow.

### 6. Security / product notes

- Login and refresh **throttle classes removed** on those views — rely on other layers for abuse control if needed.
- `UserManagementViewSet.stats` “monthly” series uses **overlapping 30-day windows**, not calendar months.
- **`RegisterSerializer`** may assign **seller** group before email verification (user still inactive).
- **Account deletion** is **soft** while OTP email text can read as **permanent**.

### 7. Minor

- Duplicate `Profile` imports in `views.py`.
- `permissions.py` only re-exports `core.permissions`.
- Firebase email lookup could use `email__iexact` for consistency.

---

## Summary

The app is the hub for **JWT auth, profiles, OTP verification, Firebase exchange, and seller promotion**, plus **admin-only user management**. Before relying on OTP-for-password-reset or automatic `SellerProfile` creation, validate the issues above (especially **signals import** and **OTP change-password auth**).
