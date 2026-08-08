-- NutrioMeals Referral Commission Upgrade
-- Extends the existing referral feature to support Admin-controlled:
--   1) fixed amount per successful payment
--   2) percentage of successful payment
--   3) fixed amount on first successful payment only
-- plus first-payment/every-payment scope and a transaction earnings ledger.
--
-- Safe/idempotent for an installation that already ran
-- PROMOTIONS_REFERRALS_SCHEMA.sql.

BEGIN;

ALTER TABLE referral_program_settings
    ADD COLUMN IF NOT EXISTS reward_mode VARCHAR(40)
        NOT NULL DEFAULT 'fixed_first_payment';

ALTER TABLE referral_program_settings
    ADD COLUMN IF NOT EXISTS reward_value DOUBLE PRECISION
        NOT NULL DEFAULT 100;

ALTER TABLE referral_program_settings
    ADD COLUMN IF NOT EXISTS commission_scope VARCHAR(40)
        NOT NULL DEFAULT 'first_payment_only';

ALTER TABLE referral_program_settings
    ADD COLUMN IF NOT EXISTS max_reward_per_payment NUMERIC(12,2)
        NULL;

-- Preserve the first-version configured reward amount.
UPDATE referral_program_settings
SET reward_value = reward_amount
WHERE id = 1
  AND (
      reward_value IS NULL
      OR reward_value = 100
  );

CREATE TABLE IF NOT EXISTS referral_earnings (
    id SERIAL PRIMARY KEY,

    referral_id INTEGER NOT NULL
        REFERENCES referrals(id)
        ON DELETE CASCADE,

    referral_code_id INTEGER NOT NULL
        REFERENCES referral_codes(id)
        ON DELETE RESTRICT,

    referrer_user_id INTEGER NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    referred_user_id INTEGER NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    subscription_id INTEGER NOT NULL
        REFERENCES subscriptions(id)
        ON DELETE CASCADE,

    payment_id INTEGER NOT NULL UNIQUE
        REFERENCES payments(id)
        ON DELETE CASCADE,

    coupon_id INTEGER NULL
        REFERENCES coupons(id)
        ON DELETE SET NULL,

    reward_mode VARCHAR(40) NOT NULL,
    reward_rate NUMERIC(12,4) NOT NULL,

    payment_amount NUMERIC(12,2) NOT NULL,
    reward_amount NUMERIC(12,2) NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'available',

    expires_at TIMESTAMP WITHOUT TIME ZONE NULL,
    used_at TIMESTAMP WITHOUT TIME ZONE NULL,
    earned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_referral_earning_payment
        UNIQUE(payment_id)
);

CREATE INDEX IF NOT EXISTS ix_referral_earnings_referral_id
    ON referral_earnings(referral_id);

CREATE INDEX IF NOT EXISTS ix_referral_earnings_referral_code_id
    ON referral_earnings(referral_code_id);

CREATE INDEX IF NOT EXISTS ix_referral_earnings_referrer_user_id
    ON referral_earnings(referrer_user_id);

CREATE INDEX IF NOT EXISTS ix_referral_earnings_referred_user_id
    ON referral_earnings(referred_user_id);

CREATE INDEX IF NOT EXISTS ix_referral_earnings_subscription_id
    ON referral_earnings(subscription_id);

CREATE INDEX IF NOT EXISTS ix_referral_earnings_coupon_id
    ON referral_earnings(coupon_id);

CREATE INDEX IF NOT EXISTS ix_referral_earnings_status
    ON referral_earnings(status);

COMMIT;

-- Verification
SELECT
    id,
    is_active,
    reward_mode,
    reward_value,
    commission_scope,
    max_reward_per_payment,
    reward_expiry_days
FROM referral_program_settings
WHERE id = 1;
