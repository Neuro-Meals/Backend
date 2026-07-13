import requests
import streamlit as st

API_BASE = "https://app.nutriomeals.com"

st.set_page_config(page_title="NeuroMeals API Tester", layout="wide")

st.title("NeuroMeals Backend API Tester")

if "token" not in st.session_state:
    st.session_state.token = None

if "user" not in st.session_state:
    st.session_state.user = None

if "tap_subscription_id" not in st.session_state:
    st.session_state.tap_subscription_id = 1

if "tap_payment_id" not in st.session_state:
    st.session_state.tap_payment_id = None

if "tap_charge_id" not in st.session_state:
    st.session_state.tap_charge_id = ""

if "tap_checkout_url" not in st.session_state:
    st.session_state.tap_checkout_url = ""


def headers():
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def show_response(res):
    st.write(f"**HTTP {res.status_code}**")
    try:
        st.json(res.json())
    except Exception:
        st.write(res.text)


def api_request(method, path, *, json=None, params=None, timeout=30):
    """Send an authenticated request to the configured backend."""
    url = f"{API_BASE}{path}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers(),
            json=json,
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        st.error(f"Request failed: {exc}")
        return None

    show_response(response)
    return response


menu = st.sidebar.selectbox(
    "Choose Module",
    [
        "Auth",
        "Profile",
        "Users",
        "RBAC",
        "Meal Categories",
        "Meals",
        "Plans",
        "Subscriptions",
        "Orders",
        "Deliveries",
        "Drivers",
        "Locations",
        "Payments",
        "Reports",
        "Custom Endpoint",
    ],
)

st.sidebar.write("### Login Status")
if st.session_state.user:
    st.sidebar.success(f"Logged in as {st.session_state.user.get('email')}")
    st.sidebar.write("Role:", st.session_state.user.get("role"))
else:
    st.sidebar.warning("Not logged in")


# ================= AUTH =================

if menu == "Auth":
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "Register",
            "Verify Email",
            "Resend OTP",
            "Login",
            "Me",
            "Forgot Password",
            "Reset Password",
        ]
    )

    with tab1:
        st.subheader("Register")

        first_name = st.text_input("First Name", "Adam")
        last_name = st.text_input("Last Name", "Katani")
        email = st.text_input("Email", "adam@example.com")
        phone = st.text_input("Phone", "+255700000000")
        password = st.text_input("Password", "123456", type="password")
        location = st.text_input("Location", "Dar es Salaam")
        address = st.text_input("Address", "Mbezi Beach")

        gender = st.selectbox("Gender", ["male", "female", "other"])
        age = st.number_input("Age", min_value=1, value=25)
        height_cm = st.number_input("Height CM", min_value=1.0, value=175.0)
        weight_kg = st.number_input("Weight KG", min_value=1.0, value=70.0)

        fitness_goal = st.selectbox(
            "Fitness Goal",
            ["weight_loss", "muscle_gain", "maintenance", "healthy_lifestyle"],
        )

        dietary_preference = st.text_input("Dietary Preference", "high protein")
        allergies_text = st.text_input("Allergies comma separated", "nuts,dairy")

        if st.button("Register"):
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "password": password,
                "location": location,
                "address": address,
                "gender": gender,
                "age": age,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "fitness_goal": fitness_goal,
                "dietary_preference": dietary_preference,
                "allergies": [x.strip() for x in allergies_text.split(",") if x.strip()],
            }

            res = requests.post(f"{API_BASE}/auth/register", json=payload)
            show_response(res)

    with tab2:
        st.subheader("Verify Email")

        email = st.text_input("Verify Email Address")
        otp = st.text_input("OTP")

        if st.button("Verify"):
            res = requests.post(
                f"{API_BASE}/auth/verify-email",
                json={"email": email, "otp": otp},
            )
            show_response(res)

    with tab3:
        st.subheader("Resend Verification OTP")

        email = st.text_input("Resend OTP Email")

        if st.button("Resend OTP"):
            res = requests.post(
                f"{API_BASE}/auth/resend-verification-otp",
                json={"email": email},
            )
            show_response(res)

    with tab4:
        st.subheader("Login")

        email = st.text_input("Login Email")
        password = st.text_input("Login Password", type="password")

        if st.button("Login"):
            res = requests.post(
                f"{API_BASE}/auth/login",
                json={"email": email, "password": password},
            )

            if res.status_code == 200:
                data = res.json()
                st.session_state.token = data["access_token"]
                st.session_state.user = data["user"]
                st.success("Login successful")

            show_response(res)

    with tab5:
        st.subheader("Auth Me")

        if st.button("Get /auth/me"):
            try:
                res = requests.get(
                    f"{API_BASE}/auth/me",
                    headers=headers(),
                    timeout=30,
                )
            except requests.RequestException as exc:
                st.error(f"Request failed: {exc}")
            else:
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.user = data

                    st.success("Authenticated")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("### User")
                        st.write(
                            f"**Name:** {data.get('first_name', '')} "
                            f"{data.get('last_name', '')}"
                        )
                        st.write(f"**Email:** {data.get('email')}")
                        st.write(f"**Role:** {data.get('role')}")

                    with col2:
                        st.write("### Permissions")
                        permissions = data.get("permissions", [])

                        if permissions:
                            for permission in permissions:
                                st.success(permission)
                        else:
                            st.warning("No permissions assigned")

                    st.divider()
                    st.json(data)
                else:
                    show_response(res)

    with tab6:
        st.subheader("Forgot Password")

        email = st.text_input("Forgot Password Email")

        if st.button("Send Password Reset OTP"):
            res = requests.post(
                f"{API_BASE}/auth/forgot-password",
                json={"email": email},
            )
            show_response(res)

    with tab7:
        st.subheader("Reset Password")

        email = st.text_input("Reset Email")
        otp = st.text_input("Reset OTP")
        new_password = st.text_input("New Password", type="password")

        if st.button("Reset Password"):
            res = requests.post(
                f"{API_BASE}/auth/reset-password",
                json={
                    "email": email,
                    "otp": otp,
                    "new_password": new_password,
                },
            )
            show_response(res)


# ================= PROFILE =================

elif menu == "Profile":
    st.subheader("Profile")

    if st.button("Get Profile"):
        res = requests.get(f"{API_BASE}/profile/", headers=headers())
        show_response(res)

    st.divider()

    st.subheader("Update Profile")

    location = st.text_input("Location", "Riyadh")
    address = st.text_input("Address", "King Fahd Road")
    weight_kg = st.number_input("Weight KG", value=72.0)
    height_cm = st.number_input("Height CM", value=175.0)
    fitness_goal = st.selectbox(
        "Fitness Goal",
        ["weight_loss", "muscle_gain", "maintenance", "healthy_lifestyle"],
    )
    allergies_text = st.text_input("Allergies", "nuts,dairy,eggs")

    if st.button("Update Profile"):
        payload = {
            "location": location,
            "address": address,
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "fitness_goal": fitness_goal,
            "allergies": [x.strip() for x in allergies_text.split(",") if x.strip()],
        }

        res = requests.put(f"{API_BASE}/profile/", json=payload, headers=headers())
        show_response(res)


# ================= USERS =================

elif menu == "Users":
    st.subheader("Users")

    search = st.text_input("Search")
    role = st.selectbox(
        "Role Filter",
        ["", "customer", "admin", "super_admin", "nutrition_manager", "delivery_manager", "driver", "finance_manager"],
    )
    page = st.number_input("Page", min_value=1, value=1)
    limit = st.number_input("Limit", min_value=1, max_value=100, value=10)

    if st.button("List Users"):
        params = {"page": page, "limit": limit}

        if search:
            params["search"] = search

        if role:
            params["role"] = role

        res = requests.get(f"{API_BASE}/users/", params=params, headers=headers())
        show_response(res)

    st.divider()

    st.subheader("Update User Primary Role")

    user_id = st.number_input("User ID", min_value=1)
    new_role = st.selectbox(
        "New Role",
        ["customer", "admin", "super_admin", "nutrition_manager", "delivery_manager", "driver", "finance_manager"],
    )

    if st.button("Update Role"):
        res = requests.patch(
            f"{API_BASE}/users/{user_id}/role",
            json={"role": new_role},
            headers=headers(),
        )
        show_response(res)


# ================= RBAC =================

elif menu == "RBAC":
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Create Role",
            "List Roles",
            "Create Permission",
            "List Permissions",
            "Assign Role",
            "Assign Permission",
        ]
    )

    with tab1:
        name = st.text_input("Role Name", "admin")
        description = st.text_input("Description", "Admin role")

        if st.button("Create Role"):
            res = requests.post(
                f"{API_BASE}/rbac/roles",
                json={"name": name, "description": description},
                headers=headers(),
            )
            show_response(res)

    with tab2:
        if st.button("List Roles"):
            res = requests.get(f"{API_BASE}/rbac/roles", headers=headers())
            show_response(res)

    with tab3:
        code = st.text_input("Permission Code", "meals.create")
        description = st.text_input("Permission Description", "Create meals")

        if st.button("Create Permission"):
            res = requests.post(
                f"{API_BASE}/rbac/permissions",
                json={"code": code, "description": description},
                headers=headers(),
            )
            show_response(res)

    with tab4:
        if st.button("List Permissions"):
            res = requests.get(f"{API_BASE}/rbac/permissions", headers=headers())
            show_response(res)

    with tab5:
        user_id = st.number_input("User ID for Role", min_value=1)
        role_id = st.number_input("Role ID", min_value=1)

        if st.button("Assign Role to User"):
            res = requests.post(
                f"{API_BASE}/rbac/assign-role",
                json={"user_id": user_id, "role_id": role_id},
                headers=headers(),
            )
            show_response(res)

    with tab6:
        role_id = st.number_input("Role ID for Permission", min_value=1)
        permission_id = st.number_input("Permission ID", min_value=1)

        if st.button("Assign Permission to Role"):
            res = requests.post(
                f"{API_BASE}/rbac/assign-permission",
                json={"role_id": role_id, "permission_id": permission_id},
                headers=headers(),
            )
            show_response(res)


# ================= MEAL CATEGORIES =================

elif menu == "Meal Categories":
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Create", "List", "Get One", "Update", "Delete"]
    )

    with tab1:
        name_en = st.text_input("Name EN", "Breakfast")
        name_ar = st.text_input("Name AR", "فطور")
        description = st.text_input("Description", "Healthy breakfast meals")
        image_url = st.text_input("Image URL")

        if st.button("Create Category"):
            res = requests.post(
                f"{API_BASE}/meal-categories/",
                json={
                    "name_en": name_en,
                    "name_ar": name_ar,
                    "description": description,
                    "image_url": image_url,
                },
                headers=headers(),
            )
            show_response(res)

    with tab2:
        search = st.text_input("Search Categories")
        page = st.number_input("Category Page", min_value=1, value=1)
        limit = st.number_input("Category Limit", min_value=1, max_value=100, value=10)

        if st.button("List Categories"):
            params = {"page": page, "limit": limit}
            if search:
                params["search"] = search

            res = requests.get(f"{API_BASE}/meal-categories/", params=params)
            show_response(res)

    with tab3:
        category_id = st.number_input("Category ID", min_value=1)

        if st.button("Get Category"):
            res = requests.get(f"{API_BASE}/meal-categories/{category_id}")
            show_response(res)

    with tab4:
        category_id = st.number_input("Update Category ID", min_value=1)
        name_en = st.text_input("Update Name EN", "Lunch")
        is_active = st.checkbox("Is Active", value=True)

        if st.button("Update Category"):
            res = requests.put(
                f"{API_BASE}/meal-categories/{category_id}",
                json={"name_en": name_en, "is_active": is_active},
                headers=headers(),
            )
            show_response(res)

    with tab5:
        category_id = st.number_input("Delete Category ID", min_value=1)

        if st.button("Delete Category"):
            res = requests.delete(
                f"{API_BASE}/meal-categories/{category_id}",
                headers=headers(),
            )
            show_response(res)


# ================= MEALS =================

elif menu == "Meals":
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Create", "List", "Get One", "Update", "Delete"]
    )

    with tab1:
        category_id = st.number_input("Category ID", min_value=1)
        name_en = st.text_input("Meal Name EN", "Grilled Chicken Bowl")
        name_ar = st.text_input("Meal Name AR", "وعاء الدجاج المشوي")
        description_en = st.text_area("Description EN", "Chicken with rice and broccoli")
        description_ar = st.text_area("Description AR", "")

        calories = st.number_input("Calories", min_value=0.0, value=520.0)
        protein_g = st.number_input("Protein G", min_value=0.0, value=45.0)
        carbs_g = st.number_input("Carbs G", min_value=0.0, value=40.0)
        fat_g = st.number_input("Fat G", min_value=0.0, value=15.0)

        fiber_g = st.number_input("Fiber G", min_value=0.0, value=5.0)
        sugar_g = st.number_input("Sugar G", min_value=0.0, value=3.0)
        sodium_mg = st.number_input("Sodium MG", min_value=0.0, value=300.0)

        price = st.number_input("Price", min_value=0.0, value=35.0)
        image_url = st.text_input("Meal Image URL")

        ingredients_text = st.text_input("Ingredients comma separated", "chicken,rice,broccoli")
        allergens_text = st.text_input("Allergens comma separated", "dairy")
        diet_tags_text = st.text_input("Diet Tags comma separated", "high_protein,muscle_gain")

        is_available = st.checkbox("Available", value=True)

        if st.button("Create Meal"):
            payload = {
                "category_id": category_id,
                "name_en": name_en,
                "name_ar": name_ar,
                "description_en": description_en,
                "description_ar": description_ar,
                "calories": calories,
                "protein_g": protein_g,
                "carbs_g": carbs_g,
                "fat_g": fat_g,
                "fiber_g": fiber_g,
                "sugar_g": sugar_g,
                "sodium_mg": sodium_mg,
                "price": price,
                "image_url": image_url,
                "ingredients": [x.strip() for x in ingredients_text.split(",") if x.strip()],
                "allergens": [x.strip() for x in allergens_text.split(",") if x.strip()],
                "diet_tags": [x.strip() for x in diet_tags_text.split(",") if x.strip()],
                "is_available": is_available,
            }

            res = requests.post(f"{API_BASE}/meals/", json=payload, headers=headers())
            show_response(res)

    with tab2:
        search = st.text_input("Search Meals")
        category_filter = st.number_input("Filter Category ID", min_value=0, value=0)
        is_available = st.selectbox("Available Filter", ["", "true", "false"])
        page = st.number_input("Meal Page", min_value=1, value=1)
        limit = st.number_input("Meal Limit", min_value=1, max_value=100, value=10)

        if st.button("List Meals"):
            params = {"page": page, "limit": limit}

            if search:
                params["search"] = search
            if category_filter > 0:
                params["category_id"] = category_filter
            if is_available:
                params["is_available"] = is_available

            res = requests.get(f"{API_BASE}/meals/", params=params)
            show_response(res)

    with tab3:
        meal_id = st.number_input("Meal ID", min_value=1)

        if st.button("Get Meal"):
            res = requests.get(f"{API_BASE}/meals/{meal_id}")
            show_response(res)

    with tab4:
        meal_id = st.number_input("Update Meal ID", min_value=1)
        name_en = st.text_input("New Meal Name", "Updated Meal")
        price = st.number_input("New Price", min_value=0.0, value=40.0)
        is_available = st.checkbox("Meal Available", value=True)

        if st.button("Update Meal"):
            res = requests.put(
                f"{API_BASE}/meals/{meal_id}",
                json={
                    "name_en": name_en,
                    "price": price,
                    "is_available": is_available,
                },
                headers=headers(),
            )
            show_response(res)

    with tab5:
        meal_id = st.number_input("Delete Meal ID", min_value=1)

        if st.button("Delete Meal"):
            res = requests.delete(
                f"{API_BASE}/meals/{meal_id}",
                headers=headers(),
            )
            show_response(res)


# ================= PLANS =================

elif menu == "Plans":
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Create", "List", "Get One", "Update", "Delete"]
    )

    with tab1:
        name_en = st.text_input("Plan Name EN", "Muscle Gain Monthly Plan")
        name_ar = st.text_input("Plan Name AR", "خطة زيادة العضلات الشهرية")
        description_en = st.text_area("Plan Description EN", "Monthly high protein plan")
        description_ar = st.text_area("Plan Description AR", "")

        plan_type = st.selectbox("Plan Type", ["weekly", "monthly", "custom", "family", "corporate"])
        goal = st.selectbox("Goal", ["weight_loss", "muscle_gain", "maintenance", "healthy_lifestyle"])

        price = st.number_input("Plan Price", min_value=0.0, value=1200.0)
        duration_days = st.number_input("Duration Days", min_value=1, value=30)
        meals_per_day = st.number_input("Meals Per Day", min_value=1, value=3)
        total_meals = st.number_input("Total Meals", min_value=1, value=90)
        image_url = st.text_input("Plan Image URL")
        is_active = st.checkbox("Plan Active", value=True)

        if st.button("Create Plan"):
            payload = {
                "name_en": name_en,
                "name_ar": name_ar,
                "description_en": description_en,
                "description_ar": description_ar,
                "plan_type": plan_type,
                "goal": goal,
                "price": price,
                "duration_days": duration_days,
                "meals_per_day": meals_per_day,
                "total_meals": total_meals,
                "image_url": image_url,
                "is_active": is_active,
            }

            res = requests.post(f"{API_BASE}/plans/", json=payload, headers=headers())
            show_response(res)

    with tab2:
        search = st.text_input("Search Plans")
        plan_type = st.selectbox("Filter Plan Type", ["", "weekly", "monthly", "custom", "family", "corporate"])
        is_active = st.selectbox("Filter Active", ["", "true", "false"])

        if st.button("List Plans"):
            params = {}

            if search:
                params["search"] = search
            if plan_type:
                params["plan_type"] = plan_type
            if is_active:
                params["is_active"] = is_active

            res = requests.get(f"{API_BASE}/plans/", params=params)
            show_response(res)

    with tab3:
        plan_id = st.number_input("Plan ID", min_value=1)

        if st.button("Get Plan"):
            res = requests.get(f"{API_BASE}/plans/{plan_id}")
            show_response(res)

    with tab4:
        plan_id = st.number_input("Update Plan ID", min_value=1)
        name_en = st.text_input("Updated Plan Name", "Updated Plan")
        price = st.number_input("Updated Plan Price", min_value=0.0, value=1000.0)
        is_active = st.checkbox("Updated Active", value=True)

        if st.button("Update Plan"):
            res = requests.put(
                f"{API_BASE}/plans/{plan_id}",
                json={
                    "name_en": name_en,
                    "price": price,
                    "is_active": is_active,
                },
                headers=headers(),
            )
            show_response(res)

    with tab5:
        plan_id = st.number_input("Delete Plan ID", min_value=1)

        if st.button("Delete Plan"):
            res = requests.delete(
                f"{API_BASE}/plans/{plan_id}",
                headers=headers(),
            )
            show_response(res)


# ================= SUBSCRIPTIONS =================

elif menu == "Subscriptions":
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Create", "My Subscriptions", "List Admin", "Update Admin", "Cancel"]
    )

    with tab1:
        plan_id = st.number_input("Plan ID", min_value=1)
        notes = st.text_area("Notes", "")

        if st.button("Create Subscription"):
            res = requests.post(
                f"{API_BASE}/subscriptions/",
                json={"plan_id": plan_id, "notes": notes},
                headers=headers(),
            )
            show_response(res)

    with tab2:
        if st.button("Get My Subscriptions"):
            res = requests.get(f"{API_BASE}/subscriptions/my", headers=headers())
            show_response(res)

    with tab3:
        status_filter = st.selectbox(
            "Status",
            ["", "pending_payment", "active", "paused", "cancelled", "expired"],
        )
        payment_filter = st.selectbox(
            "Payment Status",
            ["", "unpaid", "pending", "paid", "failed", "refunded"],
        )

        if st.button("List All Subscriptions"):
            params = {}

            if status_filter:
                params["status"] = status_filter
            if payment_filter:
                params["payment_status"] = payment_filter

            res = requests.get(
                f"{API_BASE}/subscriptions/",
                params=params,
                headers=headers(),
            )
            show_response(res)

    with tab4:
        subscription_id = st.number_input("Subscription ID", min_value=1)
        status = st.selectbox(
            "New Subscription Status",
            ["pending_payment", "active", "paused", "cancelled", "expired"],
        )
        payment_status = st.selectbox(
            "New Payment Status",
            ["unpaid", "pending", "paid", "failed", "refunded"],
        )
        notes = st.text_area("Admin Notes")

        if st.button("Admin Update Subscription"):
            res = requests.patch(
                f"{API_BASE}/subscriptions/{subscription_id}",
                json={
                    "status": status,
                    "payment_status": payment_status,
                    "notes": notes,
                },
                headers=headers(),
            )
            show_response(res)

    with tab5:
        subscription_id = st.number_input("Cancel Subscription ID", min_value=1)

        if st.button("Cancel Subscription"):
            res = requests.post(
                f"{API_BASE}/subscriptions/{subscription_id}/cancel",
                headers=headers(),
            )
            show_response(res)
            
            
            
# ================= ORDERS =================

elif menu == "Orders":
    st.header("Orders API Tester")

    create_tab, my_tab, admin_tab, one_tab, status_tab, cancel_tab = st.tabs(
        [
            "Create from Subscription",
            "My Orders",
            "Admin Orders",
            "Get One",
            "Update Status",
            "Cancel",
        ]
    )

    with create_tab:
        subscription_id = st.number_input(
            "Subscription ID",
            min_value=1,
            value=1,
            key="order_create_subscription_id",
        )
        delivery_address = st.text_input(
            "Delivery Address",
            key="order_create_address",
        )
        delivery_notes = st.text_area(
            "Delivery Notes",
            key="order_create_notes",
        )

        if st.button("Create Order", key="order_create_btn"):
            payload = {
                "subscription_id": int(subscription_id),
                "delivery_address": delivery_address or None,
                "delivery_notes": delivery_notes or None,
            }
            api_request(
                "POST",
                "/orders/from-subscription",
                json=payload,
            )

    with my_tab:
        if st.button("Get My Orders", key="orders_my_btn"):
            response = api_request("GET", "/orders/my")

            if response is not None and response.status_code == 200:
                orders = response.json()
                if isinstance(orders, list) and orders:
                    st.dataframe(
                        [
                            {
                                "id": item.get("id"),
                                "order_number": item.get("order_number"),
                                "status": item.get("status"),
                                "amount": item.get("total_amount"),
                                "delivery_date": item.get("delivery_date"),
                                "address": item.get("delivery_address"),
                            }
                            for item in orders
                        ],
                        use_container_width=True,
                    )

    with admin_tab:
        search = st.text_input("Search", key="orders_admin_search")
        status_filter = st.selectbox(
            "Status",
            [
                "",
                "pending",
                "confirmed",
                "preparing",
                "ready_for_delivery",
                "out_for_delivery",
                "delivered",
                "cancelled",
            ],
            key="orders_admin_status",
        )
        user_id = st.number_input(
            "User ID (0 = all)",
            min_value=0,
            value=0,
            key="orders_admin_user",
        )
        subscription_filter = st.number_input(
            "Subscription ID (0 = all)",
            min_value=0,
            value=0,
            key="orders_admin_subscription",
        )
        page = st.number_input(
            "Page",
            min_value=1,
            value=1,
            key="orders_admin_page",
        )
        limit = st.number_input(
            "Limit",
            min_value=1,
            max_value=100,
            value=10,
            key="orders_admin_limit",
        )

        if st.button("List All Orders", key="orders_admin_btn"):
            params = {"page": int(page), "limit": int(limit)}
            if search:
                params["search"] = search
            if status_filter:
                params["status"] = status_filter
            if user_id:
                params["user_id"] = int(user_id)
            if subscription_filter:
                params["subscription_id"] = int(subscription_filter)

            api_request("GET", "/orders/", params=params)

    with one_tab:
        order_id = st.number_input(
            "Order ID",
            min_value=1,
            value=1,
            key="orders_get_id",
        )
        if st.button("Get Order", key="orders_get_btn"):
            api_request("GET", f"/orders/{int(order_id)}")

    with status_tab:
        order_id = st.number_input(
            "Order ID",
            min_value=1,
            value=1,
            key="orders_status_id",
        )
        new_status = st.selectbox(
            "New Status",
            [
                "pending",
                "confirmed",
                "preparing",
                "ready_for_delivery",
                "out_for_delivery",
                "delivered",
                "cancelled",
            ],
            key="orders_status_value",
        )

        if st.button("Update Order Status", key="orders_status_btn"):
            api_request(
                "PATCH",
                f"/orders/{int(order_id)}/status",
                json={"status": new_status},
            )

    with cancel_tab:
        order_id = st.number_input(
            "Order ID",
            min_value=1,
            value=1,
            key="orders_cancel_id",
        )
        if st.button("Cancel Order", key="orders_cancel_btn"):
            api_request("POST", f"/orders/{int(order_id)}/cancel")


# ================= DELIVERIES =================

elif menu == "Deliveries":
    st.header("Deliveries API Tester")

    (
        driver_tab,
        customer_tab,
        admin_tab,
        create_tab,
        one_tab,
        assign_tab,
        status_tab,
        location_tab,
    ) = st.tabs(
        [
            "Driver: My Deliveries",
            "Customer: My Deliveries",
            "Admin: All Deliveries",
            "Create",
            "Get One",
            "Assign Driver",
            "Update Status",
            "Update Location",
        ]
    )

    with driver_tab:
        st.caption(
            "Login as a driver. This endpoint returns only deliveries assigned "
            "to the logged-in driver."
        )

        if st.button(
            "Get My Assigned Deliveries",
            key="driver_my_deliveries_btn",
            use_container_width=True,
        ):
            response = api_request(
                "GET",
                "/deliveries/driver/my",
            )

            if response is not None and response.status_code == 200:
                deliveries = response.json()

                if not deliveries:
                    st.info("No delivery is currently assigned to this driver.")

                if isinstance(deliveries, list):
                    for delivery in deliveries:
                        with st.expander(
                            f"Delivery #{delivery.get('id')} — "
                            f"{delivery.get('status', 'unknown')}",
                            expanded=True,
                        ):
                            col1, col2 = st.columns(2)

                            with col1:
                                st.write("### Recipient / Destination")
                                st.write(
                                    f"**Customer User ID:** "
                                    f"{delivery.get('user_id', 'N/A')}"
                                )
                                st.write(
                                    f"**Order ID:** "
                                    f"{delivery.get('order_id', 'N/A')}"
                                )
                                st.write(
                                    f"**Address:** "
                                    f"{delivery.get('delivery_address', 'N/A')}"
                                )
                                st.write(
                                    f"**Notes:** "
                                    f"{delivery.get('delivery_notes') or 'None'}"
                                )
                                st.write(
                                    f"**Scheduled:** "
                                    f"{delivery.get('scheduled_at') or 'Not scheduled'}"
                                )

                            with col2:
                                st.write("### Delivery Progress")
                                st.write(
                                    f"**Driver ID:** "
                                    f"{delivery.get('driver_id', 'N/A')}"
                                )
                                st.write(
                                    f"**Status:** "
                                    f"{delivery.get('status', 'N/A')}"
                                )
                                st.write(
                                    f"**Picked up:** "
                                    f"{delivery.get('picked_up_at') or 'No'}"
                                )
                                st.write(
                                    f"**Delivered:** "
                                    f"{delivery.get('delivered_at') or 'No'}"
                                )
                                st.write(
                                    f"**Failure reason:** "
                                    f"{delivery.get('failure_reason') or 'None'}"
                                )

                            st.json(delivery)

    with customer_tab:
        if st.button(
            "Get My Customer Deliveries",
            key="customer_my_deliveries_btn",
        ):
            api_request("GET", "/deliveries/my")

    with admin_tab:
        search = st.text_input(
            "Search address, notes, or failure reason",
            key="deliveries_admin_search",
        )
        status_filter = st.selectbox(
            "Delivery Status",
            [
                "",
                "pending",
                "assigned",
                "picked_up",
                "out_for_delivery",
                "delivered",
                "failed",
                "cancelled",
            ],
            key="deliveries_admin_status",
        )
        driver_id = st.number_input(
            "Driver ID (0 = all)",
            min_value=0,
            value=0,
            key="deliveries_admin_driver",
        )
        user_id = st.number_input(
            "Customer User ID (0 = all)",
            min_value=0,
            value=0,
            key="deliveries_admin_user",
        )
        order_id = st.number_input(
            "Order ID (0 = all)",
            min_value=0,
            value=0,
            key="deliveries_admin_order",
        )
        page = st.number_input(
            "Page",
            min_value=1,
            value=1,
            key="deliveries_admin_page",
        )
        limit = st.number_input(
            "Limit",
            min_value=1,
            max_value=100,
            value=10,
            key="deliveries_admin_limit",
        )

        if st.button("List Deliveries", key="deliveries_admin_btn"):
            params = {"page": int(page), "limit": int(limit)}
            if search:
                params["search"] = search
            if status_filter:
                params["status"] = status_filter
            if driver_id:
                params["driver_id"] = int(driver_id)
            if user_id:
                params["user_id"] = int(user_id)
            if order_id:
                params["order_id"] = int(order_id)

            api_request("GET", "/deliveries/", params=params)

    with create_tab:
        order_id = st.number_input(
            "Order ID",
            min_value=1,
            value=1,
            key="delivery_create_order",
        )
        driver_id = st.number_input(
            "Driver ID (0 = unassigned)",
            min_value=0,
            value=0,
            key="delivery_create_driver",
        )
        delivery_address = st.text_input(
            "Delivery Address (optional)",
            key="delivery_create_address",
        )
        delivery_notes = st.text_area(
            "Delivery Notes (optional)",
            key="delivery_create_notes",
        )
        scheduled_at = st.text_input(
            "Scheduled At (ISO datetime, optional)",
            placeholder="2026-07-15T12:00:00",
            key="delivery_create_scheduled",
        )

        if st.button("Create Delivery", key="delivery_create_btn"):
            payload = {
                "order_id": int(order_id),
                "driver_id": int(driver_id) if driver_id else None,
                "delivery_address": delivery_address or None,
                "delivery_notes": delivery_notes or None,
                "scheduled_at": scheduled_at or None,
            }
            api_request("POST", "/deliveries/", json=payload)

    with one_tab:
        delivery_id = st.number_input(
            "Delivery ID",
            min_value=1,
            value=1,
            key="delivery_get_id",
        )
        if st.button("Get Delivery", key="delivery_get_btn"):
            api_request("GET", f"/deliveries/{int(delivery_id)}")

    with assign_tab:
        delivery_id = st.number_input(
            "Delivery ID",
            min_value=1,
            value=1,
            key="delivery_assign_id",
        )
        driver_id = st.number_input(
            "Driver ID",
            min_value=1,
            value=1,
            key="delivery_assign_driver",
        )

        if st.button("Assign Driver", key="delivery_assign_btn"):
            api_request(
                "PATCH",
                f"/deliveries/{int(delivery_id)}/assign-driver",
                json={"driver_id": int(driver_id)},
            )

    with status_tab:
        delivery_id = st.number_input(
            "Delivery ID",
            min_value=1,
            value=1,
            key="delivery_status_id",
        )
        delivery_status = st.selectbox(
            "New Status",
            [
                "pending",
                "assigned",
                "picked_up",
                "out_for_delivery",
                "delivered",
                "failed",
                "cancelled",
            ],
            key="delivery_status_value",
        )
        failure_reason = st.text_area(
            "Failure Reason (required for failed status)",
            key="delivery_failure_reason",
        )

        if st.button("Update Delivery Status", key="delivery_status_btn"):
            payload = {
                "status": delivery_status,
                "failure_reason": failure_reason or None,
            }
            api_request(
                "PATCH",
                f"/deliveries/{int(delivery_id)}/status",
                json=payload,
            )

    with location_tab:
        delivery_id = st.number_input(
            "Delivery ID",
            min_value=1,
            value=1,
            key="delivery_location_id",
        )
        latitude = st.number_input(
            "Latitude",
            value=24.7136,
            format="%.6f",
            key="delivery_latitude",
        )
        longitude = st.number_input(
            "Longitude",
            value=46.6753,
            format="%.6f",
            key="delivery_longitude",
        )

        if st.button("Update Driver Location", key="delivery_location_btn"):
            api_request(
                "PATCH",
                f"/deliveries/{int(delivery_id)}/location",
                json={
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                },
            )


# ================= DRIVERS =================

elif menu == "Drivers":
    st.header("Driver Management API Tester")

    create_tab, list_tab, get_tab, update_tab, delete_tab = st.tabs(
        ["Create", "List", "Get One", "Update", "Deactivate"]
    )

    with create_tab:
        first_name = st.text_input(
            "First Name",
            key="driver_create_first",
        )
        last_name = st.text_input(
            "Last Name",
            key="driver_create_last",
        )
        email = st.text_input(
            "Email",
            key="driver_create_email",
        )
        phone = st.text_input(
            "Phone",
            key="driver_create_phone",
        )
        password = st.text_input(
            "Password",
            type="password",
            key="driver_create_password",
        )
        location = st.text_input(
            "Location",
            key="driver_create_location",
        )
        address = st.text_input(
            "Address",
            key="driver_create_address",
        )

        if st.button("Create Driver", key="driver_create_btn"):
            api_request(
                "POST",
                "/driver/",
                json={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone": phone,
                    "password": password,
                    "location": location or None,
                    "address": address or None,
                },
            )

    with list_tab:
        if st.button("List Drivers", key="driver_list_btn"):
            api_request("GET", "/driver/")

    with get_tab:
        driver_id = st.number_input(
            "Driver ID",
            min_value=1,
            value=1,
            key="driver_get_id",
        )
        if st.button("Get Driver", key="driver_get_btn"):
            api_request("GET", f"/driver/{int(driver_id)}")

    with update_tab:
        driver_id = st.number_input(
            "Driver ID",
            min_value=1,
            value=1,
            key="driver_update_id",
        )
        first_name = st.text_input(
            "First Name",
            key="driver_update_first",
        )
        last_name = st.text_input(
            "Last Name",
            key="driver_update_last",
        )
        phone = st.text_input(
            "Phone",
            key="driver_update_phone",
        )
        location = st.text_input(
            "Location",
            key="driver_update_location",
        )
        address = st.text_input(
            "Address",
            key="driver_update_address",
        )
        is_active = st.checkbox(
            "Active",
            value=True,
            key="driver_update_active",
        )

        if st.button("Update Driver", key="driver_update_btn"):
            payload = {
                "is_active": is_active,
            }
            if first_name:
                payload["first_name"] = first_name
            if last_name:
                payload["last_name"] = last_name
            if phone:
                payload["phone"] = phone
            if location:
                payload["location"] = location
            if address:
                payload["address"] = address

            api_request(
                "PUT",
                f"/driver/{int(driver_id)}",
                json=payload,
            )

    with delete_tab:
        driver_id = st.number_input(
            "Driver ID",
            min_value=1,
            value=1,
            key="driver_delete_id",
        )
        if st.button("Deactivate Driver", key="driver_delete_btn"):
            api_request("DELETE", f"/driver/{int(driver_id)}")


# ================= LOCATIONS =================

elif menu == "Locations":
    st.header("Saudi Locations API Tester")

    all_tab, regions_tab, cities_tab, validate_tab = st.tabs(
        ["All Locations", "Regions", "Cities by Region", "Validate"]
    )

    with all_tab:
        search = st.text_input(
            "Search (optional)",
            key="locations_search",
        )
        if st.button("Get Locations", key="locations_all_btn"):
            params = {"search": search} if search else None
            api_request("GET", "/locations/", params=params)

    with regions_tab:
        if st.button("Get Regions", key="locations_regions_btn"):
            api_request("GET", "/locations/regions")

    with cities_tab:
        region_code = st.text_input(
            "Region Code",
            value="riyadh",
            key="locations_city_region",
        )
        if st.button("Get Cities", key="locations_cities_btn"):
            api_request(
                "GET",
                f"/locations/regions/{region_code.strip()}/cities",
            )

    with validate_tab:
        region_code = st.text_input(
            "Region Code",
            value="riyadh",
            key="locations_validate_region",
        )
        city_code = st.text_input(
            "City Code",
            value="riyadh_city",
            key="locations_validate_city",
        )

        if st.button("Validate Location", key="locations_validate_btn"):
            api_request(
                "GET",
                "/locations/validate",
                params={
                    "region_code": region_code.strip(),
                    "city_code": city_code.strip(),
                },
            )


# ================= REPORTS =================

elif menu == "Reports":
    st.header("Reports API Tester")
    st.caption("These endpoints generally require an admin/reporting role.")

    endpoints = {
        "Summary": "/reports/summary",
        "Orders": "/reports/orders",
        "Subscriptions": "/reports/subscriptions",
        "Deliveries": "/reports/deliveries",
        "Revenue": "/reports/revenue",
    }

    selected = st.selectbox(
        "Report",
        list(endpoints.keys()),
        key="report_select",
    )

    if st.button("Fetch Report", key="report_fetch_btn"):
        api_request("GET", endpoints[selected])


# ================= CUSTOM ENDPOINT =================

elif menu == "Custom Endpoint":
    st.header("Custom Endpoint Tester")
    st.caption(
        "Use this for any backend endpoint that is not yet represented by a "
        "dedicated tab."
    )

    method = st.selectbox(
        "HTTP Method",
        ["GET", "POST", "PUT", "PATCH", "DELETE"],
        key="custom_method",
    )
    path = st.text_input(
        "Endpoint Path",
        value="/auth/me",
        help="Example: /notifications/my",
        key="custom_path",
    )
    params_text = st.text_area(
        "Query Parameters as JSON",
        value="{}",
        key="custom_params",
    )
    body_text = st.text_area(
        "JSON Body",
        value="{}",
        key="custom_body",
    )

    if st.button("Send Request", key="custom_send_btn"):
        import json

        try:
            params = json.loads(params_text or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid query-parameter JSON: {exc}")
            params = None

        try:
            body = json.loads(body_text or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid request-body JSON: {exc}")
            body = None

        if params is not None and body is not None:
            api_request(
                method,
                path if path.startswith("/") else f"/{path}",
                params=params or None,
                json=body or None,
                timeout=60,
            )



# ================= PAYMENTS =================

elif menu == "Payments":
    st.header("Tap Payment Tester")

    if not st.session_state.token:
        st.warning("Login as a customer before testing subscriptions and payments.")

    flow_tab, checkout_tab, verify_tab, payments_tab, admin_tab = st.tabs(
        [
            "Complete Flow",
            "Create Tap Checkout",
            "Verify Tap Charge",
            "My Payments",
            "Admin Payments",
        ]
    )

    # ------------------------------------------------------------
    # COMPLETE SUBSCRIPTION -> TAP PAYMENT FLOW
    # ------------------------------------------------------------
    with flow_tab:
        st.subheader("Complete Subscription and Tap Payment Flow")
        st.caption(
            "Use this tab to create a subscription, create a Tap sandbox charge, "
            "open Tap Checkout, verify the returned tap_id, and confirm that the "
            "subscription becomes active and paid."
        )

        col1, col2 = st.columns(2)

        with col1:
            plan_id = st.number_input(
                "Plan ID",
                min_value=1,
                value=1,
                key="tap_flow_plan_id",
            )
            notes = st.text_area(
                "Subscription Notes",
                value="Tap payment test",
                key="tap_flow_notes",
            )

            if st.button(
                "1. Create Subscription",
                key="tap_create_subscription",
                use_container_width=True,
            ):
                try:
                    res = requests.post(
                        f"{API_BASE}/subscriptions/",
                        json={"plan_id": int(plan_id), "notes": notes},
                        headers=headers(),
                        timeout=30,
                    )
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")
                else:
                    show_response(res)

                    if res.status_code in (200, 201):
                        subscription = res.json()
                        st.session_state.tap_subscription_id = subscription.get("id")
                        st.success(
                            f"Subscription #{st.session_state.tap_subscription_id} created."
                        )

            subscription_id = st.number_input(
                "Subscription ID",
                min_value=1,
                value=int(st.session_state.get("tap_subscription_id", 1)),
                key="tap_flow_subscription_id",
            )

            if st.button(
                "2. Create Tap Checkout",
                key="tap_flow_create_checkout",
                use_container_width=True,
            ):
                try:
                    res = requests.post(
                        f"{API_BASE}/payments/create-checkout",
                        json={"subscription_id": int(subscription_id)},
                        headers=headers(),
                        timeout=45,
                    )
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")
                else:
                    show_response(res)

                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.tap_charge_id = data.get("tap_charge_id")
                        st.session_state.tap_checkout_url = data.get("checkout_url")
                        st.session_state.tap_payment_id = data.get("payment_id")

                        st.success("Tap checkout created successfully.")

        with col2:
            checkout_url = st.session_state.get("tap_checkout_url")
            charge_id = st.session_state.get("tap_charge_id")

            st.write("### Current Tap Checkout")
            st.write(
                f"**Payment ID:** {st.session_state.get('tap_payment_id', 'Not created')}"
            )
            st.write(
                f"**Subscription ID:** "
                f"{st.session_state.get('tap_subscription_id', subscription_id)}"
            )
            st.write(f"**Tap Charge ID:** {charge_id or 'Not created'}")

            if checkout_url:
                st.link_button(
                    "3. Open Tap Secure Checkout",
                    checkout_url,
                    use_container_width=True,
                )
                st.info(
                    "Complete the sandbox payment. Tap will redirect to your "
                    "success page with a query parameter such as ?tap_id=chg_..."
                )
            else:
                st.warning("Create a checkout first.")

            returned_tap_id = st.text_input(
                "Tap ID returned after payment",
                value=charge_id or "",
                placeholder="chg_TS...",
                key="tap_flow_verify_id",
            )

            if st.button(
                "4. Verify Tap Payment",
                key="tap_flow_verify",
                use_container_width=True,
            ):
                if not returned_tap_id.strip():
                    st.error("Enter the Tap charge ID (tap_id).")
                else:
                    try:
                        res = requests.get(
                            f"{API_BASE}/payments/verify-charge/"
                            f"{returned_tap_id.strip()}",
                            headers=headers(),
                            timeout=45,
                        )
                    except requests.RequestException as exc:
                        st.error(f"Request failed: {exc}")
                    else:
                        show_response(res)

                        if res.status_code == 200:
                            st.success(
                                "Payment verified. The payment should now be paid "
                                "and the subscription should be active."
                            )

            if st.button(
                "5. Refresh My Subscriptions",
                key="tap_flow_refresh_subscriptions",
                use_container_width=True,
            ):
                try:
                    res = requests.get(
                        f"{API_BASE}/subscriptions/my",
                        headers=headers(),
                        timeout=30,
                    )
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")
                else:
                    show_response(res)

    # ------------------------------------------------------------
    # CREATE TAP CHECKOUT
    # ------------------------------------------------------------
    with checkout_tab:
        st.subheader("Create Tap Checkout")

        subscription_id = st.number_input(
            "Subscription ID",
            min_value=1,
            value=int(st.session_state.get("tap_subscription_id", 1)),
            key="tap_checkout_subscription_id",
        )

        if st.button(
            "Create Tap Checkout",
            key="tap_create_checkout",
            use_container_width=True,
        ):
            try:
                res = requests.post(
                    f"{API_BASE}/payments/create-checkout",
                    json={"subscription_id": int(subscription_id)},
                    headers=headers(),
                    timeout=45,
                )
            except requests.RequestException as exc:
                st.error(f"Request failed: {exc}")
            else:
                show_response(res)

                if res.status_code == 200:
                    data = res.json()
                    checkout_url = data.get("checkout_url")
                    tap_charge_id = data.get("tap_charge_id")

                    st.session_state.tap_subscription_id = int(subscription_id)
                    st.session_state.tap_checkout_url = checkout_url
                    st.session_state.tap_charge_id = tap_charge_id
                    st.session_state.tap_payment_id = data.get("payment_id")

                    st.success("Tap checkout created successfully.")

                    if checkout_url:
                        st.link_button(
                            "Open Tap Secure Checkout",
                            checkout_url,
                            use_container_width=True,
                        )

                    if tap_charge_id:
                        st.code(tap_charge_id, language=None)

    # ------------------------------------------------------------
    # VERIFY TAP CHARGE
    # ------------------------------------------------------------
    with verify_tab:
        st.subheader("Verify Tap Charge")

        st.write(
            "After Tap redirects the customer, copy the `tap_id` query parameter "
            "from the success-page URL and paste it below."
        )

        charge_id = st.text_input(
            "Tap Charge ID",
            value=st.session_state.get("tap_charge_id", ""),
            placeholder="chg_TS...",
            key="tap_verify_charge_id",
        )

        if st.button(
            "Verify Payment",
            key="tap_verify_payment",
            use_container_width=True,
        ):
            if not charge_id.strip():
                st.error("Tap Charge ID is required.")
            else:
                try:
                    res = requests.get(
                        f"{API_BASE}/payments/verify-charge/{charge_id.strip()}",
                        headers=headers(),
                        timeout=45,
                    )
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")
                else:
                    show_response(res)

                    if res.status_code == 200:
                        st.success("Tap payment is captured and verified.")

    # ------------------------------------------------------------
    # CUSTOMER PAYMENT HISTORY
    # ------------------------------------------------------------
    with payments_tab:
        st.subheader("My Payments")

        if st.button(
            "Get My Payments",
            key="tap_get_my_payments",
            use_container_width=True,
        ):
            try:
                res = requests.get(
                    f"{API_BASE}/payments/my",
                    headers=headers(),
                    timeout=30,
                )
            except requests.RequestException as exc:
                st.error(f"Request failed: {exc}")
            else:
                show_response(res)

                if res.status_code == 200:
                    payments = res.json()

                    if isinstance(payments, list) and payments:
                        rows = [
                            {
                                "id": payment.get("id"),
                                "subscription_id": payment.get("subscription_id"),
                                "provider": payment.get("provider"),
                                "status": payment.get("status"),
                                "amount": payment.get("amount"),
                                "currency": payment.get("currency"),
                                "tap_charge_id": payment.get("tap_charge_id"),
                                "paid_at": payment.get("paid_at"),
                                "created_at": payment.get("created_at"),
                            }
                            for payment in payments
                        ]
                        st.dataframe(rows, use_container_width=True)
                    elif isinstance(payments, list):
                        st.info("No payments found.")

    # ------------------------------------------------------------
    # ADMIN / FINANCE PAYMENT LIST
    # ------------------------------------------------------------
    with admin_tab:
        st.subheader("Admin Payment List")
        st.caption(
            "Requires admin, super_admin, or finance_manager authentication."
        )

        status_filter = st.selectbox(
            "Payment Status",
            ["", "pending", "paid", "failed", "cancelled"],
            key="tap_admin_status",
        )
        user_id_filter = st.number_input(
            "User ID (0 means all)",
            min_value=0,
            value=0,
            key="tap_admin_user_id",
        )
        page = st.number_input(
            "Page",
            min_value=1,
            value=1,
            key="tap_admin_page",
        )
        limit = st.number_input(
            "Limit",
            min_value=1,
            max_value=100,
            value=10,
            key="tap_admin_limit",
        )

        if st.button(
            "List Payments",
            key="tap_admin_list_payments",
            use_container_width=True,
        ):
            params = {
                "page": int(page),
                "limit": int(limit),
            }

            if status_filter:
                params["status"] = status_filter

            if user_id_filter > 0:
                params["user_id"] = int(user_id_filter)

            try:
                res = requests.get(
                    f"{API_BASE}/payments/",
                    params=params,
                    headers=headers(),
                    timeout=30,
                )
            except requests.RequestException as exc:
                st.error(f"Request failed: {exc}")
            else:
                show_response(res)