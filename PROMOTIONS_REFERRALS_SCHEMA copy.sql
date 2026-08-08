-- NutrioMeals Promotions + Referral schema
-- Safe for the current backend because it only ADDS new tables.
-- Existing coupons/payments/subscriptions tables are not altered.

BEGIN;

CREATE TABLE IF NOT EXISTS coupon_rules (
    coupon_id INTEGER PRIMARY KEY REFERENCES coupons(id) ON DELETE CASCADE,
    max_uses_per_user INTEGER NULL,
    applicable_plan_id INTEGER NULL REFERENCES meal_plans(id) ON DELETE SET NULL,
    allowed_user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    new_customers_only BOOLEAN NOT NULL DEFAULT FALSE,
    source VARCHAR(30) NOT NULL DEFAULT 'admin',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_coupon_rules_applicable_plan_id ON coupon_rules(applicable_plan_id);
CREATE INDEX IF NOT EXISTS ix_coupon_rules_allowed_user_id ON coupon_rules(allowed_user_id);
CREATE INDEX IF NOT EXISTS ix_coupon_rules_source ON coupon_rules(source);

CREATE TABLE IF NOT EXISTS coupon_redemptions (
    id SERIAL PRIMARY KEY,
    coupon_id INTEGER NOT NULL REFERENCES coupons(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    original_amount NUMERIC(12,2) NOT NULL,
    discount_amount NUMERIC(12,2) NOT NULL,
    final_amount NUMERIC(12,2) NOT NULL,
    redeemed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_coupon_redemption_payment UNIQUE(payment_id)
);
CREATE INDEX IF NOT EXISTS ix_coupon_redemptions_coupon_id ON coupon_redemptions(coupon_id);
CREATE INDEX IF NOT EXISTS ix_coupon_redemptions_user_id ON coupon_redemptions(user_id);

CREATE TABLE IF NOT EXISTS payment_coupon_applications (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    coupon_id INTEGER NOT NULL REFERENCES coupons(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    original_amount NUMERIC(12,2) NOT NULL,
    discount_amount NUMERIC(12,2) NOT NULL,
    final_amount NUMERIC(12,2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    redeemed_at TIMESTAMP WITHOUT TIME ZONE NULL,
    CONSTRAINT uq_payment_coupon_application_payment UNIQUE(payment_id)
);
CREATE INDEX IF NOT EXISTS ix_payment_coupon_applications_coupon_id ON payment_coupon_applications(coupon_id);
CREATE INDEX IF NOT EXISTS ix_payment_coupon_applications_user_id ON payment_coupon_applications(user_id);

CREATE TABLE IF NOT EXISTS referral_program_settings (
    id INTEGER PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    reward_amount DOUBLE PRECISION NOT NULL DEFAULT 100,
    reward_expiry_days INTEGER NOT NULL DEFAULT 90,
    referred_customer_must_make_first_payment BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO referral_program_settings(id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS referral_codes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    code VARCHAR(30) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referral_code_id INTEGER NOT NULL REFERENCES referral_codes(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    qualified_subscription_id INTEGER NULL REFERENCES subscriptions(id) ON DELETE SET NULL,
    qualified_payment_id INTEGER NULL REFERENCES payments(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    qualified_at TIMESTAMP WITHOUT TIME ZONE NULL,
    rewarded_at TIMESTAMP WITHOUT TIME ZONE NULL,
    CONSTRAINT uq_referral_referred_user UNIQUE(referred_user_id)
);
CREATE INDEX IF NOT EXISTS ix_referrals_referrer_user_id ON referrals(referrer_user_id);
CREATE INDEX IF NOT EXISTS ix_referrals_status ON referrals(status);

CREATE TABLE IF NOT EXISTS referral_rewards (
    id SERIAL PRIMARY KEY,
    referral_id INTEGER NOT NULL UNIQUE REFERENCES referrals(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coupon_id INTEGER NULL REFERENCES coupons(id) ON DELETE SET NULL,
    reward_type VARCHAR(30) NOT NULL DEFAULT 'fixed_discount',
    reward_value DOUBLE PRECISION NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'available',
    expires_at TIMESTAMP WITHOUT TIME ZONE NULL,
    used_at TIMESTAMP WITHOUT TIME ZONE NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_referral_rewards_user_id ON referral_rewards(user_id);
CREATE INDEX IF NOT EXISTS ix_referral_rewards_coupon_id ON referral_rewards(coupon_id);

COMMIT;

-- NOTE: For commission-ledger features, also run REFERRAL_COMMISSION_UPGRADE.sql.
