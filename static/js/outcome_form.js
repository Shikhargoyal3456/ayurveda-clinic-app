const scoreRange = document.getElementById("score-range");
const scoreOutput = document.getElementById("score-output");

if (scoreRange && scoreOutput) {
    scoreRange.addEventListener("input", () => {
        scoreOutput.textContent = scoreRange.value;
    });
}
