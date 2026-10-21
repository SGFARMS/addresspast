# Database

AddressPast runs as a tenant (`addresspast`) on the **SkyHigh BaaS**, the self-hosted Supabase in
[SGFARMS/skyhighwebsites-baas](https://github.com/SGFARMS/skyhighwebsites-baas).

The schema lives there, not here, so every tenant's migrations apply in one ordered sequence:

- `postgres/migrations/0026_addresspast_schema.sql`: all `ap_*` tables, triggers and `ap_api_*` functions
- `postgres/migrations/tests/rls_and_grants_test.sql`: the AddressPast regression block (runs in that repo's CI)

To change the schema, add a new numbered migration in that repo and apply it with
**Actions → Droplet ops → update-baas**.
