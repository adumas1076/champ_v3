# Backchannel Audio Clips

Place .wav files here for backchannel injection during voice conversations.

## Required Clips

| Filename | What It Sounds Like | Energy | Category |
|----------|-------------------|--------|----------|
| mhm.wav | "Mhm" (acknowledgment) | neutral | acknowledgment |
| yeah.wav | "Yeah" (listening) | neutral | acknowledgment |
| right.wav | "Right" (engaged listening) | engaged | acknowledgment |
| uh_huh.wav | "Uh-huh" (continue) | neutral | acknowledgment |
| oh_really.wav | "Oh really?" (interested) | surprised | engagement |
| wow.wav | "Wow" (impressed) | surprised | engagement |
| hmm.wav | "Hmm" (thinking) | engaged | engagement |
| facts.wav | "Facts" (agree) | agreeing | agreement |
| for_real.wav | "For real" (agree) | agreeing | agreement |
| haha.wav | Light laugh | amused | humor |

## Recording Tips

- Keep clips SHORT: 300-600ms
- Record in operator's voice (or close match)
- Natural, not performed — record mid-conversation
- Mono, 16kHz or 44.1kHz, WAV format
- Normalize volume to match TTS output level

## Alternative: Generate with TTS

If recording isn't practical, generate these using the operator's
TTS voice model. Most TTS engines can produce short utterances.

```python
# Example: generate backchannel with Fish S2
tts.synthesize("mhm", output="static/backchannels/mhm.wav")
tts.synthesize("yeah", output="static/backchannels/yeah.wav")
```
