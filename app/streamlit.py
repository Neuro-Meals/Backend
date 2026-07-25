"""
NutrioMeals Backend Flow Tester
================================

Run:
    pip install streamlit requests pandas
    streamlit run streamlit.py

This tester simulates: 

1. Admin login
2. Load customers, subscriptions, meals, drivers, and deliveries
3. Assign multiple meals to a customer's subscription
4. Assign a driver to a delivery/customer workflow
5. Customer login
6. Customer views assigned meals from GET /meal-selections/my

Important:
- Endpoint paths are editable in the Streamlit sidebar.
- The app stores tokens only in Streamlit session state.
- Update the endpoint paths if your FastAPI routes differ.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import pandas as pd
import requests
import streamlit as st


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="NutrioMeals Backend Tester",
    page_icon="🍽️",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    "admin_token": None,
    "admin_user": None,
    "customer_token": None,
    "customer_user": None,
    "driver_token": None,
    "driver_user": None,
    "last_response": None,
    "users_cache": [],
    "subscriptions_cache": [],
    "meals_cache": [],
    "drivers_cache": [],
    "deliveries_cache": [],
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def extract_token(payload: Any) -> Optional[str]:
    """Support common FastAPI token response formats."""
    if not isinstance(payload, dict):
        return None

    direct_keys = (
        "access_token",
        "token",
        "accessToken",
        "jwt",
    )

    for key in direct_keys:
        token = payload.get(key)
        if isinstance(token, str) and token:
            return token

    data = payload.get("data")
    if isinstance(data, dict):
        for key in direct_keys:
            token = data.get(key)
            if isinstance(token, str) and token:
                return token

    return None


def extract_user(payload: Any) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    possible = payload.get("user")
    if isinstance(possible, dict):
        return possible

    data = payload.get("data")
    if isinstance(data, dict):
        possible = data.get("user")
        if isinstance(possible, dict):
            return possible

    return None


def extract_items(payload: Any) -> list[dict[str, Any]]:
    """
    Normalize common API list response shapes:
    - [...]
    - {"data": [...]}
    - {"items": [...]}
    - {"results": [...]}
    - {"users": [...]}, {"meals": [...]}, etc.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    keys = (
        "data",
        "items",
        "results",
        "users",
        "subscriptions",
        "meals",
        "drivers",
        "deliveries",
        "meal_selections",
        "selections",
    )

    for key in keys:
        value = payload.get(key)

        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

        if isinstance(value, dict):
            for nested_key in keys:
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return [
                        item for item in nested
                        if isinstance(item, dict)
                    ]

    return []


def safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {
            "text": response.text,
            "content_type": response.headers.get("content-type"),
        }


def api_request(
    method: str,
    path: str,
    *,
    token: Optional[str] = None,
    json_body: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
    timeout: int = 30,
) -> tuple[bool, int, Any]:
    url = f"{BASE_URL}/{path.lstrip('/')}"

    headers = {
        "Accept": "application/json",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json_body,
            params=params,
            timeout=timeout,
        )

        payload = safe_json(response)
        st.session_state.last_response = {
            "method": method.upper(),
            "url": response.url,
            "status_code": response.status_code,
            "request_body": json_body,
            "query_params": params,
            "response": payload,
        }

        return response.ok, response.status_code, payload

    except requests.RequestException as exc:
        payload = {
            "error": type(exc).__name__,
            "detail": str(exc),
            "url": url,
        }

        st.session_state.last_response = {
            "method": method.upper(),
            "url": url,
            "status_code": 0,
            "request_body": json_body,
            "query_params": params,
            "response": payload,
        }

        return False, 0, payload


def show_result(
    ok: bool,
    status_code: int,
    payload: Any,
    success_message: str = "Request completed successfully.",
) -> None:
    if ok:
        st.success(f"{success_message} HTTP {status_code}")
    else:
        st.error(f"Request failed. HTTP {status_code}")

    st.json(payload)


def record_label(
    item: dict[str, Any],
    *,
    primary: tuple[str, ...],
    prefix: str,
) -> str:
    item_id = item.get("id", "?")

    name = None
    for key in primary:
        value = item.get(key)
        if value not in (None, ""):
            name = str(value)
            break

    if name is None:
        name = prefix

    return f"#{item_id} — {name}"


def find_by_id(
    items: list[dict[str, Any]],
    item_id: Any,
) -> Optional[dict[str, Any]]:
    for item in items:
        if str(item.get("id")) == str(item_id):
            return item
    return None


def display_table(items: list[dict[str, Any]], empty_message: str) -> None:
    if not items:
        st.info(empty_message)
        return

    try:
        st.dataframe(
            pd.json_normalize(items),
            use_container_width=True,
            hide_index=True,
        )
    except Exception:
        st.json(items)


def login(
    *,
    email: str,
    password: str,
    token_key: str,
    user_key: str,
) -> None:
    body = {
        LOGIN_EMAIL_FIELD: email,
        LOGIN_PASSWORD_FIELD: password,
    }

    ok, status, payload = api_request(
        "POST",
        LOGIN_ENDPOINT,
        json_body=body,
    )

    if not ok:
        show_result(ok, status, payload)
        return

    token = extract_token(payload)

    if not token:
        st.error(
            "Login succeeded, but no access token was found. "
            "Check the login response and update extract_token()."
        )
        st.json(payload)
        return

    st.session_state[token_key] = token
    st.session_state[user_key] = extract_user(payload)

    st.success("Login successful and token saved.")
    st.json(payload)


def logout(token_key: str, user_key: str) -> None:
    st.session_state[token_key] = None
    st.session_state[user_key] = None
    st.success("Local session token cleared.")


def token_status(label: str, token: Optional[str]) -> None:
    if token:
        st.success(f"{label}: authenticated")
    else:
        st.warning(f"{label}: not authenticated")


def load_resource(
    *,
    endpoint: str,
    token: Optional[str],
    cache_key: str,
    label: str,
    params: Optional[dict[str, Any]] = None,
) -> None:
    if not token:
        st.error(f"Login first before loading {label.lower()}.")
        return

    ok, status, payload = api_request(
        "GET",
        endpoint,
        token=token,
        params=params,
    )

    if ok:
        items = extract_items(payload)
        st.session_state[cache_key] = items
        st.success(f"Loaded {len(items)} {label.lower()}.")
        display_table(items, f"No {label.lower()} found.")
    else:
        show_result(ok, status, payload)


# ---------------------------------------------------------------------------
# Sidebar configuration
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ API Configuration")

BASE_URL = clean_base_url(
    st.sidebar.text_input(
        "FastAPI base URL",
        value="http://127.0.0.1:8000",
        help="Example: http://127.0.0.1:8000 or your server API URL",
    )
)

with st.sidebar.expander("Authentication endpoint", expanded=False):
    LOGIN_ENDPOINT = st.text_input(
        "Login endpoint",
        value="/auth/login",
    )
    LOGIN_EMAIL_FIELD = st.text_input(
        "Email field",
        value="email",
    )
    LOGIN_PASSWORD_FIELD = st.text_input(
        "Password field",
        value="password",
    )

with st.sidebar.expander("Admin resource endpoints", expanded=False):
    USERS_ENDPOINT = st.text_input(
        "Users endpoint",
        value="/users/",
    )
    SUBSCRIPTIONS_ENDPOINT = st.text_input(
        "Subscriptions endpoint",
        value="/subscriptions/",
    )
    MEALS_ENDPOINT = st.text_input(
        "Meals endpoint",
        value="/meals/",
    )
    DRIVERS_ENDPOINT = st.text_input(
        "Drivers endpoint",
        value="/drivers/",
    )
    DELIVERIES_ENDPOINT = st.text_input(
        "Deliveries endpoint",
        value="/deliveries/",
    )

with st.sidebar.expander("Assignment endpoints", expanded=False):
    MEAL_ASSIGN_ENDPOINT_TEMPLATE = st.text_input(
        "Meal assignment endpoint",
        value="/nutrition/subscriptions/{subscription_id}/assign-meal",
        help="Keep {subscription_id} in the path.",
    )
    DRIVER_ASSIGN_ENDPOINT_TEMPLATE = st.text_input(
        "Driver assignment endpoint",
        value="/deliveries/{delivery_id}/assign-driver",
        help=(
            "Default expected body: {'driver_id': ID}. "
            "Change the path to match your backend."
        ),
    )

with st.sidebar.expander("Customer endpoints", expanded=False):
    CUSTOMER_PROFILE_ENDPOINT = st.text_input(
        "Customer profile endpoint",
        value="/users/me",
    )
    CUSTOMER_SUBSCRIPTIONS_ENDPOINT = st.text_input(
        "Customer subscriptions endpoint",
        value="/subscriptions/my",
    )
    CUSTOMER_MEALS_ENDPOINT = st.text_input(
        "Customer assigned meals endpoint",
        value="/meal-selections/my",
    )

st.sidebar.divider()
st.sidebar.caption(f"Current base URL: {BASE_URL}")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🍽️ NutrioMeals Backend Flow Tester")
st.caption(
    "Simulate admin meal/driver assignment and customer meal viewing."
)

admin_status, customer_status, driver_status = st.columns(3)

with admin_status:
    token_status("Admin", st.session_state.admin_token)

with customer_status:
    token_status("Customer", st.session_state.customer_token)

with driver_status:
    token_status("Driver", st.session_state.driver_token)


# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------

admin_tab, customer_tab, driver_tab, raw_tab = st.tabs(
    [
        "👨‍💼 Admin Flow",
        "👤 Customer Flow",
        "🚚 Driver Flow",
        "🧪 Raw API Tester",
    ]
)


# ---------------------------------------------------------------------------
# Admin flow
# ---------------------------------------------------------------------------

with admin_tab:
    st.header("Admin flow")

    login_panel, data_panel, meal_panel, driver_panel = st.tabs(
        [
            "1. Login",
            "2. Load Data",
            "3. Assign Meals",
            "4. Assign Driver",
        ]
    )

    with login_panel:
        st.subheader("Admin login")

        with st.form("admin_login_form"):
            admin_email = st.text_input(
                "Admin email",
                value="admin@example.com",
            )
            admin_password = st.text_input(
                "Admin password",
                type="password",
            )
            admin_login_clicked = st.form_submit_button(
                "Login as admin",
                use_container_width=True,
            )

        if admin_login_clicked:
            login(
                email=admin_email,
                password=admin_password,
                token_key="admin_token",
                user_key="admin_user",
            )

        if st.session_state.admin_token:
            if st.button("Clear admin token"):
                logout("admin_token", "admin_user")

        if st.session_state.admin_user:
            st.subheader("Admin login user")
            st.json(st.session_state.admin_user)

    with data_panel:
        st.subheader("Load data required for assignment")

        if not st.session_state.admin_token:
            st.warning("Login as admin first.")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(
                "Load users",
                use_container_width=True,
                disabled=not st.session_state.admin_token,
            ):
                load_resource(
                    endpoint=USERS_ENDPOINT,
                    token=st.session_state.admin_token,
                    cache_key="users_cache",
                    label="Users",
                )

        with col2:
            if st.button(
                "Load subscriptions",
                use_container_width=True,
                disabled=not st.session_state.admin_token,
            ):
                load_resource(
                    endpoint=SUBSCRIPTIONS_ENDPOINT,
                    token=st.session_state.admin_token,
                    cache_key="subscriptions_cache",
                    label="Subscriptions",
                )

        with col3:
            if st.button(
                "Load meals",
                use_container_width=True,
                disabled=not st.session_state.admin_token,
            ):
                load_resource(
                    endpoint=MEALS_ENDPOINT,
                    token=st.session_state.admin_token,
                    cache_key="meals_cache",
                    label="Meals",
                )

        col4, col5 = st.columns(2)

        with col4:
            if st.button(
                "Load drivers",
                use_container_width=True,
                disabled=not st.session_state.admin_token,
            ):
                load_resource(
                    endpoint=DRIVERS_ENDPOINT,
                    token=st.session_state.admin_token,
                    cache_key="drivers_cache",
                    label="Drivers",
                )

        with col5:
            if st.button(
                "Load deliveries",
                use_container_width=True,
                disabled=not st.session_state.admin_token,
            ):
                load_resource(
                    endpoint=DELIVERIES_ENDPOINT,
                    token=st.session_state.admin_token,
                    cache_key="deliveries_cache",
                    label="Deliveries",
                )

        st.divider()

        resource_view = st.selectbox(
            "Preview cached data",
            [
                "Users",
                "Subscriptions",
                "Meals",
                "Drivers",
                "Deliveries",
            ],
        )

        cache_map = {
            "Users": st.session_state.users_cache,
            "Subscriptions": st.session_state.subscriptions_cache,
            "Meals": st.session_state.meals_cache,
            "Drivers": st.session_state.drivers_cache,
            "Deliveries": st.session_state.deliveries_cache,
        }

        display_table(
            cache_map[resource_view],
            f"No cached {resource_view.lower()}.",
        )

    with meal_panel:
        st.subheader("Assign meals to a customer subscription")

        if not st.session_state.admin_token:
            st.warning("Login as admin first.")

        subscriptions = st.session_state.subscriptions_cache
        meals = st.session_state.meals_cache

        if subscriptions:
            subscription_options = {
                record_label(
                    item,
                    primary=(
                        "plan_name",
                        "user_name",
                        "customer_name",
                        "status",
                    ),
                    prefix="Subscription",
                ): item.get("id")
                for item in subscriptions
            }

            selected_subscription_label = st.selectbox(
                "Subscription",
                options=list(subscription_options.keys()),
            )
            selected_subscription_id = subscription_options[
                selected_subscription_label
            ]

            selected_subscription = find_by_id(
                subscriptions,
                selected_subscription_id,
            )

            if selected_subscription:
                with st.expander("Selected subscription details"):
                    st.json(selected_subscription)
        else:
            selected_subscription_id = st.number_input(
                "Subscription ID",
                min_value=1,
                value=1,
                step=1,
                help=(
                    "Load subscriptions first for a dropdown, "
                    "or enter the subscription ID manually."
                ),
            )

        if meals:
            meal_options = {
                record_label(
                    item,
                    primary=("name_en", "name", "title"),
                    prefix="Meal",
                ): item.get("id")
                for item in meals
                if item.get("id") is not None
            }

            selected_meal_labels = st.multiselect(
                "Meals",
                options=list(meal_options.keys()),
            )

            selected_meal_ids = [
                int(meal_options[label])
                for label in selected_meal_labels
            ]
        else:
            meal_ids_text = st.text_input(
                "Meal IDs",
                value="9,6",
                help="Comma-separated meal IDs.",
            )

            selected_meal_ids = []

            try:
                selected_meal_ids = [
                    int(value.strip())
                    for value in meal_ids_text.split(",")
                    if value.strip()
                ]
            except ValueError:
                st.error("Meal IDs must be numbers separated by commas.")

        meal_col1, meal_col2 = st.columns(2)

        with meal_col1:
            day_number = st.number_input(
                "Day number",
                min_value=1,
                value=1,
                step=1,
            )

        with meal_col2:
            meal_time = st.selectbox(
                "Meal time",
                ["breakfast", "lunch", "dinner", "snack"],
                index=1,
            )

        meal_assignment_body = {
            "subscription_id": int(selected_subscription_id),
            "meal_ids": selected_meal_ids,
            "day_number": int(day_number),
            "meal_time": meal_time,
        }

        st.caption("Request body")
        st.json(meal_assignment_body)

        assign_meals_clicked = st.button(
            "Assign selected meals",
            type="primary",
            use_container_width=True,
            disabled=(
                not st.session_state.admin_token
                or not selected_meal_ids
            ),
        )

        if assign_meals_clicked:
            endpoint = MEAL_ASSIGN_ENDPOINT_TEMPLATE.format(
                subscription_id=int(selected_subscription_id)
            )

            ok, status, payload = api_request(
                "POST",
                endpoint,
                token=st.session_state.admin_token,
                json_body=meal_assignment_body,
            )

            show_result(
                ok,
                status,
                payload,
                success_message="Meal assignment completed.",
            )

    with driver_panel:
        st.subheader("Assign driver to a delivery")

        st.info(
            "This section assumes the driver is assigned to a delivery. "
            "Update the endpoint path or JSON field names in the sidebar "
            "when your backend uses a different design."
        )

        deliveries = st.session_state.deliveries_cache
        drivers = st.session_state.drivers_cache

        if deliveries:
            delivery_options = {
                record_label(
                    item,
                    primary=(
                        "delivery_number",
                        "order_number",
                        "status",
                        "customer_name",
                    ),
                    prefix="Delivery",
                ): item.get("id")
                for item in deliveries
                if item.get("id") is not None
            }

            selected_delivery_label = st.selectbox(
                "Delivery",
                options=list(delivery_options.keys()),
            )
            selected_delivery_id = delivery_options[
                selected_delivery_label
            ]

            selected_delivery = find_by_id(
                deliveries,
                selected_delivery_id,
            )

            if selected_delivery:
                with st.expander("Selected delivery details"):
                    st.json(selected_delivery)
        else:
            selected_delivery_id = st.number_input(
                "Delivery ID",
                min_value=1,
                value=1,
                step=1,
            )

        if drivers:
            driver_options = {
                record_label(
                    item,
                    primary=(
                        "full_name",
                        "name",
                        "first_name",
                        "email",
                    ),
                    prefix="Driver",
                ): item.get("id")
                for item in drivers
                if item.get("id") is not None
            }

            selected_driver_label = st.selectbox(
                "Driver",
                options=list(driver_options.keys()),
            )
            selected_driver_id = driver_options[
                selected_driver_label
            ]

            selected_driver = find_by_id(
                drivers,
                selected_driver_id,
            )

            if selected_driver:
                with st.expander("Selected driver details"):
                    st.json(selected_driver)
        else:
            selected_driver_id = st.number_input(
                "Driver ID",
                min_value=1,
                value=1,
                step=1,
            )

        assignment_mode = st.radio(
            "Driver assignment request body",
            [
                "driver_id only",
                "driver_id with delivery_id",
                "Custom JSON",
            ],
            horizontal=True,
        )

        if assignment_mode == "driver_id only":
            driver_body = {
                "driver_id": int(selected_driver_id),
            }
        elif assignment_mode == "driver_id with delivery_id":
            driver_body = {
                "delivery_id": int(selected_delivery_id),
                "driver_id": int(selected_driver_id),
            }
        else:
            custom_driver_json = st.text_area(
                "Custom JSON body",
                value=json.dumps(
                    {
                        "delivery_id": int(selected_delivery_id),
                        "driver_id": int(selected_driver_id),
                    },
                    indent=2,
                ),
                height=160,
            )

            try:
                driver_body = json.loads(custom_driver_json)
            except json.JSONDecodeError as exc:
                driver_body = {}
                st.error(f"Invalid JSON: {exc}")

        st.caption("Request body")
        st.json(driver_body)

        assign_driver_clicked = st.button(
            "Assign driver",
            type="primary",
            use_container_width=True,
            disabled=(
                not st.session_state.admin_token
                or not driver_body
            ),
        )

        if assign_driver_clicked:
            endpoint = DRIVER_ASSIGN_ENDPOINT_TEMPLATE.format(
                delivery_id=int(selected_delivery_id),
                driver_id=int(selected_driver_id),
            )

            ok, status, payload = api_request(
                "PATCH",
                endpoint,
                token=st.session_state.admin_token,
                json_body=driver_body,
            )

            show_result(
                ok,
                status,
                payload,
                success_message="Driver assignment completed.",
            )


# ---------------------------------------------------------------------------
# Customer flow
# ---------------------------------------------------------------------------

with customer_tab:
    st.header("Customer flow")

    customer_login_tab, customer_profile_tab, customer_meals_tab = st.tabs(
        [
            "1. Login",
            "2. Profile & Subscription",
            "3. View Assigned Meals",
        ]
    )

    with customer_login_tab:
        st.subheader("Customer login")

        with st.form("customer_login_form"):
            customer_email = st.text_input(
                "Customer email",
                value="customer@example.com",
            )
            customer_password = st.text_input(
                "Customer password",
                type="password",
            )
            customer_login_clicked = st.form_submit_button(
                "Login as customer",
                use_container_width=True,
            )

        if customer_login_clicked:
            login(
                email=customer_email,
                password=customer_password,
                token_key="customer_token",
                user_key="customer_user",
            )

        if st.session_state.customer_token:
            if st.button("Clear customer token"):
                logout("customer_token", "customer_user")

        if st.session_state.customer_user:
            st.subheader("Customer login user")
            st.json(st.session_state.customer_user)

    with customer_profile_tab:
        st.subheader("Customer profile and subscription")

        if not st.session_state.customer_token:
            st.warning("Login as customer first.")

        profile_col, subscription_col = st.columns(2)

        with profile_col:
            if st.button(
                "Load my profile",
                use_container_width=True,
                disabled=not st.session_state.customer_token,
            ):
                ok, status, payload = api_request(
                    "GET",
                    CUSTOMER_PROFILE_ENDPOINT,
                    token=st.session_state.customer_token,
                )
                show_result(
                    ok,
                    status,
                    payload,
                    success_message="Customer profile loaded.",
                )

        with subscription_col:
            if st.button(
                "Load my subscription",
                use_container_width=True,
                disabled=not st.session_state.customer_token,
            ):
                ok, status, payload = api_request(
                    "GET",
                    CUSTOMER_SUBSCRIPTIONS_ENDPOINT,
                    token=st.session_state.customer_token,
                )
                show_result(
                    ok,
                    status,
                    payload,
                    success_message="Customer subscription loaded.",
                )

    with customer_meals_tab:
        st.subheader("Meals assigned by admin/nutrition manager")

        if not st.session_state.customer_token:
            st.warning("Login as customer first.")

        filter_subscription = st.checkbox(
            "Filter by subscription ID",
            value=True,
        )

        customer_subscription_id = st.number_input(
            "Subscription ID",
            min_value=1,
            value=1,
            step=1,
            disabled=not filter_subscription,
        )

        load_customer_meals = st.button(
            "Load my assigned meals",
            type="primary",
            use_container_width=True,
            disabled=not st.session_state.customer_token,
        )

        if load_customer_meals:
            params = None

            if filter_subscription:
                params = {
                    "subscription_id": int(customer_subscription_id)
                }

            ok, status, payload = api_request(
                "GET",
                CUSTOMER_MEALS_ENDPOINT,
                token=st.session_state.customer_token,
                params=params,
            )

            if not ok:
                show_result(ok, status, payload)
            else:
                selections = extract_items(payload)

                st.success(
                    f"Loaded {len(selections)} assigned meal record(s)."
                )

                if not selections:
                    st.info(
                        "No assigned meals were returned for this customer."
                    )
                    st.json(payload)
                else:
                    normalized_rows: list[dict[str, Any]] = []

                    for selection in selections:
                        meal = selection.get("meal") or {}

                        normalized_rows.append(
                            {
                                "selection_id": selection.get("id"),
                                "subscription_id": selection.get(
                                    "subscription_id"
                                ),
                                "day_number": selection.get("day_number"),
                                "meal_time": selection.get("meal_time"),
                                "meal_id": selection.get("meal_id"),
                                "meal_name": (
                                    meal.get("name_en")
                                    or meal.get("name")
                                    or f"Meal #{selection.get('meal_id')}"
                                ),
                                "calories": meal.get("calories"),
                                "protein_g": meal.get("protein_g"),
                                "carbs_g": meal.get("carbs_g"),
                                "fat_g": meal.get("fat_g"),
                                "is_skipped": selection.get("is_skipped"),
                                "skip_reason": selection.get("skip_reason"),
                            }
                        )

                    dataframe = pd.DataFrame(normalized_rows)

                    st.dataframe(
                        dataframe,
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.subheader("Grouped meal schedule")

                    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = {}

                    for row in normalized_rows:
                        key = (
                            row.get("day_number"),
                            row.get("meal_time"),
                        )
                        groups.setdefault(key, []).append(row)

                    for (
                        day_value,
                        meal_time_value,
                    ), group_rows in sorted(
                        groups.items(),
                        key=lambda value: (
                            value[0][0] or 0,
                            str(value[0][1] or ""),
                        ),
                    ):
                        st.markdown(
                            f"### Day {day_value} — "
                            f"{str(meal_time_value).title()}"
                        )

                        cards = st.columns(
                            min(3, max(1, len(group_rows)))
                        )

                        for index, row in enumerate(group_rows):
                            with cards[index % len(cards)]:
                                st.markdown(
                                    f"**{row['meal_name']}**"
                                )
                                st.write(
                                    f"Calories: "
                                    f"{row.get('calories') or 0} kcal"
                                )
                                st.write(
                                    f"Protein: "
                                    f"{row.get('protein_g') or 0} g"
                                )
                                st.write(
                                    f"Carbs: "
                                    f"{row.get('carbs_g') or 0} g"
                                )
                                st.write(
                                    f"Fat: "
                                    f"{row.get('fat_g') or 0} g"
                                )

                                if row.get("is_skipped"):
                                    st.warning(
                                        "Skipped"
                                        + (
                                            f": {row.get('skip_reason')}"
                                            if row.get("skip_reason")
                                            else ""
                                        )
                                    )
                                else:
                                    st.success("Assigned")

                    with st.expander("Raw customer meal response"):
                        st.json(payload)


# ---------------------------------------------------------------------------
# Driver flow
# ---------------------------------------------------------------------------

with driver_tab:
    st.header("Driver flow")

    driver_login_tab, driver_deliveries_tab = st.tabs(
        [
            "1. Login",
            "2. View Assigned Deliveries",
        ]
    )

    with driver_login_tab:
        st.subheader("Driver login")

        with st.form("driver_login_form"):
            driver_email = st.text_input(
                "Driver email",
                value="driver@example.com",
            )
            driver_password = st.text_input(
                "Driver password",
                type="password",
            )
            driver_login_clicked = st.form_submit_button(
                "Login as driver",
                use_container_width=True,
            )

        if driver_login_clicked:
            login(
                email=driver_email,
                password=driver_password,
                token_key="driver_token",
                user_key="driver_user",
            )

        if st.session_state.driver_token:
            if st.button("Clear driver token"):
                logout("driver_token", "driver_user")

        if st.session_state.driver_user:
            st.subheader("Driver login user")
            st.json(st.session_state.driver_user)

    with driver_deliveries_tab:
        st.subheader("Driver's assigned deliveries")

        driver_my_deliveries_endpoint = st.text_input(
            "Driver deliveries endpoint",
            value="/deliveries/my",
            help=(
                "Change this endpoint when your backend uses another path, "
                "such as /drivers/me/deliveries."
            ),
        )

        if st.button(
            "Load my deliveries",
            type="primary",
            use_container_width=True,
            disabled=not st.session_state.driver_token,
        ):
            ok, status, payload = api_request(
                "GET",
                driver_my_deliveries_endpoint,
                token=st.session_state.driver_token,
            )

            if ok:
                deliveries = extract_items(payload)
                st.success(
                    f"Loaded {len(deliveries)} driver delivery record(s)."
                )
                display_table(
                    deliveries,
                    "No deliveries are assigned to this driver.",
                )

                with st.expander("Raw response"):
                    st.json(payload)
            else:
                show_result(ok, status, payload)


# ---------------------------------------------------------------------------
# Raw API tester
# ---------------------------------------------------------------------------

with raw_tab:
    st.header("Raw API tester")

    st.caption(
        "Use this when an endpoint path or request format differs from "
        "the defaults in this tester."
    )

    raw_col1, raw_col2 = st.columns([1, 3])

    with raw_col1:
        raw_method = st.selectbox(
            "Method",
            ["GET", "POST", "PUT", "PATCH", "DELETE"],
        )

    with raw_col2:
        raw_path = st.text_input(
            "Endpoint path",
            value="/health",
        )

    raw_token_source = st.selectbox(
        "Authorization token",
        [
            "None",
            "Admin token",
            "Customer token",
            "Driver token",
            "Custom token",
        ],
    )

    custom_token = ""

    if raw_token_source == "Custom token":
        custom_token = st.text_area(
            "Custom bearer token",
            height=100,
        )

    token_map = {
        "None": None,
        "Admin token": st.session_state.admin_token,
        "Customer token": st.session_state.customer_token,
        "Driver token": st.session_state.driver_token,
        "Custom token": custom_token.strip() or None,
    }

    raw_query_text = st.text_area(
        "Query parameters JSON",
        value="{}",
        height=100,
    )

    raw_body_text = st.text_area(
        "JSON request body",
        value="{}",
        height=180,
        disabled=raw_method == "GET",
    )

    send_raw = st.button(
        "Send request",
        type="primary",
        use_container_width=True,
    )

    if send_raw:
        try:
            raw_params = json.loads(raw_query_text or "{}")

            raw_body = None

            if raw_method != "GET":
                raw_body = json.loads(raw_body_text or "{}")

            ok, status, payload = api_request(
                raw_method,
                raw_path,
                token=token_map[raw_token_source],
                json_body=raw_body,
                params=raw_params,
            )

            show_result(
                ok,
                status,
                payload,
                success_message="Raw API request completed.",
            )

        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")


# ---------------------------------------------------------------------------
# Last request debugger
# ---------------------------------------------------------------------------

st.divider()

with st.expander("🔎 Last API request and response"):
    if st.session_state.last_response:
        st.json(st.session_state.last_response)
    else:
        st.info("No API request has been sent yet.")