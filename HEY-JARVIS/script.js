const chatElement = document.getElementById("chat");
const synth = window.speechSynthesis;

let socket;
let recognition;
let isProcessingResponse = false;
let isAwake = false;
let lastUserMessage = '';
let lastAIMessage = '';
let inactivityTimer;

const WAKE_WORDS = ["hey jarvis", "jarvis"];
const ACTIVATION_RESPONSES = [
    "Hello, how may I help you?",
    "I'm listening. How can I assist you?",
    "What can I do for you today?"
];
const INACTIVITY_TIMEOUT = 30000;

function preprocessText(text) {
    return text.toLowerCase()
        .replace(/[^\w\s]/g, '')
        .trim();
}

function isSimilar(text1, text2) {
    if (!text1 || !text2) return false;
    return preprocessText(text1) === preprocessText(text2);
}

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(() => {
        if (isAwake) {
            isAwake = false;
            addMessage("System", "Going into sleep mode. Say 'Hey Jarvis' to wake up.", "system");
        }
    }, INACTIVITY_TIMEOUT);
}

function establishWebSocket() {
    socket = new WebSocket("ws://127.0.0.1:8000/ws");

    socket.onopen = () => {
        addMessage("System", "Connection established. Say 'Hey Jarvis' to activate.", "system");
        startListening();
    };

    socket.onmessage = (event) => {
        const aiResponse = event.data;

        if (isSimilar(aiResponse, lastAIMessage) || isSimilar(aiResponse, lastUserMessage)) {
            addMessage("System", "Skipping redundant response.", "system");
            return;
        }

        stopListening(); // Stop listening during AI response

        lastAIMessage = aiResponse;
        addMessage("AI", aiResponse, "ai");

        isProcessingResponse = true;
        const utterance = new SpeechSynthesisUtterance(aiResponse);
        utterance.rate = 0.9;
        synth.speak(utterance);

        utterance.onend = () => {
            isProcessingResponse = false;
            startListening(); // Resume listening after AI finishes speaking
            resetInactivityTimer();
        };
    };

    socket.onerror = () => {
        addMessage("System", "Connection error. Reconnecting...", "system");
        setTimeout(establishWebSocket, 2000);
    };

    socket.onclose = () => {
        addMessage("System", "Connection closed. Reconnecting...", "system");
        setTimeout(establishWebSocket, 2000);
    };
}

function startListening() {
    if (isProcessingResponse || (recognition && recognition.continuous)) return;

    if (recognition) {
        recognition.stop();
    }

    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = "en-US";
    recognition.interimResults = false;

    recognition.onresult = (event) => {
        const transcript = event.results[event.results.length - 1][0].transcript.trim();

        if (!isAwake) {
            const containsWakeWord = WAKE_WORDS.some(word => 
                transcript.toLowerCase().includes(word)
            );

            if (containsWakeWord) {
                isAwake = true;
                addMessage("User", transcript, "user");

                const activationResponse = ACTIVATION_RESPONSES[Math.floor(Math.random() * ACTIVATION_RESPONSES.length)];
                lastAIMessage = activationResponse;
                addMessage("AI", activationResponse, "ai");

                const utterance = new SpeechSynthesisUtterance(activationResponse);
                synth.speak(utterance);

                resetInactivityTimer();
            }
        } else {
            if (isSimilar(transcript, lastUserMessage)) {
                addMessage("System", "Duplicate input ignored.", "system");
                return;
            }

            lastUserMessage = transcript;
            addMessage("User", transcript, "user");

            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(transcript);
            }

            resetInactivityTimer();
        }
    };

    recognition.onerror = () => {
        addMessage("System", "Speech recognition error. Restarting...", "system");
        setTimeout(() => {
            if (!isProcessingResponse) startListening();
        }, 1000);
    };

    recognition.onend = () => {
        if (!isProcessingResponse) {
            startListening();
        }
    };

    recognition.start();
}

function stopListening() {
    if (recognition) {
        recognition.stop();
    }
}

function addMessage(sender, message, className) {
    const messageWrapper = document.createElement("div");
    messageWrapper.className = `message ${className}`;

    const messageContent = document.createElement("div");
    messageContent.className = "message-content";
    messageContent.textContent = `${sender}: ${message}`;

    messageWrapper.appendChild(messageContent);
    chatElement.appendChild(messageWrapper);
    chatElement.scrollTop = chatElement.scrollHeight;
}

establishWebSocket();
