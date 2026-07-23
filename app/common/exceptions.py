from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

class AppException(HTTPException):
    """
    Base exception for application-level API errors.

    All custom exceptions inherit from this class so the project
    can later use one global FastAPI exception handler.
    """

    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        error_code: str | None = None,
        errors: list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        detail = {
            "success": False,
            "message": message,
            "error_code": error_code,
            "errors": errors or [],
        }

        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers,
        )

        self.message = message
        self.error_code = error_code
        self.errors = errors or []


class BadRequestException(AppException):
    def __init__(
        self,
        message: str = "Bad request.",
        *,
        error_code: str = "BAD_REQUEST",
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=message,
            error_code=error_code,
            errors=errors,
        )

class UnauthorizedException(AppException):
    def __init__(
        self,
        message: str = "Authentication is required.",
        *,
        error_code: str = "UNAUTHORIZED",
        errors: list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            error_code=error_code,
            errors=errors,
            headers=headers or {"WWW-Authenticate": "Bearer"},
        )


class InvalidCredentialsException(UnauthorizedException):
    def __init__(
        self,
        message: str = "Invalid email or password.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="INVALID_CREDENTIALS",
        )


class InvalidTokenException(UnauthorizedException):
    def __init__(
        self,
        message: str = "Invalid or expired authentication token.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="INVALID_TOKEN",
        )


class TokenExpiredException(UnauthorizedException):
    def __init__(
        self,
        message: str = "Authentication token has expired.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="TOKEN_EXPIRED",
        )

class ForbiddenException(AppException):
    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        *,
        error_code: str = "FORBIDDEN",
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            error_code=error_code,
            errors=errors,
        )


class PermissionDeniedException(ForbiddenException):
    def __init__(
        self,
        message: str = "You do not have the required permission.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
        )


class RoleRequiredException(ForbiddenException):
    def __init__(
        self,
        required_roles: list[str] | tuple[str, ...] | None = None,
        message: str | None = None,
    ) -> None:
        roles = list(required_roles or [])

        final_message = message

        if final_message is None:
            if roles:
                final_message = (
                    "This action requires one of the following roles: "
                    + ", ".join(roles)
                    + "."
                )
            else:
                final_message = "Your account role cannot perform this action."

        super().__init__(
            message=final_message,
            error_code="ROLE_REQUIRED",
        )


class AccountInactiveException(ForbiddenException):
    def __init__(
        self,
        message: str = "This account is inactive.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="ACCOUNT_INACTIVE",
        )


class AccountNotVerifiedException(ForbiddenException):
    def __init__(
        self,
        message: str = "Please verify your account before continuing.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="ACCOUNT_NOT_VERIFIED",
        )

class NotFoundException(AppException):
    def __init__(
        self,
        resource: str = "Resource",
        *,
        message: str | None = None,
        error_code: str = "NOT_FOUND",
    ) -> None:
        final_message = message or f"{resource} not found."

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=final_message,
            error_code=error_code,
        )


class UserNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "User not found.",
    ) -> None:
        super().__init__(
            resource="User",
            message=message,
            error_code="USER_NOT_FOUND",
        )


class CustomerNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Customer not found.",
    ) -> None:
        super().__init__(
            resource="Customer",
            message=message,
            error_code="CUSTOMER_NOT_FOUND",
        )


class DriverNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Driver not found.",
    ) -> None:
        super().__init__(
            resource="Driver",
            message=message,
            error_code="DRIVER_NOT_FOUND",
        )


class OrderNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Order not found.",
    ) -> None:
        super().__init__(
            resource="Order",
            message=message,
            error_code="ORDER_NOT_FOUND",
        )


class DeliveryNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Delivery not found.",
    ) -> None:
        super().__init__(
            resource="Delivery",
            message=message,
            error_code="DELIVERY_NOT_FOUND",
        )


class MealNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Meal not found.",
    ) -> None:
        super().__init__(
            resource="Meal",
            message=message,
            error_code="MEAL_NOT_FOUND",
        )


class PlanNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Plan not found.",
    ) -> None:
        super().__init__(
            resource="Plan",
            message=message,
            error_code="PLAN_NOT_FOUND",
        )


class SubscriptionNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Subscription not found.",
    ) -> None:
        super().__init__(
            resource="Subscription",
            message=message,
            error_code="SUBSCRIPTION_NOT_FOUND",
        )


class PaymentNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "Payment not found.",
    ) -> None:
        super().__init__(
            resource="Payment",
            message=message,
            error_code="PAYMENT_NOT_FOUND",
        )

class ConflictException(AppException):
    def __init__(
        self,
        message: str = "The request conflicts with the current resource state.",
        *,
        error_code: str = "CONFLICT",
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            message=message,
            error_code=error_code,
            errors=errors,
        )


class DuplicateResourceException(ConflictException):
    def __init__(
        self,
        resource: str = "Resource",
        message: str | None = None,
    ) -> None:
        super().__init__(
            message=message or f"{resource} already exists.",
            error_code="DUPLICATE_RESOURCE",
        )


class EmailAlreadyExistsException(ConflictException):
    def __init__(
        self,
        message: str = "Email is already registered.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="EMAIL_ALREADY_EXISTS",
        )


class PhoneAlreadyExistsException(ConflictException):
    def __init__(
        self,
        message: str = "Phone number is already registered.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="PHONE_ALREADY_EXISTS",
        )


class DeliveryAlreadyExistsException(ConflictException):
    def __init__(
        self,
        message: str = "A delivery already exists for this order.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="DELIVERY_ALREADY_EXISTS",
        )


class ActiveSubscriptionExistsException(ConflictException):
    def __init__(
        self,
        message: str = "The customer already has an active subscription.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="ACTIVE_SUBSCRIPTION_EXISTS",
        )

class UnprocessableEntityException(AppException):
    def __init__(
        self,
        message: str = "The supplied data could not be processed.",
        *,
        error_code: str = "UNPROCESSABLE_ENTITY",
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=message,
            error_code=error_code,
            errors=errors,
        )


class ValidationException(UnprocessableEntityException):
    def __init__(
        self,
        message: str = "Validation failed.",
        *,
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            errors=errors,
        )


class MissingDeliveryAddressException(UnprocessableEntityException):
    def __init__(
        self,
        message: str = (
            "A delivery address is required because no address "
            "was found in the request, order, or customer profile."
        ),
    ) -> None:
        super().__init__(
            message=message,
            error_code="MISSING_DELIVERY_ADDRESS",
        )


class MissingDedicatedDriverException(
    UnprocessableEntityException
):
    def __init__(
        self,
        message: str = (
            "The customer does not have an active dedicated driver."
        ),
    ) -> None:
        super().__init__(
            message=message,
            error_code="MISSING_DEDICATED_DRIVER",
        )


class InvalidStatusTransitionException(
    UnprocessableEntityException
):
    def __init__(
        self,
        *,
        current_status: str | None = None,
        requested_status: str | None = None,
        message: str | None = None,
    ) -> None:
        final_message = message

        if final_message is None:
            if current_status and requested_status:
                final_message = (
                    f"Status cannot be changed from "
                    f"'{current_status}' to '{requested_status}'."
                )
            else:
                final_message = "Invalid status transition."

        super().__init__(
            message=final_message,
            error_code="INVALID_STATUS_TRANSITION",
        )

class TooManyRequestsException(AppException):
    def __init__(
        self,
        message: str = "Too many requests. Please try again later.",
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        headers = None

        if retry_after_seconds is not None:
            headers = {
                "Retry-After": str(retry_after_seconds),
            }

        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message=message,
            error_code="TOO_MANY_REQUESTS",
            headers=headers,
        )


class OTPRateLimitException(TooManyRequestsException):
    def __init__(
        self,
        message: str = (
            "Too many OTP requests. Please wait before requesting "
            "another verification code."
        ),
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            message=message,
            retry_after_seconds=retry_after_seconds,
        )

        self.detail["error_code"] = "OTP_RATE_LIMITED"
        self.error_code = "OTP_RATE_LIMITED"

class InternalServerException(AppException):
    def __init__(
        self,
        message: str = "An unexpected server error occurred.",
        *,
        error_code: str = "INTERNAL_SERVER_ERROR",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=message,
            error_code=error_code,
        )


class DatabaseException(InternalServerException):
    def __init__(
        self,
        message: str = "A database operation failed.",
    ) -> None:
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
        )


class ExternalServiceException(AppException):
    def __init__(
        self,
        message: str = "An external service is currently unavailable.",
        *,
        error_code: str = "EXTERNAL_SERVICE_ERROR",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message=message,
            error_code=error_code,
        )