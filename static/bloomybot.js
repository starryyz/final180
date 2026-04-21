document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("bloomybot-form");
  const input = document.getElementById("bloomybot-input");
  const messages = document.getElementById("bloomybot-messages");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    const userMsg = document.createElement("div");
    userMsg.className = "bot-msg user";
    userMsg.textContent = text;
    messages.appendChild(userMsg);

    const botMsg = document.createElement("div");
    botMsg.className = "bot-msg bot";
    botMsg.textContent = "BloomyBot: Thanks for your question! A human gardener will review this soon.";
    messages.appendChild(botMsg);

    input.value = "";
    messages.scrollTop = messages.scrollHeight;
  });
});
