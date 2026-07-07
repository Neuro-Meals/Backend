import requests
import streamlit as st

API_BASE = "https://app.nutriomeals.com"

st.set_page_config(page_title="NeuroMeals API Tester", layout="wide")

st.title("NeuroMeals Backend API Tester")

if "token" not in st.session_state:
    st.session_state.token = None

if "user" not in st.session_state:
    st.session_state.user = None


def headers():
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def show_response(res):
    try:
        st.json(res.json())
    except Exception:
        st.write(res.text)


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
            res = requests.get(f"{API_BASE}/auth/me", headers=headers())
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