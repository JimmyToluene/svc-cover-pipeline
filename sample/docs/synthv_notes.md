# Phase 2 — SynthV Line-by-Line Vocal Direction Notes

Baseline: `lyrics/final.md` (v3 final) + `lyrics/synthv_input.txt` (per-line romaji,
one token = one note). Timing/pitch alignment follows `refs/anon_version.mp3`, transcribed by ear line by line.

## Voice database and global settings

- **User decision, 2026-07-04: single female-voice-database route** (the earlier dual-route plan is scrapped).
  Pick a female voice database close to Higashi Yukiren's range, SVC transpose≈0 for the smallest
  transposition burden; the "lecturing tone" is done with tension/phrasing, not with voice database gender.
  Reaching "no pronunciation errors, phrases hold together" is enough to hand off to Phase 3 for a trial conversion — don't fine-tune yet.
- Project sample rate 48kHz; export a 48kHz WAV dry vocal (no reverb!) → `vocal/synthv_source.wav`
  (the default input path for svc_infer.py).
- Input method: box-select a line's notes, then paste the corresponding line of `synthv_input.txt`
  (space-separated tokens are assigned note by note); if a geminate (sokuon) t gets assigned wrong,
  manually change that note's lyric to っ or the phoneme cl.
- Global parameter starting point: compress global vibrato depth down to ~0.6x (Higashi Yukiren's
  natural vibrato is light, and SVC preserves the source's pitch curve); don't draw the loudness
  curve at this stage — leave that to mixing.

## Section-by-section treatment

### Verse A (lines 1–4) — narrative, restrained

- Volume low-to-mid, vibrato essentially off (only a light touch at phrase ends), tension neutral.
- The phrase-final closed u in line 1「a ka ru ku」and line 3「to do ku」: shorten the final note 10–20%
  and follow with a breath, so the tail doesn't trail off weakly.
- Line 4 is the section's landing point: a slight crescendo before「shi me su」, tension +10~15% for the
  assured feel of 示す (a Zhang Xuefeng-style declaration).

### Pre-chorus (lines 5–6)

- Line 5 is where the emotion starts to lift;「ko wa ku te」is four notes in a row — articulate each clearly, no portamento.
- Line 6: cut「i ru」off cleanly before the (rest); give「mu ko u mi zu」a word-by-word clipped feel
  (5–10ms gaps between notes, or lowered legato) for a burn-the-boats tone.

### Chorus 1 (lines 7–10) — the song's hook

- Overall loudness up; open vibrato on phrase-final long notes (medium depth, onset delayed 0.2–0.3s —
  i.e. straight tone in, vibrato out).
- Line 7「wa su ra re zu」: the final zu is a closed vowel — hold mostly straight tone with shallow vibrato, to keep it from going weak and breathy.
- Line 8「so t to so t to」: add breathiness +20~30% for a breathy, whispered feel;
  「tsu na gu」pulls back to normal.
- Line 10「ku re ta」ends on the open vowel a — safe to give it a long note and a crescendo; this is the section's most expansive landing point.

### Verse B (lines 11–14) — intimate, reminiscing

- Volume drops back; closer-to-the-mic than verse A: breathiness +10~15% across the whole section.
- Line 11 is sung as the truncated shi zu (see the ruling in final.md); place the final note gently, don't press it.
- Line 12: the quoted part「mi ra i wa ma da to o i」is the teacher speaking: tension +, vibrato off,
  slight separation between notes (spoken feel); the part outside the quotes,「e ga o de ho me te」, is sung normally, for contrast.
- Lines 13–14 crescendo line by line, setting up line 15;「u ka bu」ends with a short cut-off.

### Lines 15–16 (verse B landing point)

- Line 15「do n na」: stress on do; the ん does not sit on a high note (if the melody conflicts with this, come back and flag it).
- Line 16「ho e」as two notes (per the performance ruling); crescendo through the phrase, pushing toward the bridge; e is open and can be held.

### Bridge (lines 17–20)

- Line 17: contrast the two half-phrases around the (rest): first half light, second half「to o ku e yu ku」crescendo.
- Line 19 is the quietest point of the whole song: breathiness in its maximum range,「so ba ni」almost pure breath,
  give the (rest) its full value, and slow down the articulation of every syllable in「ki mi no ko e」.
- Line 20, the teacher's quote, closes the bridge: same treatment as line 12 (tension +, vibrato off, separated),
  with the last syllable of「i ke ru」turning into a firm straight tone held to full length — this line is the peak of the "lecturing tone".

### Chorus 2 (lines 21–25) — maximum dynamics

- Lines 21/22/24: same treatment as chorus 1, with overall loudness up another notch.
- **Line 23 note split (the only line whose note count was changed)**: against the mp3, find whichever of「づ」and「な」
  has the longer duration and split it in half, giving one note to「け」(expected split: な). After splitting, the「け」note must be ≥ a 1/16-note in duration;
  otherwise split the other one instead; the k consonant must be crisp (SVC conversion cannot rescue an unvoiced consonant that is already mushy at the source).
- Line 25 closes the song:「zu t to」— emphasize the geminate's (sokuon's) stop; the final syllable ni of「ko ko ro ni」is a closed vowel —
  straight tone in, very shallow vibrato, finish with a volume fade-out, don't push it (pushing an i vowel always goes weak).
  Optionally leave one beat of breath after the end (SynthV's br note) for a more natural finish.

## Export checklist (before handing off to Phase 3)

- [ ] Line by line against the mp3: note count == romaji token count (line 23 is 14)
- [ ] Geminate/long-vowel note assignment is correct (so-っ-to; cho-o-ku)
- [ ] No reverb or effects of any kind; dry vocal exported as 48kHz WAV
- [ ] Listen through once: no obvious mispronunciations (especially the wa/ha and e/he particles)
- [ ] Files in place: `vocal/synthv_source_a.wav` (male voice database) / `_b.wav` (female voice database)
