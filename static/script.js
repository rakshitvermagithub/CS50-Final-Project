const SpeechRecongnition = window.SpeechRecongnition || window.webkitSpeechRecognition
const SpeechGrammarList = window.SpeechGrammarList || window.webkitSpeechGrammarList
const SpeechRecognitionEvent = window.SpeechRecognitionEvent || window.webkitSpeechRecognitionEvent

document.addEventListener('DOMContentLoaded',() => {
    const recordBtn = document.querySelector("#recordBtn")
    const recordBtnText = document.querySelector("#recordBtnText")
    const savedMantra = document.querySelector("#savedMantra")

    // Person clicks
    recordBtn.addEventListener('click', () => { 
        recordBtnText.textContent = "Recording..."
 
        // Form a speech recognition object
        const recognition = new SpeechRecongnition();
        recognition.lang = 'en-US';
        recognition.interimResults = false;

        // Optionally add grammar list
        const grammar = '#JSGF V1.0; grammar mantra; public <mantra> = ohm namah shivaya | hare krishna hare krishna krishna hare hare hare ram hare ram ram ram hare hare | om | jai shree krishna'
        const speechRecognitionList = new SpeechGrammarList();
        speechRecognitionList.addFromString(grammar, 1);
        recognition.grammars = speechRecognitionList;

        recognition.start()

        // Fetch results when available
        recognition.addEventListener("result", (event) => {
            const mantra = event.results[0][0].transcript;
            savedMantra.textContent = `${mantra}.`;
            
            // Need to choose one among both mantra or finalTranscript

            let finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
                }
            }

            // Send to backend
            if (finalTranscript) {
                fetch  ('/record', {
                    method: 'POST',
                    headers: {
                        'Content-type': 'application/json'
                    },
                    body: JSON.stringify({ mantra_recorded: finalTranscript })
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Success:', data.message);
                })
                .catch((error) => {
                    console.error("Error:", error);
                });
            }
            else {
                console.log("finalTranscript did not work")
            }
        });
    });
});