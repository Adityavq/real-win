document.querySelector("form").addEventListener("submit", async function (e) {
    e.preventDefault(); // Prevent page reload

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, password }),
        });

        const result = await response.json();

        if (response.ok) {
            window.location.href = "/home"; 
        } else {
            alert(result.error || "Login failed");
        }
    } catch (err) {
        console.error("Login error:", err);
        alert("An unexpected error occurred");
    }
});