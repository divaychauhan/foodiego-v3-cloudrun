const API_BASE_URL = window.API_BASE_URL || "";

let restaurants = [];
let selectedCuisine = "";
let selectedRestaurant = null;
let cart = [];
let currentUser = null;
let authMode = "login";
let eventsAttached = false;
const menuItemsCache = new Map();

const $ = (id) => document.getElementById(id);

function escapeHTML(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function getToken() {
    return localStorage.getItem("foodiego_token");
}

function authHeaders() {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

async function api(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(options.headers || {})
    };

    const finalOptions = {
        ...options,
        headers
    };

    if (finalOptions.body && typeof finalOptions.body !== "string") {
        finalOptions.body = JSON.stringify(finalOptions.body);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, finalOptions);
    const text = await response.text();
    let data = {};

    if (text) {
        try {
            data = JSON.parse(text);
        } catch (error) {
            data = { error: text };
        }
    }

    if (!response.ok) {
        throw data;
    }

    return data;
}

function showElement(id) {
    const element = $(id);
    if (element) element.classList.remove("hidden");
}

function hideElement(id) {
    const element = $(id);
    if (element) element.classList.add("hidden");
}

function openModal(id) {
    const modal = $(id);
    if (modal) modal.classList.add("show");
}

function closeModal(id) {
    const modal = $(id);
    if (modal) modal.classList.remove("show");
}

function refreshOverlay() {
    const overlay = $("overlay");
    const menuOpen = $("menuPanel")?.classList.contains("open");
    const cartOpen = $("cartDrawer")?.classList.contains("open");

    if (overlay) {
        overlay.classList.toggle("show", Boolean(menuOpen || cartOpen));
    }
}

async function initApp() {
    setupEventListeners();
    await checkMe();
    await loadCuisines();
    await loadRestaurants();
    renderCart();
}

function setupEventListeners() {
    if (eventsAttached) return;
    eventsAttached = true;

    $("authForm")?.addEventListener("submit", handleAuthSubmit);
    $("checkoutForm")?.addEventListener("submit", handleCheckoutSubmit);

    $("searchInput")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            applyFilters();
        }
    });
}

async function checkMe() {
    try {
        const data = await api("/api/auth/me");
        currentUser = data.user;
    } catch (error) {
        currentUser = null;
    }

    updateUserUi();
}

function updateUserUi() {
    const userBadge = $("userBadge");
    const loginBtn = $("loginBtn");
    const logoutBtn = $("logoutBtn");
    const adminBtn = $("adminBtn");

    if (userBadge) {
        userBadge.textContent = currentUser
            ? `${currentUser.name} (${currentUser.role})`
            : "Guest";
    }

    loginBtn?.classList.toggle("hidden", Boolean(currentUser));
    logoutBtn?.classList.toggle("hidden", !currentUser);
    adminBtn?.classList.toggle("hidden", !currentUser || currentUser.role !== "ADMIN");
}

function openAuthModal(mode = "login") {
    authMode = mode;
    updateAuthUi();
    openModal("authModal");
}

function closeAuthModal() {
    closeModal("authModal");
}

function switchAuthMode() {
    authMode = authMode === "login" ? "register" : "login";
    updateAuthUi();
}

function updateAuthUi() {
    const isRegister = authMode === "register";

    if ($("authTitle")) {
        $("authTitle").textContent = isRegister ? "Create Account" : "Login";
    }

    $("registerFields")?.classList.toggle("hidden", !isRegister);

    if ($("authSubmitBtn")) {
        $("authSubmitBtn").textContent = isRegister ? "Register" : "Login";
    }

    if ($("authSwitchText")) {
        $("authSwitchText").textContent = isRegister ? "Already registered?" : "New user?";
    }

    if ($("authSwitchBtn")) {
        $("authSwitchBtn").textContent = isRegister ? "Login" : "Create account";
    }
}

async function handleAuthSubmit(event) {
    event.preventDefault();

    const email = $("authEmail")?.value.trim();
    const password = $("authPassword")?.value;

    if (!email || !password) {
        alert("Email and password are required");
        return;
    }

    const payload = { email, password };

    if (authMode === "register") {
        payload.name = $("authName")?.value.trim();
        payload.phone = $("authPhone")?.value.trim();

        if (!payload.name || !payload.phone) {
            alert("Name and phone are required");
            return;
        }
    }

    try {
        const endpoint = authMode === "register" ? "/api/auth/register" : "/api/auth/login";
        const data = await api(endpoint, {
            method: "POST",
            body: payload
        });

        localStorage.setItem("foodiego_token", data.token);
        currentUser = data.user;
        updateUserUi();
        closeAuthModal();
        alert(data.message || "Login successful");
    } catch (error) {
        alert(error.error || "Authentication failed");
    }
}

async function logout() {
    try {
        await api("/api/auth/logout", { method: "POST" });
    } catch (error) {
        // Ignore logout API errors because token will be removed locally.
    }

    localStorage.removeItem("foodiego_token");
    currentUser = null;
    updateUserUi();
}

async function loadCuisines() {
    const categoryRow = $("categoryRow");
    if (!categoryRow) return;

    const emojis = {
        "North Indian": "🍛",
        Mughlai: "🍗",
        Pizza: "🍕",
        Italian: "🍝",
        "Fast Food": "🍔",
        Beverages: "🥤",
        Biryani: "🍚",
        Desserts: "🍰",
        "Healthy Food": "🥗",
        Salads: "🥗",
        Bowls: "🥣"
    };

    categoryRow.innerHTML = `
        <button class="category-card active" data-cuisine="" onclick="selectCuisine('')">
            <span>🍽️</span>
            <strong>All</strong>
        </button>
    `;

    try {
        const cuisines = await api("/api/cuisines");

        cuisines.slice(0, 10).forEach((cuisine) => {
            const button = document.createElement("button");
            button.className = "category-card";
            button.dataset.cuisine = cuisine;
            button.innerHTML = `
                <span>${emojis[cuisine] || "🍽️"}</span>
                <strong>${escapeHTML(cuisine)}</strong>
            `;
            button.addEventListener("click", () => selectCuisine(cuisine));
            categoryRow.appendChild(button);
        });
    } catch (error) {
        console.error("Cuisine loading failed:", error);
    }
}

async function loadRestaurants() {
    const search = $("searchInput")?.value.trim() || "";
    const restaurantsGrid = $("restaurantsGrid");

    try {
        restaurants = await api(
            `/api/restaurants?search=${encodeURIComponent(search)}&cuisine=${encodeURIComponent(selectedCuisine)}`
        );
        sortRestaurants();
    } catch (error) {
        if (restaurantsGrid) {
            restaurantsGrid.innerHTML = `<div class="empty-cart">Unable to load restaurants.</div>`;
        }
    }
}

function renderRestaurants(data) {
    const restaurantsGrid = $("restaurantsGrid");
    const restaurantCount = $("restaurantCount");

    if (!restaurantsGrid) return;

    restaurantsGrid.innerHTML = "";

    if (restaurantCount) {
        restaurantCount.textContent = `${data.length} restaurants available`;
    }

    if (!data.length) {
        restaurantsGrid.innerHTML = `
            <div class="empty-cart">
                <h3>No restaurants found</h3>
                <p>Try another search.</p>
            </div>
        `;
        return;
    }

    data.forEach((restaurant) => {
        const card = document.createElement("div");
        card.className = "restaurant-card";

        card.innerHTML = `
            <div class="restaurant-cover">
                <span>${escapeHTML(restaurant.cover_emoji)}</span>
                <div class="offer-badge">${escapeHTML(restaurant.offer)}</div>
            </div>

            <div class="restaurant-body">
                <div class="restaurant-title-row">
                    <h3>${escapeHTML(restaurant.name)}</h3>
                    <div class="rating">★ ${escapeHTML(restaurant.rating)}</div>
                </div>

                <p class="cuisine">${escapeHTML(restaurant.cuisine)}</p>

                <div class="meta-row">
                    <span>⏱️ ${escapeHTML(restaurant.delivery_time)}</span>
                    <span>₹${escapeHTML(restaurant.price_for_two)} for two</span>
                </div>

                <div class="meta-row">
                    <span>📍 ${escapeHTML(restaurant.location)}</span>
                    <span>${restaurant.is_open ? "Open" : "Closed"}</span>
                </div>

                <button class="view-menu-btn" onclick="openMenu(${restaurant.id})">
                    View Menu
                </button>
            </div>
        `;

        restaurantsGrid.appendChild(card);
    });
}

function sortRestaurants() {
    const sortBy = $("sortSelect")?.value || "rating";
    const sorted = [...restaurants];

    if (sortBy === "rating") {
        sorted.sort((a, b) => Number(b.rating || 0) - Number(a.rating || 0));
    }

    if (sortBy === "price") {
        sorted.sort((a, b) => Number(a.price_for_two || 0) - Number(b.price_for_two || 0));
    }

    if (sortBy === "time") {
        sorted.sort((a, b) => parseInt(a.delivery_time, 10) - parseInt(b.delivery_time, 10));
    }

    renderRestaurants(sorted);
}

function applyFilters() {
    loadRestaurants();
}

function selectCuisine(cuisine) {
    selectedCuisine = cuisine;

    document.querySelectorAll(".category-card").forEach((card) => {
        card.classList.toggle("active", card.dataset.cuisine === cuisine);
    });

    loadRestaurants();
}

async function openMenu(id) {
    try {
        const data = await api(`/api/restaurants/${id}/menu`);
        selectedRestaurant = data.restaurant;
        menuItemsCache.clear();

        if ($("menuRestaurantName")) {
            $("menuRestaurantName").textContent = data.restaurant.name;
        }

        if ($("menuRestaurantMeta")) {
            $("menuRestaurantMeta").textContent = `${data.restaurant.cuisine} • ${data.restaurant.delivery_time} • ★ ${data.restaurant.rating}`;
        }

        if ($("restaurantOffer")) {
            $("restaurantOffer").textContent = `🏷️ ${data.restaurant.offer}`;
        }

        const menuContent = $("menuContent");
        if (!menuContent) return;

        menuContent.innerHTML = "";

        Object.keys(data.categories).forEach((category) => {
            const section = document.createElement("div");
            section.className = "menu-category";

            let itemHtml = "";

            data.categories[category].forEach((item) => {
                menuItemsCache.set(Number(item.id), item);

                itemHtml += `
                    <div class="menu-item">
                        <div>
                            <span class="food-type">${escapeHTML(item.food_type)}</span>
                            <div class="food-name">${escapeHTML(item.name)}</div>
                            <p class="food-description">${escapeHTML(item.description)}</p>
                            <div class="food-price">₹${escapeHTML(item.price)}</div>
                        </div>

                        <div>
                            <div class="food-emoji">${escapeHTML(item.food_emoji)}</div>
                            <button class="add-btn" onclick="addToCartById(${item.id})">ADD</button>
                        </div>
                    </div>
                `;
            });

            section.innerHTML = `<h3>${escapeHTML(category)}</h3>${itemHtml}`;
            menuContent.appendChild(section);
        });

        $("menuPanel")?.classList.add("open");
        refreshOverlay();
    } catch (error) {
        alert(error.error || "Unable to load menu");
    }
}

function closeMenu() {
    $("menuPanel")?.classList.remove("open");
    refreshOverlay();
}

function addToCartById(itemId) {
    const item = menuItemsCache.get(Number(itemId));

    if (!item) {
        alert("Item not found. Please reload menu.");
        return;
    }

    addToCart(item);
}

function addToCart(item) {
    if (!selectedRestaurant) {
        alert("Please select a restaurant first");
        return;
    }

    if (cart.length && cart[0].restaurant_id !== selectedRestaurant.id) {
        const shouldClear = confirm("Cart has items from another restaurant. Clear cart?");
        if (!shouldClear) return;
        cart = [];
    }

    const existing = cart.find((cartItem) => cartItem.menu_item_id === item.id);

    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({
            restaurant_id: selectedRestaurant.id,
            restaurant_name: selectedRestaurant.name,
            menu_item_id: item.id,
            name: item.name,
            price: Number(item.price),
            quantity: 1
        });
    }

    renderCart();
    $("cartDrawer")?.classList.add("open");
    refreshOverlay();
}

function renderCart() {
    const cartItems = $("cartItems");
    const cartCount = $("cartCount");
    const cartRestaurantName = $("cartRestaurantName");

    if (!cartItems) return;

    cartItems.innerHTML = "";

    if (cartCount) {
        cartCount.textContent = cart.reduce((sum, item) => sum + item.quantity, 0);
    }

    if (!cart.length) {
        if (cartRestaurantName) {
            cartRestaurantName.textContent = "No restaurant selected";
        }

        cartItems.innerHTML = `
            <div class="empty-cart">
                <h3>Your cart is empty</h3>
                <p>Add items from a restaurant.</p>
            </div>
        `;

        updateBill();
        return;
    }

    if (cartRestaurantName) {
        cartRestaurantName.textContent = cart[0].restaurant_name;
    }

    cart.forEach((item) => {
        const div = document.createElement("div");
        div.className = "cart-item";

        div.innerHTML = `
            <div>
                <h4>${escapeHTML(item.name)}</h4>
                <p>₹${item.price} × ${item.quantity}</p>
                <strong>₹${item.price * item.quantity}</strong>
            </div>

            <div class="qty-control">
                <button onclick="changeQuantity(${item.menu_item_id}, -1)">−</button>
                <span>${item.quantity}</span>
                <button onclick="changeQuantity(${item.menu_item_id}, 1)">+</button>
            </div>
        `;

        cartItems.appendChild(div);
    });

    updateBill();
}

function changeQuantity(id, change) {
    const item = cart.find((cartItem) => cartItem.menu_item_id === id);
    if (!item) return;

    item.quantity += change;

    if (item.quantity <= 0) {
        cart = cart.filter((cartItem) => cartItem.menu_item_id !== id);
    }

    renderCart();
}

function updateBill() {
    const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
    const delivery = subtotal === 0 ? 0 : subtotal >= 499 ? 0 : 35;
    const platform = subtotal === 0 ? 0 : 5;
    const total = subtotal + delivery + platform;

    if ($("subtotalAmount")) $("subtotalAmount").textContent = `₹${subtotal}`;
    if ($("deliveryFee")) $("deliveryFee").textContent = delivery === 0 ? "FREE" : `₹${delivery}`;
    if ($("platformFee")) $("platformFee").textContent = `₹${platform}`;
    if ($("totalAmount")) $("totalAmount").textContent = `₹${total}`;
}

function toggleCart() {
    $("cartDrawer")?.classList.toggle("open");
    refreshOverlay();
}

function openCheckoutModal() {
    if (!currentUser) {
        openAuthModal("login");
        return;
    }

    if (!cart.length) {
        alert("Cart is empty");
        return;
    }

    openModal("checkoutModal");
    hideElement("orderSuccess");

    if ($("customerName")) $("customerName").value = currentUser.name || "";
    if ($("customerPhone")) $("customerPhone").value = currentUser.phone || "";
}

function closeCheckoutModal() {
    closeModal("checkoutModal");
}

async function handleCheckoutSubmit(event) {
    event.preventDefault();

    if (!cart.length) {
        alert("Cart is empty");
        return;
    }

    const phone = $("customerPhone")?.value.trim() || "";
    const pincode = $("addrPincode")?.value.trim() || "";

    if (!/^\d{10}$/.test(phone)) {
        alert("Enter valid 10 digit phone number");
        return;
    }

    if (!/^\d{6}$/.test(pincode)) {
        alert("Enter valid 6 digit pincode");
        return;
    }

    const payload = {
        customer_name: $("customerName")?.value.trim(),
        phone,
        restaurant_id: cart[0].restaurant_id,
        payment_method: $("paymentMethod")?.value || "COD",
        address: {
            flat: $("addrFlat")?.value.trim(),
            area: $("addrArea")?.value.trim(),
            city: $("addrCity")?.value.trim(),
            pincode,
            landmark: $("addrLandmark")?.value.trim()
        },
        items: cart.map((item) => ({
            menu_item_id: item.menu_item_id,
            quantity: item.quantity
        }))
    };

    if (!payload.customer_name || !payload.address.flat || !payload.address.area || !payload.address.city) {
        alert("Please fill all required delivery details");
        return;
    }

    try {
        const data = await api("/api/orders", {
            method: "POST",
            body: payload
        });

        const payButton = data.payment_required
            ? `<button class="checkout-btn" onclick="confirmPayment(${data.payment_id})">Pay Now Mock</button>`
            : "";

        showElement("orderSuccess");

        if ($("orderSuccess")) {
            $("orderSuccess").innerHTML = `
                <h3>Order placed 🎉</h3>
                <p><strong>Order ID:</strong> ${escapeHTML(data.order_id)}</p>
                <p><strong>Status:</strong> ${escapeHTML(data.status)}</p>
                <p><strong>Total:</strong> ₹${escapeHTML(data.total_amount)}</p>
                <p><strong>Payment:</strong> ${escapeHTML(data.payment_status)}</p>
                ${payButton}
            `;
        }

        cart = [];
        renderCart();
        $("cartDrawer")?.classList.remove("open");
        refreshOverlay();
    } catch (error) {
        alert(error.error || "Order failed");
    }
}

async function confirmPayment(paymentId) {
    try {
        const data = await api(`/api/payments/${paymentId}/confirm`, {
            method: "POST"
        });

        alert(`${data.message}. Transaction: ${data.transaction_id}`);
    } catch (error) {
        alert(error.error || "Payment failed");
    }
}

function openTrackModal() {
    if (!currentUser) {
        openAuthModal("login");
        return;
    }

    openModal("trackModal");
}

function closeTrackModal() {
    closeModal("trackModal");
}

async function trackOrder() {
    const id = $("trackOrderId")?.value;

    if (!id) {
        alert("Enter order ID");
        return;
    }

    try {
        const [order, tracking] = await Promise.all([
            api(`/api/orders/${id}`),
            api(`/api/orders/${id}/tracking`)
        ]);

        let steps = "";
        tracking.timeline.forEach((item) => {
            steps += `
                <div class="status-step ${item.completed ? "active" : ""}">
                    ${escapeHTML(item.status.replaceAll("_", " "))}
                </div>
            `;
        });

        const items = order.items
            .map((item) => `<li>${escapeHTML(item.item_name)} × ${item.quantity} - ₹${item.line_total}</li>`)
            .join("");

        const cancelButton = order.can_cancel
            ? `<button class="checkout-btn" onclick="cancelOrder(${order.order_id})">Cancel Order</button>`
            : "";

        if ($("trackResult")) {
            $("trackResult").innerHTML = `
                <h3>Order #${escapeHTML(order.order_id)}</h3>
                <p><strong>Restaurant:</strong> ${escapeHTML(order.restaurant)}</p>
                <p><strong>Status:</strong> ${escapeHTML(order.status)}</p>
                <p><strong>Total:</strong> ₹${escapeHTML(order.total_amount)}</p>
                <p><strong>Payment:</strong> ${escapeHTML(order.payment_status)}</p>
                <p><strong>ETA:</strong> ${escapeHTML(tracking.eta_minutes)} min</p>
                <p><strong>Driver:</strong> ${escapeHTML(tracking.driver.name)} (${escapeHTML(tracking.driver.phone)})</p>
                <p><strong>Mock Location:</strong> ${escapeHTML(tracking.location.latitude)}, ${escapeHTML(tracking.location.longitude)}</p>
                <ul style="margin-left:20px;margin-top:8px">${items}</ul>
                <div class="status-timeline">${steps}</div>
                ${cancelButton}
            `;
        }
    } catch (error) {
        if ($("trackResult")) {
            $("trackResult").innerHTML = `<p>${escapeHTML(error.error || "Unable to track order")}</p>`;
        }
    }
}

async function cancelOrder(id) {
    const reason = prompt("Cancellation reason", "Changed my mind") || "Cancelled by customer";

    try {
        const data = await api(`/api/orders/${id}/cancel`, {
            method: "POST",
            body: { reason }
        });

        alert(data.message);
        trackOrder();
    } catch (error) {
        alert(error.error || "Cancel failed");
    }
}

function openAdminModal() {
    openModal("adminModal");
    loadAdminOrders();
}

function closeAdminModal() {
    closeModal("adminModal");
}

async function loadAdminOrders() {
    const adminContent = $("adminContent");
    if (!adminContent) return;

    try {
        const orders = await api("/api/admin/orders");
        let html = "<h3>Latest Orders</h3>";

        orders.forEach((order) => {
            const statuses = ["ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"];
            const actionButtons = statuses
                .map((status) => `
                    <button onclick="adminUpdateStatus(${order.order_id}, '${status}')">
                        ${status.replaceAll("_", " ")}
                    </button>
                `)
                .join("");

            html += `
                <div class="admin-card">
                    <strong>#${escapeHTML(order.order_id)} - ${escapeHTML(order.restaurant)}</strong>
                    <p>${escapeHTML(order.customer_name)} • ₹${escapeHTML(order.total_amount)} • ${escapeHTML(order.payment_status)}</p>
                    <p>Status: ${escapeHTML(order.status)}</p>
                    <div class="admin-actions">${actionButtons}</div>
                </div>
            `;
        });

        adminContent.innerHTML = html;
    } catch (error) {
        adminContent.innerHTML = `<p>${escapeHTML(error.error || "Admin access failed")}</p>`;
    }
}

async function adminUpdateStatus(id, status) {
    try {
        await api(`/api/admin/orders/${id}/status`, {
            method: "PATCH",
            body: { status }
        });

        loadAdminOrders();
    } catch (error) {
        alert(error.error || "Update failed");
    }
}

function showCreateRestaurant() {
    const adminContent = $("adminContent");
    if (!adminContent) return;

    adminContent.innerHTML = `
        <h3>Add Restaurant</h3>
        <form id="adminRestaurantForm">
            <input id="arName" placeholder="Restaurant name" required>
            <input id="arCuisine" placeholder="Cuisine" required>
            <input id="arLocation" placeholder="Location" required>
            <input id="arOffer" placeholder="Offer">
            <input id="arEmoji" placeholder="Emoji" value="🍽️">
            <button class="checkout-btn">Create Restaurant</button>
        </form>
    `;

    $("adminRestaurantForm")?.addEventListener("submit", async (event) => {
        event.preventDefault();

        try {
            await api("/api/admin/restaurants", {
                method: "POST",
                body: {
                    name: $("arName").value.trim(),
                    cuisine: $("arCuisine").value.trim(),
                    location: $("arLocation").value.trim(),
                    offer: $("arOffer").value.trim(),
                    cover_emoji: $("arEmoji").value.trim() || "🍽️"
                }
            });

            alert("Restaurant created");
            loadRestaurants();
        } catch (error) {
            alert(error.error || "Create failed");
        }
    });
}

async function showCreateMenuItem() {
    const adminContent = $("adminContent");
    if (!adminContent) return;

    try {
        const restaurantList = await api("/api/admin/restaurants");
        const options = restaurantList
            .map((restaurant) => `<option value="${restaurant.id}">${escapeHTML(restaurant.name)}</option>`)
            .join("");

        adminContent.innerHTML = `
            <h3>Add Menu Item</h3>
            <form id="adminMenuForm">
                <select id="miRest">${options}</select>
                <input id="miName" placeholder="Item name" required>
                <input id="miDesc" placeholder="Description" required>
                <input id="miCat" placeholder="Category" required>
                <input id="miPrice" type="number" placeholder="Price" required>
                <select id="miType">
                    <option>Veg</option>
                    <option>Non-Veg</option>
                </select>
                <input id="miEmoji" value="🍽️">
                <button class="checkout-btn">Create Menu Item</button>
            </form>
        `;

        $("adminMenuForm")?.addEventListener("submit", async (event) => {
            event.preventDefault();

            try {
                await api("/api/admin/menu-items", {
                    method: "POST",
                    body: {
                        restaurant_id: parseInt($("miRest").value, 10),
                        name: $("miName").value.trim(),
                        description: $("miDesc").value.trim(),
                        category: $("miCat").value.trim(),
                        price: parseFloat($("miPrice").value),
                        food_type: $("miType").value,
                        food_emoji: $("miEmoji").value.trim() || "🍽️"
                    }
                });

                alert("Menu item created");
            } catch (error) {
                alert(error.error || "Create failed");
            }
        });
    } catch (error) {
        adminContent.innerHTML = `<p>${escapeHTML(error.error || "Unable to load restaurants")}</p>`;
    }
}

function closeAllPanels() {
    $("menuPanel")?.classList.remove("open");
    $("cartDrawer")?.classList.remove("open");
    refreshOverlay();
}

function goHome() {
    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}

window.openAuthModal = openAuthModal;
window.closeAuthModal = closeAuthModal;
window.switchAuthMode = switchAuthMode;
window.logout = logout;
window.applyFilters = applyFilters;
window.selectCuisine = selectCuisine;
window.sortRestaurants = sortRestaurants;
window.openMenu = openMenu;
window.closeMenu = closeMenu;
window.addToCartById = addToCartById;
window.changeQuantity = changeQuantity;
window.toggleCart = toggleCart;
window.openCheckoutModal = openCheckoutModal;
window.closeCheckoutModal = closeCheckoutModal;
window.confirmPayment = confirmPayment;
window.openTrackModal = openTrackModal;
window.closeTrackModal = closeTrackModal;
window.trackOrder = trackOrder;
window.cancelOrder = cancelOrder;
window.openAdminModal = openAdminModal;
window.closeAdminModal = closeAdminModal;
window.loadAdminOrders = loadAdminOrders;
window.adminUpdateStatus = adminUpdateStatus;
window.showCreateRestaurant = showCreateRestaurant;
window.showCreateMenuItem = showCreateMenuItem;
window.closeAllPanels = closeAllPanels;
window.goHome = goHome;

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}