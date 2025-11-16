document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    const nameInput = document.getElementById("name-input");

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        let name = nameInput.value.trim();
        if(!name) {
            alert("Por favor, ingresa un nombre para continuar.");
            return;
        }

        sessionStorage.setItem("userName", name); // Guarda el nombre temportalmente

        window.location.href = "/"; //Redirige a la página principal
    });
});