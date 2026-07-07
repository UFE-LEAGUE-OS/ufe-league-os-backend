# 13. Superadmin Test Data Guide

This guide helps frontend developers populate superadmin pages with test data for development and testing.

## Quick Start

### Option 1: Using the Standalone Script (Recommended)

```bash
# From the backend directory
python backend/scripts/populate_superadmin_data.py
```

This will:
1. Run migrations automatically
2. Create a super admin user
3. Populate all superadmin modules with test data

### Option 2: Using Django Management Command

```bash
# From the backend directory
python manage.py populate_governance_data
```

This populates only the governance module.

## Super Admin Credentials

After running the script, you can login with:

```
Email: admin@gmail.com
Password: Strong123!
```

## What Data Gets Populated

The script populates the following superadmin modules:

### 1. Governance Module

**Sport Variants:**
- Football 11-a-side
- Futsal
- Beach Soccer

**Competition Formats:**
- Single Round Robin
- Double Round Robin
- Group Stage + Knockout

**Rules & Standards:**
- Licensing Requirements
- Squad Registration Rules
- Financial Fair Play
- Disciplinary Code
- Stadium Safety Standards

**League Standards:**
- Rules published to first 3 active leagues

### 2. RBAC Module

**Permissions:**
- Dashboard permissions (super_admin, league_admin, club_admin)
- Module permissions (governance, monitoring, rbac, analytics, etc.)

**Permission Bundles:**
- Super Admin Bundle (full access)
- League Admin Bundle (limited access)

**Role Templates:**
- Super Administrator
- League Administrator

### 3. Monitoring Module

**Anomalies:**
- Unusual activity detection
- Payment anomalies

**Security Events:**
- Unauthorized access attempts
- Suspicious login notifications

**Compliance Trails:**
- Data access logs
- Permission change logs

**Transaction Reconciliations:**
- Sample verified reconciliation

## Command Options

### Clear Existing Data

```bash
# Clear all data and repopulate
python backend/scripts/populate_superadmin_data.py --clear

# Clear only specific module
python backend/scripts/populate_superadmin_data.py --clear --module governance
```

### Populate Specific Module

```bash
# Only governance
python backend/scripts/populate_superadmin_data.py --module governance

# Only RBAC
python backend/scripts/populate_superadmin_data.py --module rbac

# Only monitoring
python backend/scripts/populate_superadmin_data.py --module monitoring

# All modules (default)
python backend/scripts/populate_superadmin_data.py --module all
```

## API Endpoints for Manual Data Creation

If you need to create data manually via API, here are the superadmin endpoints:

### Governance Endpoints

```http
# Sport Variants
POST /api/governance/sport-variants/
Authorization: Bearer <super_admin_token>

# Competition Formats
POST /api/governance/competition-formats/
Authorization: Bearer <super_admin_token>

# Rules
POST /api/governance/rules/
Authorization: Bearer <super_admin_token>

# Publish Standards to Leagues
POST /api/governance/league-standards/
Authorization: Bearer <super_admin_token>
```

### RBAC Endpoints

```http
# Permissions
GET /api/rbac/permissions/
POST /api/rbac/bundles/
POST /api/rbac/role-templates/
POST /api/rbac/assignments/
```

### Monitoring Endpoints

```http
# Anomalies
GET /api/monitoring/anomalies/
POST /api/monitoring/anomalies/

# Security Events
GET /api/monitoring/security-events/
POST /api/monitoring/security-events/

# Compliance Trails
GET /api/monitoring/compliance/
POST /api/monitoring/compliance/
```

## Testing the Setup

1. **Login as Super Admin:**
   ```bash
   POST /api/accounts/login/
   {
     "email": "admin@gmail.com",
     "password": "Strong123!"
   }
   ```

2. **Verify Dashboard Access:**
   ```bash
   GET /api/dashboards/super-admin/
   Authorization: Bearer <token>
   ```

3. **Check Governance Data:**
   ```bash
   GET /api/governance/sport-variants/
   GET /api/governance/rules/
   Authorization: Bearer <token>
   ```

## Troubleshooting

### Script Fails with Import Errors

Make sure you're running from the backend directory:

```bash
cd c:/Users/SONY/Desktop/ufe-league-os-backend
python backend/scripts/populate_superadmin_data.py
```

### Permission Denied Errors

Ensure the super admin user has the correct role:

```bash
python backend/manage.py shell
```

```python
from accounts.models import User
user = User.objects.get(email="admin@gmail.com")
print(f"Role: {user.role}")
print(f"Is Staff: {user.is_staff}")
print(f"Is Superuser: {user.is_superuser}")
```

### No Data Appears in Frontend

1. Check that you're authenticated as a super admin
2. Verify the API responses contain data:
   ```bash
   GET /api/governance/sport-variants/
   ```
3. Check browser console for CORS errors
4. Ensure the Authorization header is set correctly

## Frontend Integration Checklist

- [ ] Super admin can login successfully
- [ ] Dashboard loads without errors
- [ ] Sport variants list displays data
- [ ] Competition formats list displays data
- [ ] Rules list displays data
- [ ] League standards show assignments
- [ ] RBAC permissions list loads
- [ ] Monitoring anomalies list loads
- [ ] Security events list loads
- [ ] Compliance trails list loads

## Notes for Frontend Developers

1. **Authentication**: All superadmin endpoints require a valid JWT token from a super admin user
2. **Base URL**: Use `http://localhost:8000` for local development
3. **CORS**: Already configured for local development
4. **Data Persistence**: Data created by the script persists until cleared or database is reset
5. **Idempotent**: The script uses `get_or_create`, so running it multiple times won't duplicate data

## Need Help?

- Check the API reference: `docs/05-api-reference.md`
- Review frontend integration guide: `docs/06-frontend-integration-guide.md`
- Backend logs will show detailed error messages if something goes wrong