
"use strict";

const statusBox = document.getElementById("status");

function setStatus(message) {
  if (statusBox) {
    statusBox.textContent = message;
  }
}

function getErrorMessage(error) {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "An unexpected checkout error occurred.";
}

async function readResponse(response) {
  const text = await response.text();

  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return {
      error: text || `Server returned HTTP ${response.status}`,
    };
  }
}

async function createOrder() {
  setStatus("Creating your order...");

  const response = await fetch("/api/orders", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({}),
  });

  const result = await readResponse(response);

  if (!response.ok || !result.id) {
    console.error("Create-order request failed:", {
      httpStatus: response.status,
      response: result,
    });

    throw new Error(
      result.error || "Unable to create the PayPal order."
    );
  }

  console.log("PayPal order created:", result.id);

  return result.id;
}

async function captureOrder(orderID) {
  setStatus("Confirming your payment...");

  const response = await fetch(
    `/api/orders/${encodeURIComponent(orderID)}/capture`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({}),
    }
  );

  const result = await readResponse(response);

  if (!response.ok || result.status !== "COMPLETED") {
    console.error("Capture request failed:", {
      orderID,
      httpStatus: response.status,
      response: result,
    });

    throw new Error(
      result.error || "PayPal has not confirmed the payment."
    );
  }

  console.log("PayPal payment completed:", result);

  setStatus("Payment completed successfully!");

  return result;
}

function handlePayPalError(error) {
  console.error("PayPal checkout error:", error);

  if (error && typeof error === "object") {
    console.error("PayPal error details:", {
      name: error.name,
      message: error.message,
      stack: error.stack,
    });
  }

  setStatus(
    "Checkout failed. Check the browser console and Flask terminal."
  );
}

function handleCancel() {
  console.log("PayPal checkout was cancelled.");
  setStatus("Checkout cancelled. No payment confirmed.");
}

if (!statusBox) {
  console.error('Missing element with id="status".');
} else if (
  typeof paypal === "undefined" ||
  typeof paypal.Buttons !== "function"
) {
  setStatus("PayPal SDK failed to load. Refresh and try again.");
  console.error("PayPal JavaScript SDK is not available.");
} else {
  paypal.Buttons({
    createOrder: async function () {
      try {
        return await createOrder();
      } catch (error) {
        handlePayPalError(error);
        throw error;
      }
    },

    onApprove: async function (data) {
      try {
        if (!data || !data.orderID) {
          throw new Error("PayPal did not provide an order ID.");
        }

        await captureOrder(data.orderID);
      } catch (error) {
        handlePayPalError(error);
        throw error;
      }
    },

    onCancel: handleCancel,

    onError: handlePayPalError,
  })
    .render("#paypal-button-container")
    .catch(handlePayPalError);
}