# -*- coding: utf-8 -*-
"""
Synchronous API for client-side display in both iOS and Web Apps
"""
from fastapi import APIRouter, status
from py2neo.matching import NodeMatcher

from shared.logger import logger
from shared.models.user_entities import (HealthReport, ListUsersResponse, User)
from shared.models.risk_entities import UserRiskItem
from shared.models.admin_entities import UserLocationStatus
from shared.service.neo_config import Neo4JGraph
from shared.utilities import pst_date
from .authorization import AUTH_USER

# Synchronous API Router-- we can mount it to the main API
SYNC_ROUTER = APIRouter()


@SYNC_ROUTER.get('/list/users', response_model=ListUsersResponse, status_code=status.HTTP_200_OK,
                 description="List the users from a specified school (no PII)", operation_id='list_users')
async def list_users(user: User = AUTH_USER):
    """
    List the users who belong to a specified school
    """
    logger.info(f"Listing Users for school: {user.school}")
    with Neo4JGraph() as g:
        logger.info("Acquired Neo4J Graph... Running Selection query")
        result_set = list(NodeMatcher(graph=g).match("Member").where(f"_.school = '{user.school}'"))
    return ListUsersResponse(users=[User(**member) for member in result_set])


@SYNC_ROUTER.get('/user-status', response_model=UserRiskItem, status_code=status.HTTP_200_OK,
                 description="Get a user's current health status", operation_id='user_status')
async def user_healthy(user: User = AUTH_USER):
    """
    Retrieve the current user status from the backend
    """
    logger.info(f"Retrieving user status for school: {user.school}")
    risk_item = UserRiskItem()

    with Neo4JGraph() as graph:
        record = list(graph.run(
            """MATCH (m:Member {email: $email,school: $school})
              OPTIONAL MATCH (m)-[r:reported]-(d:DailyReport {date: $date})
              RETURN r as report, m.location as location, m.first_name + " " + m.last_name as name""",
            email=user.email, school=user.school, date=pst_date()
        ))
        record = dict(record[0])
        risk_item.name = record['name']

        if not record.get('report'):
            return risk_item.set_incomplete()

        if UserLocationStatus.blocked(record['location']):
            return risk_item.set_location_blocked(location=record['location'])

        return risk_item.from_health_report(HealthReport(**record['report']))
