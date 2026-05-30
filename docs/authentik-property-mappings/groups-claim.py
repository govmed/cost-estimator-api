# Authentik Scope Mapping — "SOW Calc: groups claim"
#
# Paste this into:
#   Authentik admin → Customisation → Property Mappings
#   → Create Scope Mapping → Expression
#
# Scope name: groups
# This expression runs server-side in Authentik and adds the user's
# Authentik group names to the access token as a "groups" array claim.
# The FastAPI backend reads this claim in app/auth/oidc.py to derive
# the user's role (see app/auth/roles.py).

return [group.name for group in request.user.ak_groups.all()]
