// Minimalist Chat App — Authentication Script

function showAlert(message, type = "error") {
    const alertBox = document.getElementById("auth-alert");
    if (!alertBox) return;
    alertBox.textContent = message;
    alertBox.className = `alert-box ${type}`;
    alertBox.classList.remove("hidden");
}

function hideAlert() {
    const alertBox = document.getElementById("auth-alert");
    if (alertBox) {
        alertBox.classList.add("hidden");
    }
}

function setButtonLoading(isLoading, defaultText = "Submit") {
    const btn = document.getElementById("submit-btn");
    if (!btn) return;
    const btnText = btn.querySelector(".btn-text");
    if (isLoading) {
        btn.disabled = true;
        if (btnText) btnText.textContent = "Please wait...";
        btn.style.opacity = "0.7";
    } else {
        btn.disabled = false;
        if (btnText) btnText.textContent = defaultText;
        btn.style.opacity = "1";
    }
}

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPassword = input.type === "password";
    input.type = isPassword ? "text" : "password";
    
    // Update Lucide icon
    btn.innerHTML = isPassword ? '<i data-lucide="eye-off"></i>' : '<i data-lucide="eye"></i>';
    if (window.lucide) {
        lucide.createIcons();
    }
}

function updateSelectedAvatar() {
    const selectedRadio = document.querySelector('input[name="avatar_seed"]:checked');
    const profilePicInput = document.getElementById("profile_picture");
    const options = document.querySelectorAll('.avatar-option');
    
    options.forEach(opt => {
        const radio = opt.querySelector('input[type="radio"]');
        if (radio && radio.checked) {
            opt.classList.add('selected');
            const img = opt.querySelector('img');
            if (img && profilePicInput) {
                profilePicInput.value = img.src;
            }
        } else {
            opt.classList.remove('selected');
        }
    });
}

async function handleLogin(event) {
    event.preventDefault();
    hideAlert();
    setButtonLoading(true, "Sign In");

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Login failed. Please check your credentials.");
        }

        // Store JWT in localStorage as well
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("current_user", JSON.stringify(data.user));

        // Redirect to chat
        window.location.href = "/chat";
    } catch (err) {
        showAlert(err.message || "An unexpected error occurred.");
    } finally {
        setButtonLoading(false, "Sign In");
    }
}

async function handleRegister(event) {
    event.preventDefault();
    hideAlert();
    setButtonLoading(true, "Create Account");

    const username = document.getElementById("username").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    
    // Selected avatar or default
    updateSelectedAvatar();
    let profilePicture = document.getElementById("profile_picture") ? document.getElementById("profile_picture").value : "";
    if (!profilePicture) {
        profilePicture = `https://api.dicebear.com/7.x/initials/svg?seed=${encodeURIComponent(username)}&backgroundColor=f1f5f9&textColor=0f172a`;
    }

    try {
        const response = await fetch("/api/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                username,
                email,
                password,
                profile_picture: profilePicture
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Registration failed.");
        }

        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("current_user", JSON.stringify(data.user));

        window.location.href = "/chat";
    } catch (err) {
        showAlert(err.message || "An unexpected error occurred.");
    } finally {
        setButtonLoading(false, "Create Account");
    }
}

// Initial run
document.addEventListener("DOMContentLoaded", () => {
    updateSelectedAvatar();
    if (window.lucide) {
        lucide.createIcons();
    }
});
