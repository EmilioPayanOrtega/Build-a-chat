document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    const input = document.getElementById("name-input");
    const errorMsg = document.getElementById("login-error");

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const name = input.value.trim();
        if(!name) {
            errorMsg.textContent = "Debes ingresar un nombre.";
            return;
        }

        sessionStorage.setItem("user_name", name); // Guarda el nombre temportalmente

        window.location.href = "/cliente"; //Redirige a la página principal
    });
});