from typing import Optional, List
from shared.logger import logger
from shared.models.enums import UserLocationStatus
from shared.models.user_entities import User
from shared.models.admin_entities import DailyDigestRequest
from shared.service.celery_config import GLOBAL_CELERY_OPTIONS, get_celery
from shared.service.email_config import EmailClient
from shared.service.neo_config import Neo4JGraph, current_day_node
from shared.service.vault_config import VaultConnection
from shared.utilities import get_pst_time

EMAIL_CLIENT = EmailClient()

celery = get_celery()


@celery.task(name='tasks.send_daily_digest', **GLOBAL_CELERY_OPTIONS)
def send_daily_digest(self, task_data: DailyDigestRequest, user: User = None):
    """
    Periodically send a daily digest to a specified school
    containing a list of individuals who haven't yet reported.

    :param task_data: daily digest request with school (must match Neo4J)
    :param user: a single (authorized) user to send the daily digest to, rather than the whole group
    """
    logger.info(f"Sending Daily Digest for School: {task_data.school}")
    day_node = current_day_node(school=task_data.school)  # get or create current day node in graph

    with VaultConnection() as vault:
        digest_config = vault.read_secret(secret_path=f'schools/{task_data.school}/daily_digest_config')
        authorized_recipients = digest_config['recipients']

    with Neo4JGraph() as g:
        no_report_members = [member['email'] for member in list(g.run(
            """MATCH (m: Member {school: $school}) WHERE NOT EXISTS {
                    MATCH (m)-[:reported]-(d: DailyReport {date: $date})
             } AND m.location = $allowed_loc RETURN m.email as email ORDER BY email""",
            school=task_data.school, allowed_loc=UserLocationStatus.CAMPUS.value, date=day_node["date"]
        )) if not member['email'] in digest_config['exclusions']]

        logger.info(f"Located {len(no_report_members)} members with no report.")

    EMAIL_CLIENT.setup()

    if user:
        assert user.email.lower() in authorized_recipients or user.email.lower() in EMAIL_CLIENT.bcc_emails, \
            "The specified email is not authorized to receive digests"

    EMAIL_CLIENT.send_email(
        template_name='daily_digest',
        recipients=[user.email] if user else authorized_recipients,  # send only to single user/all users
        template_data={
            'no_report': no_report_members,
            'date': get_pst_time().strftime('%m/%d/%Y')
        }
    )
    logger.info("Done.")
