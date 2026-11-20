const balanceToggle = document.querySelector("#balance-toggle");
const balance = document.querySelector(".balance-amount");
const visibleBalance = balance.innerHTML;

if (balanceToggle) {
  balanceToggle.addEventListener("click", () => {
    const isHidden = balanceToggle.getAttribute("aria-pressed") === "true";
    balance.innerHTML = isHidden ? visibleBalance : "••••••••";
    balanceToggle.setAttribute("aria-pressed", String(!isHidden));
    balanceToggle.setAttribute("aria-label", isHidden ? "Hide balance" : "Show balance");
  });
}

document.querySelectorAll(".account-operation-form").forEach((form) => {
  const accountNumber = form.querySelector('[name="account_number"]');
  const accountHolder = form.querySelector(".account-holder-name");
  const lookupStatus = form.querySelector(".account-lookup-status");
  const amount = form.querySelector('[name="amount"]');
  const submitButton = form.querySelector('button[type="submit"]');
  let lookupController;

  accountNumber.addEventListener("input", () => {
    if (lookupController) lookupController.abort();

    accountHolder.value = "";
    amount.value = "";
    amount.disabled = true;
    submitButton.disabled = true;
    lookupStatus.classList.remove("is-error", "is-success");

    if (!/^[0-9]{14}$/.test(accountNumber.value)) {
      lookupStatus.textContent = "Enter a valid 14-digit account number.";
      lookupStatus.classList.add("is-error");
      return;
    }

    const controller = new AbortController();
    lookupController = controller;
    lookupStatus.textContent = "Verifying account...";

    fetch(
      `${form.dataset.lookupUrl}?account_number=${encodeURIComponent(accountNumber.value)}`,
      {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      },
    )
      .then(async (response) => ({
        ok: response.ok,
        status: response.status,
        data: await response.json(),
      }))
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.ok) {
          lookupStatus.textContent = result.data.message || "Account not found.";
          lookupStatus.classList.add("is-error");
          return;
        }

        accountHolder.value = result.data.owner_name;
        amount.disabled = false;
        submitButton.disabled = false;
        lookupStatus.textContent = "Account holder verified.";
        lookupStatus.classList.add("is-success");
      })
      .catch((error) => {
        if (error.name === "AbortError") return;
        lookupStatus.textContent = `Unable to verify this account: ${error.message}`;
        lookupStatus.classList.add("is-error");
      });
  });
});

