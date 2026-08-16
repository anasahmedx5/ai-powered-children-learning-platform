// Base API URL can be overridden globally (e.g. window.API_BASE_URL)
// Falls back to current origin if served from non-file environment, or defaults to http://localhost:8000
const API_BASE_URL = window.API_BASE_URL || 
    (typeof window !== "undefined" && window.location && window.location.origin && !window.location.origin.includes("file://") && window.location.port !== "3000"
        ? window.location.origin 
        : "http://localhost:8000");

const API_URL = `${API_BASE_URL}/api/evaluate`;
const API_SPEECH_URL = `${API_BASE_URL}/api/evaluate-speech`;
const API_WORDS_URL = `${API_BASE_URL}/api/words`;

async function fetchWordsDictionary() {
    try {
        const response = await fetch(API_WORDS_URL);
        if (!response.ok) return null;
        const data = await response.json();
        return data.words || null;
    } catch (e) {
        console.warn("Failed to fetch words dictionary from API:", e);
        return null;
    }
}

async function evaluateDrawing(blob, targetCharacter) {
    const formData = new FormData();
    formData.append("file", blob, "trace.png");
    formData.append("target_character", targetCharacter);

    const response = await fetch(API_URL, {
        method: "POST",
        body: formData
    });

    if (!response.ok) {
        throw new Error("Failed to evaluate drawing from API");
    }

    return await response.json();
}

async function evaluateSpeech(audioBlob, targetCharacter) {
    const formData = new FormData();
    formData.append("audio_data", audioBlob, "speech.wav");
    formData.append("target", targetCharacter);

    const response = await fetch(API_SPEECH_URL, {
        method: "POST",
        body: formData
    });

    if (!response.ok) {
        throw new Error("Failed to evaluate speech from API");
    }

    return await response.json();
}
