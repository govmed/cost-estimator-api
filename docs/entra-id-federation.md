# Entra ID Federation via Authentik (B2.c)

This guide wires Gainwell's Azure Entra ID (formerly Azure AD) as an upstream
identity source for Authentik. Staff sign in with their corporate credentials
— no separate Authentik password needed.

## Architecture

```
User clicks "Sign in"
  → Authentik login page
    → "Sign in with Microsoft" button
      → Entra ID login (MFA enforced by Entra policy)
        → Entra issues OIDC code to Authentik callback
          → Authentik upserts user, issues its own OIDC token
            → API validates Authentik token
```

Authentik acts as a broker: it trusts Entra for authentication but issues
its own tokens, so the API only ever talks to Authentik. Swapping or adding
identity sources later requires no API changes.

---

## Step 1 — Azure App Registration

In **portal.azure.com → Entra ID → App registrations → New registration**:

| Field | Value |
|---|---|
| Name | `Authentik SOW Calc` |
| Supported account types | Accounts in this organizational directory only |
| Redirect URI (Web) | `http://localhost:9000/source/oauth/callback/entra-id/` |

After creation, also add the production redirect URI if you have one:
```
https://your-authentik-domain.com/source/oauth/callback/entra-id/
```

**API permissions** (add + grant admin consent):
- `openid` (delegated)
- `email` (delegated)
- `profile` (delegated)
- `User.Read` (delegated)
- `GroupMember.Read.All` (delegated) — needed to read group membership

**Certificates & secrets → New client secret**:
- Note the **Value** (only shown once) — this is your `client_secret`

**Overview page** — note:
- **Application (client) ID** → `client_id`
- **Directory (tenant) ID** → used in the OIDC discovery URL

---

## Step 2 — Authentik Federation Source

In **Authentik admin → Directory → Federation & Social login → Create**:

| Field | Value |
|---|---|
| Name | `Entra ID` |
| Slug | `entra-id` |
| Protocol | OAuth2/OIDC |
| Consumer key | `<Application (client) ID from step 1>` |
| Consumer secret | `<client_secret from step 1>` |
| OIDC well-known URL | `https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration` |
| Scopes | `openid email profile User.Read` |

Leave all other settings at defaults and save.

---

## Step 3 — Authentik Groups (for role mapping)

Create the groups that the API reads from the `groups` claim:

In **Authentik admin → Directory → Groups → Create**:

| Group name | Maps to API role |
|---|---|
| `SOWCalc-Admins` | `admin` |
| `SOWCalc-Users` | `user` (default — all provisioned users) |

> **Note:** The group names must match `ADMIN_GROUPS` in `app/auth/roles.py`.
> Edit that constant if you prefer different names.

---

## Step 4 — Group Sync from Entra

Authentik can mirror Entra groups automatically via its SCIM or LDAP
integration, or you can assign groups manually. For a small team, manual
assignment is easiest:

1. In **Authentik admin → Directory → Users**, find a user who logged in via
   Entra ID federation.
2. Open the user → **Groups** tab → add them to `SOWCalc-Admins` or
   `SOWCalc-Users`.

For automatic sync (larger orgs), set up the **Microsoft Entra SCIM** source
in Authentik — it syncs users and groups on a schedule.

---

## Step 5 — Add Groups to the OIDC Token

Authentik must include group names in the access token so the API can read
them. This requires a **Scope Mapping**:

In **Authentik admin → Customisation → Property Mappings → Create Scope Mapping**:

| Field | Value |
|---|---|
| Name | `SOW Calc — groups claim` |
| Scope name | `groups` |
| Description | `Adds user's Authentik group names to the access token` |
| Expression | *(see below)* |

**Expression** (Python, evaluated by Authentik):
```python
return [group.name for group in request.user.ak_groups.all()]
```

Then add this scope mapping to the OIDC provider:

**Authentik admin → Applications → Providers → cost-estimator-api → Edit**:
- In **Advanced protocol settings → Scopes**, add `SOW Calc — groups claim`

---

## Step 6 — Add the Login Button to Authentik's Login Page

By default the Entra ID source appears as a button on Authentik's login page
automatically once the source is active. If it doesn't:

**Authentik admin → Flows & Stages → Flows → default-authentication-flow**:
- Click on the **Identification Stage**
- Under **Sources**, enable `Entra ID`

---

## Step 7 — Test End-to-End

1. Open `http://localhost:9000/if/flow/default-authentication-flow/`
2. Click **"Sign in with Entra ID"**
3. Complete Entra ID login (MFA if required by your Entra policy)
4. Authentik should redirect back and show the dashboard
5. The user should appear in **Authentik → Directory → Users**
6. Check the API: call `GET /auth/me` with the token — the `role` field
   should reflect group membership

---

## Step 8 — Configure the API

Set in `.env`:

```env
AUTH_MODE=oidc
AUTHENTIK_ISSUER=http://localhost:9000/application/o/cost-estimator-api/
```

The API reads the `groups` claim from every token on each request and syncs
the user's role automatically. Promoting a user to admin by adding them to
`SOWCalc-Admins` in Authentik takes effect on their next login.

---

## Entra ID Conditional Access (recommended for production)

Apply a Conditional Access policy in Entra ID requiring MFA for the
`Authentik SOW Calc` application. This enforces MFA for all users regardless
of whether Authentik's own MFA is configured — defence in depth.

**Entra ID → Security → Conditional Access → New policy**:
- **Users**: All users (or a specific group)
- **Cloud apps**: `Authentik SOW Calc`
- **Grant**: Require multi-factor authentication

---

## Troubleshooting

**"Sign in with Entra ID" button not appearing**
→ Check that the federation source is enabled and added to the authentication
flow's Identification Stage.

**User lands in Authentik but role is always `user`**
→ Check that the `groups` scope mapping is added to the provider and that the
user is a member of `SOWCalc-Admins` in Authentik.

**`groups` claim is empty in the token**
→ Verify the scope mapping expression is correct and the scope is listed in
the provider's scopes. Test via `GET /auth/me` — the API logs the decoded
claims at DEBUG level.

**Entra groups not syncing to Authentik groups**
→ Manual assignment via the Authentik admin UI is the simplest fix. For
automatic sync, set up the Microsoft Entra SCIM source.

**Token validation error: "issuer mismatch"**
→ `AUTHENTIK_ISSUER` must exactly match the `iss` claim in the token
(including trailing slash). Check `/.well-known/openid-configuration` at
your Authentik issuer URL to confirm.
