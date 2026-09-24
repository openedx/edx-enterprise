from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0235_enterprisecustomeradmin'),
    ]
    operations = [
        # Custom SQL to add view that unions EnterpriseCustomerUser and PendingEnterpriseCustomerUser records
        # together to facilitate querying both simultaneously
        migrations.RunSQL(
            sql="""
                CREATE VIEW view_enterprise_customer_support_users AS
                    with admins as (
                        SELECT era.id, era.enterprise_customer_id, era.user_id
                        FROM enterprise_systemwideenterpriseuserroleassignment AS era
                        INNER JOIN enterprise_systemwideenterpriserole AS ra ON era.role_id = ra.id
                        WHERE ra.name = 'enterprise_admin'
                    )
                    SELECT ecu.enterprise_customer_id,
                    au.email AS user_email,
                    FALSE AS is_pending,
                    ecu.user_id,
                    au.username,
                    au.first_name,
                    au.last_name,
                    au.is_staff,
                    au.is_active,
                    au.date_joined,
                    CASE WHEN ad.id IS NULL THEN false ELSE true END AS is_admin
                    FROM enterprise_enterprisecustomeruser AS ecu
                    INNER JOIN auth_user AS au ON au.id = ecu.user_fk
                    LEFT JOIN admins AS ad ON ad.enterprise_customer_id = ecu.enterprise_customer_id AND ad.user_id = au.id
                
                    UNION
                
                    SELECT pecu.enterprise_customer_id,
                    pecu.user_email,
                    TRUE AS is_pending,
                    0 AS user_id,
                    '' AS username,
                    '' AS first_name,
                    '' AS last_name,
                    FALSE AS is_staff,
                    FALSE AS is_active,
                    NULL AS date_joined,
                    CASE WHEN pecau.id IS NULL THEN false ELSE true END AS is_admin
                    FROM enterprise_pendingenterprisecustomeruser AS pecu
                    LEFT JOIN enterprise_pendingenterprisecustomeradminuser AS pecau on pecu.user_email = pecau.user_email
            """,
            reverse_sql="""
                DROP VIEW view_enterprise_customer_support_users
            """
        ),
    ]
