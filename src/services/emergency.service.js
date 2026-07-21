const EMERGENCY_KEYWORDS = [
  ["chest pain", "critical"],
  ["chest tightness", "critical"],
  ["cannot breathe", "critical"],
  ["can't breathe", "critical"],
  ["difficulty breathing", "critical"],
  ["breathlessness", "critical"],
  ["unconscious", "critical"],
  ["fainted", "critical"],
  ["collapsed", "critical"],
  ["seizure", "critical"],
  ["convulsion", "critical"],
  ["stroke", "critical"],
  ["facial drooping", "critical"],
  ["arm weakness", "critical"],
  ["slurred speech", "critical"],
  ["severe bleeding", "critical"],
  ["bleeding won't stop", "critical"],
  ["heart attack", "critical"],
  ["severe headache", "high"],
  ["worst headache", "high"],
  ["sudden vision loss", "critical"],
  ["paralysis", "critical"],
  ["choking", "critical"],
  ["anaphylaxis", "critical"],
  ["allergic reaction", "high"],
  ["poisoning", "critical"],
  ["overdose", "critical"],
  ["suicide", "critical"],
  ["self harm", "critical"],
  ["seene mein dard", "critical"],
  ["saans nahi aa raha", "critical"],
  ["saans lene mein takleef", "critical"],
  ["behosh ho gaya", "critical"],
  ["behoshi", "critical"],
  ["mirgi", "critical"],
  ["jhatke aa rahe", "critical"],
  ["लकवा", "critical"],
  ["lakwa", "critical"],
  ["muh tedha", "critical"],
  ["haath kaam nahi kar raha", "critical"],
  ["aankhon ke aage andhera", "high"],
  ["tej sar dard", "high"],
  ["khoon nahi ruk raha", "critical"],
  ["dil ka daura", "critical"],
  ["zeher kha liya", "critical"],
  ["neend ki goli kha li", "critical"],
  ["khud ko chot", "critical"]
];

function detectEmergency(text) {
  const cleaned = String(text || "").trim().toLowerCase();
  if (!cleaned) {
    return { isEmergency: false, keyword: "", severity: "normal" };
  }
  for (const [keyword, severity] of EMERGENCY_KEYWORDS) {
    if (cleaned.includes(keyword.toLowerCase())) {
      return { isEmergency: true, keyword, severity };
    }
  }
  return { isEmergency: false, keyword: "", severity: "normal" };
}

module.exports = {
  EMERGENCY_KEYWORDS,
  detectEmergency
};
