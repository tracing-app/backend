# -*- coding: utf-8 -*-
"""
API Models for type validation and API doc generation
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from shared.service.celery_config import get_celery
from shared.utilities import pst_timestamp


# Base Classes
class Timestamped(BaseModel):
    """
    Base Timestamped model
    """

    timestamp: int = Field(default_factory=lambda: int(pst_timestamp()))


class Paginated(BaseModel):
    """
    Request for paginated data
    """
    pagination_token: int = 0
    limit: int = 20


class PaginatedResponse(Timestamped):
    """
    Response from retrieving paginated data
    """
    pagination_token: Optional[int]


# ENUMS - Use String Mixin to make JSON Serializeable: https://stackoverflow.com/a/51976841/4501002
class ResponseStatus(str, Enum):
    """
    Possible response statuses from the API
    """
    MALFORMED = "MALFORMED"
    UNEXPECTED_ERROR = "UNEXPECTED"
    SUCCESS = "SUCCESS"
    QUEUED = "QUEUED"
    ACCESS_DENIED = "ACCESS_DENIED"


class DashboardSummaryStatus(str, Enum):
    """
    Item code representing User Health
    """
    HEALTHY = "HEALTHY"
    NO_REPORT = "INCOMPLETE"
    POSITIVE_TEST = "POSITIVE_TEST"
    POSITIVE_TEST_WITH_SYMPTOMS = "POSITIVE_TEST_WITH_SYMPTOMS"
    NEGATIVE_TEST_WITH_SYMPTOMS = "NEGATIVE_TEST_WITH_SYMPTOMS"
    NEGATIVE_TEST = "NEGATIVE_TESTS"
    SYMPTOMATIC = "SYMPTOMATIC"


class DashboardSummaryColors(str, Enum):
    """
    Summary Item colors for dashboard items
    """
    UNHEALTHY = "danger"
    HEALTHY = "success"
    NO_REPORT = "gray"


class TestType(str, Enum):
    """
    Test Type of the report
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"


class UserStatus(str, Enum):
    """
    User status
    """

    INACTIVE = "inactive"
    ACTIVE = "active"


# Entities and Reports
class InteractionReport(BaseModel):
    """
    Interaction report schema for API validation and documentation
    """

    targets: List[str]


class TestReport(Timestamped):
    """
    Report either a positive or negative test
    """

    test_type: TestType

    def get_test(self):
        """
        Get the test type as a string
        :return: string version of the test
        """
        if self.test_type == TestType.POSITIVE:
            return "Positive Test"
        elif self.test_type == TestType.NEGATIVE:
            return "Negative Test"
        raise Exception(f"Unknown Test Type {self.test_type}")


class SymptomReport(Timestamped):
    """
    Symptom Report
    """
    num_symptoms: int = 0


class Report(BaseModel):
    """
    Base Report Holder
    """
    interactions: List[InteractionReport] = []
    tests: List[TestReport] = []
    symptoms: List[SymptomReport] = []


class RiskNotification(BaseModel):
    """
    Risk Notification model
    """
    criteria: str


# REST Entities
class UserEmailIdentifier(BaseModel):
    """
    Identification for a user by their email
    """
    email: str


class OptionalPaginatedUserEmailIdentifier(Paginated):
    """
    Identification for a user pagination optionally by their email
    """
    email: str = None


class PaginatedUserEmailIdentifer(UserEmailIdentifier, Paginated):
    """
    Pagination identification for a user by their email
    """
    pass


class AdminDashboardUser(BaseModel):
    """
    User who is using the admin dashboard
    """
    first_name: str
    last_name: str
    email: str
    school: str


class DashboardUserSummaryItem(BaseModel):
    """
    Entity representing a summary item on the dashboard
    """
    email: Optional[str]
    timestamp: Optional[str]
    color: str = None
    message: str = None
    code: str = None

    def set_negative_test(self, num_symptoms=0):
        self.color = DashboardSummaryColors.HEALTHY
        if num_symptoms > 0:
            self.code = DashboardSummaryStatus.NEGATIVE_TEST_WITH_SYMPTOMS
            self.message = f'Negative Test & {num_symptoms} Symptoms'
        else:
            self.code = DashboardSummaryStatus.NEGATIVE_TEST
            self.message = 'Negative Test'
        return self

    def set_positive_test(self, num_symptoms=0):
        self.color = DashboardSummaryColors.UNHEALTHY
        if num_symptoms > 0:
            self.code = DashboardSummaryStatus.POSITIVE_TEST_WITH_SYMPTOMS
            self.message = f'Positive Test & {num_symptoms} Symptoms'
        else:
            self.code = DashboardSummaryStatus.POSITIVE_TEST
            self.message = 'Positive Test'
        return self

    def set_symptomatic(self, num_symptoms):
        self.color = DashboardSummaryColors.UNHEALTHY
        self.code = DashboardSummaryStatus.SYMPTOMATIC
        self.message = f'{num_symptoms} Symptoms'
        return self

    def set_incomplete(self):
        self.color = DashboardSummaryColors.NO_REPORT
        self.code = DashboardSummaryStatus.NO_REPORT
        self.message = "No Report"
        return self

    def set_healthy(self):
        self.color = DashboardSummaryColors.HEALTHY
        self.code = DashboardSummaryStatus.HEALTHY
        self.message = 'Healthy'
        return self


class DashboardUserInfoDetail(BaseModel):
    """
    Entity representing user info detail on the user
    detail page
    """
    email: str
    first_name: str
    last_name: str
    cohort: Optional[int]
    active: bool
    school: str


class User(BaseModel):
    """
    User Schema for API validation and documentation
    """
    first_name: str
    last_name: str
    email: str
    school: str
    status: UserStatus = UserStatus.INACTIVE

    def queue_task(self, *, task_name: str, task_data: Optional[BaseModel] = None) -> str:
        """
        Send a task to service via rabbitmq
        :param task_name: the task name to queue the task to
        :param task_data: data to send to the target worker
        :return: the task id
        """
        task_params = {'user': self}

        if task_data:
            task_params['task_data'] = task_data

        queued_task = get_celery().send_task(
            name=task_name, args=[], kwargs=task_params
        )
        return queued_task.id

    class Config:
        """
        Pydantic configuration
        """
        use_enum_values = True  # Serialize enum values to strings


# Responses
class Response(Timestamped):
    """
    Base API Response back to client
    """
    status: ResponseStatus = ResponseStatus.SUCCESS


class FailureResponse(Response):
    """
    Failure Response Model back to client
    """

    reason: str


class ListUsersResponse(Response):
    """
    Listing users in the database response
    """
    users: List[User]


class CreatedAsyncTask(Response):
    """
    Created Asynchronous task with service
    """
    status = ResponseStatus.QUEUED
    task_id: str


class DashboardNumericalWidgetResponse(Response):
    """
    Numerical Widget Value on the homescreen of the dashboard
    """
    value: int


class DashboardUserSummaryResponse(Paginated):
    """
    User Summary Response for the Dashboard
    """
    records: List[DashboardUserSummaryItem]


class DashboardUserInteraction(BaseModel):
    """
    Interaction between two users on the dashboard
    """
    email: str
    timestamp: str


class DashboardUserInteractions(Paginated):
    """
    User Interactions for the Dasboard
    """
    users: List[DashboardUserInteraction]
