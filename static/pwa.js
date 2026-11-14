(() => {
  "use strict";

  const installButton = document.getElementById("install-app");
  const installHelp = document.getElementById("install-help");
  let installPrompt = null;
  const isIos = /iPhone|iPad|iPod/i.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches
    || navigator.standalone === true;

  function showHelp(message) {
    if (!installHelp) return;
    installHelp.textContent = message;
    installHelp.classList.remove("hidden");
  }

  if (installButton && isStandalone) {
    installButton.hidden = true;
  } else if (installButton) {
    window.addEventListener("beforeinstallprompt", (event) => {
      event.preventDefault();
      installPrompt = event;
      if (installHelp) installHelp.classList.add("hidden");
    });

    window.addEventListener("appinstalled", () => {
      installButton.hidden = true;
      showHelp("ARANKO FOOD quedó instalada en este dispositivo.");
    });

    installButton.addEventListener("click", async () => {
      if (!installPrompt) {
        showHelp(isIos
          ? "En iPhone o iPad, abre esta página en Safari, toca Compartir y elige Añadir a pantalla de inicio."
          : "En Android, abre el menú de tres puntos del navegador y elige Instalar app o Añadir a pantalla principal.");
        return;
      }

      const prompt = installPrompt;
      installPrompt = null;
      try {
        const promptResult = await prompt.prompt();
        const choice = promptResult || await prompt.userChoice;
        if (choice.outcome === "accepted") {
          showHelp("Se inició la instalación de ARANKO FOOD.");
        } else {
          showHelp("La instalación se canceló. Puedes intentarlo de nuevo desde este botón.");
        }
      } catch (error) {
        console.error("No se pudo abrir el diálogo de instalación.", error);
        showHelp("No se pudo abrir la instalación. Usa el menú del navegador para añadir la app a la pantalla de inicio.");
      }
    });
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch((error) => {
      console.error("No se pudo registrar el Service Worker.", error);
      showHelp("No se pudo preparar la app instalable. Comprueba la conexión e inténtalo de nuevo.");
    });
  }
})();
