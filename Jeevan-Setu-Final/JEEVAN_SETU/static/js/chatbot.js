/**
 * chatbot.js — Chatbot frontend logic.
 */

(function () {
    'use strict';

    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    /**
     * Send a message to the chatbot API.
     */
    window.sendMessage = function () {
        const message = chatInput.value.trim();
        if (!message) return;

        const patientIdInput = document.getElementById('patient-id-input');
        const patientId = patientIdInput ? patientIdInput.value.trim() : null;

        // Add user message to chat
        appendMessage(message, 'user');
        chatInput.value = '';
        chatInput.focus();

        // Send to API
        fetch('/chatbot/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                patient_id: patientId ? parseInt(patientId) : null
            })
        })
            .then(res => res.json())
            .then(data => {
                appendMessage(data.text || 'Sorry, I could not process that.', 'bot');
            })
            .catch(err => {
                appendMessage('⚠️ Connection error. Please try again.', 'bot');
                console.error('Chatbot error:', err);
            });
    };

    /**
     * Append a message to the chat window.
     */
    function appendMessage(text, sender) {
        const div = document.createElement('div');
        div.className = `message ${sender === 'user' ? 'user-message' : 'bot-message'}`;
        div.innerHTML = `<p>${text.replace(/\n/g, '<br>')}</p>`;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Enter key to send
    if (chatInput) {
        chatInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
    }
})();
