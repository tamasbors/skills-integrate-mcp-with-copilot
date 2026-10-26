document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const signupContainer = document.getElementById("signup-container");
  const messageDiv = document.getElementById("message");
  const accountMenuToggle = document.getElementById("account-menu-toggle");
  const accountMenu = document.getElementById("account-menu");
  const accountStatus = document.getElementById("account-status");
  const loginOpenButton = document.getElementById("login-open");
  const logoutButton = document.getElementById("logout-button");
  const loginDialog = document.getElementById("login-dialog");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  let isTeacher = false;

  function showMessage(message, className) {
    messageDiv.textContent = message;
    messageDiv.className = className;
    messageDiv.classList.remove("hidden");
    setTimeout(() => messageDiv.classList.add("hidden"), 5000);
  }

  function renderAccountState(username = "") {
    signupContainer.hidden = !isTeacher;
    accountStatus.textContent = isTeacher ? `Signed in as ${username}` : "Not signed in";
    loginOpenButton.classList.toggle("hidden", isTeacher);
    logoutButton.classList.toggle("hidden", !isTeacher);
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      const activities = await response.json();

      // Clear loading message
      activitiesList.innerHTML = "";
      activitySelect.innerHTML = '<option value="">-- Select an activity --</option>';

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft =
          details.max_participants - details.participants.length;

        // Create participants HTML with delete icons instead of bullet points
        const participantsHTML =
          details.participants.length > 0
            ? `<div class="participants-section">
              <h5>Participants:</h5>
              <ul class="participants-list">
                ${details.participants
                  .map(
                    (email) => `<li><span class="participant-email"></span>${
                      isTeacher
                        ? `<button class="delete-btn" data-activity="${encodeURIComponent(name)}" data-email="${encodeURIComponent(email)}" type="button">Remove</button>`
                        : ""
                    }</li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No participants yet</em></p>`;

        activityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Schedule:</strong> ${details.schedule}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-container">
            ${participantsHTML}
          </div>
        `;

        activityCard.querySelectorAll(".participant-email").forEach((element, index) => {
          element.textContent = details.participants[index];
        });
        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        if (isTeacher) {
          const option = document.createElement("option");
          option.value = name;
          option.textContent = name;
          activitySelect.appendChild(option);
        }
      });

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    const button = event.currentTarget;
    const activity = decodeURIComponent(button.getAttribute("data-activity"));
    const email = decodeURIComponent(button.getAttribute("data-email"));

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  accountMenuToggle.addEventListener("click", () => {
    const isExpanded = accountMenuToggle.getAttribute("aria-expanded") === "true";
    accountMenuToggle.setAttribute("aria-expanded", String(!isExpanded));
    accountMenu.classList.toggle("hidden", isExpanded);
  });

  loginOpenButton.addEventListener("click", () => {
    loginError.classList.add("hidden");
    loginForm.reset();
    loginDialog.showModal();
  });

  document.getElementById("login-cancel").addEventListener("click", () => {
    loginDialog.close();
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginError.classList.add("hidden");
    const formData = new FormData(loginForm);

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        loginError.textContent = result.detail || "Unable to sign in";
        loginError.classList.remove("hidden");
        return;
      }

      isTeacher = true;
      renderAccountState(result.username);
      loginDialog.close();
      accountMenu.classList.add("hidden");
      accountMenuToggle.setAttribute("aria-expanded", "false");
      fetchActivities();
    } catch (error) {
      loginError.textContent = "Failed to sign in. Please try again.";
      loginError.classList.remove("hidden");
      console.error("Error signing in:", error);
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/auth/logout", { method: "POST" });
      if (!response.ok) {
        showMessage("Failed to sign out. Please try again.", "error");
        return;
      }
      isTeacher = false;
      renderAccountState();
      accountMenu.classList.add("hidden");
      accountMenuToggle.setAttribute("aria-expanded", "false");
      fetchActivities();
    } catch (error) {
      showMessage("Failed to sign out. Please try again.", "error");
      console.error("Error signing out:", error);
    }
  });

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(
          activity
        )}/signup?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");
        signupForm.reset();

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to sign up. Please try again.", "error");
      console.error("Error signing up:", error);
    }
  });

  // Initialize app
  fetch("/auth/session")
    .then((response) => {
      if (!response.ok) {
        throw new Error("Unable to check teacher session");
      }
      return response.json();
    })
    .then((session) => {
      isTeacher = session.authenticated;
      renderAccountState(session.username);
    })
    .catch((error) => {
      renderAccountState();
      showMessage("Unable to verify teacher sign-in status.", "error");
      console.error("Error checking teacher session:", error);
    })
    .finally(fetchActivities);
});
