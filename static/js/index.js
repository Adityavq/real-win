
document.addEventListener("DOMContentLoaded", function () {
    fetch("/api/last_predictions")
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById("predictionTableBody");
            tbody.innerHTML = ""; // Clear previous data

            data.forEach(pred => {
                const row = document.createElement("tr");

                row.innerHTML = `
                            <td>${pred.team1}</td>
                            <td>${pred.team2}</td>
                            <td>${pred.prediction}</td>
                            <td class="${pred.result.toLowerCase()}">${pred.result}</td>
                            <td>${pred.date}</td>
                            `;

                tbody.appendChild(row);
            });
        })
        .catch(err => {
            console.error("Error loading predictions:", err);
        });
});
