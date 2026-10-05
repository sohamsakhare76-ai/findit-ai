document.addEventListener("DOMContentLoaded", () => {
  // Example search chips -> fill the search box
  const searchInput = document.getElementById("search-input");
  document.querySelectorAll(".example-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (searchInput) {
        searchInput.value = chip.textContent.trim();
        searchInput.focus();
      }
    });
  });

  // Location chips -> fill the location input
  const locationInput = document.getElementById("location-input");
  document.querySelectorAll(".location-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (locationInput) locationInput.value = chip.textContent.trim();
    });
  });

  // Image preview + drag & drop
  const fileInput = document.getElementById("image-input");
  const preview = document.getElementById("preview");
  const dzText = document.getElementById("dz-text");
  const dropzone = document.getElementById("dropzone");

  function showPreview() {
    const file = fileInput && fileInput.files && fileInput.files[0];
    if (!file || !preview || !dzText) return;
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
    dzText.textContent = file.name;
  }

  if (fileInput && dropzone) {
    fileInput.addEventListener("change", showPreview);
    ["dragenter", "dragover"].forEach((ev) =>
      dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.add("drag");
      })
    );
    ["dragleave", "drop"].forEach((ev) =>
      dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.remove("drag");
      })
    );
    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        showPreview();
      }
    });
  }

  // Loading state on normal form navigation.
  // Keep the state on the current page while Flask processes the request,
  // but reset it whenever the page is restored from browser cache/back-forward.
  document.querySelectorAll("form[data-loading]").forEach((form) => {
    const btn = form.querySelector("button[type=submit]");
    if (!btn) return;

    btn.dataset.defaultHtml = btn.innerHTML;

    form.addEventListener("submit", (event) => {
      // Prevent accidental double submissions while the request is starting.
      if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }

      form.dataset.submitting = "true";
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      btn.innerHTML = '<span class="spinner" aria-hidden="true"></span>' + form.dataset.loading;
    });
  });

  // Browsers can restore a previous page from the back/forward cache with
  // its disabled button and spinner intact. Always restore the normal state.
  window.addEventListener("pageshow", () => {
    document.querySelectorAll("form[data-loading]").forEach((form) => {
      const btn = form.querySelector("button[type=submit]");
      if (!btn) return;
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
      btn.innerHTML = btn.dataset.defaultHtml || btn.innerHTML;
      delete form.dataset.submitting;
    });
  });

  // Auto-dismiss info messages
  document.querySelectorAll(".flash-info").forEach((el) =>
    setTimeout(() => (el.style.display = "none"), 6000)
  );
});
