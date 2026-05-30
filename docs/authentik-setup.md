# Authentik Setup Guide

Authentik is the identity provider for the SOW Cost Calculator. It handles
login, SSO, and (optionally) federation with Entra ID / AD.

## 1. Start the stack

```bash
cp .env.example .env   # edit passwords + secret keys
docker compose up -d
```

Authentik takes ~60 seconds on first boot while it runs migrations.

## 2. Complete the initial setup

Open http://localhost:9000/if/flow/initial-setup/ and create your admin account.

## 3. Create the OIDC provider

In the Authentik admin UI (http://localhost:9000/if/admin/):

1. **Applications → Providers → Create**
   - Type: **OAuth2/OpenID Provider**
   - Name: `cost-estimator-api`
   - Authorization flow: `default-provider-authorization-implicit-consent`
   - Client type: **Confidential**
   - Note the **Client ID** and **Client Secret**

2. **Redirect URIs** (add all that apply):
   ```
   http://localhost:5173/auth/callback    ← SPA dev server
   https://your-domain.com/auth/callback ← production
   ```

3. **Scopes**: ensure `openid`, `email`, `profile` are selected

4. Note the **Issuer URL** from the provider detail page:
   ```
   http://localhost:9000/application/o/cost-estimator-api/
   ```

## 4. Create the Application

1. **Applications → Applications → Create**
   - Name: `SOW Cost Estimator`
   - Slug: `cost-estimator`
   - Provider: the one you just created

## 5. Configure the API

In your `.env`:

```env
AUTH_MODE=oidc
AUTHENTIK_ISSUER=http://localhost:9000/application/o/cost-estimator-api/
```

Restart the API:

```bash
docker compose restart api
```

The API will now validate Bearer tokens issued by Authentik. Standalone JWT
login is disabled. First login provisions the user locally using the `sub`
claim from Authentik as the user ID.

## 6. Configure the SPA (B2.c)

The SPA will use the Authorization Code + PKCE flow:

```
Client ID:  (from step 3)
Issuer:     http://localhost:9000/application/o/cost-estimator-api/
Scopes:     openid email profile
```

No client secret is needed for the SPA (public client, PKCE).

## 7. Entra ID federation (optional — B2.d)

To let Gainwell staff log in with their corporate credentials:

1. In Authentik admin: **Directory → Federation Sources → Create**
   - Type: **OAuth2/OIDC**
   - Name: `Entra ID`
   - Consumer key: Azure App Registration client ID
   - Consumer secret: Azure client secret
   - OIDC well-known URL:
     `https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration`

2. Map Entra groups to Authentik groups for role-based access.

3. Users log in via "Sign in with Entra ID" on the Authentik login page —
   no separate Azure SSO integration needed in the SPA or API.

## Useful URLs

| URL | Purpose |
|---|---|
| http://localhost:9000/if/admin/ | Authentik admin UI |
| http://localhost:9000/application/o/cost-estimator-api/.well-known/openid-configuration | OIDC discovery |
| http://localhost:9000/application/o/cost-estimator-api/jwks/ | JWKS (public keys) |

## Rotating keys

Authentik rotates signing keys automatically. If you force a rotation:

```bash
docker compose exec api python -c "from app.auth.oidc import refresh_jwks; refresh_jwks()"
```

Or restart the API — the JWKS cache is in-process.
