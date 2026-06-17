# League OS Backend - Authentication API Testing Guide

This guide documents the current authentication API flow for League OS backend testing using Postman or curl.

Base local API URL:

```text
http://localhost:8000
```

## 1. Health Check

### Endpoint

```http
GET /api/health/
```

### curl

```bash
curl http://localhost:8000/api/health/
```

### Expected Response

```json
{
  "status": "OK",
  "service": "League OS Backend API",
  "version": "sprint-1-foundation"
}
```

---

# 2. Register User

Registration creates a new user and sends an email verification OTP.

### Endpoint

```http
POST /api/accounts/register/
```

### Body

```json
{
  "email": "newfan@example.com",
  "phone_number": "+256701000000",
  "first_name": "New",
  "last_name": "Fan",
  "password": "StrongPass123",
  "confirm_password": "StrongPass123"
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/accounts/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newfan@example.com",
    "phone_number": "+256701000000",
    "first_name": "New",
    "last_name": "Fan",
    "password": "StrongPass123",
    "confirm_password": "StrongPass123"
  }'
```

### Expected Response

```json
{
  "message": "Registration successful. Please check your email for the verification code.",
  "requires_email_verification": true,
  "user": {
    "email": "newfan@example.com",
    "role": "FAN",
    "is_email_verified": false
  }
}
```

Important: use `phone_number`, not `phone`.

---

# 3. Login Before OTP Verification

A user must verify their email OTP before logging in.

### Endpoint

```http
POST /api/accounts/login/
```

### Body

```json
{
  "identifier": "newfan@example.com",
  "password": "StrongPass123"
}
```

### Expected Response

```json
{
  "detail": "Please verify your email address before logging in.",
  "code": "email_not_verified",
  "requires_email_verification": true,
  "email": "newfan@example.com"
}
```

### Expected Status

```text
403 Forbidden
```

The backend must not return `access` or `refresh` tokens before OTP verification.

---

# 4. Verify Email OTP

Use the OTP sent to the user email address.

### Endpoint

```http
POST /api/accounts/verify-otp/
```

### Body

```json
{
  "email": "newfan@example.com",
  "code": "123456",
  "purpose": "EMAIL_VERIFICATION"
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/accounts/verify-otp/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newfan@example.com",
    "code": "123456",
    "purpose": "EMAIL_VERIFICATION"
  }'
```

### Expected Response

```json
{
  "message": "Email verified successfully."
}
```

After this step, `is_email_verified` becomes `true`.

---

# 5. Resend Email OTP

Resending an OTP invalidates previous unused email verification OTPs.

### Endpoint

```http
POST /api/accounts/resend-otp/
```

### Body

```json
{
  "email": "newfan@example.com"
}
```

### Expected Response

```json
{
  "message": "A new OTP has been sent to your email address."
}
```

Already verified users should not be allowed to request another email verification OTP.

---

# 6. Login After OTP Verification

After email verification, login returns JWT tokens.

### Endpoint

```http
POST /api/accounts/login/
```

### Body

```json
{
  "identifier": "newfan@example.com",
  "password": "StrongPass123"
}
```

### Expected Response

```json
{
  "message": "Login successful.",
  "access": "<access_token>",
  "refresh": "<refresh_token>",
  "role": "FAN",
  "frontend_dashboard_route": "/dashboard/fan",
  "backend_dashboard_route": "/api/dashboards/fan/",
  "requires_email_verification": false
}
```

Save the `access` token for authenticated endpoints.

---

# 7. Get Current User

### Endpoint

```http
GET /api/accounts/me/
```

### Headers

```http
Authorization: Bearer <access_token>
```

### curl

```bash
curl -X GET http://localhost:8000/api/accounts/me/ \
  -H "Authorization: Bearer <access_token>"
```

---

# 8. Get Profile

### Endpoint

```http
GET /api/accounts/profile/
```

### Headers

```http
Authorization: Bearer <access_token>
```

---

# 9. Update Profile

### Endpoint

```http
PATCH /api/accounts/profile/
```

### Headers

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Body

```json
{
  "first_name": "Updated",
  "last_name": "Name",
  "phone_number": "0721000000"
}
```

The backend normalizes local Ugandan phone numbers to international format.

Example:

```text
0721000000 → +256721000000
```

---

# 10. Upload Avatar

### Endpoint

```http
PATCH /api/accounts/profile/
```

### Body Type

```text
form-data
```

### Fields

```text
avatar: image file
```

Maximum avatar size:

```text
2 MB
```

---

# 11. Remove Avatar

### Endpoint

```http
DELETE /api/accounts/profile/avatar/
```

### Headers

```http
Authorization: Bearer <access_token>
```

---

# 12. Password Reset Request

This creates and emails a password reset OTP.

### Endpoint

```http
POST /api/accounts/password-reset/request/
```

### Body

```json
{
  "email": "newfan@example.com"
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/accounts/password-reset/request/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newfan@example.com"
  }'
```

### Expected Response

```json
{
  "message": "A password reset OTP has been sent to your email address."
}
```

---

# 13. Password Reset Confirm

Use the password reset OTP to set a new password.

### Endpoint

```http
POST /api/accounts/password-reset/confirm/
```

### Body

```json
{
  "email": "newfan@example.com",
  "code": "123456",
  "password": "NewStrongPass123",
  "confirm_password": "NewStrongPass123"
}
```

### curl

```bash
curl -X POST http://localhost:8000/api/accounts/password-reset/confirm/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newfan@example.com",
    "code": "123456",
    "password": "NewStrongPass123",
    "confirm_password": "NewStrongPass123"
  }'
```

### Expected Response

```json
{
  "message": "Password reset successful. You can now log in."
}
```

After this, the old password should fail and the new password should log in successfully.

---

# 14. OTP Rules

The backend applies the following OTP rules:

```text
1. OTPs expire after the configured expiry period.
2. Expired OTPs are marked as used.
3. Used OTPs cannot be reused.
4. Invalid OTP attempts are counted.
5. OTPs are locked after the maximum number of failed attempts.
6. Resending email verification OTP invalidates previous unused verification OTPs.
7. Already verified users cannot request another verification OTP.
```

---

# 15. Sponsor Account Access After Authentication

A normal fan can become a sponsor by creating a sponsor account.

### Endpoint

```http
POST /api/sponsorships/accounts/
```

### Headers

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Individual Sponsor Body

```json
{
  "sponsor_type": "INDIVIDUAL",
  "name": "Sponsor Fan Individual Account"
}
```

### Corporate Sponsor Body

```json
{
  "sponsor_type": "CORPORATE",
  "name": "Nile Special",
  "registration_country": "UG",
  "brn": "BRN-TEST-001",
  "tin": "1234567890"
}
```

After sponsor account creation, the user can access the sponsor dashboard if they have active sponsor membership.

---

# 16. Sponsor Dashboard

### Endpoint

```http
GET /api/dashboards/sponsor/
```

### Headers

```http
Authorization: Bearer <access_token>
```

Users without sponsor access receive:

```text
403 Forbidden
```

Users with sponsor account membership receive sponsor dashboard data.
