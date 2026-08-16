let currentCaseMode = 'upper';
let currentCharacter = 'A';
let isDrawing = false;

let isTracingUnlocked = false;
let isRecording = false;
let micAutoStopTimer = null;
let micCountdownInterval = null;
let micSecondsRemaining = 10;
let audioCtx = null;
let micStream = null;
let scriptProcessor = null;
let pcmBuffers = [];
let pcmTotalLength = 0;

let userScore = parseInt(localStorage.getItem('mindbuzz_score') || '0');
let userStars = parseInt(localStorage.getItem('mindbuzz_stars') || '0');
let unlockedCharacters = new Set(JSON.parse(localStorage.getItem('mindbuzz_unlocked') || '[]'));
let completedCharacters = new Set(JSON.parse(sessionStorage.getItem('mindbuzz_completed') || '[]'));

function updateScoreUI() {
    const scoreElem = document.getElementById('header-score-display');
    if (scoreElem) scoreElem.innerText = userScore;

    const starsElem = document.getElementById('header-stars-display');
    if (starsElem) starsElem.innerText = userStars;
}

function addScore(points) {
    userScore += points;
    userStars = Math.floor(userScore / 100);

    localStorage.setItem('mindbuzz_score', userScore.toString());
    localStorage.setItem('mindbuzz_stars', userStars.toString());

    updateScoreUI();
}

const drawCanvas = document.getElementById('drawCanvas');
const drawCtx = drawCanvas ? drawCanvas.getContext('2d') : null;
let hasDrawn = false;

const TARGET_WORD_MAPPING = {
    'A': 'Apple', 'B': 'Banana', 'C': 'Castle', 'D': 'Dolphin', 'E': 'Elephant',
    'F': 'Flower', 'G': 'Garden', 'H': 'Hammer', 'I': 'Igloo', 'J': 'Jacket',
    'K': 'Kitten', 'L': 'Lemon', 'M': 'Monkey', 'N': 'Number', 'O': 'Orange',
    'P': 'Panda', 'Q': 'Queen', 'R': 'Rabbit', 'S': 'Spider', 'T': 'Turtle',
    'U': 'Umbrella', 'V': 'Volcano', 'W': 'Window', 'X': 'Xylophone', 'Y': 'Yellow', 'Z': 'Zebra'
};

let customWordsDict = {
    'A': ['apple', 'anchor', 'animal'],
    'B': ['banana', 'basket', 'button'],
    'C': ['castle', 'candle', 'cookie'],
    'D': ['dolphin', 'dragon', 'donut'],
    'E': ['elephant', 'engine', 'elbow'],
    'F': ['flower', 'feather', 'forest'],
    'G': ['garden', 'giraffe', 'guitar'],
    'H': ['hammer', 'helmet', 'honey'],
    'I': ['igloo', 'insect', 'island'],
    'J': ['jacket', 'jungle', 'jelly'],
    'K': ['kitten', 'kettle', 'kangaroo'],
    'L': ['lemon', 'lizard', 'lantern'],
    'M': ['monkey', 'magnet', 'muffin'],
    'N': ['number', 'noodle', 'napkin'],
    'O': ['orange', 'octopus', 'ostrich'],
    'P': ['panda', 'pencil', 'puppet'],
    'Q': ['queen', 'quilt', 'quack'],
    'R': ['rabbit', 'rocket', 'rainbow'],
    'S': ['spider', 'squirrel', 'sunflower'],
    'T': ['turtle', 'tiger', 'tomato'],
    'U': ['umbrella', 'unicorn', 'uniform'],
    'V': ['volcano', 'violet', 'violin'],
    'W': ['window', 'watermelon', 'whisper'],
    'X': ['xylophone', 'xray', 'xerox'],
    'Y': ['yellow', 'yogurt', 'yacht'],
    'Z': ['zebra', 'zipper', 'zucchini']
};

let letterWordIndices = {};
let letterFailCounts = {};

function randomizeStartingWords() {
    letterWordIndices = {};
    for (const key in customWordsDict) {
        if (customWordsDict[key] && customWordsDict[key].length > 0) {
            letterWordIndices[key] = Math.floor(Math.random() * customWordsDict[key].length);
        }
    }
}

function getTargetWord(char) {
    const key = (char || currentCharacter || '').toUpperCase();
    if (customWordsDict[key] && customWordsDict[key].length > 0) {
        if (letterWordIndices[key] === undefined) {
            letterWordIndices[key] = Math.floor(Math.random() * customWordsDict[key].length);
        }
        const idx = letterWordIndices[key];
        const wordList = customWordsDict[key];
        const rawWord = wordList[Math.min(idx, wordList.length - 1)];
        return rawWord.charAt(0).toUpperCase() + rawWord.slice(1);
    }
    return TARGET_WORD_MAPPING[char] || char;
}

function updateTargetWordUI(word) {
    const speechTargetBadge = document.getElementById('speech-target-badge');
    if (speechTargetBadge) speechTargetBadge.innerText = `Say: ${word}`;

    const speechTargetWordText = document.getElementById('speech-target-word-text');
    if (speechTargetWordText) speechTargetWordText.innerText = word;

    const speechTargetWordDisplay = document.getElementById('speech-target-word-display');
    if (speechTargetWordDisplay) speechTargetWordDisplay.innerText = word;

    const overlayTargetWord = document.getElementById('overlay-target-word');
    if (overlayTargetWord) overlayTargetWord.innerText = word;
}

function speakWord(customText) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const word = customText || getTargetWord(currentCharacter);
        const utterance = new SpeechSynthesisUtterance(word);
        utterance.rate = 0.85;
        utterance.pitch = 1.1;
        window.speechSynthesis.speak(utterance);
    } else {
        alert("Text-to-speech is not supported on your browser.");
    }
}

function checkFreshLaunch() {
    const urlParams = new URLSearchParams(window.location.search);
    const freshLaunchId = urlParams.get('fresh_launch');
    if (freshLaunchId) {
        const lastLaunchId = sessionStorage.getItem('mindbuzz_last_launch');
        if (lastLaunchId !== freshLaunchId) {
            sessionStorage.setItem('mindbuzz_last_launch', freshLaunchId);
            localStorage.removeItem('mindbuzz_unlocked');
            localStorage.removeItem('mindbuzz_score');
            localStorage.removeItem('mindbuzz_stars');
            sessionStorage.removeItem('mindbuzz_completed');
            userScore = 0;
            userStars = 0;
            unlockedCharacters = new Set();
            completedCharacters = new Set();
            letterWordIndices = {};
            letterFailCounts = {};
        }
    }
}

window.onload = async () => {
    checkFreshLaunch();
    initCanvas();
    renderAlphabetGrid();
    setupPointerEvents();
    updateScoreUI();

    if (typeof fetchWordsDictionary === 'function') {
        const apiWords = await fetchWordsDictionary();
        if (apiWords && Object.keys(apiWords).length > 0) {
            customWordsDict = apiWords;
        }
    }
    randomizeStartingWords();
    setCharacter(getCharacterList().charAt(0));
};

function initCanvas() {
    if (!drawCtx) return;
    drawCtx.lineCap = 'round';
    drawCtx.lineJoin = 'round';
    drawCtx.lineWidth = 18;
    drawCtx.strokeStyle = '#2563eb';
}

function setCaseMode(mode) {
    currentCaseMode = 'upper';
    setCharacter('A');
    renderAlphabetGrid();
}

function isCharacterAccessible(char) {
    const chars = getCharacterList().split('');
    const idx = chars.indexOf(char);
    if (idx <= 0) return true;
    const prevChar = chars[idx - 1];
    return completedCharacters.has(prevChar);
}

function renderAlphabetGrid() {
    const gridContainer = document.getElementById('alphabet-grid');
    if (!gridContainer) return;

    gridContainer.innerHTML = '';
    let chars = getCharacterList().split('');

    chars.forEach((char, index) => {
        const isSelected = char === currentCharacter;
        const isCompleted = completedCharacters.has(char);
        const isUnlockedSpeech = unlockedCharacters.has(char);
        const isAccessible = isCharacterAccessible(char);

        const btn = document.createElement('button');

        if (!isAccessible) {
            btn.innerHTML = `${char}<span class="text-[9px] ml-0.5 opacity-60">🔒</span>`;
            const prevChar = index > 0 ? chars[index - 1] : 'previous';
            btn.title = `Complete ${prevChar} first to unlock!`;
            btn.onclick = () => {
                updateFeedback(`Locked! Complete ${prevChar} first to unlock ${char}.`, "warning");
            };
            btn.className = "h-10 w-10 text-lg font-black rounded-xl border border-slate-200 bg-slate-100 text-slate-400 opacity-60 cursor-not-allowed flex items-center justify-center";
        } else {
            btn.innerHTML = `${char}${isCompleted ? '<span class="text-[10px] ml-0.5 text-emerald-500 font-black">✓</span>' : (isUnlockedSpeech ? '<span class="text-[9px] ml-0.5 text-amber-500">🔓</span>' : '')}`;
            btn.onclick = () => setCharacter(char);
            btn.className = `h-10 w-10 text-lg font-black rounded-xl border transition-all flex items-center justify-center relative ${isSelected
                ? "bg-indigo-600 text-white border-indigo-600 shadow-md scale-105"
                : isCompleted
                    ? "bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-indigo-50 hover:border-indigo-300"
                }`;
        }
        gridContainer.appendChild(btn);
    });
}

function setCharacter(char) {
    char = (char || 'A').toUpperCase();
    if (!isCharacterAccessible(char)) {
        const chars = getCharacterList().split('');
        const idx = chars.indexOf(char);
        const prevChar = idx > 0 ? chars[idx - 1] : 'previous';
        updateFeedback(`Locked! Complete ${prevChar} first to unlock ${char}.`, "warning");
        return;
    }

    currentCharacter = char;
    currentCaseMode = 'upper';
    hideGroqCoachCard();

    const activeDisplay = document.getElementById('active-mode-display');
    if (activeDisplay) {
        activeDisplay.innerText = `Letter ${char}`;
    }

    const badge = document.getElementById('target-letter-badge');
    if (badge) badge.innerText = char;

    const word = getTargetWord(char);
    updateTargetWordUI(word);

    renderAlphabetGrid();

    if (unlockedCharacters.has(char)) {
        unlockCanvas();
        updateSpeechStatus(`Character <strong>${char}</strong> is unlocked! Tracing active.`, "success");
    } else {
        lockCanvas();
    }

    resetCanvas();
}

function lockCanvas() {
    isTracingUnlocked = false;
    const lockOverlay = document.getElementById('canvas-lock-overlay');
    if (lockOverlay) lockOverlay.classList.remove('hidden');

    const statusDisplay = document.getElementById('stroke-status-display');
    if (statusDisplay) {
        statusDisplay.innerText = "Locked";
        statusDisplay.className = "text-amber-600 font-extrabold bg-amber-50 px-3 py-1 rounded-xl border border-amber-200";
    }

    const statusDot = document.getElementById('canvas-status-dot');
    if (statusDot) statusDot.className = "w-2.5 h-2.5 rounded-full bg-rose-500 inline-block animate-pulse";

    const statusLabel = document.getElementById('canvas-status-label');
    if (statusLabel) statusLabel.innerText = "Locked - Pronunciation Required";

    const submitBtn = document.getElementById('btn-submit-drawing');
    if (submitBtn) submitBtn.classList.add('opacity-50', 'pointer-events-none');

    const targetWord = getTargetWord(currentCharacter);
    updateSpeechStatus(`Click <strong>Listen Word</strong> to hear it, then <strong>Record Voice</strong> and pronounce <strong class="text-indigo-600">${targetWord}</strong> clearly!`, "info");
}

function unlockCanvas() {
    isTracingUnlocked = true;
    const lockOverlay = document.getElementById('canvas-lock-overlay');
    if (lockOverlay) lockOverlay.classList.add('hidden');

    const statusDisplay = document.getElementById('stroke-status-display');
    if (statusDisplay) {
        statusDisplay.innerText = "Ready to draw";
        statusDisplay.className = "text-indigo-600 font-extrabold bg-indigo-50 px-3 py-1 rounded-xl border border-indigo-200";
    }

    const statusDot = document.getElementById('canvas-status-dot');
    if (statusDot) statusDot.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block animate-pulse";

    const statusLabel = document.getElementById('canvas-status-label');
    if (statusLabel) statusLabel.innerText = "Unlocked - Tracing Active";

    const submitBtn = document.getElementById('btn-submit-drawing');
    if (submitBtn) submitBtn.classList.remove('opacity-50', 'pointer-events-none');
}

function getCharacterList() {
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
}

function nextCharacter() {
    const letters = getCharacterList().split('');
    let idx = letters.indexOf(currentCharacter);
    if (idx === -1) idx = 0;
    const nextIdx = (idx + 1) % letters.length;
    const nextChar = letters[nextIdx];

    if (!isCharacterAccessible(nextChar)) {
        updateFeedback(`Locked! Complete ${currentCharacter} first to unlock ${nextChar}.`, "warning");
        return;
    }
    setCharacter(nextChar);
}

function prevCharacter() {
    const letters = getCharacterList().split('');
    let idx = letters.indexOf(currentCharacter);
    if (idx === -1) idx = 0;
    const prevIdx = (idx - 1 + letters.length) % letters.length;
    setCharacter(letters[prevIdx]);
}

function setupPointerEvents() {
    if (!drawCanvas) return;
    const getCoords = (e) => {
        const rect = drawCanvas.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        return {
            x: clientX - rect.left,
            y: clientY - rect.top
        };
    };

    const startDrawing = (e) => {
        if (!isTracingUnlocked) {
            updateFeedback(`Canvas is locked! Pronounce '${getTargetWord(currentCharacter)}' first.`, "warning");
            return;
        }
        e.preventDefault();
        const pos = getCoords(e);
        isDrawing = true;
        hasDrawn = true;
        drawCtx.beginPath();
        drawCtx.moveTo(pos.x, pos.y);

        updateFeedback(`Drawing ${currentCharacter}...`, "info");
        const statusDisplay = document.getElementById('stroke-status-display');
        if (statusDisplay) statusDisplay.innerText = "Drawing in progress...";
    };

    const draw = (e) => {
        if (!isDrawing) return;
        e.preventDefault();
        const pos = getCoords(e);
        drawCtx.lineTo(pos.x, pos.y);
        drawCtx.stroke();
    };

    const stopDrawing = (e) => {
        if (!isDrawing) return;
        isDrawing = false;
        drawCtx.closePath();

        updateFeedback(`Drawing complete! Click Evaluate Drawing.`, "info");
        const statusDisplay = document.getElementById('stroke-status-display');
        if (statusDisplay) statusDisplay.innerText = "Drawing complete";
    };

    drawCanvas.addEventListener('mousedown', startDrawing);
    drawCanvas.addEventListener('mousemove', draw);
    window.addEventListener('mouseup', stopDrawing);

    drawCanvas.addEventListener('touchstart', startDrawing, { passive: false });
    drawCanvas.addEventListener('touchmove', draw, { passive: false });
    window.addEventListener('touchend', stopDrawing);
}

async function toggleVoiceRecording() {
    if (isRecording) {
        stopVoiceRecording();
    } else {
        await startVoiceRecording();
    }
}

async function startVoiceRecording() {
    try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = audioCtx.createMediaStreamSource(micStream);
        
        scriptProcessor = audioCtx.createScriptProcessor(4096, 1, 1);
        pcmBuffers = [];
        pcmTotalLength = 0;

        scriptProcessor.onaudioprocess = (e) => {
            if (!isRecording) return;
            const channelData = e.inputBuffer.getChannelData(0);
            const bufCopy = new Float32Array(channelData.length);
            bufCopy.set(channelData);
            pcmBuffers.push(bufCopy);
            pcmTotalLength += channelData.length;
        };

        source.connect(scriptProcessor);
        scriptProcessor.connect(audioCtx.destination);

        isRecording = true;
        micSecondsRemaining = 10;

        const updateMicTimerUI = () => {
            const micBtnText = document.getElementById('mic-btn-text');
            if (micBtnText) micBtnText.innerText = `Stop (${micSecondsRemaining}s)`;
            updateSpeechStatus(`Recording voice... Speak <strong>${getTargetWord(currentCharacter)}</strong> now! (Auto-evaluating in ${micSecondsRemaining}s)`, "info");
        };

        updateMicTimerUI();

        if (micCountdownInterval) clearInterval(micCountdownInterval);
        micCountdownInterval = setInterval(() => {
            if (!isRecording) {
                clearInterval(micCountdownInterval);
                return;
            }
            micSecondsRemaining -= 1;
            if (micSecondsRemaining > 0) {
                updateMicTimerUI();
            } else {
                clearInterval(micCountdownInterval);
            }
        }, 1000);

        if (micAutoStopTimer) clearTimeout(micAutoStopTimer);
        micAutoStopTimer = setTimeout(() => {
            if (isRecording) {
                console.log("Mic 10-second timer reached. Auto-stopping recording...");
                stopVoiceRecording();
            }
        }, 10000);

        const micBtn = document.getElementById('btn-mic-record');
        if (micBtn) micBtn.className = "py-3 px-3 bg-rose-600 hover:bg-rose-700 text-white font-extrabold rounded-xl shadow-md flex items-center justify-center space-x-1.5 transition-all active:scale-95 text-xs animate-pulse";
    } catch (err) {
        console.error("Microphone access error:", err);
        updateSpeechStatus("Microphone access denied or unavailable. Check browser permissions.", "error");
    }
}

function stopVoiceRecording() {
    if (micAutoStopTimer) {
        clearTimeout(micAutoStopTimer);
        micAutoStopTimer = null;
    }
    if (micCountdownInterval) {
        clearInterval(micCountdownInterval);
        micCountdownInterval = null;
    }
    if (!isRecording) return;
    isRecording = false;

    if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
    }
    if (scriptProcessor) {
        scriptProcessor.disconnect();
    }
    if (audioCtx) {
        audioCtx.close();
    }

    const mergedPCM = new Float32Array(pcmTotalLength);
    let offset = 0;
    for (let b of pcmBuffers) {
        mergedPCM.set(b, offset);
        offset += b.length;
    }

    const wavBlob = encodeWAV(mergedPCM, 16000);

    const micBtnText = document.getElementById('mic-btn-text');
    if (micBtnText) micBtnText.innerText = "Evaluating...";

    const micBtn = document.getElementById('btn-mic-record');
    if (micBtn) micBtn.className = "py-3 px-3 bg-amber-500 text-white font-extrabold rounded-xl shadow-md flex items-center justify-center space-x-1.5 transition-all text-xs cursor-wait";

    updateSpeechStatus("Processing audio with Whisper AI...", "info");

    processVoiceAudio(wavBlob);
}

function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);

    let index = 44;
    for (let i = 0; i < samples.length; i++) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        index += 2;
    }

    return new Blob([view], { type: 'audio/wav' });
}

function formatRecognizedText(text) {
    if (!text || text === '(unintelligible)') return '(unintelligible)';
    let clean = text.replace(/^[^\w\s]+|[^\w\s]+$/g, '').replace(/\.+/g, '').trim();
    if (!clean) return '(unintelligible)';
    return clean.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
}

function updateGroqCoachCard(msg, attemptNum, problemLetter, weakestScore, isBelowThreshold, isPass) {
    const coachCard = document.getElementById('groq-speech-coach-card');
    if (!coachCard) return;

    const msgElem = document.getElementById('groq-speech-msg');
    const badgeElem = document.getElementById('groq-attempt-badge');
    const letterBadge = document.getElementById('groq-problem-letter-badge');
    const scoreText = document.getElementById('groq-letter-score-text');
    const letterRow = document.getElementById('groq-problem-letter-row');

    if (msgElem) {
        msgElem.innerText = `"${msg}"`;
        msgElem.classList.remove('hidden');
    }

    if (badgeElem) {
        if (attemptNum === 'changed') {
            badgeElem.innerText = "Word Changed!";
            badgeElem.className = "px-2.5 py-0.5 bg-purple-200 text-purple-900 rounded-full text-[10px] font-black uppercase tracking-wider animate-bounce";
        } else if (isPass) {
            badgeElem.innerText = "Passed!";
            badgeElem.className = "px-2.5 py-0.5 bg-emerald-200 text-emerald-900 rounded-full text-[10px] font-black uppercase tracking-wider";
        } else {
            badgeElem.innerText = `Attempt ${attemptNum} of 3`;
            badgeElem.className = "px-2.5 py-0.5 bg-amber-200 text-amber-900 rounded-full text-[10px] font-black uppercase tracking-wider";
        }
    }

    if (isPass) {
        if (letterRow) letterRow.classList.add('hidden');
        if (msgElem) msgElem.className = "text-xs font-bold text-emerald-900 leading-snug italic bg-emerald-100/70 p-2.5 rounded-xl border border-emerald-200/80";
        coachCard.className = "p-4 rounded-2xl bg-emerald-50/90 border border-emerald-200 shadow-sm space-y-2.5 transition-all block";
    } else {
        if (letterRow) letterRow.classList.remove('hidden');
        if (letterBadge) letterBadge.innerText = problemLetter || 'Letter';
        if (scoreText) scoreText.innerText = `Conf: ${weakestScore}% (< 50% Threshold)`;
        if (msgElem) msgElem.className = "text-xs font-bold text-amber-950 leading-snug italic bg-amber-100/70 p-2.5 rounded-xl border border-amber-200/80";
        coachCard.className = "p-4 rounded-2xl bg-amber-50/90 border border-amber-200 shadow-sm space-y-2.5 transition-all block animate-pulse";
        setTimeout(() => coachCard.classList.remove('animate-pulse'), 1000);
    }
}

function hideGroqCoachCard() {
    const coachCard = document.getElementById('groq-speech-coach-card');
    const msgElem = document.getElementById('groq-speech-msg');
    const letterRow = document.getElementById('groq-problem-letter-row');
    const badgeElem = document.getElementById('groq-attempt-badge');

    if (msgElem) msgElem.classList.add('hidden');
    if (letterRow) letterRow.classList.add('hidden');
    if (badgeElem) {
        badgeElem.innerText = "Ready";
        badgeElem.className = "px-2.5 py-0.5 bg-indigo-100 text-indigo-900 rounded-full text-[10px] font-black uppercase tracking-wider";
    }
    if (coachCard) {
        coachCard.className = "p-4 rounded-2xl bg-white border border-indigo-100 shadow-sm space-y-2.5 transition-all block";
    }
}

async function processVoiceAudio(audioBlob) {
    const targetWord = getTargetWord(currentCharacter);
    try {
        const result = await evaluateSpeech(audioBlob, targetWord);
        
        const micBtnText = document.getElementById('mic-btn-text');
        if (micBtnText) micBtnText.innerText = "Record Voice";

        const micBtn = document.getElementById('btn-mic-record');
        if (micBtn) micBtn.className = "py-3 px-3 bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold rounded-xl shadow-md flex items-center justify-center space-x-1.5 transition-all active:scale-95 text-xs";

        const key = currentCharacter.toUpperCase();
        const heardText = formatRecognizedText(result.recognized);

        const isPass = result.is_pass !== undefined ? result.is_pass : (result.is_correct && !result.is_below_threshold);
        const groqMsg = result.groq_msg || result.feedback || "Keep practicing!";
        const weakestLetter = result.weakest_letter || key;
        const weakestScore = result.weakest_score !== undefined ? result.weakest_score : (result.overall_score || 0);

        if (isPass) {
            letterFailCounts[key] = 0;
            playSuccessSound();
            launchConfetti('medium');
            showFloatingPoints('+50 PTS!', 'speech-unlock-card');

            const card = document.getElementById('speech-unlock-card');
            if (card) {
                card.classList.add('animate-celebrate-card');
                setTimeout(() => card.classList.remove('animate-celebrate-card'), 2000);
            }

            const isFirstTime = !unlockedCharacters.has(currentCharacter);
            unlockedCharacters.add(currentCharacter);
            localStorage.setItem('mindbuzz_unlocked', JSON.stringify(Array.from(unlockedCharacters)));

            unlockCanvas();
            renderAlphabetGrid();

            updateGroqCoachCard(groqMsg, 1, weakestLetter, weakestScore, false, true);

            if (isFirstTime) {
                addScore(50);
                updateSpeechStatus(`Awesome! Heard <strong>${heardText}</strong>. Unlocked (+50 pts)!`, "success");
                updateFeedback(`Pronunciation verified (+50 pts)! Draw ${currentCharacter} on the canvas and click Evaluate.`, "success");
            } else {
                updateSpeechStatus(`Awesome! Heard <strong>${heardText}</strong>. Already unlocked!`, "success");
                updateFeedback(`Pronunciation verified! Draw ${currentCharacter} on the canvas and click Evaluate.`, "success");
            }
        } else {
            letterFailCounts[key] = (letterFailCounts[key] || 0) + 1;
            const attempts = letterFailCounts[key];
            const wordsList = customWordsDict[key] || [];
            const currentIdx = letterWordIndices[key] || 0;

            if (attempts >= 3 && wordsList.length > 0) {
                letterFailCounts[key] = 0;
                letterWordIndices[key] = (currentIdx + 1) % wordsList.length;
                const newWord = getTargetWord(currentCharacter);

                updateTargetWordUI(newWord);
                speakWord(newWord);

                updateGroqCoachCard(groqMsg, 'changed', weakestLetter, weakestScore, true, false);

                updateSpeechStatus(`Tried 3 times! Switched to new word: <strong>${newWord}</strong>. Say <strong>${newWord}</strong>!`, "warning");
                updateFeedback(`Pronunciation failed 3 times. Switched to new word: ${newWord}. Give it a try!`, "warning");
            } else {
                const attemptsLeft = 3 - attempts;
                updateGroqCoachCard(groqMsg, attempts, weakestLetter, weakestScore, true, false);
                updateSpeechStatus(`Heard <strong>"${heardText}"</strong> &mdash; Target: <strong>${targetWord}</strong> (${attemptsLeft} attempt${attemptsLeft === 1 ? '' : 's'} left)`, "warning");
                updateFeedback(`Pronunciation check failed for '${targetWord}'. Follow AI Tutor guidance below!`, "warning");
            }
        }
    } catch (err) {
        console.error("Speech evaluation error:", err);
        updateSpeechStatus("Error connecting to backend Whisper API.", "error");

        const micBtnText = document.getElementById('mic-btn-text');
        if (micBtnText) micBtnText.innerText = "Record Voice";
        const micBtn = document.getElementById('btn-mic-record');
        if (micBtn) micBtn.className = "py-3 px-3 bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold rounded-xl shadow-md flex items-center justify-center space-x-1.5 transition-all active:scale-95 text-xs";
    }
}

function updateSpeechStatus(msg, type) {
    const textElem = document.getElementById('speech-status-text');
    if (!textElem) return;
    textElem.innerHTML = msg;
}

function updateFeedback(msg, type) {
    const card = document.getElementById('feedback-card');
    const text = document.getElementById('feedback-text');
    if (!text || !card) return;

    text.innerText = msg;
    if (type === 'error') {
        card.className = "p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 shadow-sm";
    } else if (type === 'success') {
        card.className = "p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-700 shadow-sm";
    } else if (type === 'warning') {
        card.className = "p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-700 shadow-sm";
    } else {
        card.className = "p-4 rounded-2xl bg-slate-100 border border-slate-200 text-slate-600";
    }
}

function resetCanvas() {
    if (drawCtx) drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    hasDrawn = false;

    if (isTracingUnlocked) {
        const statusDisplay = document.getElementById('stroke-status-display');
        if (statusDisplay) statusDisplay.innerText = "Ready to draw";
        updateFeedback(`Canvas cleared for ${currentCharacter}. Draw freely!`, "info");
    } else {
        updateFeedback(`Pronounce ${getTargetWord(currentCharacter)} to unlock tracing.`, "info");
    }
}

async function submitDrawing() {
    if (!isTracingUnlocked) {
        updateFeedback(`Canvas is locked! Pronounce ${getTargetWord(currentCharacter)} first.`, "warning");
        return;
    }
    if (!hasDrawn) {
        updateFeedback(`Please draw ${currentCharacter} on the canvas first!`, "warning");
        return;
    }

    drawCanvas.toBlob(async (blob) => {
        updateFeedback("Evaluating drawing with backend AI model...", "info");

        try {
            const result = await evaluateDrawing(blob, currentCharacter);

            const iconBg = document.getElementById('modal-icon-bg');
            const confidenceContainer = document.getElementById('modal-confidence-container');
            const failBanner = document.getElementById('modal-fail-banner');
            const failMessage = document.getElementById('modal-fail-message');

            if (result.passed) {
                playSuccessSound();
                launchConfetti('high');
                const displayScore = Math.max(result.confidence || 0, result.top_confidence || 0);
                
                const isFirstTimeCompleted = !completedCharacters.has(currentCharacter);
                completedCharacters.add(currentCharacter);
                sessionStorage.setItem('mindbuzz_completed', JSON.stringify(Array.from(completedCharacters)));

                const isFirstTimeTracing = !unlockedCharacters.has(currentCharacter + "_traced");
                unlockedCharacters.add(currentCharacter + "_traced");
                localStorage.setItem('mindbuzz_unlocked', JSON.stringify(Array.from(unlockedCharacters)));

                const pointsEarned = 100 + Math.round(displayScore);
                if (isFirstTimeTracing) {
                    addScore(pointsEarned);
                }
                showFloatingPoints(`+${pointsEarned} PTS!`, 'modal-icon-bg');

                renderAlphabetGrid();

                if (iconBg) iconBg.className = "w-16 h-16 bg-sage/20 text-sage rounded-3xl flex items-center justify-center mx-auto";

                if (confidenceContainer) confidenceContainer.classList.remove('hidden');
                if (failBanner) failBanner.classList.add('hidden');

                document.getElementById('modal-confidence-text').innerText = `${displayScore}%`;

                const scoreRewardElem = document.getElementById('modal-score-reward');
                if (scoreRewardElem) {
                    scoreRewardElem.innerText = isFirstTimeTracing ? `🏆 +${pointsEarned} Points Earned!` : `🏆 Completed! (${pointsEarned} pts)`;
                }

                const chars = getCharacterList().split('');
                const currIdx = chars.indexOf(currentCharacter);
                const nextChar = (currIdx >= 0 && currIdx < chars.length - 1) ? chars[currIdx + 1] : null;

                const modalBtn = document.getElementById('modal-action-btn');
                if (modalBtn) {
                    if (nextChar) {
                        modalBtn.innerText = `Next Letter: ${nextChar} →`;
                        modalBtn.onclick = () => {
                            closeModal();
                            setCharacter(nextChar);
                        };
                    } else {
                        modalBtn.innerText = "Mode Completed! Try Another";
                        modalBtn.onclick = () => {
                            closeModal();
                        };
                    }
                }
            } else {
                if (iconBg) iconBg.className = "w-16 h-16 bg-terracotta/20 text-terracotta rounded-3xl flex items-center justify-center mx-auto";

                if (confidenceContainer) confidenceContainer.classList.add('hidden');

                if (failBanner) failBanner.classList.remove('hidden');
                if (failMessage) failMessage.innerText = result.message || `The model recognized ${result.predicted} instead of ${result.target}. Try again!`;

                const modalBtn = document.getElementById('modal-action-btn');
                if (modalBtn) {
                    modalBtn.innerText = "Try Drawing Again";
                    modalBtn.onclick = () => {
                        closeModal();
                    };
                }
            }

            const targetDisplay = document.getElementById('modal-target-text');
            if (targetDisplay) targetDisplay.innerText = result.target;

            const predDisplay = document.getElementById('modal-predicted-text');
            if (predDisplay) predDisplay.innerText = result.predicted || result.target;

            const coachingText = document.getElementById('modal-coaching-text');
            if (coachingText) coachingText.innerText = result.coaching_tip || "Keep practicing your strokes!";

            document.getElementById('results-modal').classList.remove('hidden');
        } catch (err) {
            updateFeedback("Error connecting to FastAPI backend. Ensure server is running on port 8000.", "error");
            console.error(err);
        }
    });
}

function playSuccessSound() {
    try {
        const audio = new Audio('assets/sounds/success - Sound Effect.mp3');
        audio.currentTime = 0;
        audio.play().catch(err => console.warn("Audio autoplay constraint:", err));
    } catch (e) {
        console.error("Audio playback error:", e);
    }
}

function closeModal() {
    document.getElementById('results-modal').classList.add('hidden');
    resetCanvas();
}

function launchConfetti(intensity = 'medium') {
    if (typeof confetti === 'function') {
        confetti({
            particleCount: 45,
            spread: 60,
            origin: { y: 0.7 }
        });
    } else {
        launchNativeConfetti();
    }
}

function launchNativeConfetti() {
    const colors = ['#f59e0b', '#10b981', '#6366f1', '#ec4899', '#8b5cf6', '#3b82f6'];
    for (let i = 0; i < 18; i++) {
        const particle = document.createElement('div');
        particle.className = 'fixed pointer-events-none z-50 rounded-sm';
        particle.style.width = `${Math.floor(Math.random() * 6 + 4)}px`;
        particle.style.height = `${Math.floor(Math.random() * 8 + 6)}px`;
        particle.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        particle.style.left = `${Math.random() * 80 + 10}vw`;
        particle.style.top = '-20px';
        particle.style.transition = 'transform 1.4s cubic-bezier(0.25, 1, 0.5, 1), opacity 1.4s ease-out';
        document.body.appendChild(particle);

        requestAnimationFrame(() => {
            const xShift = (Math.random() - 0.5) * 120;
            const yShift = window.innerHeight + 40;
            const rot = Math.random() * 360 - 180;
            particle.style.transform = `translate(${xShift}px, ${yShift}px) rotate(${rot}deg)`;
            particle.style.opacity = '0';
        });

        setTimeout(() => particle.remove(), 1500);
    }
}

function showFloatingPoints(text, originElemId) {
    const originElem = document.getElementById(originElemId) || document.body;
    const rect = originElem.getBoundingClientRect();

    const popup = document.createElement('div');
    popup.className = 'fixed font-black text-amber-400 text-2xl drop-shadow-lg z-50 pointer-events-none animate-float-pts flex items-center space-x-1';
    popup.innerHTML = `<span>⭐</span><span>${text}</span>`;
    
    popup.style.left = `${rect.left + rect.width / 2}px`;
    popup.style.top = `${rect.top}px`;

    document.body.appendChild(popup);
    setTimeout(() => popup.remove(), 1700);
}
