document.getElementById('signup-form').addEventListener('submit', async function (e) {
    e.preventDefault();

    const fullName = document.getElementById('full-name').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (password !== confirmPassword) {
        alert("Passwords do not match.");
        return;
    }

    try {
        const response = await fetch('/api/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: fullName,
                email: email,
                password: password
            })
        });

        const result = await response.json();

        if (response.ok) {
            window.location.href = '/signin'; 
        } else {
            alert(result.error); // Show error
        }
    } catch (err) {
        alert("An error occurred. Please try again later.");
        console.error(err);
    }
});